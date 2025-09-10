"""AI-assisted content generation helpers for Project Planner and Timeline Advisor.

This module centralizes:
- Calling the configured LLM (via loaders.llama_index_setup.get_openai_client)
- Building guarded prompts grounded in user inputs (Planner/Interview/Timeline)
- Returning structured JSON outputs for easy rendering
- Lightweight caching in Streamlit session_state and optional disk artifact

Usage from pages:
    from utils.ai_writer import generate_project_brief_ai, generate_timeline_guidance_ai

Notes:
- Graceful degradation: if OPENAI_API_KEY is not configured, functions return a deterministic
  fallback derived from user inputs so the UI still works.
- Response format: we ask the model to return JSON for safe parsing. We validate keys and
  coerce minimal structure on errors.
"""

from __future__ import annotations

import json
import os
import textwrap
from collections.abc import Mapping
from datetime import datetime
from typing import Any

try:
    # Streamlit available in app runtime; absent in unit tests
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore

# Central LLM client (OpenAI SDK v1) and model resolution
from loaders.llama_index_setup import get_openai_client  # type: ignore
from utils.user_context import load_advisor_report_json  # type: ignore

# Path used when persisting AI outputs to a report; tests or runtime can override via env
PERSIST_REPORT_PATH = os.getenv("ADVISOR_REPORT_PATH", "advisor_report.json")


# Stable hashing helper (kept internal to avoid importing advisor.* from Planner/TL pages)
def _json_dumps_stable(obj: Any) -> str:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        try:
            return json.dumps(str(obj))
        except Exception:
            return "{}"


def _stable_hash_for_obj(obj: Any) -> str:
    # Small, dependency-free stable hash (sha256 truncated) to avoid importing advisor.schemas
    import hashlib

    return hashlib.sha256(_json_dumps_stable(obj).encode("utf-8")).hexdigest()[:16]


def _is_ai_available() -> bool:
    # Rely on environment variable that the OpenAI SDK v1 expects.
    # loaders.llama_index_setup may also export the key from config into env.
    try:
        return bool(os.getenv("OPENAI_API_KEY"))
    except Exception:
        return False


def _put_session_cache(kind: str, key: str, payload: dict[str, Any]) -> None:
    """Cache AI result into st.session_state under a namespaced dict."""
    try:
        if st is None:
            return
        cache_key = f"__ai_cache_{kind}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = {}
        st.session_state[cache_key][key] = {
            "payload": payload,
            "saved_at": datetime.now().isoformat(),
        }
    except Exception:
        # Best-effort only
        pass


def _get_session_cache(kind: str, key: str) -> dict[str, Any] | None:
    try:
        if st is None:
            return None
        cache_key = f"__ai_cache_{kind}"
        entry = st.session_state.get(cache_key)  # type: ignore[attr-defined]
        if isinstance(entry, dict) and key in entry:
            value = entry[key]
            if isinstance(value, dict):
                return value.get("payload")
    except Exception:
        pass
    return None


def _write_disk_artifact(dir_name: str, filename: str, data: dict[str, Any]) -> None:
    """Optionally persist output for user export or debugging."""
    try:
        out_dir = os.path.join(".artifacts", "ai", dir_name)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"generated_at": datetime.now().isoformat(), "data": data},
                f,
                indent=2,
            )
    except Exception:
        # Non-fatal
        pass


def _extract_numeric_context(report: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract compact numeric grounding from advisor_report.json if available."""
    ctx: dict[str, Any] = {}
    try:
        if not isinstance(report, Mapping):
            return ctx
        # Figures stats (median, p90) if present
        figures = report.get("figures", [])
        if isinstance(figures, list):
            for fig in figures:
                try:
                    summary = (fig or {}).get("summary") or {}
                    stats = summary.get("stats") or {}
                    if isinstance(stats, dict):
                        if "median" in stats and "median_award_usd" not in ctx:
                            try:
                                ctx["median_award_usd"] = float(stats["median"])
                            except Exception:
                                pass
                        if "p90" in stats and "p90_award_usd" not in ctx:
                            try:
                                ctx["p90_award_usd"] = float(stats["p90"])
                            except Exception:
                                pass
                except Exception:
                    # continue scanning other figures
                    continue
        # Recommendations sizing tips
        recs = (report.get("recommendations") or {}).get("response_tuning") or []
        tips: list[str] = []
        if isinstance(recs, list):
            for r in recs:
                try:
                    txt = (r or {}).get("text")
                    if isinstance(txt, str) and txt.strip():
                        tips.append(txt.strip())
                except Exception:
                    continue
        if tips:
            ctx["sizing_tips"] = tips[:6]
    except Exception:
        return ctx
    return ctx


def _get_numeric_context_json_str() -> str:
    """Return JSON string for numeric grounding; '{}' if unavailable."""
    try:
        report = load_advisor_report_json(PERSIST_REPORT_PATH)
        ctx = _extract_numeric_context(report)
        return _json_dumps_stable(ctx if isinstance(ctx, dict) else {})
    except Exception:
        return "{}"


def _persist_ai_section(section: str, payload: dict[str, Any]) -> None:
    """Persist AI outputs into advisor_report.json under the given section key."""
    try:
        base: dict[str, Any] = {}
        if os.path.exists(PERSIST_REPORT_PATH):
            with open(PERSIST_REPORT_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    base = loaded
        base[section] = {"saved_at": datetime.now().isoformat(), "payload": payload}
        with open(PERSIST_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=2)
    except Exception:
        # Non-fatal persistence
        pass


def _build_planner_prompt(interview: Mapping[str, Any] | None, planner: Mapping[str, Any]) -> str:
    """Construct user prompt for Project Brief generation grounded in inputs."""
    inter_json = _json_dumps_stable(interview or {})
    plan_json = _json_dumps_stable(planner or {})

    return textwrap.dedent(
        f"""
        You are an expert grant strategist and proposal writer. Write a beautiful, robust, and practical Project Brief and strategy for a grant-seeking organization.

        Constraints and guardrails:
        - Use ONLY the information provided in the JSON inputs below (Interview + Planner form).
        - Do NOT fabricate specific data (funders, amounts, or statistics) not present in the context.
        - If something is unknown, clearly label it as "Not specified" and provide a practical suggestion to fill it.
        - Use clear, plain language suitable for non-experts, structured with headings and bullet points where helpful.
        - Keep the tone encouraging but realistic about funder expectations and timeframes.
        - If the requested budget appears high for most entry-level programs (e.g., over $100,000), suggest a multi-grant strategy and sequencing.

        Required JSON output schema (return JSON only, no Markdown fences):
        {{
          "brief_md": "markdown string (concise 4-7 paragraphs with headings)",
          "strategy_md": "markdown string (cover target funder types, positioning, and ask formulation)",
          "next_steps": ["action item 1", "action item 2", "..."],
          "assumptions": ["explicit assumption 1", "..."]
        }}

        Interview JSON:
        {inter_json}

        Planner JSON:
        {plan_json}
        """
    ).strip()


def _build_timeline_prompt(
    interview: Mapping[str, Any] | None,
    planner: Mapping[str, Any] | None,
    timeline: Mapping[str, Any],
) -> str:
    """Construct user prompt for Timeline Advisor narrative and cadence suggestions."""
    inter_json = _json_dumps_stable(interview or {})
    plan_json = _json_dumps_stable(planner or {})
    timeline_json = _json_dumps_stable(timeline or {})

    return textwrap.dedent(
        f"""
        You are a grant timeline and operations coach. Provide realistic guidance on how long grant applications take, how to stagger applications, and what cadence to aim for.

        Constraints and guardrails:
        - Ground advice in the provided Interview, Planner, and Timeline inputs only.
        - Do not invent concrete funder names or proprietary deadlines.
        - Provide ranges (e.g., "responses often take 2–4 months") and practical sequencing tips.
        - Use simple, actionable language for non-experts.

        Required JSON output schema (return JSON only, no Markdown fences):
        {{
          "timeline_guidance_md": "markdown string (expectations and pacing)",
          "cadence_md": "markdown string (how many applications per month/quarter, pipeline)",
          "stagger_plan_md": "markdown string (how to overlap prep/reviews/submissions)",
          "risks_mitigations": ["risk 1 with mitigation", "..."]
        }}

        Interview JSON:
        {inter_json}

        Planner JSON:
        {plan_json}

        Timeline JSON:
        {timeline_json}
        """
    ).strip()


def _safe_parse_json(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content or "{}")
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _fallback_planner(
    interview: Mapping[str, Any] | None, planner: Mapping[str, Any]
) -> dict[str, Any]:
    """Deterministic fallback without LLM."""
    # Compose a simple brief using provided fields
    name = (
        planner.get("project_name") or interview.get("program_area") if interview else ""
    ) or "Untitled Project"
    problem = planner.get("problem") or "Not specified"
    beneficiaries = planner.get("beneficiaries") or "Not specified"
    activities = planner.get("activities") or "Not specified"
    outcomes = planner.get("outcomes") or "Not specified"
    timeline = planner.get("timeline") or "Not specified"
    budget = planner.get("budget_range") or "Not specified"

    brief_lines = [
        f"# {name}",
        "",
        f"**Problem:** {problem}",
        f"**Beneficiaries:** {beneficiaries}",
        f"**Activities:** {activities}",
        f"**Expected Outcomes:** {outcomes}",
        f"**Timeline:** {timeline}",
        f"**Estimated Budget:** {budget}",
        "",
        "This brief is a starter template derived from your inputs. Edit and refine as needed.",
    ]
    strategy = textwrap.dedent(
        """
        ## Strategy Overview
        - Identify 8–15 potential funders aligned to your program area and geography
        - Prepare a modular proposal (core brief + tailored cover paragraphs)
        - Sequence applications monthly to build a steady pipeline
        - If your target budget is large, plan a multi-grant strategy with phased scope
        """
    ).strip()
    next_steps = [
        "Draft a one-page summary using this brief",
        "Compile required documents (IRS letter, board list, budget, letters of support)",
        "Create a list of 10 potential funders and note deadlines",
        "Schedule internal reviews 2 weeks before each submission",
    ]
    assumptions = ["No external numerical analysis available; generic pacing applied"]

    return {
        "brief_md": "\n".join(brief_lines),
        "strategy_md": strategy,
        "next_steps": next_steps,
        "assumptions": assumptions,
    }


def _fallback_timeline(
    interview: Mapping[str, Any] | None,
    planner: Mapping[str, Any] | None,
    timeline: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic fallback without LLM."""
    name = (
        (timeline.get("project_name") or (planner or {}).get("project_name"))
        or (interview or {}).get("program_area")
        or "Your Project"
    )

    guidance = textwrap.dedent(
        f"""
        # Timeline Guidance for {name}

        - New applicants often need 6–10 weeks to prepare a complete grant application
        - Reviews commonly take 2–4 months after submission
        - Build in extra time for board approvals and partner letters
        """
    ).strip()
    cadence = textwrap.dedent(
        """
        ## Submission Cadence
        - Aim for 1 submission per month to maintain momentum
        - Keep a rolling list of 8–12 opportunities in your pipeline
        - Start outreach (emails/calls) 4–6 weeks before deadlines
        """
    ).strip()
    stagger = textwrap.dedent(
        """
        ## Stagger Plan
        - Week 1–2: Research and outline
        - Week 3–4: Draft core narrative and budget
        - Week 5: Internal reviews; collect letters
        - Week 6: Finalize and submit
        - Overlap next opportunity research during Week 3 of current application
        """
    ).strip()
    risks = [
        "Underestimating document collection time — Mitigation: start early with a checklist",
        "Single-point dependency on one reviewer — Mitigation: schedule two reviewers",
        "Over-ambitious monthly cadence — Mitigation: reduce scope or alternate months",
    ]
    return {
        "timeline_guidance_md": guidance,
        "cadence_md": cadence,
        "stagger_plan_md": stagger,
        "risks_mitigations": risks,
    }


def generate_project_brief_ai(
    planner: Mapping[str, Any],
    interview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate an AI-authored Project Brief and strategy from Planner + Interview.

    Returns dict with keys:
      - brief_md: Markdown
      - strategy_md: Markdown
      - next_steps: list[str]
      - assumptions: list[str]
      - cache_key: str
    """
    # Cache by stable hash of inputs
    cache_key = _stable_hash_for_obj({"planner": planner or {}, "interview": interview or {}})
    cached = _get_session_cache("planner_brief", cache_key)
    if isinstance(cached, dict):
        # Attach cache_key for traceability
        cached["cache_key"] = cache_key
        return cached

    if not _is_ai_available():
        result = _fallback_planner(interview, planner)
        result["cache_key"] = cache_key
        _put_session_cache("planner_brief", cache_key, result)
        _write_disk_artifact(
            "planner", f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{cache_key}.json", result
        )
        _persist_ai_section("planner_ai", result)
        return result

    client = get_openai_client()
    prompt = _build_planner_prompt(interview, planner)
    _num_json = _get_numeric_context_json_str()
    if _num_json and _num_json != "{}":
        # Append numeric grounding as an additional JSON block
        prompt = f"{prompt}\n\nDatapoints JSON:\n{_num_json}"

    # Call OpenAI Chat Completions (SDK v1)
    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious assistant. Return JSON only. "
                        "Do not invent unknown facts. Keep outputs actionable and clear."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = ""
        try:
            content = resp.choices[0].message.content or ""
        except Exception:
            content = ""
        data = _safe_parse_json(content)

        # Validate required keys
        brief_md = str(data.get("brief_md") or "").strip()
        strategy_md = str(data.get("strategy_md") or "").strip()
        next_steps = data.get("next_steps") or []
        assumptions = data.get("assumptions") or []

        if not brief_md or not strategy_md or not isinstance(next_steps, list):
            data = _fallback_planner(interview, planner)
        else:
            # Normalize lists to strings
            next_steps = [str(x) for x in next_steps if str(x).strip()]
            assumptions = [str(x) for x in (assumptions or []) if str(x).strip()]
            data = {
                "brief_md": brief_md,
                "strategy_md": strategy_md,
                "next_steps": next_steps,
                "assumptions": assumptions,
            }
    except Exception:
        data = _fallback_planner(interview, planner)

    data["cache_key"] = cache_key
    _put_session_cache("planner_brief", cache_key, data)
    _write_disk_artifact(
        "planner", f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{cache_key}.json", data
    )
    # Persist into advisor_report.json (non-fatal if file missing or write fails)
    _persist_ai_section("planner_ai", data)
    return data


def generate_timeline_guidance_ai(
    timeline: Mapping[str, Any],
    planner: Mapping[str, Any] | None = None,
    interview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate an AI-authored timeline narrative, cadence guidance, and stagger plan.

    Returns dict with keys:
      - timeline_guidance_md: Markdown
      - cadence_md: Markdown
      - stagger_plan_md: Markdown
      - risks_mitigations: list[str]
      - cache_key: str
    """
    cache_key = _stable_hash_for_obj(
        {"timeline": timeline or {}, "planner": planner or {}, "interview": interview or {}}
    )
    cached = _get_session_cache("timeline_ai", cache_key)
    if isinstance(cached, dict):
        cached["cache_key"] = cache_key
        return cached

    if not _is_ai_available():
        result = _fallback_timeline(interview, planner, timeline)
        result["cache_key"] = cache_key
        _put_session_cache("timeline_ai", cache_key, result)
        _write_disk_artifact(
            "timeline", f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{cache_key}.json", result
        )
        _persist_ai_section("timeline_ai", result)
        return result

    client = get_openai_client()
    prompt = _build_timeline_prompt(interview, planner, timeline)
    _num_json = _get_numeric_context_json_str()
    if _num_json and _num_json != "{}":
        # Append numeric grounding as an additional JSON block
        prompt = f"{prompt}\n\nDatapoints JSON:\n{_num_json}"

    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious assistant. Return JSON only. "
                        "Provide realistic ranges and emphasize planning discipline."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = ""
        try:
            content = resp.choices[0].message.content or ""
        except Exception:
            content = ""
        data = _safe_parse_json(content)

        # Validate required keys
        tl_md = str(data.get("timeline_guidance_md") or "").strip()
        cadence_md = str(data.get("cadence_md") or "").strip()
        stagger_md = str(data.get("stagger_plan_md") or "").strip()
        risks = data.get("risks_mitigations") or []

        if not tl_md or not cadence_md or not stagger_md or not isinstance(risks, list):
            data = _fallback_timeline(interview, planner, timeline)
        else:
            risks = [str(x) for x in risks if str(x).strip()]
            data = {
                "timeline_guidance_md": tl_md,
                "cadence_md": cadence_md,
                "stagger_plan_md": stagger_md,
                "risks_mitigations": risks,
            }
    except Exception:
        data = _fallback_timeline(interview, planner, timeline)

    data["cache_key"] = cache_key
    _put_session_cache("timeline_ai", cache_key, data)
    _write_disk_artifact(
        "timeline", f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{cache_key}.json", data
    )
    # Persist into advisor_report.json (non-fatal if file missing or write fails)
    _persist_ai_section("timeline_ai", data)
    return data
