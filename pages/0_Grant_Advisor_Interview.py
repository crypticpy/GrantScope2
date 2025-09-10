import os
import sys
from typing import Any, cast

import pandas as pd
import streamlit as st

# Ensure package-relative imports work when running pages directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.app_state import (  # type: ignore
    get_data,
    init_session_state,
    sidebar_controls,
)

# Guarded import for download_text utility (works in package or local)
try:
    from utils.utils import download_text  # type: ignore
except Exception:  # pragma: no cover
    try:
        from GrantScope.utils.utils import download_text  # type: ignore
    except Exception:
        download_text = None  # type: ignore
from config import is_enabled  # type: ignore
from utils.app_state import (
    get_session_profile,  # type: ignore
    is_newbie,  # type: ignore
)
from utils.help import render_page_help_panel  # type: ignore

# Flexible imports for the Advisor package (prefer local repo modules, fallback to package)
try:
    from advisor.demo import (  # type: ignore
        get_demo_responses_dict,
        load_demo_responses_json,
    )
    from advisor.persist import (  # type: ignore
        import_bundle_from_upload,
    )
    from advisor.pipeline import run_interview_pipeline  # type: ignore
    from advisor.pipeline.progress import get_progress_state, get_report  # type: ignore
    from advisor.renderer import (  # type: ignore
        # render_report_html,
        build_workbook_bundle,
        render_report_streamlit,
    )
    from advisor.schemas import InterviewInput  # type: ignore
    from advisor.ui_progress import (  # type: ignore
        STAGES,  # type: ignore
        render_live_progress_tracker,
        # render_minimal_progress,
        # cleanup_progress_state,
    )
except Exception:
    from GrantScope.advisor.demo import (  # type: ignore
        get_demo_responses_dict,
        load_demo_responses_json,
    )
    from GrantScope.advisor.persist import (  # type: ignore
        import_bundle_from_upload,
    )
    from GrantScope.advisor.pipeline import run_interview_pipeline  # type: ignore
    from GrantScope.advisor.pipeline.progress import get_progress_state, get_report  # type: ignore
    from GrantScope.advisor.renderer import (  # type: ignore
        # render_report_html,
        build_workbook_bundle,
        render_report_streamlit,
    )
    from GrantScope.advisor.schemas import InterviewInput  # type: ignore
    from GrantScope.advisor.ui_progress import (  # type: ignore
        STAGES,  # type: ignore
        render_live_progress_tracker,
        # render_minimal_progress,
        # cleanup_progress_state,
    )


st.set_page_config(page_title="GrantScope — Grant Advisor Interview", page_icon=":memo:")


# --- Workbook Export helpers (Download Workbook action) ---


def _collect_session_prefix(prefix: str) -> dict:
    """Collect a shallow dict of st.session_state items whose keys start with prefix."""
    try:
        ss = st.session_state  # type: ignore[attr-defined]
    except Exception:
        return {}
    out: dict = {}
    try:
        for k, v in ss.items():
            if isinstance(k, str) and k.startswith(prefix):
                out[k] = v
    except Exception:
        pass
    return out


def _collect_insights_from_report(report: Any) -> dict:
    """
    Build a lightweight insights dict from a ReportBundle-like object:
    - tables: [{'title', 'markdown'}] from datapoints.table_md
    - figures: [{'label'}] from figures
    - recommendations: [{'title','reason'}] from recommendations.funder_candidates
    """
    ins: dict = {"tables": [], "figures": [], "recommendations": []}
    try:
        # Tables from datapoints (markdown tables captured as pre text)
        dps = getattr(report, "datapoints", []) or []
        for dp in dps[:3]:
            title = getattr(dp, "title", "") or getattr(dp, "id", "Table")
            table_md = getattr(dp, "table_md", "") or ""
            if table_md:
                ins["tables"].append({"title": str(title), "markdown": str(table_md)})
    except Exception:
        pass
    try:
        figs = getattr(report, "figures", []) or []
        for fig in figs[:3]:
            label = getattr(fig, "label", "") or getattr(fig, "id", "Figure")
            ins["figures"].append({"label": str(label)})
    except Exception:
        pass
    try:
        recs = getattr(getattr(report, "recommendations", None), "funder_candidates", []) or []
        for fc in recs[:5]:
            name = getattr(fc, "name", "Recommendation")
            rationale = getattr(fc, "rationale", "") or ""
            grounded = getattr(fc, "grounded_dp_ids", None)
            if grounded:
                rationale = f"{rationale} (cites {', '.join(grounded)})".strip()
            ins["recommendations"].append({"title": str(name), "reason": str(rationale)})
    except Exception:
        pass
    return ins


def _render_workbook_download(report: Any) -> None:
    """
    Render a 'Download Workbook' action when a report exists.
    Builds workbook bundle via advisor.renderer.build_workbook_bundle and uses download_text for .md.
    HTML export is optional; shown only if available.
    """
    if report is None:
        return

    # Gather inputs
    try:
        profile = get_session_profile()  # type: ignore[call-arg]
    except Exception:
        profile = {}

    # Coerce UserProfile/dataclass to dict for builder compatibility
    try:
        if profile and not isinstance(profile, dict):
            if hasattr(profile, "to_dict"):
                profile = profile.to_dict()  # type: ignore[assignment]
            elif hasattr(profile, "__dict__"):
                profile = dict(profile.__dict__)  # type: ignore[assignment]
    except Exception:
        profile = {}

    planner = _collect_session_prefix("planner_")
    budget = _collect_session_prefix("budget_")
    insights = _collect_insights_from_report(report)

    # UI
    st.divider()
    st.subheader("Download Workbook")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📘 Download Workbook (.md)", key="download_workbook_md_btn"):
            try:
                pr = cast(dict[str, Any], profile or {})
                bundle = build_workbook_bundle(pr, planner, budget, insights)
                md_text = bundle.get("markdown") or ""
                if md_text and download_text:
                    download_text(md_text, "workbook.md", mime="text/markdown")  # type: ignore[misc]
                else:
                    st.code(
                        md_text or "# GrantScope Workbook\n\n_No content available._",
                        language="markdown",
                    )
            except Exception as e:
                st.warning(f"Could not generate workbook markdown: {e}")
    with c2:
        if st.button("🧪 Download HTML (optional)", key="download_workbook_html_btn"):
            try:
                pr = cast(dict[str, Any], profile or {})
                bundle = build_workbook_bundle(pr, planner, budget, insights)
                html_text = bundle.get("html")
                if html_text and download_text:
                    download_text(html_text, "workbook.html", mime="text/html")  # type: ignore[misc]
                elif html_text:
                    st.code(
                        html_text[:5000] + ("\n... (truncated)" if len(html_text) > 5000 else ""),
                        language="html",
                    )
                else:
                    st.info(
                        "HTML export is not available in this environment. Markdown is provided above."
                    )
            except Exception as e:
                st.warning(f"Could not generate workbook HTML: {e}")


def _ensure_session_keys() -> None:
    st.session_state.setdefault("advisor_form", {})
    st.session_state.setdefault("advisor_demo_autorun", False)
    st.session_state.setdefault("advisor_last_bundle", None)
    st.session_state.setdefault("advisor_store", {})
    st.session_state.setdefault("advisor_progress", {})


def _comma_split(text: str) -> list[str]:
    parts = [p.strip() for p in str(text or "").split(",")]
    return [p for p in parts if p]


def _range_parse(text: str) -> tuple[float | None, float | None]:
    txt = str(text or "").strip()
    if not txt:
        return None, None
    try:
        if "," in txt:
            lo, hi = txt.split(",", 1)
            lo_v = float(lo.strip()) if lo.strip() else None
            hi_v = float(hi.strip()) if hi.strip() else None
            return lo_v, hi_v
        # Single value -> min only
        return float(txt), None
    except Exception:
        return None, None


def _prefill_from_demo() -> dict[str, Any]:
    # Prefer JSON file override if present
    data = load_demo_responses_json() or get_demo_responses_dict()
    return data


def _make_interview_from_inputs(
    program_area: str,
    populations_txt: str,
    geography_txt: str,
    timeframe_years: int | None,
    budget_range_txt: str,
    outcomes_txt: str,
    constraints_txt: str,
    funder_types_txt: str,
    keywords_txt: str,
    notes: str,
    user_role: str,
) -> InterviewInput:
    lo, hi = _range_parse(budget_range_txt)
    return InterviewInput(
        program_area=str(program_area or ""),
        populations=_comma_split(populations_txt),
        geography=_comma_split(geography_txt),
        timeframe_years=int(timeframe_years) if timeframe_years is not None else None,
        budget_usd_range=(lo, hi) if (lo is not None or hi is not None) else None,
        outcomes=_comma_split(outcomes_txt),
        constraints=_comma_split(constraints_txt),
        preferred_funder_types=_comma_split(funder_types_txt),
        keywords=_comma_split(keywords_txt),
        notes=str(notes or ""),
        user_role=str(user_role or "Grant Analyst/Writer"),
    )


def _analysis_start_toast() -> None:
    """Show a transient toast indicating expected runtime."""
    try:
        st.toast(
            "Starting analysis — this may take up to ~5 minutes on first run. "
            "Subsequent runs will be faster due to caching. ☕",
            icon="⏳",
        )
    except Exception:
        # Fallback for Streamlit versions without toast
        st.warning(
            "Starting analysis — this may take up to ~5 minutes on first run. "
            "Subsequent runs will be faster due to caching."
        )


def _get_report_id(interview_data: dict[str, Any], df: pd.DataFrame) -> str:
    """Generate a unique report ID for progress tracking."""
    try:
        from advisor.pipeline.cache import cache_key_for  # type: ignore

        try:
            from advisor.schemas import stable_hash_for_obj  # type: ignore
        except Exception:  # pragma: no cover
            from GrantScope.advisor.schemas import stable_hash_for_obj  # type: ignore

        key = cache_key_for(interview_data, df)
        return f"RPT-{stable_hash_for_obj({'k': key})[:8].upper()}"
    except Exception:
        # Fallback to timestamp if imports fail
        import time

        return f"RPT-{int(time.time())}"


def _run_pipeline_with_progress(
    interview: InterviewInput, df: pd.DataFrame, report_id: str, progress_placeholder
) -> Any | None:
    """Run the pipeline with real-time progress updates."""
    try:
        # Initialize progress state
        progress_key = f"advisor_progress_{report_id}"
        st.session_state[progress_key] = {"current_stage": -1, "status": "pending"}

        # Show initial progress
        with progress_placeholder:
            render_live_progress_tracker(report_id, show_estimates=True)

        # Run pipeline with progress callback
        report = run_interview_pipeline(interview, df)

        # Mark final stage as complete
        if progress_key in st.session_state:
            st.session_state[progress_key].update(
                {"current_stage": len(STAGES) - 1, "status": "completed"}
            )

        return report

    except Exception as e:
        # Mark as error
        progress_key = f"advisor_progress_{report_id}"
        if progress_key in st.session_state:
            st.session_state[progress_key]["status"] = "error"
        raise e


def render_interview_page() -> None:
    init_session_state()
    _ensure_session_keys()

    uploaded_file, selected_role, ai_enabled = sidebar_controls()
    df, grouped_df, err = get_data(uploaded_file)

    st.title("Grant Advisor Interview")

    # Guided help panel (Newbie Mode gated)
    try:
        profile = get_session_profile()
        if is_newbie(profile) and is_enabled("GS_ENABLE_NEWBIE_MODE"):
            render_page_help_panel("advisor_report", audience="new")
    except Exception:
        pass

    # Newbie-friendly overlay
    try:
        profile = get_session_profile()
        if is_newbie(profile):
            with st.expander("👋 What you'll get from this interview", expanded=True):
                st.markdown(
                    """
                - A simple project summary in plain English
                - A short list of potential funders to research
                - Clear next steps to get grant-ready
                """
                )
            st.success(
                """
            Quick checklist before you start:
            1) Know your rough budget and timeline
            2) List who benefits and how
            3) Have a short description of your project
            """
            )
    except Exception:
        pass

    # Runtime notice for users about potential analysis duration
    st.info(
        "Heads up: The Advisor analysis may take up to ~5 minutes on first run. "
        "Subsequent runs are faster due to caching."
    )

    # Data source notice
    if err:
        st.error(f"Data load error: {err}")
        return
    else:
        if uploaded_file is None:
            st.info(
                "No file uploaded. Using bundled sample dataset (GrantScope/data/sample.json) for analysis."
            )
        else:
            st.success("Using your uploaded dataset for analysis.")

    # Demo controls
    demo_col, prefill_col = st.columns([1, 1])
    with demo_col:
        if st.button("Load Demo (Prefill + Auto-run)", key="load_demo_autorun_btn"):
            st.session_state["advisor_form"] = _prefill_from_demo()
            st.session_state["advisor_demo_autorun"] = True
            st.rerun()
    with prefill_col:
        if st.button("Prefill Demo Only", key="prefill_demo_only_btn"):
            st.session_state["advisor_form"] = _prefill_from_demo()
            st.session_state["advisor_demo_autorun"] = False
            st.rerun()

    # Guard: AI disabled (no API key)
    if not ai_enabled:
        st.warning(
            "AI features are disabled. Provide an API key via Streamlit secrets, environment, "
            "or one-time input in the sidebar to enable the Advisor pipeline."
        )

    # Build the interview form
    st.subheader("Interview")
    with st.form(key="advisor_interview_form", clear_on_submit=False):
        fvals: dict[str, Any] = dict(st.session_state.get("advisor_form") or {})

        # For newcomers: explain each field inline
        try:
            profile = get_session_profile()
            newbie = is_newbie(profile)
        except Exception:
            newbie = True

        program_area = st.text_input(
            "Program Area",
            value=fvals.get("program_area", ""),
            help=(
                "What is your project about? (e.g., after-school program, food pantry)"
                if newbie
                else None
            ),
        )
        populations_txt = st.text_input(
            "Populations (comma-separated)",
            value=", ".join(fvals.get("populations", [])),
            help=(
                "Who will benefit? (e.g., middle school students, seniors, veterans)"
                if newbie
                else None
            ),
        )
        geography_txt = st.text_input(
            "Geography (comma-separated region/state/country)",
            value=", ".join(fvals.get("geography", [])),
            help=("Where does the project take place? (e.g., California, NYC)" if newbie else None),
        )
        timeframe_years = st.number_input(
            "Timeframe (years, optional)",
            min_value=0,
            max_value=10,
            value=int(fvals.get("timeframe_years") or 0),
        )
        budget_range_txt = st.text_input(
            "Budget USD Range (min,max optional)",
            value=", ".join(map(str, fvals.get("budget_usd_range", []))) or "",
            help=(
                "Example: 10000, 50000 (if unsure, start with a small range)" if newbie else None
            ),
        )
        outcomes_txt = st.text_input(
            "Outcomes (comma-separated)",
            value=", ".join(fvals.get("outcomes", [])),
            help=("What changes will happen because of this project?" if newbie else None),
        )
        constraints_txt = st.text_input(
            "Constraints (comma-separated)",
            value=", ".join(fvals.get("constraints", [])),
            help=("What might be hard? (e.g., staffing, timeline)" if newbie else None),
        )
        funder_types_txt = st.text_input(
            "Preferred Funder Types (comma-separated)",
            value=", ".join(fvals.get("preferred_funder_types", [])),
            help=("Examples: foundations, corporations, government" if newbie else None),
        )
        keywords_txt = st.text_input(
            "Keywords (comma-separated)",
            value=", ".join(fvals.get("keywords", [])),
            help=("Important words for your project (e.g., STEM, literacy)" if newbie else None),
        )
        notes = st.text_area(
            "Notes",
            value=fvals.get("notes", ""),
            help=("Any extra context you'd like to add" if newbie else None),
        )
        # Bind to global selected role for consistency
        user_role = selected_role

        run_now = st.form_submit_button("Start Analysis", disabled=not ai_enabled)

    # Auto-run when demo requested
    if st.session_state.get("advisor_demo_autorun") and ai_enabled:
        form_vals = st.session_state.get("advisor_form") or _prefill_from_demo()
        interview = InterviewInput(**form_vals)
        st.session_state["advisor_demo_autorun"] = False  # one-shot
        df_nonnull = cast(pd.DataFrame, df) if df is not None else None
        if df_nonnull is None:
            st.error("Data not available for analysis.")
        else:
            _analysis_start_toast()

            # Generate report ID for progress tracking
            report_id = _get_report_id(form_vals, df_nonnull)

            # Create placeholder for progress tracker
            progress_placeholder = st.empty()

            # Run the pipeline
            try:
                report = run_interview_pipeline(interview, df_nonnull)
                st.session_state["advisor_last_bundle"] = report

                # Clear progress tracker and show completion
                progress_placeholder.empty()
                st.success("✅ Demo analysis complete!")

            except Exception as e:
                progress_placeholder.empty()
                st.error(f"Pipeline error: {e}")
                return

        render_report_streamlit(st.session_state["advisor_last_bundle"])
        st.stop()

    # Mini action plan for newbies (client-side, quick guidance)
    try:
        profile = get_session_profile()
        if is_newbie(profile):
            st.subheader("🗺️ Mini Action Plan")
            bullets = []
            if program_area:
                bullets.append(f"Write a 1-paragraph summary of your project in {program_area}.")
            if geography_txt:
                bullets.append(f"List 3–5 local funders that support work in {geography_txt}.")
            if budget_range_txt:
                bullets.append(
                    "Pick a realistic budget range and find funders with similar awards."
                )
            bullets.append("Collect basic documents: org overview, simple budget, timeline.")
            for b in bullets[:5]:
                st.markdown(f"- {b}")
    except Exception:
        pass

    # Normal run path
    # Background execution and live progress rendering
    if run_now and ai_enabled:
        interview = _make_interview_from_inputs(
            program_area=cast(str, program_area),
            populations_txt=populations_txt,
            geography_txt=geography_txt,
            timeframe_years=timeframe_years if timeframe_years != 0 else None,
            budget_range_txt=budget_range_txt,
            outcomes_txt=outcomes_txt,
            constraints_txt=constraints_txt,
            funder_types_txt=funder_types_txt,
            keywords_txt=keywords_txt,
            notes=cast(str, notes),
            user_role=cast(str, user_role),
        )
        # Save raw form for persistence
        st.session_state["advisor_form"] = {
            "program_area": program_area,
            "populations": _comma_split(populations_txt),
            "geography": _comma_split(geography_txt),
            "timeframe_years": int(timeframe_years) if timeframe_years != 0 else None,
            "budget_usd_range": list(_range_parse(budget_range_txt)),
            "outcomes": _comma_split(outcomes_txt),
            "constraints": _comma_split(constraints_txt),
            "preferred_funder_types": _comma_split(funder_types_txt),
            "keywords": _comma_split(keywords_txt),
            "notes": notes,
            "user_role": user_role,
        }

        df_nonnull2 = cast(pd.DataFrame, df) if df is not None else None

        if df_nonnull2 is None:
            st.error("Data not available for analysis.")
        else:
            import threading
            import time

            # Generate report ID for progress tracking
            report_id = _get_report_id(st.session_state.get("advisor_form", {}), df_nonnull2)
            st.session_state["advisor_current_report_id"] = report_id

            _analysis_start_toast()

            # Background thread to run pipeline (no Streamlit calls inside)
            def _run_pipeline_bg():
                try:
                    # Invoke pipeline; progress updates occur via internal callbacks/store
                    rpt = run_interview_pipeline(interview, df_nonnull2)
                    # Persist result into the store for retrieval on UI thread
                    from advisor.pipeline.progress import _LOCK, _REPORT_STORE  # type: ignore

                    with _LOCK:
                        _REPORT_STORE[report_id] = rpt
                except Exception as e:
                    from advisor.pipeline.progress import _LOCK, _PROGRESS_STATE  # type: ignore

                    with _LOCK:
                        st_err = str(e)
                        state = _PROGRESS_STATE.setdefault(report_id, {})
                        state.update({"status": "error", "message": st_err})

            if not st.session_state.get("advisor_run_in_progress"):
                st.session_state["advisor_run_in_progress"] = True
                t = threading.Thread(target=_run_pipeline_bg, daemon=True)
                t.start()

            # Create placeholder for progress tracker
            report = None
            progress_placeholder = st.empty()

            # Show live progress tracker and auto-refresh until completion
            with progress_placeholder:
                render_live_progress_tracker(report_id, show_estimates=True)

            state = get_progress_state(report_id)
            if st.session_state.get("advisor_run_in_progress") and state.get("status") not in {
                "completed",
                "error",
            }:
                last = st.session_state.get("advisor_last_refresh_ts", 0.0)
                now = time.time()
                # Throttle reruns to ~1.5s
                if now - float(last) > 1.5:
                    st.session_state["advisor_last_refresh_ts"] = now
                    # Trigger a rerun to update progress display
                    st.rerun()
            else:
                # Clear progress placeholder and show completion or error
                progress_placeholder.empty()
                # mark not in progress
                st.session_state["advisor_run_in_progress"] = False
                if state.get("status") == "error":
                    err_msg = state.get("message") or "Pipeline error"
                    st.error(f"Pipeline error: {err_msg}")
                    report = None
                else:
                    st.success("✅ Analysis complete!")
                    # Retrieve report from store if available, fallback to session
                    report = get_report(report_id) or st.session_state.get("advisor_last_bundle")
            render_report_streamlit(report)
            try:
                _render_workbook_download(report)
            except Exception:
                pass
            st.success("Analysis complete. See tabs above for details and downloads.")

    # Restore from JSON
    st.subheader("Restore Report From JSON")
    up = st.file_uploader(
        "Upload an exported Advisor JSON", type=["json"], key="advisor_restore_upload"
    )
    if up is not None and st.button("Import Report JSON", key="import_report_json_btn"):
        try:
            restored = import_bundle_from_upload(up)
            st.session_state["advisor_last_bundle"] = restored
            st.success("Report imported. Rendering below…")
            render_report_streamlit(restored)
            try:
                _render_workbook_download(restored)
            except Exception:
                pass
        except Exception as e:
            st.error(f"Failed to import JSON: {e}")

    # Show last bundle if available (helps persistence when navigating back)
    if (
        st.session_state.get("advisor_last_bundle")
        and not run_now
        and not st.session_state.get("advisor_demo_autorun")
    ):
        st.markdown("### Last Report")
        render_report_streamlit(st.session_state["advisor_last_bundle"])
        try:
            _render_workbook_download(st.session_state["advisor_last_bundle"])
        except Exception:
            pass


# Entrypoint for Streamlit page
if __name__ == "__main__":
    render_interview_page()
