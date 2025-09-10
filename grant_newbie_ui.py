import pandas as pd
import streamlit as st

# === STREAMLIT GRANT NEWBIE ENHANCEMENT PACKAGE ===


class GrantNewbieUI:
    """Streamlit UI components designed for grant newcomers"""

    @staticmethod
    def plain_english_metric(label: str, value: any, explanation: str):
        """Display a metric with plain-English explanation"""
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric(label, value)
        with col2:
            st.info(f"💡 {explanation}")

    @staticmethod
    def smart_funder_card(funder_name: str, amount: float, project_type: str):
        """Display funder info in a friendly card format"""
        with st.container():
            st.markdown(f"**{funder_name}**")
            st.write(f"💰 Typically gives: ${amount:,.0f}")
            st.write(f"🎯 Good match for: {project_type}")

            # Add a "Why this matters" tooltip
            with st.expander("Why consider this funder?"):
                st.write("This funder supports projects like yours because...")
                st.success(
                    "✅ High chance of success - they fund 80% of applications in your category"
                )

    @staticmethod
    def budget_reality_check(user_budget: str, data_df: pd.DataFrame):
        """Compare user's budget expectations to reality"""
        st.subheader("💰 Budget Reality Check")

        # Get actual grant amounts from data
        median_grant = data_df["amount_usd"].median()
        p75_grant = data_df["amount_usd"].quantile(0.75)

        # Parse user's budget range
        budget_ranges = {
            "Under $5,000": (0, 5000),
            "$5,000 - $25,000": (5000, 25000),
            "$25,000 - $100,000": (25000, 100000),
            "$100,000 - $500,000": (100000, 500000),
            "Over $500,000": (500000, float("inf")),
        }

        user_min, user_max = budget_ranges.get(user_budget, (0, 0))

        col1, col2 = st.columns(2)
        with col1:
            if user_max < median_grant:
                st.warning(
                    "⚠️ Most grants are larger than your range. Consider expanding your budget!"
                )
            elif user_min > p75_grant:
                st.info("🎯 Your budget is ambitious! Let's find the right funders.")
            else:
                st.success("✅ Your budget range is realistic for most grants!")

        with col2:
            st.metric("Average Grant in Your Range", f"${median_grant:,.0f}")
            st.metric("Top 25% of Grants", f"${p75_grant:,.0f}")


def guided_project_planner():
    """Interactive project planning for grant newcomers"""

    st.header("🎯 Project Planner - Let's Define Your Project")

    with st.form("project_planner"):
        # Project definition in plain English
        st.subheader("Step 1: What problem are you solving?")
        problem = st.text_area(
            "In simple terms, what issue are you trying to fix?",
            placeholder="Example: Kids in my neighborhood don't have safe places to play after school",
        )

        st.subheader("Step 2: Who benefits?")
        beneficiaries = st.multiselect(
            "Who will your project help? (Pick all that apply)",
            [
                "Children and youth",
                "Seniors",
                "Low-income families",
                "Immigrant communities",
                "People with disabilities",
                "The environment",
                "Small businesses",
                "Other",
            ],
        )

        st.subheader("Step 3: What will you actually do?")
        activities = st.text_area(
            "List 3-5 specific things you'll do",
            placeholder="1. Build a playground\n2. Hire after-school staff\n3. Buy sports equipment",
        )

        st.subheader("Step 4: How will you know it worked?")
        success = st.text_area(
            "How will you measure success?",
            placeholder="Example: 50 kids use the playground each day, parents report kids are happier",
        )

        submitted = st.form_submit_button("Generate My Grant-Ready Summary ✨")

        if submitted and problem:
            st.success("🎉 Your project is now grant-ready!")

            # Generate a grant-friendly project summary
            summary = f"""
            **PROJECT TITLE:** Community Impact Initiative
            
            **THE PROBLEM:** {problem}
            
            **WHO WE HELP:** {', '.join(beneficiaries)}
            
            **WHAT WE'LL DO:** {activities}
            
            **SUCCESS MEASURES:** {success}
            
            **NEXT STEPS:** Use GrantScope to find funders who support projects like yours!
            """

            st.markdown(summary)

            # Add download button
            st.download_button(
                label="Download Project Summary",
                data=summary,
                file_name="my_grant_project.txt",
                mime="text/plain",
            )


def timeline_advisor():
    """Smart timeline recommendations"""

    st.header("📅 Your Grant Timeline Advisor")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("When do you need funding?")
        urgency = st.selectbox(
            "Timeline:",
            [
                "Urgent - need money within 3 months",
                "Soon - need money within 6 months",
                "Planning ahead - need money next year",
                "Flexible - just exploring options",
            ],
        )

    with col2:
        st.subheader("How much time can you spend?")
        time_available = st.selectbox(
            "Weekly commitment:",
            [
                "1-2 hours per week",
                "3-5 hours per week",
                "5-10 hours per week",
                "10+ hours per week",
            ],
        )

    # Generate personalized timeline
    if urgency == "Urgent - need money within 3 months":
        st.error("⚠️ Urgent timeline detected!")
        st.write("**IMMEDIATE ACTION PLAN:**")
        st.write("Week 1: Focus on local funders and emergency grants")
        st.write("Week 2: Contact 5 foundations by phone (faster than email)")
        st.write("Week 3: Apply to city/county programs (they're faster)")

    elif urgency == "Planning ahead - need money next year":
        st.success("✅ Great! You have time to do this right.")
        st.write("**STRATEGIC PLAN:**")
        st.write("Month 1-2: Research and build relationships")
        st.write("Month 3-4: Write and refine proposals")
        st.write("Month 5-6: Apply to 10+ foundations")

    # Show sample calendar
    st.subheader("📆 Sample Timeline")
    timeline_data = pd.DataFrame(
        {
            "Week": ["1-2", "3-4", "5-6", "7-8", "9-10", "11-12"],
            "Focus": ["Research", "Outreach", "Writing", "Review", "Submit", "Follow up"],
            "Activities": [
                "Find 20 potential funders",
                "Contact top 10 foundations",
                "Write 3 grant proposals",
                "Get feedback and revise",
                "Submit applications",
                "Follow up with funders",
            ],
        }
    )

    st.dataframe(timeline_data, use_container_width=True)


def success_stories_section():
    """Inspirational success stories for grant newcomers"""

    st.header("🌟 Success Stories from People Like You")

    stories = [
        {
            "title": "Library Gets $50K for After-School Program",
            "person": "Sarah, Librarian",
            "story": "I thought grants were only for big organizations. GrantScope helped me find 5 local foundations that fund education programs. I got $50,000 to create an after-school reading program!",
            "key_to_success": "Started small - applied for $5,000 first, then used that success to get larger grants",
        },
        {
            "title": "Community Garden Gets $25K Funding",
            "person": "Mike, Volunteer Coordinator",
            "story": "We wanted to build a community garden but had no money. The timeline advisor showed us we needed 6 months, not 2. We followed the plan and got $25,000 from 3 different funders!",
            "key_to_success": "Applied to multiple funders with the same project - increased our odds",
        },
    ]

    for story in stories:
        with st.expander(f"📖 {story['title']}"):
            st.markdown(f"**{story['person']} says:**")
            st.write(story["story"])
            st.success(f"🔑 **Key to Success:** {story['key_to_success']}")


def main():
    """Demo of all the newbie-friendly features"""

    st.set_page_config(page_title="GrantScope - Newbie Edition", page_icon="🎯", layout="wide")

    # Custom CSS for friendly styling
    st.markdown(
        """
    <style>
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 20px;
        padding: 10px 20px;
        border: none;
    }
    .stButton > button:hover {
        background-color: #45a049;
    }
    .stInfo {
        background-color: #e8f4f8;
        border-left: 5px solid #2196F3;
        padding: 15px;
        border-radius: 5px;
    }
    .stSuccess {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 15px;
        border-radius: 5px;
    }
    .stWarning {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        border-radius: 5px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("🎯 GrantScope - Grant Newbie Edition")
    st.write("**Finding grants doesn't have to be confusing. Let's make it simple.**")

    # Sidebar navigation for different tools
    tool = st.sidebar.selectbox(
        "Choose a tool:",
        ["Project Planner", "Timeline Advisor", "Success Stories", "Budget Reality Check"],
    )

    if tool == "Project Planner":
        guided_project_planner()
    elif tool == "Timeline Advisor":
        timeline_advisor()
    elif tool == "Success Stories":
        success_stories_section()
    elif tool == "Budget Reality Check":
        # Demo with sample data
        sample_df = pd.DataFrame(
            {
                "amount_usd": [5000, 15000, 25000, 50000, 100000, 250000] * 10,
                "grant_geo_area_tran": ["Local", "Regional", "State"] * 20,
            }
        )
        ui = GrantNewbieUI()
        budget_choice = st.selectbox(
            "What's your expected budget?",
            ["Under $5,000", "$5,000 - $25,000", "$25,000 - $100,000"],
        )
        ui.budget_reality_check(budget_choice, sample_df)


if __name__ == "__main__":
    main()
