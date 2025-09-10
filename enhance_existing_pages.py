import pandas as pd
import plotly.express as px
import streamlit as st

# === INTEGRATION WITH EXISTING GRANTSCOPE PAGES ===


def enhance_data_summary_for_newbies(
    df: pd.DataFrame, grouped_df: pd.DataFrame, selected_role: str
):
    """Enhanced version of data_summary that includes newbie-friendly features"""

    st.header("📊 Your Funding Landscape")

    # Add newbie context at the top
    with st.expander("🤔 New to grants? Start here!", expanded=True):
        st.markdown(
            """
        **What you're looking at:** This shows you ALL the grants in our database.
        Think of it like a map of where the money is going in your area.
        
        **Key things to notice:**
        - **Total grants**: How many opportunities exist
        - **Top funders**: Who has the most money to give
        - **Grant types**: What kinds of organizations give money
        """
        )

    # Simplified metrics with explanations
    col1, col2, col3 = st.columns(3)

    with col1:
        total_grants = df["grant_key"].nunique()
        st.metric(label="Total Opportunities", value=f"{total_grants:,}")
        st.caption("💡 This is how many grants you could potentially apply for")

    with col2:
        total_funders = df["funder_name"].nunique()
        st.metric(label="Organizations with Money", value=f"{total_funders:,}")
        st.caption("💡 These are your potential funding partners")

    with col3:
        total_recipients = df["recip_name"].nunique()
        st.metric(label="Successful Projects", value=f"{total_recipients:,}")
        st.caption("💡 Proof that people DO get funded! You can be next.")

    # Newbie-friendly top funders
    st.subheader("🏆 Who Has the Most Money to Give?")

    top_n = st.slider(
        "Show me the top organizations with money",
        min_value=3,
        max_value=15,
        value=5,
        step=1,
        help="Start with top 5 - these are your best bets for large funding",
    )

    unique_df = df.drop_duplicates(subset="grant_key")
    top_funders = unique_df.groupby("funder_name")["amount_usd"].sum().nlargest(top_n).reset_index()

    # Add plain-English explanations
    fig = px.bar(
        top_funders,
        x="funder_name",
        y="amount_usd",
        title=f"Top {top_n} Organizations with Money to Give Away",
    )
    fig.update_layout(xaxis_title="Organization Name", yaxis_title="Total Money Given ($)")
    st.plotly_chart(fig)

    # Add context for each funder
    if st.checkbox("🤔 What do these organizations actually fund?"):
        for _, row in top_funders.head(3).iterrows():
            funder_name = row["funder_name"]
            amount = row["amount_usd"]

            st.write(f"**{funder_name}**")
            st.write(f"💰 Gives away: ${amount:,.0f} total")

            # Show what they typically fund
            funder_grants = unique_df[unique_df["funder_name"] == funder_name]
            if len(funder_grants) > 0 and "grant_subject_tran" in funder_grants.columns:
                top_subjects = funder_grants["grant_subject_tran"].value_counts().head(3)
                st.write("🎯 They usually fund:", ", ".join(top_subjects.index.tolist()))

            st.write("")

    # Replace technical pie chart with simple explanation
    st.subheader("🎨 What Types of Organizations Give Money?")

    funder_type_dist = unique_df.groupby("funder_type")["amount_usd"].sum().reset_index()

    # Simplify to top categories, group rest as "Other"
    if len(funder_type_dist) > 8:
        top_types = funder_type_dist.nlargest(7, "amount_usd")
        other_sum = funder_type_dist.nsmallest(len(funder_type_dist) - 7, "amount_usd")[
            "amount_usd"
        ].sum()
        other_df = pd.DataFrame([{"funder_type": "Other", "amount_usd": other_sum}])
        funder_type_dist = pd.concat([top_types, other_df], ignore_index=True)

    fig = px.pie(
        funder_type_dist,
        values="amount_usd",
        names="funder_type",
        title="Types of Organizations That Give Money",
    )
    st.plotly_chart(fig)

    # Add plain-English explanations for each type
    if st.checkbox("🤔 What do these organization types mean?"):
        explanations = {
            "Foundation": "Private organizations set up by wealthy people/companies to give money away",
            "Community Foundation": "Local organizations that manage money for community improvement",
            "Corporate Giving Program": "Companies that give back to communities where they operate",
            "Government Agency": "Federal, state, or local government programs that fund projects",
        }

        for org_type in funder_type_dist["funder_type"]:
            if org_type in explanations:
                st.info(f"**{org_type}**: {explanations[org_type]}")

    # Add "What to do next" section
    st.subheader("🚀 What Should I Do Next?")

    next_steps = [
        "📋 **Make a list** of 3-5 funders from the chart above that match your project",
        "🔍 **Research their websites** - look for 'Grant Guidelines' or 'Apply' pages",
        "📞 **Call or email** 2-3 funders to introduce yourself before applying",
        "📝 **Start your application** - most funders want a 1-2 page letter first",
    ]

    for step in next_steps:
        st.write(step)

    # Only show data table for advanced users
    if selected_role == "Grant Analyst/Writer":
        if st.checkbox("Show detailed data table (advanced)"):
            st.write(top_funders)


def enhance_grant_distribution_for_newbies(df: pd.DataFrame, selected_role: str):
    """Enhanced grant amount distribution with newbie context"""

    st.header("💰 How Much Money Should You Ask For?")

    # Add context for grant amounts
    with st.expander("🤔 Not sure how much to ask for? Read this first!", expanded=True):
        st.markdown(
            """
        **The #1 mistake new grant seekers make:** Asking for too much or too little money.
        
        **Here's the secret:** Most foundations have a "sweet spot" - amounts they like to give.
        This chart shows you what that looks like in your area.
        
        **How to use this:**
        1. Look at the tallest bars - those are the most common grant sizes
        2. Start with those amounts for your first applications
        3. You can always ask for more once you build relationships
        """
        )

    # Create amount clusters with plain-English names
    amount_clusters = [
        "Under $5K (starter grants)",
        "$5K-$25K (small projects)",
        "$25K-$100K (medium projects)",
        "$100K-$500K (big projects)",
        "Over $500K (major initiatives)",
    ]

    cluster_col = st.selectbox(
        "View grant amounts as:",
        ["Simple categories", "Exact dollar amounts"],
        help="Start with 'Simple categories' if you're new to grants",
    )

    if cluster_col == "Simple categories":
        # Create simplified visualization
        unique_df = df.drop_duplicates(subset="grant_key")

        # Add amount cluster logic (simplified)
        conditions = [
            unique_df["amount_usd"] < 5000,
            (unique_df["amount_usd"] >= 5000) & (unique_df["amount_usd"] < 25000),
            (unique_df["amount_usd"] >= 25000) & (unique_df["amount_usd"] < 100000),
            (unique_df["amount_usd"] >= 100000) & (unique_df["amount_usd"] < 500000),
            unique_df["amount_usd"] >= 500000,
        ]

        unique_df["amount_category"] = pd.np.select(conditions, amount_clusters)

        category_counts = unique_df["amount_category"].value_counts()

        fig = px.bar(
            x=category_counts.index,
            y=category_counts.values,
            title="How Many Grants Are in Each Size Range?",
            labels={"x": "Grant Size", "y": "Number of Grants Available"},
        )
        st.plotly_chart(fig)

        # Add recommendations
        st.subheader("🎯 My Recommendations for You")

        most_common = category_counts.index[0]
        most_common_count = category_counts.iloc[0]

        st.success(
            f"""
        **Start here:** {most_common}
        
        **Why:** {most_common_count} grants are in this range - your best odds!
        **What to ask for:** ${most_common.split(' ')[0].replace('$','').replace('K','000')}
        **Perfect for:** First-time applicants and pilot projects
        """
        )

    else:
        # Show detailed distribution for advanced users
        st.subheader("Detailed Grant Amount Distribution")
        # ... existing detailed analysis code ...


def add_contextual_help():
    """Add hover tooltips and help text throughout the app"""

    # Grant terminology glossary
    glossary = {
        "funder": "An organization that gives money (like a foundation or government agency)",
        "recipient": "The person or organization that receives the money",
        "grant_amount": "How much money is being given",
        "funder_type": "What kind of organization is giving the money",
        "grant_subject": "What the money can be used for (education, health, arts, etc.)",
        "amount_usd": "Grant size in US dollars",
        "year_issued": "When the money was given out",
    }

    return glossary


# === EXAMPLE INTEGRATION WITH EXISTING PAGES ===


def create_newbie_friendly_page(df: pd.DataFrame, page_type: str):
    """Create a newbie-friendly version of existing pages"""

    # Add glossary to session state
    if "glossary" not in st.session_state:
        st.session_state.glossary = add_contextual_help()

    # Add help button in sidebar
    with st.sidebar:
        if st.button("🤔 Grant Terms Confusing?"):
            with st.expander("📖 Plain-English Glossary"):
                for term, definition in st.session_state.glossary.items():
                    st.write(f"**{term}**: {definition}")

    # Route to appropriate enhanced function
    if page_type == "data_summary":
        enhance_data_summary_for_newbies(df, st.session_state.get("user_role", "Normal Grant User"))
    elif page_type == "grant_distribution":
        enhance_grant_distribution_for_newbies(
            df, st.session_state.get("user_role", "Normal Grant User")
        )

    # Add universal "What to do next" section
    st.sidebar.subheader("🚀 Quick Actions")
    st.sidebar.write("1. 📋 Save 3-5 funders you like")
    st.sidebar.write("2. 🔍 Visit their websites")
    st.sidebar.write("3. 📞 Call to introduce yourself")
    st.sidebar.write("4. 📝 Start your application")


# === DEMO ===
if __name__ == "__main__":
    # Create sample data for demo
    sample_data = pd.DataFrame(
        {
            "grant_key": range(1, 101),
            "funder_name": [
                "Community Foundation",
                "Local Arts Council",
                "City Grant Program",
                "State Agency",
                "Corporate Giving",
            ]
            * 20,
            "funder_type": [
                "Foundation",
                "Community Foundation",
                "Government",
                "Government",
                "Corporate",
            ]
            * 20,
            "recip_name": ["Library", "School", "Nonprofit", "Hospital", "Museum"] * 20,
            "amount_usd": [5000, 15000, 25000, 50000, 100000] * 20,
            "grant_subject_tran": ["Education", "Arts", "Community", "Health", "Culture"] * 20,
            "grant_geo_area_tran": ["Local", "Regional", "State", "National", "Local"] * 20,
            "year_issued": [2023, 2024] * 50,
        }
    )

    st.set_page_config(page_title="GrantScope - Newbie Enhanced", page_icon="🎯")

    st.title("🎯 GrantScope - Newbie Edition Demo")
    st.write("This shows how we can enhance existing pages to be friendly for grant newcomers")

    page_choice = st.selectbox("Choose a page to enhance:", ["Data Summary", "Grant Distribution"])

    if page_choice == "Data Summary":
        create_newbie_friendly_page(sample_data, "data_summary")
    else:
        create_newbie_friendly_page(sample_data, "grant_distribution")
