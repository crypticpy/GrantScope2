import json
from pathlib import Path
from typing import Any


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Msg(content)


class _Choices:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Chat:
    def __init__(self, content: str):
        self._content = content

    class completions:
        # Will be set per instance via monkeypatch below
        create = None  # type: ignore


class _FakeClient:
    def __init__(self, content: str):
        # Prepare a minimal client.chat.completions.create(...) that returns object with .choices[0].message.content
        def _create(**kwargs):  # noqa: ANN001
            return _Choices(content)

        self.chat = _Chat(content)
        # Bind the function on the nested class
        self.chat.completions.create = _create  # type: ignore[attr-defined]


def _make_sample_report() -> dict[str, Any]:
    return {
        "figures": [
            {
                "summary": {
                    "stats": {
                        "median": 55293.0,
                        "p90": 203280.0,
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


def test_llm_path_planner_and_timeline_persist(tmp_path, monkeypatch):
    import utils.ai_writer as aiw  # type: ignore

    # Create a temp advisor_report.json to read numeric context and to persist into
    report_path: Path = tmp_path / "advisor_report.json"
    report_path.write_text(json.dumps(_make_sample_report(), indent=2), encoding="utf-8")
    aiw.PERSIST_REPORT_PATH = str(report_path)

    # Force "AI available" path and inject fake client
    monkeypatch.setattr(aiw, "_is_ai_available", lambda: True, raising=False)

    # Return JSON payload for planner with all required keys
    planner_resp = json.dumps(
        {
            "brief_md": "# LLM Brief\n\nContent.",
            "strategy_md": "## Strategy\n\nDetails.",
            "next_steps": ["One", "Two"],
            "assumptions": ["Assumption A"],
        }
    )
    # Return JSON payload for timeline with all required keys
    timeline_resp = json.dumps(
        {
            "timeline_guidance_md": "# Guidance\n\nDo X.",
            "cadence_md": "## Cadence\n\nMonthly.",
            "stagger_plan_md": "## Stagger\n\nOverlap tasks.",
            "risks_mitigations": ["Risk 1 — Mitigation"],
        }
    )

    # Monkeypatch the client factory to return a fake client that yields the provided content
    def _fake_get_client_planner():
        return _FakeClient(planner_resp)

    def _fake_get_client_timeline():
        return _FakeClient(timeline_resp)

    # Test planner generation and persistence
    monkeypatch.setattr(aiw, "get_openai_client", _fake_get_client_planner, raising=False)
    brief = aiw.generate_project_brief_ai({"project_name": "LLM Path"})  # type: ignore
    assert isinstance(brief, dict)
    assert "brief_md" in brief and brief["brief_md"].startswith("# LLM Brief")

    # Verify persisted into planner_ai
    data_after_planner = json.loads(report_path.read_text(encoding="utf-8"))
    assert "planner_ai" in data_after_planner
    assert "payload" in data_after_planner["planner_ai"]
    assert "brief_md" in data_after_planner["planner_ai"]["payload"]

    # Test timeline generation and persistence
    monkeypatch.setattr(aiw, "get_openai_client", _fake_get_client_timeline, raising=False)
    tl = aiw.generate_timeline_guidance_ai({"project_name": "LLM Path", "milestones": []})  # type: ignore
    assert isinstance(tl, dict)
    assert "timeline_guidance_md" in tl and tl["timeline_guidance_md"].startswith("# Guidance")

    # Verify persisted into timeline_ai
    data_after_tl = json.loads(report_path.read_text(encoding="utf-8"))
    assert "timeline_ai" in data_after_tl
    assert "payload" in data_after_tl["timeline_ai"]
    assert "cadence_md" in data_after_tl["timeline_ai"]["payload"]
