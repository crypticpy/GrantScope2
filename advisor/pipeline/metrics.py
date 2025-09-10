from __future__ import annotations

from typing import Any

import pandas as pd

from .ids import _stable_dp_id
from .imports import (
    DataPoint,
    MetricRequest,
    StructuredNeeds,
    _apply_needs_filters,
    _canonical_value_samples,
    generate_page_prompt,
    resolve_chart_context,
    tool_query,
)
from .json_utils import _json_dumps_stable


def _ensure_funder_metric(
    df: pd.DataFrame, needs: StructuredNeeds, mrs: list[MetricRequest]
) -> list[MetricRequest]:
    """
    Ensure plan includes at least one funder-level metric (df_groupby_sum by 'funder_name')
    when interview needs indicate subjects/populations/geographies and columns exist.
    """
    try:
        for mr in mrs:
            try:
                by = mr.params.get("by") if isinstance(mr.params, dict) else None
            except Exception:
                by = None
            if mr.tool == "df_groupby_sum" and isinstance(by, list) and "funder_name" in by:
                return mrs

        if "funder_name" not in df.columns or "amount_usd" not in df.columns:
            return mrs

        has_signal = bool(
            (getattr(needs, "subjects", None) and len(getattr(needs, "subjects", [])) > 0)
            or (getattr(needs, "populations", None) and len(getattr(needs, "populations", [])) > 0)
            or (getattr(needs, "geographies", None) and len(getattr(needs, "geographies", [])) > 0)
        )
        if not has_signal:
            return mrs

        by_cols: list[str] = ["funder_name"]
        if (
            getattr(needs, "subjects", None)
            and "grant_subject_tran" in df.columns
            and len(by_cols) < 3
        ):
            by_cols.append("grant_subject_tran")
        if (
            getattr(needs, "geographies", None)
            and "grant_geo_area_tran" in df.columns
            and len(by_cols) < 3
        ):
            by_cols.append("grant_geo_area_tran")
        if (
            getattr(needs, "populations", None)
            and "grant_population_tran" in df.columns
            and len(by_cols) < 3
        ):
            by_cols.append("grant_population_tran")

        params: dict[str, Any] = {"by": by_cols, "value": "amount_usd", "n": 10}
        mrs.insert(
            0, MetricRequest(tool="df_groupby_sum", params=params, title="Top Funders by Amount")
        )
    except Exception:
        return mrs
    return mrs


def _build_pre_prompt(df: pd.DataFrame, interview: Any) -> str:
    selected_chart = "data_summary.general"
    selected_role = getattr(interview, "user_role", None) or "Grant Analyst/Writer"
    additional_context = "Advisor pipeline metric execution"
    try:
        pre = generate_page_prompt(
            df=df,
            _grouped_df=df,
            selected_chart=selected_chart,
            selected_role=selected_role,
            additional_context=additional_context,
            current_filters=None,
            sample_df=df.head(50),
        )
    except Exception:
        pre = f"Known Columns: {', '.join(map(str, getattr(df, 'columns', [])))}."
    try:
        samples = _canonical_value_samples(df)
        hints: list[str] = []
        if samples.get("grant_subject_tran"):
            hints.append(
                f"- grant_subject_tran e.g., {', '.join(samples['grant_subject_tran'][:6])}"
            )
        if samples.get("grant_population_tran"):
            hints.append(
                f"- grant_population_tran e.g., {', '.join(samples['grant_population_tran'][:6])}"
            )
        if samples.get("grant_geo_area_tran"):
            hints.append(
                f"- grant_geo_area_tran e.g., {', '.join(samples['grant_geo_area_tran'][:6])}"
            )
        if hints:
            pre = (
                pre
                + "\n\nUse ONLY values present in the dataset for filters. Examples:\n"
                + "\n".join(hints)
                + "\nIf geographies are provided as codes (e.g., 'TX', 'US'), translate to names like 'Texas' or 'United States'."
            )
    except Exception:
        pass
    return pre


def _is_no_match(text: str) -> bool:
    try:
        s = (text or "").strip().lower()
    except Exception:
        s = ""
    if not s:
        return True
    needles = [
        "no matching records",
        "no data available",
        "empty",
    ]
    return any(n in s for n in needles)


def _metric_targeted_focus(df: pd.DataFrame, needs: StructuredNeeds, top_n: int = 25) -> str:
    """Programmatic fallback for targeted focus when SQL yields nothing.

    Returns a compact Markdown table of subject x population with total amount and count.
    """
    try:
        df_f, _used = _apply_needs_filters(df, needs)
    except Exception:
        df_f = df
    if df_f is None or df_f.empty:
        return "No matching records after applying filters."

    # Choose canonical columns
    subj = (
        "grant_subject_tran"
        if "grant_subject_tran" in df_f.columns
        else ("grant_subject" if "grant_subject" in df_f.columns else None)
    )
    pop = (
        "grant_population_tran"
        if "grant_population_tran" in df_f.columns
        else ("grant_population" if "grant_population" in df_f.columns else None)
    )
    amt = (
        "amount_usd"
        if "amount_usd" in df_f.columns
        else ("amount" if "amount" in df_f.columns else None)
    )

    if subj is None or pop is None or amt is None:
        return "No matching records after applying filters."

    try:
        vals = pd.to_numeric(df_f[amt], errors="coerce").fillna(0.0)
        tmp = df_f.assign(_val=vals)
        g = (
            tmp.groupby([subj, pop], dropna=False)["_val"]
            .agg([("total_amount_usd", "sum"), ("grant_count", "size")])
            .reset_index()
        )
        if g.empty:
            return "No matching records after applying filters."
        g = g.sort_values(["total_amount_usd", "grant_count"], ascending=[False, False]).head(top_n)
        # Build Markdown table
        header = f"| {subj.replace('_', ' ').title()} | {pop.replace('_', ' ').title()} | Grant Count | Total Amount (USD) |\n"
        sep = "|---|---:|---:|---:|\n"
        rows = []
        for _, row in g.iterrows():
            s = str(row[subj]) if row[subj] is not None else "Unknown"
            p = str(row[pop]) if row[pop] is not None else "Unknown"
            cnt = int(row["grant_count"]) if pd.notna(row["grant_count"]) else 0
            tot = float(row["total_amount_usd"]) if pd.notna(row["total_amount_usd"]) else 0.0
            rows.append(f"| {s} | {p} | {cnt:,} | ${tot:,.0f} |\n")
        return header + sep + "".join(rows)
    except Exception:
        return "No matching records after applying filters."


def _execute_metric(df: pd.DataFrame, pre_prompt: str, tool: str, params: dict[str, Any]) -> str:
    q = (
        "Please call the specified analysis tool with the provided parameters and return only a small Markdown table or short summary.\n"
        f"Tool: {tool}\n"
        f"Parameters (JSON): {_json_dumps_stable(params)}"
    )
    try:
        extra_ctx = resolve_chart_context("data_summary.general")
    except Exception:
        extra_ctx = None
    try:
        result = tool_query(df, q, pre_prompt, extra_ctx).strip()
        if result and not result.startswith("[tool_query error]"):
            # If df_sql_select yields nothing, compute targeted focus programmatically
            if tool == "df_sql_select" and _is_no_match(result):
                try:
                    # We need needs to compute proper filters; embed a lightweight heuristic here: if params contain SELECT with WHERE, fall back
                    # Since _execute_metric lacks direct access to needs, handle in caller when collecting datapoints
                    return result
                except Exception:
                    return result
            return result
    except Exception:
        # Fall back to direct analysis if tool_query fails
        pass

    # Fallback: Generate analysis directly from DataFrame
    return _fallback_metric_analysis(df, tool, params)


def _fallback_metric_analysis(df: pd.DataFrame, tool: str, params: dict[str, Any]) -> str:
    """
    Generate analysis directly from DataFrame when tool_query fails.
    """
    try:
        if df is None or df.empty:
            return "| Status | Message |\n|--------|---------|\n| Empty | No data available for analysis |"

        if tool == "df_describe" and "column" in params:
            col = params["column"]
            if col in df.columns:
                series = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(series) > 0:
                    stats = series.describe()
                    return (
                        f"| Statistic | Value |\n"
                        f"|-----------|-------|\n"
                        f"| Count | {int(stats['count']):,} |\n"
                        f"| Mean | ${stats['mean']:,.0f} |\n"
                        f"| Median | ${stats['50%']:,.0f} |\n"
                        f"| Min | ${stats['min']:,.0f} |\n"
                        f"| Max | ${stats['max']:,.0f} |\n"
                        f"| Std Dev | ${stats['std']:,.0f} |"
                    )

        elif tool == "df_value_counts" and "column" in params:
            col = params["column"]
            n = params.get("n", 10)
            if col in df.columns:
                counts = df[col].value_counts().head(n)
                if len(counts) > 0:
                    table = (
                        f"| {col.replace('_', ' ').title()} | Count |\n|"
                        + "-" * 20
                        + "|-" * 8
                        + "|\n"
                    )
                    for val, count in counts.items():
                        val_str = str(val)[:30] if val is not None else "Unknown"
                        table += f"| {val_str} | {count:,} |\n"
                    return table

        elif tool == "df_groupby_sum" and "by" in params and "value" in params:
            by_cols = params["by"]
            value_col = params["value"]
            n = params.get("n", 10)

            if all(col in df.columns for col in by_cols + [value_col]):
                # Handle groupby with fallback for missing data
                try:
                    grouped = (
                        df.groupby(by_cols)[value_col].sum().sort_values(ascending=False).head(n)
                    )
                    if len(grouped) > 0:
                        # Create table header
                        headers = [col.replace("_", " ").title() for col in by_cols] + [
                            "Total Amount"
                        ]
                        header_row = "| " + " | ".join(headers) + " |\n"
                        separator = "|" + "|".join("-" * (len(h) + 2) for h in headers) + "|\n"

                        table = header_row + separator
                        for idx, amount in grouped.items():
                            if isinstance(idx, tuple):
                                row_values = [
                                    str(v)[:25] if v is not None else "Unknown" for v in idx
                                ]
                            else:
                                row_values = [str(idx)[:25] if idx is not None else "Unknown"]
                            row_values.append(f"${amount:,.0f}")
                            table += "| " + " | ".join(row_values) + " |\n"
                        return table
                except Exception:
                    pass

        elif tool == "df_pivot_table" and "index" in params:
            index_cols = params["index"]
            value_col = params.get("value", "amount_usd")
            agg = params.get("agg", "sum")
            top = params.get("top", 15)

            if all(col in df.columns for col in index_cols) and value_col in df.columns:
                try:
                    # Simple aggregation by index columns
                    if agg == "sum":
                        result = (
                            df.groupby(index_cols)[value_col]
                            .sum()
                            .sort_values(ascending=False)
                            .head(top)
                        )
                    elif agg == "count":
                        result = (
                            df.groupby(index_cols).size().sort_values(ascending=False).head(top)
                        )
                    else:
                        result = (
                            df.groupby(index_cols)[value_col]
                            .mean()
                            .sort_values(ascending=False)
                            .head(top)
                        )

                    if len(result) > 0:
                        header_cols = [col.replace("_", " ").title() for col in index_cols] + [
                            f"{agg.title()} Value"
                        ]
                        header_row = "| " + " | ".join(header_cols) + " |\n"
                        separator = "|" + "|".join("-" * (len(h) + 2) for h in header_cols) + "|\n"

                        table = header_row + separator
                        for idx, val in result.items():
                            if isinstance(idx, tuple):
                                row_values = [
                                    str(v)[:20] if v is not None else "Unknown" for v in idx
                                ]
                            else:
                                row_values = [str(idx)[:20] if idx is not None else "Unknown"]

                            if "amount" in value_col.lower():
                                row_values.append(f"${val:,.0f}")
                            else:
                                row_values.append(f"{val:,.0f}")
                            table += "| " + " | ".join(row_values) + " |\n"
                        return table
                except Exception:
                    pass

        elif tool == "df_top_n" and "column" in params:
            col = params["column"]
            n = params.get("n", 10)
            if col in df.columns:
                try:
                    top_values = df.nlargest(n, col)[[col]]
                    if len(top_values) > 0:
                        table = (
                            f"| Rank | {col.replace('_', ' ').title()} |\n|------|"
                            + "-" * 15
                            + "|\n"
                        )
                        for i, (_, row) in enumerate(top_values.iterrows(), 1):
                            val = row[col]
                            if "amount" in col.lower():
                                table += f"| {i} | ${val:,.0f} |\n"
                            else:
                                table += f"| {i} | {val:,.0f} |\n"
                        return table
                except Exception:
                    pass

        # Generic fallback
        return f"| Analysis | Result |\n|----------|--------|\n| Tool | {tool} |\n| Status | Analysis completed with limited data |"

    except Exception as e:
        return f"| Error | Details |\n|-------|---------|\n| Status | Analysis failed |\n| Tool | {tool} |\n| Message | {str(e)[:50]} |"


def _collect_datapoints(df: pd.DataFrame, interview: Any, plan) -> list[DataPoint]:
    pre = _build_pre_prompt(df, interview)
    datapoints: list[DataPoint] = []
    # Attempt to derive needs if present on plan or interview for targeted focus fallback
    needs_like = getattr(interview, "needs", None)
    if needs_like is None and hasattr(plan, "narrative_outline"):
        # not available; leave None
        pass
    for item in plan.metric_requests:
        content = _execute_metric(df, pre, item.tool, item.params)
        # Automatic fallback for targeted focus when SQL returns empty
        if item.tool == "df_sql_select" and _is_no_match(content):
            try:
                # Use interview.needs if available else derive minimal structure from interview
                from .imports import StructuredNeeds as _SN  # local import to avoid cycles

                if needs_like is None:
                    subs = getattr(interview, "keywords", []) or []
                    pops = getattr(interview, "populations", []) or []
                    geos = getattr(interview, "geography", []) or []
                    needs_like = _SN(subjects=subs, populations=pops, geographies=geos)
                content = _metric_targeted_focus(df, needs_like)
            except Exception:
                pass
        dp_dict = {
            "id": _stable_dp_id(item.title or item.tool, item.tool, item.params),
            "title": item.title or item.tool,
            "method": item.tool,
            "params": item.params,
            "table_md": content,
            "notes": "",
        }
        datapoints.append(DataPoint(**dp_dict))
    return datapoints
