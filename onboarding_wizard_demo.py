import pandas as pd
import streamlit as st


def onboarding_wizard():
    """Interactive onboarding for grant newcomers"""

    if "onboarding_complete" not in st.session_state:
        st.session_state.onboarding_complete = False

    if not st.session_state.onboarding_complete:
        st.title("🎯 Welcome to GrantScope!")
        st.write("Let's get you started on finding funding for your project.")

        # Step 1: What are grants?
        with st.expander("📚 First, what are grants and why should you care?", expanded=True):
            st.markdown(
                """
            **Grants are free money** (you don't pay it back!) given by:
            - **Foundations** (like the Gates Foundation)
            - **Government agencies** (like the National Science Foundation)
            - **Corporations** (like Google's education grants)
            
            **Why grants matter:**
            - Fund your community project without going into debt
            - Get support for research, education, or social causes
            - Build credibility for your organization
            - Create positive change in your community
            """
            )

        # Step 2: What do you need funding for?
        st.subheader("🎨 What brings you here today?")
        project_type = st.selectbox(
            "I need funding for...",
            [
                "A community program (library, park, arts)",
                "Education or research",
                "A small business or startup",
                "Healthcare or social services",
                "Environmental or conservation work",
                "Something else",
            ],
        )

        # Step 3: Budget range (simplified)
        st.subheader("💰 What's your dream budget?")
        budget_range = st.select_slider(
            "Pick a range (we'll help you figure out what's realistic)",
            options=[
                "Under $5,000",
                "$5,000 - $25,000",
                "$25,000 - $100,000",
                "$100,000 - $500,000",
                "Over $500,000",
            ],
        )

        # Step 4: Timeline
        st.subheader("⏰ When do you need the money?")
        timeline = st.selectbox(
            "My timeline is...",
            ["ASAP (within 3 months)", "This year", "Next year", "I'm flexible - just exploring"],
        )

        # Step 5: Experience level
        st.subheader("🎓 Have you written grants before?")
        experience = st.radio(
            "My experience level:", ["Never", "A little", "Some experience", "Very experienced"]
        )

        if st.button("Get My Personalized Dashboard 🚀"):
            st.session_state.onboarding_complete = True
            st.session_state.user_profile = {
                "project_type": project_type,
                "budget_range": budget_range,
                "timeline": timeline,
                "experience": experience,
            }
            st.rerun()

    else:
        # Show personalized dashboard
        profile = st.session_state.get("user_profile", {})
        st.success(
            f"Great! You're looking for {profile.get('budget_range', 'funding')} for {profile.get('project_type', 'your project')}"
        )


def plain_english_chart_explainer():
    """Add plain-English explanations to charts"""

    st.subheader("📊 What This Chart Means for You")

    # Contextual explanations based on current chart
    if "chart_type" in st.session_state:
        explanations = {
            "funder_distribution": """
            **What this means:** The bigger the slice, the more money this type of organization gives out.
            **For your project:** If you see big slices for "Community Foundations" or "Corporate Giving Programs," 
            those are great places to start your search!
            """,
            "top_funders": """
            **What this means:** These organizations give out the most money overall.
            **For your project:** Don't just chase the biggest funders! Sometimes smaller foundations 
            are more likely to fund local or niche projects.
            """,
        }

        if st.session_state.chart_type in explanations:
            st.info(explanations[st.session_state.chart_type])


def smart_recommendations(df: pd.DataFrame):
    """Generate personalized funding recommendations"""

    st.subheader("🎯 Recommended Next Steps")

    # Simple recommendation engine based on data
    if len(df) > 0:
        # Find funders in their area (simplified)
        local_funders = df[df["grant_geo_area_tran"].str.contains("Local", na=False)]
        if len(local_funders) > 0:
            st.success(
                f"💡 **Local Opportunity Found!** {len(local_funders)} funders support local projects like yours."
            )

        # Budget guidance
        avg_amount = df["amount_usd"].median()
        st.info(
            f"💰 **Budget Reality Check:** Half of grants in your area are under ${avg_amount:,.0f}"
        )

        # Timeline guidance
        recent_grants = df[df["year_issued"] >= 2023]
        if len(recent_grants) > 0:
            st.warning(
                f"⏰ **Timing Insight:** {len(recent_grants)} recent grants show funders are actively giving now!"
            )


if __name__ == "__main__":
    st.set_page_config(page_title="GrantScope - Grant Newbie Edition", page_icon="🎯")

    # Add custom CSS for friendly styling
    st.markdown(
        """
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 20px;
        padding: 10px 20px;
    }
    .stInfo {
        background-color: #e8f4f8;
        border-left: 5px solid #2196F3;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    onboarding_wizard()

    # Show example of how to integrate with existing data
    if st.session_state.get("onboarding_complete"):
        st.write("---")
        st.header("📈 Your Personalized Insights")

        # Mock data for demo
        sample_df = pd.DataFrame(
            {
                "funder_name": ["Community Foundation", "Local Arts Council", "City Grant Program"],
                "amount_usd": [15000, 8000, 25000],
                "grant_geo_area_tran": ["Local", "Regional", "Local"],
                "year_issued": [2023, 2024, 2023],
            }
        )

        smart_recommendations(sample_df)
        plain_english_chart_explainer()
