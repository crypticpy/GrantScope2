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
        return tool_query(df, q, pre_prompt, extra_ctx).strip()
    except Exception as e:
        return f"[tool_query error] {e}"

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
