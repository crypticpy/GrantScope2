from textwrap import shorten

import plotly.express as px
import streamlit as st

from utils.utils import download_excel, download_multi_sheet_excel, generate_page_prompt
from utils.chat_panel import chat_panel
from utils.app_state import set_selected_chart
from config import is_enabled
from utils.ai_explainer import render_ai_explainer


def top_categories_unique_grants(df, grouped_df, selected_chart, selected_role, ai_enabled):
    if selected_chart == "Top Categories by Unique Grant Count":
        st.header("Top Categories by Unique Grant Count")

        audience = "pro" if selected_role == "Grant Analyst/Writer" else "new"
        if is_enabled("GS_ENABLE_PLAIN_HELPERS") and audience == "new":
            st.info("""
            What this page shows:
            - Which categories have the most distinct grants

            Why it matters:
            - Points you to active areas with many opportunities

            What to do next:
            - Pick a category that matches your work
            - Explore the grants list to see examples
            """)

        st.write("""
        Welcome to the Top Categories by Unique Grant Count page! This interactive visualization allows you to explore the distribution of unique grant counts across different categorical variables.

        To get started, select a categorical variable from the dropdown menu. You can choose to analyze categories such as funder type, recipient organization, grant subject, population served, funding strategy, or year of issuance.

        Customize the visualization by selecting the number of top categories to display and the chart type (bar chart, pie chart, or treemap). You can also sort the categories in ascending or descending order based on the unique grant count.

        Click on a category in the chart to view more details about the grants associated with that category. You can explore the grant key, description, amount, recipient organization, and year of issuance for each grant.

        Feel free to download the data used in the chart as an Excel file for further analysis.
        """)

        key_categorical_columns = ['funder_type', 'recip_organization_tran', 'grant_subject_tran',
                                   'grant_population_tran',
                                   'grant_strategy_tran', 'year_issued']

        col1, col2 = st.columns(2)

        with col1:
            selected_categorical = st.selectbox("Select Categorical Variable", options=key_categorical_columns)
            top_n = st.slider("Number of Top Categories", min_value=5, max_value=20, value=10, step=1)

        with col2:
            chart_type = st.selectbox("Select Chart Type", options=["Bar Chart", "Pie Chart", "Treemap"])
            sort_order = st.radio("Sort Order", options=["Descending", "Ascending"])

        normalized_counts = df.groupby(selected_categorical)['grant_key'].nunique().sort_values(
            ascending=(sort_order == "Ascending")).reset_index()

        normalized_counts.columns = [selected_categorical, 'Unique Grant Keys']

        normalized_counts['truncated_col'] = normalized_counts[selected_categorical].apply(
            lambda x: shorten(x, width=30, placeholder="..."))

        if chart_type == "Bar Chart":
            fig = px.bar(normalized_counts.head(top_n), x='Unique Grant Keys', y='truncated_col', orientation='h',
                         title=f"Top {top_n} Categories in {selected_categorical}",
                         hover_data={selected_categorical: True})
            fig.update_layout(yaxis_title=selected_categorical, margin=dict(l=0, r=0, t=30, b=0))
        elif chart_type == "Pie Chart":
            fig = px.pie(normalized_counts.head(top_n), values='Unique Grant Keys', names='truncated_col',
                         title=f"Distribution of Unique Grant Keys Across Top {top_n} Categories in {selected_categorical}")
        else:  # Treemap
            fig = px.treemap(normalized_counts.head(top_n), path=['truncated_col'], values='Unique Grant Keys',
                             title=f"Treemap of Unique Grant Keys Across Top {top_n} Categories in {selected_categorical}")

        st.plotly_chart(fig)

        # AI Explainer for top categories view
        try:
            additional_context = (
                f"unique grant counts for top {int(top_n)} categories in {selected_categorical} "
                f"rendered as a {chart_type.lower()} (sorted {sort_order.lower()})"
            )
            pre_prompt = generate_page_prompt(
                df,
                grouped_df,
                selected_chart,
                selected_role,
                additional_context,
                current_filters={
                    "selected_categorical": selected_categorical,
                    "top_n": int(top_n),
                    "chart_type": chart_type,
                    "sort_order": sort_order,
                },
                sample_df=normalized_counts.head(int(top_n)),
            )
            render_ai_explainer(normalized_counts.head(int(top_n)), pre_prompt, chart_id="top_categories.main", sample_df=normalized_counts.head(int(top_n)))
        except Exception:
            pass

        # Persist state for AI chart-state tool
        try:
            st.session_state["topcat_selected_categorical"] = str(selected_categorical)
            st.session_state["topcat_top_n"] = int(top_n)
            st.session_state["topcat_chart_type"] = str(chart_type)
            st.session_state["topcat_sort_order"] = str(sort_order)
        except Exception:
            pass

        # Sidebar chat panel (single chart on this page)
        if ai_enabled:
            st.sidebar.subheader("Chat")
            _ = st.sidebar.selectbox(
                "Chat about",
                options=["Top Categories Chart"],
                index=0,
                key="topcat_chat_target",
            )
            # Single selector per page: set chart id for downstream chat context
            set_selected_chart("top_categories.main")
            additional_context = (
                f"unique grant counts for top {int(top_n)} categories in {selected_categorical} "
                f"rendered as a {chart_type.lower()} (sorted {sort_order.lower()})"
            )
            pre_prompt = generate_page_prompt(
                df,
                grouped_df,
                selected_chart,
                selected_role,
                additional_context,
                current_filters={
                    "selected_categorical": selected_categorical,
                    "top_n": int(top_n),
                    "chart_type": chart_type,
                    "sort_order": sort_order,
                },
                sample_df=normalized_counts.head(int(top_n)),
            )
            chat_panel(
                normalized_counts.head(int(top_n)),
                pre_prompt,
                state_key="top_categories_chat",
                title="Top Categories — AI Assistant",
            )

        st.write(
            f"Top {top_n} Categories account for {normalized_counts.head(top_n)['Unique Grant Keys'].sum() / normalized_counts['Unique Grant Keys'].sum():.2%} of total unique grants")

        expander = st.expander(f"Show Grants for Selected {selected_categorical} Category")
        with expander:
            selected_category = st.selectbox(f"Select {selected_categorical} Category",
                                             options=normalized_counts[selected_categorical])

            category_grants = df[df[selected_categorical] == selected_category].drop_duplicates(subset=['grant_key'])

            if not category_grants.empty:
                st.write(f"### Grant Details for {selected_category}:")
                grant_details = category_grants[
                    ['grant_key', 'grant_description', 'amount_usd', 'recip_organization_tran', 'year_issued']]
                st.dataframe(grant_details)
            else:
                st.write(f"No grants found for the selected category: {selected_category}")

        if st.button("Download Data for Chart"):
            sheets = {
                'Top Categories': normalized_counts,
                'Grants for Selected Category': category_grants if 'category_grants' in locals() else normalized_counts.head(0)
            }
            href = download_multi_sheet_excel(sheets, "grants_data_chart.xlsx")
            st.markdown(href, unsafe_allow_html=True)

        st.write("""
        We hope you find the Top Categories by Unique Grant Count page informative and helpful in exploring the distribution of grants across different categories. If you have any questions or suggestions, please don't hesitate to reach out.

        Happy exploring!
        """)
        st.markdown(""" This app was produced by [Christopher Collins](https://www.linkedin.com/in/cctopher/) using the latest methods for enabling AI to Chat with Data. It also uses the Candid API, Streamlit, Plotly, and other open-source libraries. Generative AI solutions such as OpenAI GPT-5 and Claude Opus were used to generate portions of the source code.
                        """)