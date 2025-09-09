import re
from typing import Any, Dict

import pytest

# Import build_workbook_bundle with flexible path resolution (repo or package)
try:
    from GrantScope.advisor.renderer import build_workbook_bundle  # type: ignore
except Exception:  # pragma: no cover
    from advisor.renderer import build_workbook_bundle  # type: ignore


def _make_bundle(
    profile: Dict[str, Any] | None = None,
    planner: Dict[str, Any] | None = None,
    budget: Dict[str, Any] | None = None,
    insights: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Helper to call the builder with defaults."""
    return build_workbook_bundle(profile or {}, planner or {}, budget or {}, insights or {})


def test_bundle_has_required_keys_and_headers() -> None:
    # Arrange
    bundle = _make_bundle()

    # Assert: contract keys
    assert isinstance(bundle, dict)
    assert "markdown" in bundle
    assert "html" in bundle  # may be None or str
    assert "assets" in bundle and isinstance(bundle["assets"], dict)

    md = bundle["markdown"]
    assert isinstance(md, str) and len(md) > 0

    # Required section headers (Writer Pack)
    required_headers = [
        "## Profile Summary",
        "## Budget Summary",
        "## Project Plan",
        "## Key Charts",
        "## Recommendations",
        "## Draft Proposal Language",
    ]
    for h in required_headers:
        assert h in md, f"Missing required header: {h}"


def test_missing_optional_inputs_inserts_placeholders() -> None:
    # Arrange: no insights provided
    bundle = _make_bundle(insights={})
    md = bundle["markdown"]

    # Assert: placeholder for Key Charts when none are available
    assert "No charts captured yet" in md or "_No charts captured yet." in md


def test_redaction_and_truncation_in_free_text() -> None:
    # Arrange: planner with PII and very long text
    long_text = "A" * 1200
    planner = {
        "planner_problem": (
            "Please contact me at user@example.com or (555) 123-4567. "
            "Our org EIN is 12-3456789. " + long_text
        ),
        "planner_beneficiaries": "Families in West Region",
        "planner_activities": "After-school tutoring and weekend workshops.",
        "planner_outcomes": "Improve reading scores by 10% in 12 months.",
        "planner_budget_range": "$25,000 - $100,000",
    }

    # Act
    bundle = _make_bundle(planner=planner)
    md = bundle["markdown"]

    # Assert: PII is redacted
    assert "[redacted email]" in md
    assert "[redacted phone]" in md
    assert "[redacted EIN]" in md
    assert "user@example.com" not in md
    assert "123-4567" not in md  # common tail of phone formats
    assert "12-3456789" not in md

    # Assert: truncation marker present somewhere for very long text
    assert "... [truncated]" in md


def test_recommendations_section_handles_missing_gracefully() -> None:
    # Arrange: insights without recommendations
    insights = {"tables": [], "figures": []}

    # Act
    bundle = _make_bundle(insights=insights)

    # Assert: recommendation placeholder text appears
    md = bundle["markdown"]
    assert "Suggestions will appear here" in md or "Based on the current view and your goal" in md


def test_optional_html_export_is_string_or_none() -> None:
    # Arrange
    bundle = _make_bundle()

    # Assert
    html = bundle.get("html")
    assert html is None or isinstance(html, str)