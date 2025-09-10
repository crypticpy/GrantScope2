import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import is_enabled  # type: ignore
from plots.top_categories_unique_grants import top_categories_unique_grants  # type: ignore
from utils.app_state import (  # type: ignore
    get_data,
    get_session_profile,
    init_session_state,
    is_newbie,
    sidebar_controls,
)
from utils.help import render_page_help_panel  # type: ignore

st.set_page_config(page_title="GrantScope — Top Categories", page_icon=":top:")

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
    render_page_help_panel("top_categories_unique_grants", audience="new")

if err:
    st.error(f"Data load error: {err}")
else:
    top_categories_unique_grants(
        df, grouped_df, "Top Categories by Unique Grant Count", selected_role, ai_enabled
    )
