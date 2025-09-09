import os, sys
import streamlit as st
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.app_state import init_session_state, sidebar_controls, get_data, get_session_profile, is_newbie  # type: ignore
from plots.data_summary import data_summary  # type: ignore
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


st.set_page_config(page_title="GrantScope — Data Summary", page_icon=":bar_chart:")

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
    render_page_help_panel("data_summary", audience="new")

if err:
    st.error(f"Data load error: {err}")
else:
    data_summary(df, grouped_df, "Data Summary", selected_role, ai_enabled)

# Guided navigation UI (Newbie Mode only)
try:
    profile = get_session_profile()
except Exception:
    profile = None

if is_enabled("GS_ENABLE_NEWBIE_MODE") and is_newbie(profile):
    # Identify current page
    current_slug = "data_summary"
    current_file = "pages/1_Data_Summary.py"
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
            # Build first, prev, current representation
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
