"""
Timeline Advisor page for GrantScope.
Helps users create realistic grant application timelines.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import streamlit as st

from utils.app_state import get_session_profile, init_session_state, is_newbie, sidebar_controls

st.set_page_config(page_title="Timeline Advisor - GrantScope", page_icon="📅")


def generate_timeline_plan(
    submission_date: datetime,
    team_size: str,
    review_needs: list[str],
    experience_level: str,
    grant_complexity: str,
) -> list[dict]:
    """Generate a backward-planned timeline with milestones."""

    # Base timeline adjustments based on factors
    base_weeks = 8  # Default timeline

    # Adjust based on team size
    if team_size == "Just me":
        base_weeks += 2
    elif team_size == "2-3 people":
        base_weeks += 0
    elif team_size == "4+ people":
        base_weeks -= 1

    # Adjust based on experience
    if experience_level == "new":
        base_weeks += 4
    elif experience_level == "some":
        base_weeks += 1

    # Adjust based on complexity
    if grant_complexity == "Simple (under $25,000, basic requirements)":
        base_weeks -= 2
    elif grant_complexity == "Complex (over $100,000, detailed requirements)":
        base_weeks += 4

    # Adjust for review needs
    if "Board approval" in review_needs:
        base_weeks += 2
    if "External partner review" in review_needs:
        base_weeks += 1
    if "Financial review" in review_needs:
        base_weeks += 1

    # Minimum 4 weeks, maximum 20 weeks
    base_weeks = max(4, min(20, base_weeks))

    # Generate milestones working backward from submission
    milestones = []
    current_date = submission_date

    # Submission (0 days before)
    milestones.append(
        {
            "date": current_date,
            "milestone": "📤 Submit Application",
            "description": "Final submission to funder",
            "weeks_before": 0,
            "days": 1,
        }
    )

    # Final review and formatting (3-7 days before)
    current_date = current_date - timedelta(days=5)
    milestones.append(
        {
            "date": current_date,
            "milestone": "✅ Final Review & Formatting",
            "description": "Last chance to catch errors, format properly",
            "weeks_before": 1,
            "days": 3,
        }
    )

    # External reviews if needed
    if review_needs:
        review_days = 7
        if "Board approval" in review_needs:
            review_days = 14
        current_date = current_date - timedelta(days=review_days)
        milestones.append(
            {
                "date": current_date,
                "milestone": "👥 External Reviews",
                "description": f"Complete: {', '.join(review_needs)}",
                "weeks_before": 2,
                "days": review_days,
            }
        )

    # Complete first draft (2-3 weeks before external review)
    draft_weeks = 3 if experience_level == "new" else 2
    current_date = current_date - timedelta(weeks=draft_weeks)
    milestones.append(
        {
            "date": current_date,
            "milestone": "📝 Complete First Draft",
            "description": "Full draft ready for review",
            "weeks_before": draft_weeks + (2 if review_needs else 1),
            "days": draft_weeks * 7,
        }
    )

    # Gather supporting documents (1-2 weeks)
    current_date = current_date - timedelta(weeks=2)
    milestones.append(
        {
            "date": current_date,
            "milestone": "📋 Gather Supporting Documents",
            "description": "Letters of support, budgets, organizational documents",
            "weeks_before": (draft_weeks + (2 if review_needs else 1) + 2),
            "days": 14,
        }
    )

    # Research and outline (1-3 weeks depending on experience)
    research_weeks = 3 if experience_level == "new" else 1
    current_date = current_date - timedelta(weeks=research_weeks)
    milestones.append(
        {
            "date": current_date,
            "milestone": "🔍 Research & Outline",
            "description": "Understand requirements, create detailed outline",
            "weeks_before": (draft_weeks + (2 if review_needs else 1) + 2 + research_weeks),
            "days": research_weeks * 7,
        }
    )

    # Project planning and team alignment
    planning_weeks = 2 if experience_level == "new" else 1
    current_date = current_date - timedelta(weeks=planning_weeks)
    milestones.append(
        {
            "date": current_date,
            "milestone": "🎯 Project Planning",
            "description": "Finalize project details, assign responsibilities",
            "weeks_before": (
                draft_weeks + (2 if review_needs else 1) + 2 + research_weeks + planning_weeks
            ),
            "days": planning_weeks * 7,
        }
    )

    # Start date
    milestones.append(
        {
            "date": current_date,
            "milestone": "🚀 Start Grant Application Process",
            "description": "Begin working on this grant application",
            "weeks_before": base_weeks,
            "days": 0,
        }
    )

    # Reverse to get chronological order
    milestones.reverse()

    return milestones


def render_timeline_table(milestones: list[dict]) -> None:
    """Render the timeline as a nice table."""
    st.markdown("### Your Grant Application Timeline")

    # Create the table data
    table_data = []
    for i, milestone in enumerate(milestones):
        if i == 0:
            duration = "Start"
        else:
            duration = f"{milestone['days']} days"

        table_data.append(
            {
                "Date": milestone["date"].strftime("%b %d, %Y"),
                "Milestone": milestone["milestone"],
                "Description": milestone["description"],
                "Duration": duration,
            }
        )

    st.table(table_data)


def generate_calendar_export(milestones: list[dict], project_name: str) -> str:
    """Generate a simple text-based calendar export."""
    export_text = f"""GRANT APPLICATION TIMELINE: {project_name}
Generated by GrantScope Timeline Advisor on {datetime.now().strftime('%Y-%m-%d')}

MILESTONE SCHEDULE:
==================

"""

    for milestone in milestones:
        export_text += f"""
Date: {milestone['date'].strftime('%A, %B %d, %Y')}
Milestone: {milestone['milestone']}
Description: {milestone['description']}
Duration: {milestone.get('days', 0)} days
---"""

    export_text += """

QUICK TIPS:
- Add buffer time for unexpected delays
- Start earlier if this is your first grant application
- Schedule regular check-ins with your team
- Set up calendar reminders for each milestone

Questions? Use the GrantScope chat assistant for help!
"""

    return export_text


def main():
    """Main Timeline Advisor page function."""
    init_session_state()

    # Guided pages are always available; no feature flag gate

    # Get user profile for customization
    profile = get_session_profile()
    is_newbie_user = is_newbie(profile)
    experience_level = profile.experience_level if profile else "new"

    st.title("📅 Timeline Advisor")
    st.markdown("**Create a realistic timeline for your grant application.**")

    # Show help panel for newbies
    if is_newbie_user:
        with st.expander("📋 Why Timelines Matter", expanded=True):
            st.markdown(
                """
            **Good planning prevents last-minute stress!**
            
            Grant applications take longer than most people expect. A timeline helps you:
            - Avoid rushing and making mistakes
            - Get better reviews from colleagues
            - Have time to find all required documents
            - Write a stronger, more thoughtful proposal
            
            Most successful grant writers start 2-3 months before the deadline.
            """
            )

    # Sidebar controls
    sidebar_controls()

    # Main content in tabs
    tab1, tab2, tab3 = st.tabs(["⚙️ Plan Timeline", "📊 Your Timeline", "📥 Export"])

    with tab1:
        st.header("Tell us about your grant application")

        with st.form("timeline_form"):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Grant Details")

                project_name = st.text_input(
                    "Project/Grant Name",
                    placeholder="What are you calling this grant?",
                    help="This helps personalize your timeline",
                )

                submission_date = st.date_input(
                    "Application Deadline",
                    value=datetime.now() + timedelta(days=60),
                    min_value=datetime.now().date(),
                    help="When is the grant application due?",
                )

                grant_complexity = st.selectbox(
                    "How complex is this grant?",
                    options=[
                        "Simple (under $25,000, basic requirements)",
                        "Medium (up to $100,000, standard requirements)",
                        "Complex (over $100,000, detailed requirements)",
                    ],
                    help="Complex grants need more time for research and documentation",
                )

            with col2:
                st.subheader("Your Situation")

                team_size = st.selectbox(
                    "Who's working on this application?",
                    options=["Just me", "2-3 people", "4+ people"],
                    help="Larger teams can work faster but need coordination time",
                )

                review_needs = st.multiselect(
                    "What approvals do you need?",
                    options=[
                        "Board approval",
                        "Department head approval",
                        "External partner review",
                        "Financial review",
                        "Legal review",
                    ],
                    help="These reviews take additional time - plan accordingly",
                )

                urgency = st.selectbox(
                    "How urgent is this application?",
                    options=[
                        "Very urgent - deadline soon!",
                        "Somewhat urgent - good to get started",
                        "Not urgent - plenty of time to plan",
                    ],
                )

            submitted = st.form_submit_button("🎯 Create My Timeline", type="primary")

            if submitted and project_name and submission_date:
                # Generate timeline
                milestones = generate_timeline_plan(
                    datetime.combine(submission_date, datetime.min.time()),
                    team_size,
                    review_needs,
                    experience_level,
                    grant_complexity,
                )

                # Store in session
                st.session_state.timeline_data = {
                    "project_name": project_name,
                    "submission_date": submission_date.isoformat(),
                    "team_size": team_size,
                    "review_needs": review_needs,
                    "grant_complexity": grant_complexity,
                    "urgency": urgency,
                    "experience_level": experience_level,
                    "milestones": milestones,
                    "created_at": datetime.now().isoformat(),
                }

                st.success("✅ Timeline created! Check the 'Your Timeline' tab to see it.")

                # Show urgency warnings
                total_weeks = milestones[-1]["weeks_before"] if milestones else 8
                days_until_deadline = (submission_date - datetime.now().date()).days
                weeks_until_deadline = days_until_deadline / 7

                if weeks_until_deadline < total_weeks:
                    st.warning(
                        f"""
                    ⚠️ **Timeline Alert!**
                    
                    Your deadline is in {days_until_deadline} days ({weeks_until_deadline:.1f} weeks), 
                    but we recommend {total_weeks} weeks for this type of grant.
                    
                    **Options:**
                    - Work extra hours to meet this deadline
                    - Look for grants with later deadlines
                    - Simplify your project scope for this round
                    """
                    )

    with tab2:
        st.header("Your Application Timeline")

        if st.session_state.get("timeline_data"):
            data = st.session_state.timeline_data

            # Show timeline overview
            st.info(
                f"""
            **Project**: {data['project_name']}  
            **Deadline**: {datetime.fromisoformat(data['submission_date']).strftime('%B %d, %Y')}  
            **Team Size**: {data['team_size']}  
            **Complexity**: {data['grant_complexity']}
            """
            )

            # Show timeline table
            if "milestones" in data and data["milestones"]:
                render_timeline_table(data["milestones"])

                # Additional tips based on user profile
                if is_newbie_user:
                    st.markdown("### Tips for First-Time Grant Writers")
                    st.info(
                        """
                    - **Start with research**: Understand exactly what the funder wants
                    - **Ask for help**: Find someone who has won grants to review your work  
                    - **Don't wait**: If something seems hard, start it early
                    - **Keep notes**: Track what works for future applications
                    """
                    )

                # Review reminders
                if data.get("review_needs"):
                    st.markdown("### Review Reminders")
                    for review in data["review_needs"]:
                        st.markdown(f"- **{review}**: Schedule this early - people are busy!")

        else:
            st.info("💡 Use the 'Plan Timeline' tab to create your personalized timeline.")

    with tab3:
        st.header("Export Your Timeline")

        if st.session_state.get("timeline_data"):
            data = st.session_state.timeline_data

            st.markdown("### Download Options")

            col1, col2 = st.columns(2)

            with col1:
                # Text export
                calendar_text = generate_calendar_export(data["milestones"], data["project_name"])

                st.download_button(
                    label="📄 Download Timeline (Text)",
                    data=calendar_text,
                    file_name=f"grant_timeline_{data['project_name'].replace(' ', '_')}.txt",
                    mime="text/plain",
                )

            with col2:
                # JSON export
                st.download_button(
                    label="💾 Download Data (JSON)",
                    data=json.dumps(data, indent=2, default=str),
                    file_name=f"timeline_data_{data['project_name'].replace(' ', '_')}.json",
                    mime="application/json",
                )

            st.markdown("### Share with Your Team")
            st.markdown(
                """
            **Next steps:**
            1. Save this timeline where your team can see it
            2. Add milestones to your calendar app
            3. Set up regular check-ins to stay on track
            4. Adjust dates if things change
            """
            )

            # Quick copy-paste format
            with st.expander("📋 Quick Copy Format"):
                quick_format = f"""
GRANT TIMELINE: {data['project_name']}
Deadline: {datetime.fromisoformat(data['submission_date']).strftime('%B %d, %Y')}

KEY DATES:
"""
                for milestone in data["milestones"]:
                    quick_format += (
                        f"• {milestone['date'].strftime('%m/%d')} - {milestone['milestone']}\n"
                    )

                st.code(quick_format, language=None)

        else:
            st.info("💡 Create a timeline first to see export options.")


if __name__ == "__main__":
    main()
