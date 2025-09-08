import os
import streamlit as st
from loaders.data_loader import load_data, preprocess_data
from utils.utils import build_sample_grants_json, download_text

# Centralized config for secrets/flags (supports package and direct execution contexts)
try:
    from GrantScope import config  # when executed via package context
except Exception:
    try:
        import config  # fallback when executed inside GrantScope/ directly
    except Exception:
        config = None  # type: ignore


def init_session_state():
    """Initialize shared session state and clear cached data once per session."""
    if "cache_initialized" not in st.session_state:
        st.session_state.cache_initialized = False
    if not st.session_state.cache_initialized:
        st.cache_data.clear()
        st.session_state.cache_initialized = True

    # Ensure global user role key exists for cross-page persistence
    if "user_role" not in st.session_state:
        st.session_state.user_role = "Grant Analyst/Writer"


def sidebar_controls():
    """Render the shared sidebar controls and return (uploaded_file, selected_role, ai_enabled)."""
    # Hide the default Streamlit multipage sidebar list to free space for the chat.
    # This keeps only our compact dropdown-based navigation.
    try:
        st.sidebar.markdown(
            "<style>div[data-testid='stSidebarNav'] { display: none; }</style>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # Navigation dropdown (sidebar) — compact and navigates without callbacks
    try:
        st.sidebar.subheader("Navigate")
        pages = {
            "Grant Advisor Interview": "0_Grant_Advisor_Interview.py",
            "Data Summary": "1_Data_Summary.py",
            "Grant Amount Distribution": "2_Grant_Amount_Distribution.py",
            "Grant Amount Heatmap": "3_Grant_Amount_Heatmap.py",
            "Grant Amount Scatter Plot": "4_Grant_Amount_Scatter_Plot.py",
            "Grant Description Word Clouds": "5_Grant_Description_Word_Clouds.py",
            "Treemaps with Extended Analysis": "6_Treemaps_Extended_Analysis.py",
            "General Analysis of Relationships": "7_General_Analysis_of_Relationships.py",
            "Top Categories by Unique Grant Count": "8_Top_Categories_Unique_Grants.py",
        }

        page_labels = list(pages.keys())
        selected_label = st.sidebar.selectbox(
            "Go to page",
            options=page_labels,
            index=page_labels.index(st.session_state.get("nav_selected_page", page_labels[0]))
            if st.session_state.get("nav_selected_page") in page_labels else 0,
            key="nav_selected_page",
        )

        # Navigate at top-level (not in a callback) to avoid st.rerun() no-op issues within callbacks
        prev = st.session_state.get("nav_prev_label")
        if selected_label != prev:
            st.session_state["nav_prev_label"] = selected_label
            try:
                if selected_label in pages:
                    st.switch_page(f"pages/{pages[selected_label]}")
            except Exception:
                # Fallback for older Streamlit: render a page link for the selected target
                try:
                    if selected_label in pages:
                        st.sidebar.page_link(f"pages/{pages[selected_label]}", label=f"Open: {selected_label}")
                except Exception:
                    pass
    except Exception:
        # Navigation dropdown is optional; ignore failures on older Streamlit versions
        pass

    uploaded_file = st.sidebar.file_uploader(
        "Upload Candid API JSON File 10MB or less",
        accept_multiple_files=False,
        type="json",
    )

    with st.sidebar.expander("Sample & Schema", expanded=False):
        st.caption(
            "Expect a JSON object with a 'grants' array. Each grant should include core "
            "funder/recipient fields, amount_usd, year_issued, codes and translations for "
            "subject/population/strategy/transaction/geo, and description."
        )
        if st.button("Download Sample JSON"):
            download_text(build_sample_grants_json(), "sample_grants.json", mime="application/json")

    # Prefer st.secrets before any UI input; then fall back to env/.env via config
    resolved_key = None
    if config is not None:
        try:
            resolved_key = config.get_openai_api_key()
        except Exception:
            resolved_key = None

    user_key = None
    if not resolved_key:
        user_key = st.sidebar.text_input("Enter your OpenAI API Key:", type="password")
        if user_key:
            # Do not persist in session or secrets; set process env for current run only
            if not os.getenv("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = user_key
            # Optionally refresh config cache so downstream getters see the newly-set env
            if config is not None:
                try:
                    config.refresh_cache()
                except Exception:
                    pass

    ai_enabled = bool(resolved_key or user_key)
    if not ai_enabled:
        st.sidebar.warning(
            "AI features are disabled. Provide an API key via Streamlit secrets, environment, "
            "or one-time input to enable AI-assisted analysis. Keys are never persisted."
        )

    user_roles = ["Grant Analyst/Writer", "Normal Grant User"]
    # Bind the selectbox to session state key for cross-page persistence
    selected_role = st.sidebar.selectbox(
        "Select User Role",
        options=user_roles,
        index=user_roles.index(st.session_state.get("user_role", user_roles[0])),
        key="user_role",
    )

    # Flexible spacer to push the chat panel to the bottom of the sidebar viewport
    try:
        st.sidebar.markdown('<div class="gs-sidebar-spacer"></div>', unsafe_allow_html=True)
    except Exception:
        pass

    return uploaded_file, selected_role, ai_enabled


@st.cache_data
def _load_and_preprocess(file_path: str | None, file_bytes):
    grants = load_data(file_path=file_path, uploaded_file=file_bytes)
    return preprocess_data(grants)


def get_data(uploaded_file):
    try:
        if uploaded_file is not None:
            df, grouped_df = _load_and_preprocess(None, uploaded_file)
        else:
            df, grouped_df = _load_and_preprocess('data/sample.json', None)
        return df, grouped_df, None
    except (OSError, ValueError, KeyError) as e:
        return None, None, str(e)


def set_selected_chart(chart_id: str) -> None:
    """Set the globally selected chart identifier for the current page/view."""
    try:
        st.session_state["selected_chart_id"] = str(chart_id)
    except Exception:
        # If session state is unavailable, fail silently
        pass


def get_selected_chart(default: str | None = None) -> str | None:
    """Get the globally selected chart identifier, or the provided default if unset."""
    try:
        val = st.session_state.get("selected_chart_id", default)
        return str(val) if val is not None else None
    except Exception:
        return default
