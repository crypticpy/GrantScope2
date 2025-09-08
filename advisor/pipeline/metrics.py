from __future__ import annotations
from typing import Any, Dict, List
import pandas as pd

from .imports import (
    StructuredNeeds, MetricRequest, DataPoint,
    generate_page_prompt, resolve_chart_context, tool_query,
    _canonical_value_samples,
)
from .json_utils import _json_dumps_stable
from .ids import _stable_dp_id
import numpy as np

def _ensure_funder_metric(df: pd.DataFrame, needs: StructuredNeeds, mrs: List[MetricRequest]) -> List[MetricRequest]:
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

        by_cols: List[str] = ["funder_name"]
        if getattr(needs, "subjects", None) and "grant_subject_tran" in df.columns and len(by_cols) < 3:
            by_cols.append("grant_subject_tran")
        if getattr(needs, "geographies", None) and "grant_geo_area_tran" in df.columns and len(by_cols) < 3:
            by_cols.append("grant_geo_area_tran")
        if getattr(needs, "populations", None) and "grant_population_tran" in df.columns and len(by_cols) < 3:
            by_cols.append("grant_population_tran")

        params: Dict[str, Any] = {"by": by_cols, "value": "amount_usd", "n": 10}
        mrs.insert(0, MetricRequest(tool="df_groupby_sum", params=params, title="Top Funders by Amount"))
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
        hints: List[str] = []
        if samples.get("grant_subject_tran"):
            hints.append(f"- grant_subject_tran e.g., {', '.join(samples['grant_subject_tran'][:6])}")
        if samples.get("grant_population_tran"):
            hints.append(f"- grant_population_tran e.g., {', '.join(samples['grant_population_tran'][:6])}")
        if samples.get("grant_geo_area_tran"):
            hints.append(f"- grant_geo_area_tran e.g., {', '.join(samples['grant_geo_area_tran'][:6])}")
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

def _execute_metric(df: pd.DataFrame, pre_prompt: str, tool: str, params: Dict[str, Any]) -> str:
    q = (
        "Please call the specified analysis tool with the provided parameters and return only a small Markdown table or short summary.\n"
        f"Tool: {tool}\n"
        f"Parameters (JSON): { _json_dumps_stable(params) }"
    )
    try:
        extra_ctx = resolve_chart_context("data_summary.general")
    except Exception:
        extra_ctx = None
    try:
        result = tool_query(df, q, pre_prompt, extra_ctx).strip()
        if result and not result.startswith("[tool_query error]"):
            return result
    except Exception as e:
        # Fall back to direct analysis if tool_query fails
        pass
    
    # Fallback: Generate analysis directly from DataFrame
    return _fallback_metric_analysis(df, tool, params)

def _fallback_metric_analysis(df: pd.DataFrame, tool: str, params: Dict[str, Any]) -> str:
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
                    table = f"| {col.replace('_', ' ').title()} | Count |\n|" + "-" * 20 + "|-" * 8 + "|\n"
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
                    grouped = df.groupby(by_cols)[value_col].sum().sort_values(ascending=False).head(n)
                    if len(grouped) > 0:
                        # Create table header
                        headers = [col.replace('_', ' ').title() for col in by_cols] + ["Total Amount"]
                        header_row = "| " + " | ".join(headers) + " |\n"
                        separator = "|" + "|".join("-" * (len(h) + 2) for h in headers) + "|\n"
                        
                        table = header_row + separator
                        for idx, amount in grouped.items():
                            if isinstance(idx, tuple):
                                row_values = [str(v)[:25] if v is not None else "Unknown" for v in idx]
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
                        result = df.groupby(index_cols)[value_col].sum().sort_values(ascending=False).head(top)
                    elif agg == "count":
                        result = df.groupby(index_cols).size().sort_values(ascending=False).head(top)
                    else:
                        result = df.groupby(index_cols)[value_col].mean().sort_values(ascending=False).head(top)
                    
                    if len(result) > 0:
                        header_cols = [col.replace('_', ' ').title() for col in index_cols] + [f"{agg.title()} Value"]
                        header_row = "| " + " | ".join(header_cols) + " |\n"
                        separator = "|" + "|".join("-" * (len(h) + 2) for h in header_cols) + "|\n"
                        
                        table = header_row + separator
                        for idx, val in result.items():
                            if isinstance(idx, tuple):
                                row_values = [str(v)[:20] if v is not None else "Unknown" for v in idx]
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
                        table = f"| Rank | {col.replace('_', ' ').title()} |\n|------|" + "-" * 15 + "|\n"
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
    

def _collect_datapoints(df: pd.DataFrame, interview: Any, plan) -> List[DataPoint]:
    pre = _build_pre_prompt(df, interview)
    datapoints: List[DataPoint] = []
    for item in plan.metric_requests:
        content = _execute_metric(df, pre, item.tool, item.params)
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
