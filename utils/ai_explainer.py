"""
AI Explainer utility for charts and pages.
Renders a short, audience-appropriate explainer when an API key is present.
"""

from __future__ import annotations

import streamlit as st

# Central config import tolerant to package layout
try:
    from GrantScope import config  # type: ignore
except Exception:
    import config  # type: ignore

from loaders.llama_index_setup import tool_query

# Expose a module-level alias for tests to patch: utils.ai_explainer.get_session_profile
# Actual retrieval remains deferred inside functions for runtime safety.
try:
    from utils.app_state import get_session_profile as _get_session_profile_alias  # type: ignore
except Exception:
    _get_session_profile_alias = None  # type: ignore
get_session_profile = _get_session_profile_alias  # type: ignore


def _audience_preface() -> str:
    """Return a tone/style instruction based on session profile."""
    try:
        from utils.app_state import get_session_profile  # deferred import to avoid cycles

        prof = get_session_profile()
        if prof and getattr(prof, "experience_level", "new") == "new":
            return (
                "Explain like I'm new to grants. Use short sentences and plain language. "
                "End with 2-3 clear next steps."
            )
    except Exception:
        pass
    return "Be concise and specific for an experienced user."


def render_ai_explainer(
    df,
    pre_prompt: str,
    *,
    chart_id: str | None = None,
    sample_df=None,
    extra_ctx: str | None = None,
    ai_enabled: bool | None = None,
    title: str = "🤖 AI Explainer",
) -> None:
    """
    Render a short AI-generated explainer for the current view.

    Args:
        df: Primary dataframe context
        pre_prompt: Base grounding prompt (include Known Columns context upstream when possible)
        chart_id: Optional chart identifier for display only
        sample_df: Optional smaller dataframe to ground the tool_query
        extra_ctx: Optional extra context string
        ai_enabled: Optional override; if None uses presence of API key
        title: Panel title
    """
    # Gate on AI availability
    if ai_enabled is None:
        try:
            ai_enabled = bool(config.get_openai_api_key())
        except Exception:
            ai_enabled = False
    if not ai_enabled:
        return

    # Build audience-aware preface and instruction
    preface = _audience_preface()
    instruction = (
        "Write a short, friendly explainer in 3–4 bullet points: What it shows, Why it matters, "
        "and What to do next. Avoid jargon. Limit to ~100 words."
    )
    pre_prompt_eff = f"{preface}\n\n{pre_prompt}\n\nInstruction: {instruction}".strip()

    # Choose a compact grounding dataframe if provided
    df_ground = sample_df if sample_df is not None else df

    try:
        content = tool_query(df_ground, "Explain this view.", pre_prompt_eff, extra_ctx)
    except Exception as e:
        st.info(f"AI explainer unavailable: {e}")
        return

    with st.expander(title, expanded=False):
        if chart_id:
            st.caption(f"Context: {chart_id}")
        st.markdown(content)
