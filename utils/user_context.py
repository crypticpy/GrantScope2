"""Utilities to share user interview context across pages (Planner, Timeline).

This module centralizes:
- Loading the latest interview answers from Streamlit session_state or advisor_report.json
- Deriving sensible prefill defaults for Project Planner and Timeline Advisor
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


# Lazy import streamlit to avoid hard import-time dependency (helps tests)
def _get_session_state() -> Any | None:
    try:
        import streamlit as st  # type: ignore

        return st.session_state  # type: ignore[attr-defined]
    except Exception:
        return None


def load_advisor_report_json(path: str = "advisor_report.json") -> dict[str, Any] | None:
    """Load advisor_report.json if present and parse JSON."""
    try:
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def extract_interview_from_report(report: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Extract embedded interview object from a loaded report dict."""
    if not isinstance(report, Mapping):
        return None
    iv = report.get("interview")
    return iv if isinstance(iv, dict) else None


def load_interview_profile() -> dict[str, Any] | None:
    """
    Obtain the most recent interview responses:
    1) Prefer st.session_state["advisor_form"] (raw form values)
    2) Else fall back to advisor_report.json["interview"] if available
    """
    ss = _get_session_state()
    if ss and isinstance(ss.get("advisor_form"), dict):
        return dict(ss["advisor_form"])  # shallow copy

    report = load_advisor_report_json()
    interview = extract_interview_from_report(report)
    if isinstance(interview, dict):
        return dict(interview)

    return None


def _safe_list(val: Any) -> list[str]:
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    if isinstance(val, str):
        return [val]
    return []


def _human_join(items: Iterable[str], sep: str = ", ") -> str:
    items = [str(x).replace("_", " ").strip() for x in items if str(x).strip()]
    return sep.join(items)


def _map_budget_to_label(budget_range: Sequence[float] | None) -> str | None:
    """
    Map numeric budget range (min,max) to the discrete UI buckets used in Planner.
    Buckets:
      - Under $5,000
      - $5,000 - $25,000
      - $25,000 - $100,000
      - $100,000 - $500,000
      - Over $500,000
    Strategy: use the upper bound if present, else the midpoint/only value.
    """
    try:
        if not budget_range:
            return None
        nums = [float(x) for x in budget_range if x is not None]  # type: ignore[arg-type]
        if not nums:
            return None
        upper = max(nums)
        if upper <= 5000:
            return "Under $5,000"
        if upper <= 25_000:
            return "$5,000 - $25,000"
        if upper <= 100_000:
            return "$25,000 - $100,000"
        if upper <= 500_000:
            return "$100,000 - $500,000"
        return "Over $500,000"
    except Exception:
        return None


def _map_years_to_planner_timeline(years: int | float | None) -> str | None:
    """
    Planner timeline options: "3 months", "6 months", "1 year", "2 years", "3+ years".
    """
    try:
        if years is None:
            return None
        y = float(years)
        if y <= 0.5:
            return "6 months" if y > 0.25 else "3 months"
        if y <= 1.25:
            return "1 year"
        if y <= 2.5:
            return "2 years"
        return "3+ years"
    except Exception:
        return None


def _map_budget_to_complexity(budget_range: Sequence[float] | None) -> str | None:
    """
    Timeline Advisor complexity selectbox:
      - Simple (under $25,000, basic requirements)
      - Medium (up to $100,000, standard requirements)
      - Complex (over $100,000, detailed requirements)
    """
    try:
        if not budget_range:
            return None
        nums = [float(x) for x in budget_range if x is not None]  # type: ignore[arg-type]
        if not nums:
            return None
        upper = max(nums)
        if upper <= 25_000:
            return "Simple (under $25,000, basic requirements)"
        if upper <= 100_000:
            return "Medium (up to $100,000, standard requirements)"
        return "Complex (over $100,000, detailed requirements)"
    except Exception:
        return None


def _map_team_size_from_experience(experience_level: str | None) -> str:
    """
    Sensible default for team size based on user experience.
      - new  -> "Just me"
      - some -> "2-3 people"
      - pro  -> "4+ people"
    """
    if experience_level == "pro":
        return "4+ people"
    if experience_level == "some":
        return "2-3 people"
    return "Just me"


@dataclass
class PlannerPrefill:
    project_name: str | None = None
    org_name: str | None = None
    budget_range: str | None = None
    problem: str | None = None
    beneficiaries: str | None = None
    activities: str | None = None
    outcomes: str | None = None
    timeline: str | None = None


def derive_project_planner_prefill(interview: Mapping[str, Any]) -> dict[str, Any]:
    """
    Convert interview responses into defaults for Project Planner fields.
    Only sets values that can be reasonably inferred; leave others None.
    """
    program_area = str(interview.get("program_area") or "").strip() or None
    pops = _safe_list(interview.get("populations"))
    outcomes = _safe_list(interview.get("outcomes"))
    timeframe_years = interview.get("timeframe_years")
    budget_range = interview.get("budget_usd_range")

    return {
        "project_name": program_area,
        "org_name": None,  # cannot infer
        "budget_range": _map_budget_to_label(budget_range),
        "problem": None,  # cannot reliably infer from constraints/outcomes
        "beneficiaries": _human_join(pops),
        "activities": None,  # cannot infer
        "outcomes": _human_join(outcomes, sep="; "),
        "timeline": _map_years_to_planner_timeline(timeframe_years),
    }


def derive_timeline_prefill(
    interview: Mapping[str, Any],
    planner_data: Mapping[str, Any] | None = None,
    experience_level: str | None = None,
) -> dict[str, Any]:
    """
    Convert interview (and optional planner data) into defaults for Timeline Advisor.
    Returns keys:
      - project_name
      - grant_complexity
      - team_size
      - review_needs (list[str], default empty)
    """
    project_name = None
    if planner_data and isinstance(planner_data.get("project_name"), str):
        pn = planner_data.get("project_name", "")
        project_name = pn.strip() or None
    if not project_name:
        program_area = str(interview.get("program_area") or "").strip()
        project_name = program_area or None

    return {
        "project_name": project_name,
        "grant_complexity": _map_budget_to_complexity(interview.get("budget_usd_range")),
        "team_size": _map_team_size_from_experience(experience_level),
        "review_needs": [],  # leave empty by default; user can select as needed
    }
