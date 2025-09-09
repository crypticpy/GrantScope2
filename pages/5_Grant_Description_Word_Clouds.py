import os, sys
import streamlit as st
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.app_state import init_session_state, sidebar_controls, get_data, get_session_profile, is_newbie  # type: ignore
from plots.grant_description_word_clouds import grant_description_word_clouds  # type: ignore
from config import is_enabled  # type: ignore
from utils.help import render_page_help_panel  # type: ignore


st.set_page_config(page_title="GrantScope — Word Clouds", page_icon=":cloud:")

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
    render_page_help_panel("grant_description_word_clouds", audience="new")

if err:
    st.error(f"Data load error: {err}")
else:
    grant_description_word_clouds(df, grouped_df, "Grant Description Word Clouds", selected_role, ai_enabled)
