from __future__ import annotations

"""
Stage helper functions for the Advisor pipeline.

This module centralizes the cached LLM-backed stages to keep
advisor.pipeline lean and under 300 lines per file where feasible.
It preserves behavior and public API by providing the same
stage helper functions previously defined in pipeline.py.
"""

from typing import Any, Dict, List
import json as _json

import streamlit as st

# Flexible imports to work when run as package or local
try:
    from GrantScope.advisor.prompts import (  # type: ignore
        system_guardrails,
        stage0_intake_summary_user,
        stage1_normalize_user,
        stage2_plan_user,
        stage4_synthesize_user,
        stage5_recommend_user,
        chart_interpretation_user,
        WHITELISTED_TOOLS,
    )
except Exception:  # pragma: no cover
    from advisor.prompts import (  # type: ignore
        system_guardrails,
        stage0_intake_summary_user,
        stage1_normalize_user,
        stage2_plan_user,
        stage4_synthesize_user,
        stage5_recommend_user,
        chart_interpretation_user,
        WHITELISTED_TOOLS,
    )

try:
    from GrantScope.loaders.llama_index_setup import get_openai_client  # type: ignore
except Exception:  # pragma: no cover
    from loaders.llama_index_setup import get_openai_client  # type: ignore

# Optional central config (model selection)
try:
    from GrantScope import config as _cfg  # type: ignore
except Exception:  # pragma: no cover
    try:
        import config as _cfg  # type: ignore
    except Exception:
        _cfg = None  # type: ignore


def _json_dumps_stable(obj: Any) -> str:
    return _json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _json_loads(text: str) -> Any:
    return _json.loads(text)


def _model_name() -> str:
    if _cfg is not None:
        try:
            return _cfg.get_model_name()
        except Exception:
            pass
    return "gpt-5"


def _chat_completion_text(user_content: str) -> str:
    """Return assistant message content (non-streaming)."""
    client = get_openai_client()
    system = system_guardrails()
    resp = client.chat.completions.create(
        model=_model_name(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    try:
        content = resp.choices[0].message.content or ""
    except Exception:
        content = str(resp)
    return content


def _chat_completion_json(user_content: str) -> Any:
    """Return parsed JSON from an assistant response. If parsing fails, raise."""
    txt = _chat_completion_text(user_content)
    s = txt.strip()
    if "```" in s:
        try:
            start = s.index("```")
            rest = s[start + 3 :]
            if rest.lower().startswith("json"):
                rest = rest[4:]
            end = rest.index("```")
            s = rest[:end]
        except Exception:
            s = s
    try:
        return _json_loads(s)
    except Exception as e:
        raise ValueError(
            f"Assistant did not return valid JSON: {e}. Raw: {txt[:240]}"
        ) from e


@st.cache_data(show_spinner=True)
def _stage0_intake_summary_cached(key: str, interview_dict: Dict[str, Any]) -> str:
    try:
        return _chat_completion_text(stage0_intake_summary_user(interview_dict)).strip()
    except Exception:
        pa = interview_dict.get("program_area") or "a municipal program"
        geo = ", ".join(interview_dict.get("geography") or []) or "target geographies"
        return (
            f"This interview focuses on {pa} serving {geo}. "
            "The goal is to align needs with funders using historical grant data."
        )


@st.cache_data(show_spinner=True)
def _stage1_normalize_cached(key: str, interview_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage1_normalize_user(interview_dict))
        if isinstance(obj, dict):
            allowed = {"subjects", "populations", "geographies", "weights"}
            return {k: v for k, v in obj.items() if k in allowed}
    except Exception:
        pass
    subj: List[str] = []
    kw = interview_dict.get("keywords") or []
    if isinstance(kw, list):
        subj = [str(x).strip().lower().replace(" ", "_") for x in kw][:5]
    return {
        "subjects": subj,
        "populations": [
            str(x).lower().replace(" ", "_") for x in (interview_dict.get("populations") or [])
        ],
        "geographies": [str(x).upper() for x in (interview_dict.get("geography") or [])],
        "weights": {},
    }


@st.cache_data(show_spinner=True)
def _stage2_plan_cached(key: str, needs_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage2_plan_user(needs_dict))
        mr = obj.get("metric_requests", []) if isinstance(obj, dict) else []
        clean: List[Dict[str, Any]] = []
        for item in mr:
            try:
                tool = str(item.get("tool"))
                if tool not in WHITELISTED_TOOLS:
                    continue
                params = item.get("params") or {}
                title = str(item.get("title") or tool)
                clean.append({"tool": tool, "params": params, "title": title})
            except Exception:
                continue
        outline = obj.get("narrative_outline", []) if isinstance(obj, dict) else []
        return {"metric_requests": clean, "narrative_outline": outline}
    except Exception:
        return {
            "metric_requests": [
                {
                    "tool": "df_groupby_sum",
                    "params": {"by": ["grant_subject_tran"], "value": "amount_usd", "n": 10},
                    "title": "Top Subjects by Amount",
                },
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_population_tran", "n": 10},
                    "title": "Top Populations",
                },
                {
                    "tool": "df_pivot_table",
                    "params": {"index": ["year_issued"], "value": "amount_usd", "agg": "sum", "top": 20},
                    "title": "Time Trend by Year",
                },
            ],
            "narrative_outline": ["Overview", "Funding Patterns", "Populations Served", "Time Trends"],
        }


@st.cache_data(show_spinner=True)
def _stage4_synthesize_cached(key: str, plan_dict: Dict[str, Any], dps_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        obj = _chat_completion_json(stage4_synthesize_user(plan_dict, dps_index))
        if isinstance(obj, list):
            clean: List[Dict[str, Any]] = []
            for it in obj:
                if isinstance(it, dict) and "title" in it and "markdown_body" in it:
                    clean.append({"title": str(it["title"]), "markdown_body": str(it["markdown_body"])})
            if clean:
                return clean
    except Exception:
        pass
    return [
        {
            "title": "Overview",
            "markdown_body": (
                "This report synthesizes insights grounded in the collected DataPoints. "
                "It highlights funding patterns by subject areas, populations served, and geographies, "
                "and surfaces notable funders and time trends to inform grant strategy."
            ),
        },
        {
            "title": "Funding Patterns and Key Players",
            "markdown_body": (
                "We examine top funders by awarded amount and identify concentration across a few leading organizations. "
                "Use the Data Evidence section to review tables for top funders and category breakdowns (see DP-IDs). "
                "Consider aligning outreach with funders showing a consistent pattern of awards in your focus areas."
            ),
        },
        {
            "title": "Populations and Geographies",
            "markdown_body": (
                "The dataset includes a range of populations (e.g., children and youth, students, low-income people) "
                "and geographic areas (e.g., city and state names). Where possible, we ground observations in those categories. "
                "If filters were broad or unconstrained, interpret findings as general patterns rather than definitive targeting."
            ),
        },
        {
            "title": "Actionable Next Steps",
            "markdown_body": (
                "1) Shortlist 5–10 funders with demonstrated fit and recent activity. "
                "2) Tailor messaging to emphasize outcomes and populations where data suggests alignment. "
                "3) Conduct targeted research on top geographies and subject areas to refine proposals and partnerships."
            ),
        },
    ]


@st.cache_data(show_spinner=True)
def _interpret_chart_cached(key: str, summary: Dict[str, Any], interview_dict: Dict[str, Any]) -> str:
    """Return a short interpretation for a chart, grounded in the provided summary and interview."""
    try:
        user_msg = chart_interpretation_user(summary, interview_dict)
        txt = _chat_completion_text(user_msg).strip()
        if txt:
            return txt
    except Exception:
        pass
    hi = summary.get("highlights") or []
    if hi:
        base = "; ".join(map(str, hi[:2]))
        return f"What this means: {base}."
    missing: List[str] = []
    for field in ("stats", "label"):
        try:
            if not summary.get(field):
                missing.append(field)
        except Exception:
            missing.append(field)
    if missing:
        return f"What this means: Interpretation unavailable; missing fields: {', '.join(missing)}."
    return "What this means: Interpretation unavailable due to limited data."


@st.cache_data(show_spinner=True)
def _stage5_recommend_cached(key: str, needs_dict: Dict[str, Any], dps_index: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage5_recommend_user(needs_dict, dps_index))
        if isinstance(obj, dict):
            fc = obj.get("funder_candidates") or []
            rt = obj.get("response_tuning") or []
            sq = obj.get("search_queries") or []
            return {"funder_candidates": fc, "response_tuning": rt, "search_queries": sq}
    except Exception:
        pass
    return {"funder_candidates": [], "response_tuning": [], "search_queries": []}


__all__ = [
    "_stage0_intake_summary_cached",
    "_stage1_normalize_cached",
    "_stage2_plan_cached",
    "_stage4_synthesize_cached",
    "_interpret_chart_cached",
    "_stage5_recommend_cached",
]