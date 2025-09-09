import os, sys
import streamlit as st
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.app_state import init_session_state, sidebar_controls, get_data, get_session_profile, is_newbie  # type: ignore
from plots.grant_amount_distribution import grant_amount_distribution  # type: ignore
from config import is_enabled  # type: ignore
from utils.help import render_page_help_panel  # type: ignore
from utils.navigation import (  # type: ignore
    push_breadcrumb,
    get_recommended_next_page,
    get_page_label,
    get_breadcrumbs,
    compute_continue_state,
    continue_to,
)


st.set_page_config(page_title="GrantScope — Distribution", page_icon=":chart_with_upwards_trend:")

init_session_state()
uploaded_file, selected_role, ai_enabled = sidebar_controls()
df, grouped_df, err = get_data(uploaded_file)

st.title("GrantScope Dashboard")

# Render guided help panel only when Newbie Mode is active
try:
    profile = get_session_profile()
except Exception:
    profile = None

if is_enabled("GS_ENABLE_NEWBIE_MODE") and is_newbie(profile):
    render_page_help_panel("grant_amount_distribution", audience="new")

if err:
    st.error(f"Data load error: {err}")
else:
    grant_amount_distribution(df, grouped_df, "Grant Amount Distribution", selected_role, ai_enabled)

# Guided navigation UI (Newbie Mode only)
try:
    profile = get_session_profile()
except Exception:
    profile = None

if is_enabled("GS_ENABLE_NEWBIE_MODE") and is_newbie(profile):
    # Identify current page
    current_slug = "grant_amount_distribution"
    current_file = "pages/2_Grant_Amount_Distribution.py"
    current_label = get_page_label(current_slug)

    # Update breadcrumbs and compute next step
    push_breadcrumb(current_label, current_file)
    next_file = get_recommended_next_page(current_slug)
    next_label = get_page_label(next_file)

    # Determine Continue state based on data availability
    data_loaded = (err is None) and (df is not None)
    enabled, tooltip = compute_continue_state(data_loaded, next_label)

    # Render breadcrumbs (first › prev › current)
    try:
        bc = get_breadcrumbs()
        if bc:
            labels = [item.get("label", "") for item in bc if isinstance(item, dict)]
            parts = []
            if len(labels) >= 1:
                parts.append(labels[0])
            if len(labels) >= 2:
                parts.append(labels[-2])
            if len(labels) >= 1:
                parts.append(f"**{labels[-1]}**")
            breadcrumb_view = " › ".join(parts)
            st.caption(breadcrumb_view)
    except Exception:
        pass

    # Continue button
    if st.button("Continue →", help=tooltip, disabled=not enabled, type="primary"):
        continue_to(next_file)
