from __future__ import annotations

import pandas as pd
import pytest

# Import pipeline module to allow monkeypatching internal helpers
try:
    import GrantScope.advisor.pipeline as pipeline  # type: ignore
except Exception:  # pragma: no cover
    import advisor.pipeline as pipeline  # type: ignore


try:
    from GrantScope.advisor.schemas import (
        AnalysisPlan,
        ChartSummary,
        FigureArtifact,
        InterviewInput,
        Recommendations,
        ReportBundle,
        ReportSection,
        StructuredNeeds,
    )  # type: ignore
except Exception:  # pragma: no cover
    from advisor.schemas import (
        AnalysisPlan,
        ChartSummary,
        FigureArtifact,
        InterviewInput,
        Recommendations,
        ReportBundle,
        ReportSection,
        StructuredNeeds,
    )  # type: ignore

try:
    from GrantScope.advisor.renderer import render_report_html  # type: ignore
except Exception:  # pragma: no cover
    from advisor.renderer import render_report_html  # type: ignore


def _make_sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "funder_name": ["Alpha Foundation", "Beta Trust", "Alpha Foundation", "Gamma Org"],
            "amount_usd": [10000, 5000, 20000, 12000],
            "year_issued": [2019, 2020, 2021, 2021],
            "grant_subject_tran": ["health; education", "education", "health", "health; housing"],
            "grant_geo_area_tran": ["TX", "CA", "TX", "NY"],
        }
    )


def test_figures_default_produces_interpretations(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    df = _make_sample_df()
    interview = InterviewInput(program_area="Health programs", user_role="Analyst")
    needs = StructuredNeeds(subjects=["health"], geographies=["TX"], populations=[])

    # Mock the LLM-backed interpreter to avoid network calls
    monkeypatch.setattr(
        pipeline,
        "_interpret_chart_cached",
        lambda key, summary, interview_dict: "Short test interpretation.",
    )

    # Act
    figs = pipeline._figures_default(df, interview, needs)

    # Assert: expect at least 3 figures (top funders, distribution, time trend)
    assert isinstance(figs, list)
    assert len(figs) >= 3
    for f in figs:
        assert isinstance(f, FigureArtifact)
        # New fields should be present
        assert getattr(f, "summary", None) is not None
        assert isinstance(f.summary, ChartSummary)
        text = str(getattr(f, "interpretation_text", "") or "")
        assert text != ""
        assert "interpretation" in text.lower()


def test_render_report_html_includes_interpretations() -> None:
    # Arrange: build a minimal bundle with one figure carrying interpretation text
    interview = InterviewInput(program_area="Test")
    needs = StructuredNeeds()
    plan = AnalysisPlan(metric_requests=[], narrative_outline=[])
    fig = FigureArtifact(
        id="FIG-TEST",
        label="Demo",
        png_base64=None,
        html=None,
        summary=ChartSummary(label="Demo", highlights=["example"], stats={"n": 1}),
        interpretation_text="Hello world.",
    )
    bundle = ReportBundle(
        interview=interview,
        needs=needs,
        plan=plan,
        datapoints=[],
        recommendations=Recommendations(),
        sections=[ReportSection(title="Overview", markdown_body="Overview text.")],
        figures=[fig],
    )

    # Act
    html = render_report_html(bundle)

    # Assert
    assert "What this means" in html
    assert "Hello world." in html
