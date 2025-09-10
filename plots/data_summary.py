"""Data Summary module for GrantScope - provides overview charts and statistics."""

import contextlib

import pandas as pd
import plotly.express as px
import streamlit as st

from config import is_enabled
from utils.ai_explainer import render_ai_explainer
from utils.chat_panel import chat_panel

# Constants
CHART_TITLE_TOP_FUNDERS = "Top {top_n} Funders by Total Grant Amount"
CHART_TITLE_FUNDER_TYPE = "Grant Distribution by Funder Type"
CHART_TITLE_SUBJECT_AREAS = "Top 10 Grant Subject Areas by Total Amount"
CHART_TITLE_POPULATIONS = "Top 10 Populations Served by Total Grant Amount"

# AI Chart IDs
AI_CHART_TOP_FUNDERS = "data_summary.top_funders"
AI_CHART_FUNDER_TYPE = "data_summary.funder_type"
AI_CHART_SUBJECT_AREAS = "data_summary.subject_areas"
AI_CHART_POPULATIONS = "data_summary.population_served"
AI_CHART_GENERAL = "data_summary.general"

# Session state keys
SESSION_TOP_N = "ds_top_n"

# Chat targets
CHAT_TARGET_TOP_FUNDERS = "Top Funders"
CHAT_TARGET_FUNDER_TYPE = "Funder Type Distribution"
CHAT_TARGET_SUBJECT_AREAS = "Top Subject Areas"
CHAT_TARGET_POPULATIONS = "Top Populations"
CHAT_TARGET_GENERAL = "General Dataset"


def data_summary(
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
    ai_enabled: bool,
) -> None:
    """Render the Data Summary page and optional AI chat when selected.

    Args:
        df: Grant dataset DataFrame
        grouped_df: Pre-grouped DataFrame for AI functionality
        selected_chart: Currently selected navigation chart
        selected_role: User role (Grant Analyst/Writer or Grant Writer Assistant)
        ai_enabled: Whether AI features are enabled
    """
    if selected_chart != "Data Summary":
        return

    st.header("Introduction")

    # Audience detection for helpers
    audience = "pro" if selected_role == "Grant Analyst/Writer" else "new"
    if is_enabled("GS_ENABLE_PLAIN_HELPERS") and audience == "new":
        st.info(
            """
        What this page shows:
        - The big picture of your grant data
        - Who gives money, who receives it, and which topics get funded
        - Simple charts to spot patterns fast

        What to do next:
        - Note the top funders and subjects
        - Compare these to your project focus and location
        - Click the checkboxes to see the numbers behind each chart
        """
        )

    st.markdown(
        """
        Welcome to the GrantScope Tool! This powerful prototype application was built by [Christopher Collins](https://www.linkedin.com/in/cctopher/) to assist grant writers and analysts in navigating and extracting insights from a complex grant dataset. By leveraging the capabilities AI integrated with this tool, you can identify potential funding opportunities, analyze trends, and gain valuable information.

        The application has select pages which have been enhanced with experimental features from Llama-Index's QueryPipeline for Pandas Dataframes, and OpenAI GPT-5 to provide you with additional insights and analysis. You can interact with the AI assistant to ask questions, generate summaries, and explore the data in a more intuitive manner.

        The preloaded dataset encompasses a small sample of grant data, including details about funders, recipients, grant amounts, subject areas, populations served, and more. With this tool, you can explore the data through interactive visualizations, filter and search for specific grants, and download relevant data for further analysis.
        """
    )

    _render_dataset_overview(df, selected_role)
    _render_key_metrics(df)

    top_funders = _render_top_funders(df, grouped_df, selected_chart, selected_role, top_n=10)

    # Defer AI chat rendering; consolidated into a single chat panel with context selector below.

    _render_smart_recommendations(df)
    top_categories = _render_funder_type_distribution(df, grouped_df, selected_chart, selected_role)

    subject_dist = _render_subject_areas(df, grouped_df, selected_chart, selected_role)
    population_dist = _render_population_served(df, grouped_df, selected_chart, selected_role)

    if ai_enabled:
        # Sidebar chat selector to keep the center content clean
        st.sidebar.subheader("Chat")
        chat_target = st.sidebar.selectbox(
            "Chat about",
            options=[
                CHAT_TARGET_TOP_FUNDERS,
                CHAT_TARGET_FUNDER_TYPE,
                CHAT_TARGET_SUBJECT_AREAS,
                CHAT_TARGET_POPULATIONS,
                CHAT_TARGET_GENERAL,
            ],
            index=0,
            key="ds_chat_target",
        )
        _render_selected_chat(
            chat_target,
            df,
            grouped_df,
            selected_chart,
            selected_role,
            top_funders,
            top_categories,
            subject_dist,
            population_dist,
        )
    else:
        st.info("AI-assisted analysis is disabled. Provide an API key to enable this feature.")

    st.divider()

    st.markdown(
        """
        This page serves as a glimpse into insights you can uncover using GrantScope. Feel free to explore the other plots of the application by using the menu on the left. From there you can dive deeper into specific aspects of the grant data, such as analyzing trends over time or examining population distributions.

        Happy exploring and best of luck with your grant related endeavors!

        This app was produced by [Christopher Collins](https://www.linkedin.com/in/cctopher/) using the latest methods to enable AI conversation with Data. It also uses the Candid API, Streamlit, Plotly, and other open-source libraries. Generative AI solutions such as OpenAI GPT-5 and Claude Opus were used to generate portions of the source code.
        """
    )


def _render_selected_chat(
    chat_target: str,
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
    top_funders: pd.DataFrame,
    top_categories: pd.DataFrame,
    subject_dist: pd.DataFrame,
    population_dist: pd.DataFrame,
) -> None:
    """Render the selected chat interface based on user choice."""
    from utils.utils import generate_page_prompt

    if chat_target == CHAT_TARGET_TOP_FUNDERS:
        top_n = st.session_state.get(SESSION_TOP_N, 10)
        additional_context = f"the top {top_n} funders by total grant amount"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters={"top_n": int(top_n)},
            sample_df=top_funders,
        )
        chat_panel(
            top_funders,
            pre_prompt,
            state_key="data_summary_top_funders",
            title="Top Funders — AI Assistant",
        )

    elif chat_target == CHAT_TARGET_FUNDER_TYPE:
        additional_context = "the distribution of total grant amounts by funder type (with smaller categories possibly grouped into 'Other')"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters=None,
            sample_df=top_categories,
        )
        chat_panel(
            top_categories,
            pre_prompt,
            state_key="data_summary_funder_type",
            title="Funder Type — AI Assistant",
        )

    elif chat_target == CHAT_TARGET_SUBJECT_AREAS:
        additional_context = "the top 10 grant subject areas by total amount"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters=None,
            sample_df=subject_dist,
        )
        chat_panel(
            subject_dist,
            pre_prompt,
            state_key="data_summary_subject",
            title="Subject Areas — AI Assistant",
        )

    elif chat_target == CHAT_TARGET_POPULATIONS:
        additional_context = "the top 10 populations served by total grant amount"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters=None,
            sample_df=population_dist,
        )
        chat_panel(
            population_dist,
            pre_prompt,
            state_key="data_summary_population",
            title="Populations — AI Assistant",
        )

    else:
        additional_context = "the overall grant dataset, including funders, recipients, grant amounts, subject areas, and populations served"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters=None,
            sample_df=df,
        )
        chat_panel(
            df,
            pre_prompt,
            state_key="data_summary_general",
            title="General Dataset — AI Assistant",
        )


def _render_dataset_overview(df: pd.DataFrame, selected_role: str) -> None:
    """Render dataset overview section for Analyst role."""
    if selected_role == "Grant Analyst/Writer":
        st.subheader("Dataset Overview")
        st.write(df.head())


def _render_key_metrics(df: pd.DataFrame) -> None:
    """Render key metrics cards."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total Unique Grants", value=df["grant_key"].nunique())
    with col2:
        st.metric(label="Total Unique Funders", value=df["funder_name"].nunique())
    with col3:
        st.metric(label="Total Unique Recipients", value=df["recip_name"].nunique())


def _render_top_funders(
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
    top_n: int = 10,
) -> pd.DataFrame:
    """Render top funders chart and return the funders DataFrame."""
    st.subheader("Top Funders by Total Grant Amount")
    top_n_slider = st.slider(
        "Select the number of top funders to display",
        min_value=5,
        max_value=20,
        value=top_n,
        step=1,
    )
    # Persist Top Funders slider for AI chart-state tool
    with contextlib.suppress(Exception):
        st.session_state[SESSION_TOP_N] = int(top_n_slider)

    unique_df = df.drop_duplicates(subset="grant_key")
    top_funders = (
        unique_df.groupby("funder_name")["amount_usd"].sum().nlargest(top_n_slider).reset_index()
    )

    fig = px.bar(
        top_funders,
        x="funder_name",
        y="amount_usd",
        title=CHART_TITLE_TOP_FUNDERS.format(top_n=top_n_slider),
    )
    fig.update_layout(xaxis_title="Funder Name", yaxis_title="Total Grant Amount (USD)")
    st.plotly_chart(fig, use_container_width=True)

    # AI Explainer for Top Funders chart
    with contextlib.suppress(Exception):
        from utils.utils import generate_page_prompt

        additional_context = f"the top {top_n_slider} funders by total grant amount"
        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            additional_context,
            current_filters={"top_n": int(top_n_slider)},
            sample_df=top_funders,
        )
        render_ai_explainer(
            top_funders, pre_prompt, chart_id=AI_CHART_TOP_FUNDERS, sample_df=top_funders
        )

    audience = "pro" if selected_role == "Grant Analyst/Writer" else "new"
    if is_enabled("GS_ENABLE_PLAIN_HELPERS") and audience == "new":
        st.success(
            """
        Why this matters:
        - These are the funders that give the most in your data
        - If your project matches their focus, they may be good targets

        Next steps:
        - Click "Show Top Funders Data Table" to see their names
        - Write down 3–5 funders to research
        """
        )

    if st.checkbox("Show Top Funders Data Table"):
        st.write(top_funders)

    return top_funders


def _render_smart_recommendations(df: pd.DataFrame) -> None:
    """Render smart recommendations panel."""
    with contextlib.suppress(Exception):
        from utils.recommendations import GrantRecommender

        unique_df = df.drop_duplicates(subset="grant_key")
        GrantRecommender.render_panel(unique_df)


def _render_funder_type_distribution(
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
) -> pd.DataFrame:
    """Render funder type distribution chart and return the categories DataFrame."""
    st.subheader("Grant Distribution by Funder Type")
    unique_df = df.drop_duplicates(subset="grant_key")
    funder_type_dist = unique_df.groupby("funder_type")["amount_usd"].sum().reset_index()
    funder_type_dist_sorted = None

    # Check if there are more than 10 funder types
    if len(funder_type_dist) > 10:
        # Sort the dataframe by 'amount_usd' to ensure we're aggregating the smallest categories
        funder_type_dist_sorted = funder_type_dist.sort_values(by="amount_usd", ascending=False)
        # Create a new dataframe for top 11 categories
        top_categories = funder_type_dist_sorted.head(11).copy()
        # Calculate the sum of 'amount_usd' for the "Other" category
        other_sum = funder_type_dist_sorted.iloc[11:]["amount_usd"].sum()
        # Append the "Other" category to the top categories dataframe
        other_row = pd.DataFrame(data={"funder_type": ["Other"], "amount_usd": [other_sum]})
        top_categories = pd.concat([top_categories, other_row], ignore_index=True)
    else:
        top_categories = funder_type_dist

    # Generate the pie chart with the possibly modified dataframe
    fig = px.pie(
        top_categories,
        values="amount_usd",
        names="funder_type",
        title=CHART_TITLE_FUNDER_TYPE,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Display the table for the "Other" category if it exists
    if len(funder_type_dist) > 12 and funder_type_dist_sorted is not None:
        st.subheader("Details of 'Other' Funder Types")
        # Get the rows that were aggregated into "Other"
        other_details = funder_type_dist_sorted.iloc[11:].reset_index(drop=True)
        st.dataframe(other_details.style.format({"amount_usd": "{:,.2f}"}))

    # AI Explainer for Funder Type Distribution
    with contextlib.suppress(Exception):
        from utils.utils import generate_page_prompt

        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            "grant distribution by funder type (pie chart)",
            current_filters=None,
            sample_df=top_categories,
        )
        render_ai_explainer(
            top_categories,
            pre_prompt,
            chart_id=AI_CHART_FUNDER_TYPE,
            sample_df=top_categories,
        )

    if st.checkbox("Show Funder Type Data Table"):
        st.write(funder_type_dist)

    return top_categories


def _render_subject_areas(
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
) -> pd.DataFrame:
    """Render subject areas chart and return the subject distribution DataFrame."""
    st.subheader("Grant Distribution by Subject Area")
    unique_df = df.drop_duplicates(subset="grant_key")
    subject_dist = (
        unique_df.groupby("grant_subject_tran")["amount_usd"].sum().nlargest(10).reset_index()
    )

    fig = px.bar(
        subject_dist,
        x="grant_subject_tran",
        y="amount_usd",
        title=CHART_TITLE_SUBJECT_AREAS,
    )
    fig.update_layout(xaxis_title="Subject Area", yaxis_title="Total Grant Amount (USD)")
    st.plotly_chart(fig, use_container_width=True)

    # AI Explainer for Subject Areas
    with contextlib.suppress(Exception):
        from utils.utils import generate_page_prompt

        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            "top 10 grant subject areas by total amount",
            current_filters=None,
            sample_df=subject_dist,
        )
        render_ai_explainer(
            subject_dist, pre_prompt, chart_id=AI_CHART_SUBJECT_AREAS, sample_df=subject_dist
        )

    return subject_dist


def _render_population_served(
    df: pd.DataFrame,
    grouped_df: pd.DataFrame,
    selected_chart: str,
    selected_role: str,
) -> pd.DataFrame:
    """Render population served chart and return the population distribution DataFrame."""
    st.subheader("Grant Distribution by Population Served")
    unique_df = df.drop_duplicates(subset="grant_key")
    population_dist = (
        unique_df.groupby("grant_population_tran")["amount_usd"].sum().nlargest(10).reset_index()
    )

    fig = px.bar(
        population_dist,
        x="grant_population_tran",
        y="amount_usd",
        title=CHART_TITLE_POPULATIONS,
    )
    fig.update_layout(xaxis_title="Population Served", yaxis_title="Total Grant Amount (USD)")
    st.plotly_chart(fig, use_container_width=True)

    # AI Explainer for Population Served
    with contextlib.suppress(Exception):
        from utils.utils import generate_page_prompt

        pre_prompt = generate_page_prompt(
            df,
            grouped_df,
            selected_chart,
            selected_role,
            "top 10 populations served by total grant amount",
            current_filters=None,
            sample_df=population_dist,
        )
        render_ai_explainer(
            population_dist,
            pre_prompt,
            chart_id=AI_CHART_POPULATIONS,
            sample_df=population_dist,
        )
    return population_dist
