import pandas as pd
import pytest

# Import pipeline module to enable monkeypatching its internals
try:
    import GrantScope.advisor.pipeline as ap  # type: ignore
    from GrantScope.advisor.demo import get_demo_interview  # type: ignore
    from GrantScope.advisor.schemas import InterviewInput, ReportBundle  # type: ignore
except Exception:  # pragma: no cover
    import advisor.pipeline as ap  # type: ignore
    from advisor.demo import get_demo_interview  # type: ignore
    from advisor.schemas import InterviewInput, ReportBundle  # type: ignore


def _tiny_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "funder_name": ["A", "B", "A"],
            "recip_name": ["X", "Y", "Z"],
            "amount_usd": [100.0, 200.0, 50.0],
            "grant_population_tran": ["Youth", "Adults", "Youth"],
            "grant_subject_tran": ["Education", "Health", "Education"],
            "year_issued": ["2023", "2024", "2023"],
        }
    )


def test_schema_defaults_and_hash():
    interview = InterviewInput(program_area="Education")
    # Defaults present
    assert isinstance(interview.populations, list)
    assert isinstance(interview.geography, list)
    assert interview.user_role in ("Grant Analyst/Writer", "Normal Grant User")
    # Stable hash returns short hex
    h = interview.stable_hash()
    assert isinstance(h, str)
    assert len(h) == 16


def test_cache_key_stability_invalidation():
    df1 = _tiny_df()
    interview = InterviewInput(program_area="Education", populations=["youth"])
    key1 = ap.cache_key_for(interview, df1)

    # Change data (sum(amount_usd) different) -> signature changes
    df2 = df1.copy()
    df2.loc[0, "amount_usd"] = 999.0
    key2 = ap.cache_key_for(interview, df2)
    assert key1 != key2

    # Same data, change interview -> key changes
    interview2 = InterviewInput(program_area="Health", populations=["adults"])
    key3 = ap.cache_key_for(interview2, df1)
    assert key1 != key3


def test_pipeline_with_mocks(monkeypatch):
    df = _tiny_df()
    interview = InterviewInput(program_area="Education", populations=["youth"], geography=["TX"])

    # Stub deterministic cached stages to avoid API calls
    monkeypatch.setattr(
        ap,
        "_stage0_intake_summary_cached",
        lambda key, d: "This is a concise intake summary.",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {
            "subjects": ["education"],
            "populations": ["youth"],
            "geographies": ["TX"],
            "weights": {},
        },
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {
            "metric_requests": [
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_population_tran", "n": 5},
                    "title": "Population freq",
                },
                {
                    "tool": "df_pivot_table",
                    "params": {
                        "index": ["year_issued"],
                        "value": "amount_usd",
                        "agg": "sum",
                        "top": 10,
                    },
                    "title": "Year trend",
                },
            ],
            "narrative_outline": ["Overview", "Findings"],
        },
        raising=True,
    )
    # Tool path returns a small markdown table regardless of input
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| col | value |\n| --- | --- |\n| demo | 1 |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [
            {"title": "Synthesis", "markdown_body": "Grounded narrative referencing DP IDs."}
        ],
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [
                {
                    "name": "Example Foundation",
                    "score": 0.9,
                    "rationale": "Strong alignment",
                    "grounded_dp_ids": ["DP-00000001"],
                }
            ],
            "response_tuning": [
                {"text": "Emphasize STEM outcomes", "grounded_dp_ids": ["DP-00000001"]}
            ],
            "search_queries": [{"query": "STEM youth Texas grants", "notes": ""}],
        },
        raising=True,
    )

    report = ap.run_interview_pipeline(interview, df)
    assert isinstance(report, ReportBundle)
    assert report.datapoints and len(report.datapoints) >= 1
    assert report.sections and any("Synthesis" in s.title for s in report.sections)
    assert report.recommendations and len(report.recommendations.funder_candidates) >= 1


def test_demo_flow_with_mocks(monkeypatch):
    df = _tiny_df()
    interview = get_demo_interview()

    # Reuse the same stubs as above to avoid API calls and speed up tests
    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Demo summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {
            "subjects": ["education"],
            "populations": ["youth"],
            "geographies": ["TX"],
            "weights": {},
        },
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {
            "metric_requests": [
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_population_tran", "n": 5},
                    "title": "Population freq",
                }
            ],
            "narrative_outline": ["Overview"],
        },
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Demo", "markdown_body": "Demo narrative."}],
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    report = ap.run_interview_pipeline(interview, df)
    assert isinstance(report, ReportBundle)
    # Smoke: bundle has the core fields
    assert report.interview.program_area != ""
    assert isinstance(report.sections, list)
    assert isinstance(report.datapoints, list)


def test_fallback_candidates_from_sample(monkeypatch):
    # Local import to avoid modifying module imports
    try:
        from GrantScope.loaders.data_loader import load_data, preprocess_data  # type: ignore
    except Exception:  # pragma: no cover
        from loaders.data_loader import load_data, preprocess_data  # type: ignore

    # Load real sample dataset to ensure many funders exist
    grants = load_data(file_path="data/sample.json")
    df, _grouped_df = preprocess_data(grants)

    # Stub deterministic cached stages to avoid API calls and force fallback
    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {
            "subjects": ["education"],
            "populations": ["youth"],
            "geographies": ["TX"],
            "weights": {},
        },
        raising=True,
    )
    # Plan without funder-level metrics (pipeline should auto-ensure one, but we force fallback by empty recs)
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {
            "metric_requests": [
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_subject_tran", "n": 5},
                    "title": "Subjects",
                }
            ],
            "narrative_outline": ["Overview"],
        },
        raising=True,
    )
    # Tool path returns a tiny markdown table
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Synthesis", "markdown_body": "Narrative."}],
        raising=True,
    )
    # Force empty LLM recommendations so pipeline fallback engages
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    interview = InterviewInput(
        program_area="STEM Education", populations=["Youth"], geography=["TX"]
    )
    report = ap.run_interview_pipeline(interview, df)

    cands = report.recommendations.funder_candidates
    assert cands and len(cands) >= 5
    assert all(fc.score > 0 for fc in cands[:5])
    assert all(isinstance(fc.rationale, str) and fc.rationale for fc in cands[:5])


def test_fallback_uses_count_when_amount_missing(monkeypatch):
    try:
        from GrantScope.loaders.data_loader import load_data, preprocess_data  # type: ignore
    except Exception:  # pragma: no cover
        from loaders.data_loader import load_data, preprocess_data  # type: ignore

    grants = load_data(file_path="data/sample.json")
    df, _grouped_df = preprocess_data(grants)
    # Remove amount_usd to trigger count-based ranking; keep funder_name
    if "amount_usd" in df.columns:
        df = df.drop(columns=["amount_usd"])

    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {
            "subjects": ["education"],
            "populations": ["youth"],
            "geographies": ["TX"],
            "weights": {},
        },
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {"metric_requests": [], "narrative_outline": ["Overview"]},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Synthesis", "markdown_body": "Narrative."}],
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    interview = InterviewInput(program_area="Education", populations=["Youth"], geography=["TX"])
    report = ap.run_interview_pipeline(interview, df)

    cands = report.recommendations.funder_candidates
    assert cands and len(cands) >= 5
    assert all(fc.score > 0 for fc in cands[:5])
    # Rationale should mention basis (grant count)
    assert any("count" in fc.rationale.lower() for fc in cands[:5])


def test_graceful_when_funder_missing(monkeypatch):
    try:
        from GrantScope.loaders.data_loader import load_data, preprocess_data  # type: ignore
    except Exception:  # pragma: no cover
        from loaders.data_loader import load_data, preprocess_data  # type: ignore

    grants = load_data(file_path="data/sample.json")
    df, _grouped_df = preprocess_data(grants)
    if "funder_name" not in df.columns:
        pytest.skip("Sample dataset lacks funder_name; cannot test this degradation case.")

    # Drop funder_name to make fallback impossible
    df2 = df.drop(columns=["funder_name"])

    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {
            "subjects": ["education"],
            "populations": ["youth"],
            "geographies": ["TX"],
            "weights": {},
        },
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {"metric_requests": [], "narrative_outline": ["Overview"]},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Synthesis", "markdown_body": "Narrative."}],
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    interview = InterviewInput(program_area="Education", populations=["Youth"], geography=["TX"])
    report = ap.run_interview_pipeline(interview, df2)

    # Graceful degradation: no crash and recommendations object present; no candidates can be derived
    assert report.recommendations is not None
    assert isinstance(report.recommendations.funder_candidates, list)
    assert len(report.recommendations.funder_candidates) == 0


def test_stage5_coercion_sanitization_variants(monkeypatch):
    df = _tiny_df()
    interview = InterviewInput(program_area="Education")

    # Stub deterministic stages to avoid network/LLM
    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {"subjects": [], "populations": [], "geographies": [], "weights": {}},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {"metric_requests": [], "narrative_outline": []},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Synthesis", "markdown_body": "Narrative."}],
        raising=True,
    )

    # Provide mixed/dirty funder candidate inputs to exercise _coerce_funder_candidate
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [
                # dict with only funder_name -> should coerce name from funder_name, score -> float, rationale -> str, grounded ids -> str list
                {
                    "funder_name": "Zed Foundation",
                    "score": "0.7",
                    "rationale": 123,
                    "grounded_dp_ids": [1, "DP-X"],
                },
                # invalid/empty-name cases -> should be skipped
                {"name": None, "score": 0.1},
                {"funder_name": None},
                "",
                "   ",
                {"funder_name": "nan"},
                {"label": "Label Funder"},  # should accept via 'label' fallback
                "Simple String Funder",  # should accept as-is
            ],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    report = ap.run_interview_pipeline(interview, df)
    cands = report.recommendations.funder_candidates
    names = {c.name for c in cands}

    # Expected accepted names present
    assert "Zed Foundation" in names
    assert "Label Funder" in names
    assert "Simple String Funder" in names

    # No null-ish/empty names should be present
    assert all(
        isinstance(n, str) and n.strip() and n.strip().lower() not in {"nan", "none", "null"}
        for n in names
    )


def test_fallback_ignores_nullish_funders(monkeypatch):
    # Build a df containing null-ish funder_name values mixed with valid ones
    df = pd.DataFrame(
        {
            "funder_name": ["A", None, "nan", " ", "B", "null", "C"],
            "amount_usd": [100.0, 10.0, 5.0, 0.0, 200.0, 1.0, 50.0],
            "year_issued": ["2023"] * 7,
        }
    )

    interview = InterviewInput(program_area="Test")

    # Stub deterministic stages and force empty LLM recs so fallback engages
    monkeypatch.setattr(
        ap, "_stage0_intake_summary_cached", lambda key, d: "Summary.", raising=True
    )
    monkeypatch.setattr(
        ap,
        "_stage1_normalize_cached",
        lambda key, d: {"subjects": [], "populations": [], "geographies": [], "weights": {}},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage2_plan_cached",
        lambda key, d: {"metric_requests": [], "narrative_outline": []},
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "tool_query",
        lambda _df, _q, _pre, _extra=None: "| k | v |\n| - | - |\n| a | b |",
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage4_synthesize_cached",
        lambda key, plan, dps: [{"title": "Synthesis", "markdown_body": "Narrative."}],
        raising=True,
    )
    monkeypatch.setattr(
        ap,
        "_stage5_recommend_cached",
        lambda key, needs, dps: {
            "funder_candidates": [],
            "response_tuning": [],
            "search_queries": [],
        },
        raising=True,
    )

    report = ap.run_interview_pipeline(interview, df)
    cands = report.recommendations.funder_candidates
    names = {c.name for c in cands}

    # Only valid names should remain; null-ish values ("", "nan", "none", "null") must be filtered out
    assert names.issubset({"A", "B", "C"})
    assert names == {"A", "B", "C"}  # all three valid appear
    assert all(c.score > 0 for c in cands if c.name in {"A", "B", "C"})
    assert all(
        isinstance(c.rationale, str) and c.rationale for c in cands if c.name in {"A", "B", "C"}
    )
