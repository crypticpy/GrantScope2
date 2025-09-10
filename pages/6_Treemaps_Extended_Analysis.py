import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import is_enabled  # type: ignore
from plots.treemaps_extended_analysis import treemaps_extended_analysis  # type: ignore
from utils.app_state import (  # type: ignore
    get_data,
    get_session_profile,
    init_session_state,
    is_newbie,
    sidebar_controls,
)
from utils.help import render_page_help_panel  # type: ignore

st.set_page_config(page_title="GrantScope — Treemaps", page_icon=":evergreen_tree:")

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
    render_page_help_panel("treemaps_extended", audience="new")

if err:
    st.error(f"Data load error: {err}")
else:
    treemaps_extended_analysis(
        df, grouped_df, "Treemaps with Extended Analysis", selected_role, ai_enabled
    )
