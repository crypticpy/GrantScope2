"""
Demo presets for the Advisor interview page.

APIs:
- get_demo_interview() -> InterviewInput
- get_demo_responses_dict() -> dict[str, Any]
- load_demo_responses_json(path: str = "GrantScope/advisor/demo_responses.json") -> dict | None
"""

from __future__ import annotations

import contextlib
import json as _json
import os
from typing import Any

# Flexible imports so this works both as a package and direct module
try:
    from GrantScope.advisor.schemas import InterviewInput  # type: ignore
except Exception:  # pragma: no cover
    from advisor.schemas import InterviewInput  # type: ignore


DEMO_INTERVIEW_DEFAULT: dict[str, Any] = {
    "program_area": "Youth education and after-school STEM",
    "populations": ["youth", "students", "low_income"],
    "geography": ["TX", "US"],
    "timeframe_years": 2,
    "budget_usd_range": [100000, 500000],
    "outcomes": [
        "Increase STEM program enrollment by 25%",
        "Improve standardized test scores by 10% for participating students",
    ],
    "constraints": ["Limited staff capacity", "Need for equipment and devices"],
    "preferred_funder_types": ["Foundation", "Corporate"],
    "keywords": ["education", "STEM", "after_school", "technology", "equipment"],
    "notes": "Pilot expansion in Austin metro; partner with local schools and libraries.",
    "user_role": "Grant Analyst/Writer",
}


def get_demo_responses_dict() -> dict[str, Any]:
    """Return a dict suitable for pre-filling the interview form."""
    return dict(DEMO_INTERVIEW_DEFAULT)


def get_demo_interview() -> InterviewInput:
    """Return a ready-to-use InterviewInput instance for demos."""
    return InterviewInput(**get_demo_responses_dict())


def load_demo_responses_json(
    path: str = "GrantScope/advisor/demo_responses.json",
) -> dict[str, Any] | None:
    """Load an optional JSON file that can override the built-in demo responses.

    Returns:
        dict with InterviewInput fields if file exists and loads successfully, else None.
    """
    with contextlib.suppress(Exception):
        if not os.path.exists(path):
            # Try bare repo-relative path if running inside package dir structure
            alt = os.path.join("advisor", "demo_responses.json")
            if os.path.exists(alt):
                path = alt
            else:
                return None
        with open(path, encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, dict):
            return data
    return None
