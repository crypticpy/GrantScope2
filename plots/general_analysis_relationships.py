import plotly.express as px
import streamlit as st

from utils.utils import download_csv, generate_page_prompt
from utils.chat_panel import chat_panel
from utils.app_state import set_selected_chart


def general_analysis_relationships(df, _grouped_df, selected_chart, _selected_role, _ai_enabled):
    if selected_chart != "General Analysis of Relationships":
        return
    st.header("General Analysis of Relationships")
    st.write("""
        Welcome to the General Analysis of Relationships page! This section of the GrantScope application is designed to help you uncover meaningful connections and trends within the grant data. By exploring the relationships between various factors and the award amount, you can gain valuable insights to inform your grant-related decisions.

        The interactive visualizations on this page allow you to examine how different aspects of grants, such as the length of the grant description, funding strategies, target populations, and geographical areas, correlate with the awarded amounts. You can also investigate the affinity of specific funders towards certain subjects, populations, or strategies.

        To get started, simply select the desired factors from the dropdown menus and the application will generate informative plots for you to analyze. Feel free to upload your own dataset to uncover insights tailored to your specific needs.
        """)

    unique_grants_df = df.drop_duplicates(subset=['grant_key'])

    st.subheader("Relationship between Grant Description Length and Award Amount")
    st.write("Explore how the number of words in a grant description correlates with the award amount.")
    unique_grants_df['description_word_count'] = unique_grants_df['grant_description'].apply(
        lambda x: len(str(x).split()))
    fig = px.scatter(unique_grants_df, x='description_word_count', y='amount_usd', opacity=0.5,
                     title="Grant Description Length vs. Award Amount")
    fig.update_layout(xaxis_title='Number of Words in Grant Description', yaxis_title='Award Amount (USD)',
                      width=800, height=600)
    st.plotly_chart(fig)

    st.subheader("Average Award Amount by Different Factors")
    st.write(
            "Investigate how award amounts are distributed across various factors. Choose your factos and explore a bar chart or box plot."
            " You can select factors such as grant strategy, grant population, grant geographical area, and funder name."
            " The box plot provides a visual representation of the distribution of award amounts within each category. "
            " This option also allows you to identify potential outliers and variations in award amounts.")

    factors = ['grant_strategy_tran', 'grant_population_tran', 'grant_geo_area_tran', 'funder_name']
    selected_factor = st.selectbox("Select Factor", options=factors)

    # Columns are already normalized in preprocessing; only split if raw data contains semicolons
    if df[selected_factor].astype(str).str.contains(';').any():
        exploded_df = df.assign(**{selected_factor: df[selected_factor].astype(str).str.split(';')}).explode(selected_factor)
    else:
        exploded_df = df.copy()
    avg_amount_by_factor = exploded_df.groupby(selected_factor)['amount_usd'].mean().reset_index()
    avg_amount_by_factor = avg_amount_by_factor.sort_values('amount_usd', ascending=False)

    chart_type = st.radio("Select Chart Type", options=["Bar Chart", "Box Plot"])

    if chart_type == "Bar Chart":
        fig = px.bar(avg_amount_by_factor, x=selected_factor, y='amount_usd',
                     title=f"Average Award Amount by {selected_factor}")
        fig.update_layout(xaxis_title=selected_factor, yaxis_title='Average Award Amount (USD)', width=800,
                          height=600,
                          xaxis_tickangle=-45, xaxis_tickfont=dict(size=10))
    else:
        fig = px.box(exploded_df, x=selected_factor, y='amount_usd',
                     title=f"Award Amount Distribution by {selected_factor}")
        fig.update_layout(xaxis_title=selected_factor, yaxis_title='Award Amount (USD)', width=800, height=600,
                          boxmode='group')

    st.plotly_chart(fig)

    st.subheader("Funder Affinity Analysis")
    st.write("Analyze the affinity of a specific funder towards certain subjects, populations, or strategies.")
    funders = unique_grants_df['funder_name'].unique().tolist()
    selected_funder = st.selectbox("Select Funder", options=funders)
    affinity_factors = ['grant_subject_tran', 'grant_population_tran', 'grant_strategy_tran']
    selected_affinity_factor = st.selectbox("Select Affinity Factor", options=affinity_factors)
    funder_grants_df = unique_grants_df[unique_grants_df['funder_name'] == selected_funder]
    exploded_funder_df = funder_grants_df.assign(
        **{selected_affinity_factor: funder_grants_df[selected_affinity_factor].str.split(';')}).explode(
        selected_affinity_factor)
    funder_affinity = exploded_funder_df.groupby(selected_affinity_factor)['amount_usd'].sum().reset_index()
    funder_affinity = funder_affinity.sort_values('amount_usd', ascending=False)
    fig = px.bar(funder_affinity, x=selected_affinity_factor, y='amount_usd',
                 title=f"Funder Affinity: {selected_funder} - {selected_affinity_factor}")
    fig.update_layout(xaxis_title=selected_affinity_factor, yaxis_title='Total Award Amount (USD)', width=800,
                      height=600,
                      xaxis_tickangle=-45, xaxis_tickfont=dict(size=10))
    st.plotly_chart(fig)

    # Persist relationships state for chart-state tool
    try:
        st.session_state["rel_selected_factor"] = selected_factor
        st.session_state["rel_chart_type"] = chart_type
        st.session_state["rel_selected_funder"] = selected_funder
        st.session_state["rel_selected_affinity_factor"] = selected_affinity_factor
    except Exception:
        pass

    # Sidebar chat selector for multiple relationship charts on this page
    if _ai_enabled:
        st.sidebar.subheader("Chat")
        chat_target = st.sidebar.selectbox(
            "Chat about",
            options=["Description vs Amount", "Average by Factor", "Funder Affinity"],
            index=0,
            key="rel_chat_target",
        )

        if chat_target == "Description vs Amount":
            set_selected_chart("relationships.description_vs_amount")
            additional_context = "the relationship between grant description word count and award amount"
            pre_prompt = generate_page_prompt(
                df,
                _grouped_df,
                selected_chart,
                _selected_role,
                additional_context,
                current_filters=None,
                sample_df=unique_grants_df,
            )
            chat_panel(
                unique_grants_df,
                pre_prompt,
                state_key="relationships_chat",
                title="Relationships — AI Assistant",
            )

        elif chat_target == "Average by Factor":
            set_selected_chart("relationships.avg_by_factor")
            additional_context = f"average award amount by the selected factor '{selected_factor}' using a {chart_type}"
            pre_prompt = generate_page_prompt(
                df,
                _grouped_df,
                selected_chart,
                _selected_role,
                additional_context,
                current_filters={"selected_factor": selected_factor, "chart_type": chart_type},
                sample_df=avg_amount_by_factor,
            )
            chat_panel(
                avg_amount_by_factor,
                pre_prompt,
                state_key="relationships_chat",
                title="Relationships — AI Assistant",
            )

        else:
            set_selected_chart("relationships.funder_affinity")
            additional_context = f"funder affinity for '{selected_funder}' across '{selected_affinity_factor}'"
            pre_prompt = generate_page_prompt(
                df,
                _grouped_df,
                selected_chart,
                _selected_role,
                additional_context,
                current_filters={
                    "selected_funder": selected_funder,
                    "affinity_factor": selected_affinity_factor,
                },
                sample_df=funder_affinity,
            )
            chat_panel(
                funder_affinity,
                pre_prompt,
                state_key="relationships_chat",
                title="Relationships — AI Assistant",
            )

    st.write("""
        We hope that this General Analysis of Relationships page helps you uncover valuable insights and trends within the grant data. If you have any questions or need further assistance, please don't hesitate to reach out.

        Happy exploring!
        """)

    if st.checkbox("Show Underlying Data"):
        st.write(unique_grants_df)

    if st.button("Download Data as CSV"):
        href = download_csv(unique_grants_df, "grant_data.csv")
        st.markdown(href, unsafe_allow_html=True)

    st.markdown(""" This app was produced by [Christopher Collins](https://www.linkedin.com/in/cctopher/) using the latest methods for enabling AI to Chat with Data. It also uses the Candid API, Streamlit, Plotly, and other open-source libraries. Generative AI solutions such as OpenAI GPT-5 and Claude Opus were used to generate portions of the source code.
                        """)