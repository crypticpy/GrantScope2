import json
from pathlib import Path
from typing import Any


def _make_sample_report(median: float = 55293.0, p90: float = 203280.0) -> dict[str, Any]:
    return {
        "figures": [
            {
                "summary": {
                    "stats": {
                        "median": median,
                        "p90": p90,
                    }
                }
            }
        ],
        "recommendations": {
            "response_tuning": [
                {"text": "Size your first ask around $50,000–60,000 for pilot programs."},
                {"text": "Plan multiple small grants to meet your budget."},
            ]
        },
    }


def test_numeric_context_extraction(tmp_path, monkeypatch):
    # Import inside test to avoid module-level constant resolution issues before we patch
    import utils.ai_writer as aiw  # type: ignore

    report_path: Path = tmp_path / "advisor_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(_make_sample_report(), f, indent=2)

    # Point ai_writer to our temp report path
    aiw.PERSIST_REPORT_PATH = str(report_path)

    # Validate extraction JSON contains expected numeric keys
    json_str = aiw._get_numeric_context_json_str()  # type: ignore[attr-defined]
    ctx = json.loads(json_str)
    assert isinstance(ctx, dict)
    # Keys come from figure summary stats
    assert "median_award_usd" in ctx
    assert "p90_award_usd" in ctx
    assert ctx["median_award_usd"] == 55293.0
    assert ctx["p90_award_usd"] == 203280.0
    # Tips pulled from recommendations.response_tuning
    assert "sizing_tips" in ctx
    assert isinstance(ctx["sizing_tips"], list)
    assert any("Size your first ask" in tip for tip in ctx["sizing_tips"])


def test_persist_ai_section_and_generate_functions(tmp_path, monkeypatch):
    import utils.ai_writer as aiw  # type: ignore

    report_path: Path = tmp_path / "advisor_report.json"
    # Start with a minimal valid report file
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(_make_sample_report(), f, indent=2)

    # Point ai_writer to our temp report path
    aiw.PERSIST_REPORT_PATH = str(report_path)

    # Persist a small payload into planner_ai section
    payload_planner = {"ok": True, "note": "test persist"}
    aiw._persist_ai_section("planner_ai", payload_planner)  # type: ignore[attr-defined]
    with report_path.open("r", encoding="utf-8") as f:
        written = json.load(f)
    assert "planner_ai" in written
    assert "payload" in written["planner_ai"]
    assert written["planner_ai"]["payload"]["ok"] is True

    # Force fallback path (no OpenAI key), then call generators and ensure they also persist
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Project brief generation (fallback) and persistence
    brief = aiw.generate_project_brief_ai({"project_name": "Test Project"})  # type: ignore
    assert isinstance(brief, dict)
    assert "brief_md" in brief
    # Verify persisted section updated
    with report_path.open("r", encoding="utf-8") as f:
        written2 = json.load(f)
    assert "planner_ai" in written2
    assert "payload" in written2["planner_ai"]
    assert "brief_md" in written2["planner_ai"]["payload"]

    # Timeline guidance generation (fallback) and persistence
    timeline = aiw.generate_timeline_guidance_ai({"project_name": "Test Project", "milestones": []})  # type: ignore
    assert isinstance(timeline, dict)
    assert "timeline_guidance_md" in timeline
    with report_path.open("r", encoding="utf-8") as f:
        written3 = json.load(f)
    assert "timeline_ai" in written3
    assert "payload" in written3["timeline_ai"]
    assert "cadence_md" in written3["timeline_ai"]["payload"]
