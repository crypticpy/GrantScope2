import os

import streamlit as st

from utils.app_state import (
    get_session_profile,
    init_session_state,
    set_session_profile,
    sidebar_controls,
)
from utils.onboarding import OnboardingWizard

st.set_page_config(page_title="GrantScope", page_icon=":chart_with_upwards_trend:")


def _legacy_enabled() -> bool:
    """Return True if the legacy single-file router is enabled via env var."""
    return str(os.getenv("GS_ENABLE_LEGACY_ROUTER", "0")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def legacy_main() -> None:
    """Legacy single-file selectbox router (kept behind a feature flag)."""
    # Lazy imports to avoid overhead unless legacy mode is explicitly enabled
    from loaders.data_loader import load_data, preprocess_data  # local import
    from plots.data_summary import data_summary  # local import
    from plots.general_analysis_relationships import general_analysis_relationships  # local import
    from plots.grant_amount_distribution import grant_amount_distribution  # local import
    from plots.grant_amount_heatmap import grant_amount_heatmap  # local import
    from plots.grant_amount_scatter_plot import grant_amount_scatter_plot  # local import
    from plots.grant_description_word_clouds import grant_description_word_clouds  # local import
    from plots.top_categories_unique_grants import top_categories_unique_grants  # local import
    from plots.treemaps_extended_analysis import treemaps_extended_analysis  # local import
    from utils.utils import build_sample_grants_json, download_text  # local import

    # Sidebar controls (upload, API key, user role, sample download)
    st.sidebar.markdown("Click to contact me with any questions or feedback!")
    st.sidebar.markdown(
        '<a href="mailto:dltzshz8@anonaddy.me">Contact the Developer!</a>',
        unsafe_allow_html=True,
    )
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

    # Data load
    if uploaded_file is not None:
        grants = load_data(uploaded_file=uploaded_file)
    else:
        grants = load_data(file_path="data/sample.json")
    df, grouped_df = preprocess_data(grants)

    chart_options = {
        "Grant Analyst/Writer": [
            "Data Summary",
            "Grant Amount Distribution",
            "Grant Amount Scatter Plot",
            "Grant Amount Heatmap",
            "Grant Description Word Clouds",
            "Treemaps with Extended Analysis",
            "General Analysis of Relationships",
            "Top Categories by Unique Grant Count",
        ],
        "Normal Grant User": [
            "Data Summary",
            "Grant Amount Distribution",
            "Grant Amount Scatter Plot",
            "Grant Amount Heatmap",
            "Grant Description Word Clouds",
            "Treemaps with Extended Analysis",
        ],
    }

    user_roles = ["Grant Analyst/Writer", "Normal Grant User"]
    selected_role = st.sidebar.selectbox("Select User Role", options=user_roles)
    selected_chart = st.sidebar.selectbox("Select Chart", options=chart_options[selected_role])

    st.title("GrantScope Dashboard")

    if selected_chart == "Data Summary":
        data_summary(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Grant Amount Distribution":
        grant_amount_distribution(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Grant Amount Scatter Plot":
        grant_amount_scatter_plot(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Grant Amount Heatmap":
        grant_amount_heatmap(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Grant Description Word Clouds":
        grant_description_word_clouds(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Treemaps with Extended Analysis":
        treemaps_extended_analysis(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "General Analysis of Relationships":
        general_analysis_relationships(df, grouped_df, selected_chart, selected_role, True)
    elif selected_chart == "Top Categories by Unique Grant Count":
        top_categories_unique_grants(df, grouped_df, selected_chart, selected_role, True)


def main() -> None:
    """Multipage-first entrypoint. Legacy router is behind GS_ENABLE_LEGACY_ROUTER."""
    init_session_state()

    if _legacy_enabled():
        st.warning(
            "Legacy single-page router enabled via GS_ENABLE_LEGACY_ROUTER. "
            "This mode will be removed in a future release."
        )
        legacy_main()
        return

    # Show onboarding by default on first run (no feature flag required)
    profile = get_session_profile()
    if profile is None or not getattr(profile, "completed_onboarding", False):
        wizard = OnboardingWizard()
        new_profile, completed = wizard.render(profile)
        if completed and new_profile:
            set_session_profile(new_profile)
            st.success("Setup complete! Welcome to GrantScope.")
            st.balloons()
            # Give user a moment to see success message, then rerun to show main app
            if st.button("Continue to Dashboard"):
                st.rerun()
        return

    # Multipage landing: keep it light; shared state lives in utils/app_state.py and individual pages
    st.title("GrantScope Dashboard")

    # Show user info if available
    if profile and profile.completed_onboarding:
        from utils.app_state import role_label

        st.info(f"Welcome back! You're set up as: {role_label(profile.experience_level)}")
    else:
        st.info(
            "Multipage navigation is enabled. Use the page selector in the left sidebar to explore "
            "Data Summary, Distribution, Scatter, Heatmap, Word Clouds, Treemaps, Relationships, and more."
        )

    # Render shared sidebar so uploads/role are centralized and persist via st.session_state
    sidebar_controls()


if __name__ == "__main__":
    main()
