"""
Project Planner page for GrantScope.
Helps users organize their grant project ideas with a newbie-friendly approach.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st

from config import require_flag, is_enabled
from utils.app_state import init_session_state, sidebar_controls, get_session_profile, is_newbie
from utils.help import render_page_help_panel, render_contextual_help_buttons, render_help


st.set_page_config(page_title="Project Planner - GrantScope", page_icon="📋")


def render_project_brief(data: Dict) -> str:
    """Generate a clean project brief paragraph from form data."""
    
    # Build the brief in parts
    parts = []
    
    if data.get("project_name"):
        parts.append(f"**{data['project_name']}**")
    
    if data.get("problem"):
        parts.append(f"addresses {data['problem'].lower()}")
    
    if data.get("beneficiaries"):
        parts.append(f"to help {data['beneficiaries'].lower()}")
    
    if data.get("activities"):
        parts.append(f"through {data['activities'].lower()}")
    
    if data.get("outcomes"):
        parts.append(f"with the goal of {data['outcomes'].lower()}")
    
    if data.get("timeline"):
        parts.append(f"over {data['timeline'].lower()}")
    
    # Join parts with appropriate connectors
    if len(parts) <= 1:
        return " ".join(parts)
    
    brief = parts[0]
    for i, part in enumerate(parts[1:], 1):
        if i == len(parts) - 1 and len(parts) > 2:
            brief += f", and {part}"
        elif i == 1:
            brief += f" {part}"
        else:
            brief += f", {part}"
    
    brief += "."
    
    return brief


def generate_starter_checklist(data: Dict, experience_level: str) -> List[str]:
    """Generate a starter checklist based on project data and user experience."""
    
    checklist = []
    
    # Universal items
    checklist.append("✅ Research similar successful projects in your area")
    checklist.append("✅ Identify 3-5 potential funders that match your project")
    
    if experience_level == "new":
        checklist.extend([
            "✅ Write a one-page project summary using this planner",
            "✅ List your organization's qualifications and past successes",
            "✅ Create a simple budget with main categories (staff, supplies, etc.)",
            "✅ Find someone experienced to review your project idea",
            "✅ Check funder deadlines and requirements"
        ])
    elif experience_level == "some":
        checklist.extend([
            "✅ Develop detailed project timeline with milestones", 
            "✅ Create comprehensive budget with justifications",
            "✅ Identify evaluation methods and success metrics",
            "✅ Research funder priorities and past awards",
            "✅ Begin drafting key proposal sections"
        ])
    else:  # pro
        checklist.extend([
            "✅ Conduct stakeholder analysis and engagement plan",
            "✅ Develop logic model and theory of change", 
            "✅ Create detailed evaluation framework with baseline data",
            "✅ Identify strategic partnerships and letters of support",
            "✅ Analyze competitive landscape and differentiation"
        ])
    
    return checklist


def main():
    """Main Project Planner page function."""
    init_session_state()
    
    if not require_flag("GS_ENABLE_NEW_PAGES", "Project Planner is not available"):
        return
    
    # Get user profile for customization
    profile = get_session_profile()
    is_newbie_user = is_newbie(profile)
    experience_level = profile.experience_level if profile else "new"
    
    st.title("📋 Project Planner")
    st.markdown("**Organize your grant project ideas step by step.**")
    
    # Show help panel for newbies
    if is_newbie_user:
        render_page_help_panel("project_planner", audience="new")
    
    # Sidebar controls
    sidebar_controls()
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📝 Plan Your Project", "📄 Project Brief", "📋 Next Steps"])
    
    with tab1:
        st.header("Tell us about your project")
        
        # Initialize session state for form data
        if "project_data" not in st.session_state:
            st.session_state.project_data = {}
        
        with st.form("project_planner_form"):
            st.subheader("Basic Information")
            
            project_name = st.text_input(
                "Project Name",
                value=st.session_state.project_data.get("project_name", ""),
                placeholder="What will you call this project?",
                help="Keep it simple and memorable"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                org_name = st.text_input(
                    "Organization Name",
                    value=st.session_state.project_data.get("org_name", ""),
                    placeholder="Your organization's name"
                )
            
            with col2:
                budget_range = st.selectbox(
                    "Estimated Budget Range",
                    options=["Under $5,000", "$5,000 - $25,000", "$25,000 - $100,000", "$100,000 - $500,000", "Over $500,000"],
                    index=0 if not st.session_state.project_data.get("budget_range") else 
                          ["Under $5,000", "$5,000 - $25,000", "$25,000 - $100,000", "$100,000 - $500,000", "Over $500,000"].index(st.session_state.project_data.get("budget_range", "Under $5,000"))
                )
            
            # Add help for budget range
            if is_newbie_user:
                render_help("grant_amount", audience="new", variant="expander")
            
            st.subheader("Project Details")
            
            problem = st.text_area(
                "What problem does your project solve?",
                value=st.session_state.project_data.get("problem", ""),
                placeholder="Describe the issue or need your project addresses...",
                help="Be specific about the problem and why it matters"
            )
            
            beneficiaries = st.text_area(
                "Who will benefit from your project?",
                value=st.session_state.project_data.get("beneficiaries", ""),
                placeholder="Describe your target population or community...",
                help="Be specific about who you're helping and how many people"
            )
            
            activities = st.text_area(
                "What will you do? (Main Activities)",
                value=st.session_state.project_data.get("activities", ""),
                placeholder="List the key things you'll do to address the problem...",
                help="Focus on the most important activities"
            )
            
            outcomes = st.text_area(
                "What changes do you expect to see?",
                value=st.session_state.project_data.get("outcomes", ""),
                placeholder="Describe the positive changes your project will create...",
                help="Think about both short-term and long-term results"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                timeline = st.selectbox(
                    "Project Timeline",
                    options=["3 months", "6 months", "1 year", "2 years", "3+ years"],
                    index=0 if not st.session_state.project_data.get("timeline") else
                          ["3 months", "6 months", "1 year", "2 years", "3+ years"].index(st.session_state.project_data.get("timeline", "3 months"))
                )
            
            with col2:
                urgency = st.selectbox(
                    "How urgent is this project?",
                    options=["Very urgent (immediate need)", "Somewhat urgent (within 6 months)", "Not urgent (flexible timing)"],
                    index=0 if not st.session_state.project_data.get("urgency") else
                          ["Very urgent (immediate need)", "Somewhat urgent (within 6 months)", "Not urgent (flexible timing)"].index(st.session_state.project_data.get("urgency", "Very urgent (immediate need)"))
                )
            
            # Experience-based advanced fields
            if not is_newbie_user and st.checkbox("Show advanced fields", key="show_advanced"):
                st.subheader("Advanced Planning")
                
                sustainability = st.text_area(
                    "How will you sustain this project after the grant?",
                    value=st.session_state.project_data.get("sustainability", ""),
                    placeholder="Describe your long-term funding and operational plans..."
                )
                
                partnerships = st.text_area(
                    "Key partnerships or collaborations",
                    value=st.session_state.project_data.get("partnerships", ""),
                    placeholder="List organizations or individuals you'll work with..."
                )
                
                risks = st.text_area(
                    "Potential challenges and how you'll address them",
                    value=st.session_state.project_data.get("risks", ""),
                    placeholder="What could go wrong and what's your backup plan?..."
                )
            else:
                sustainability = st.session_state.project_data.get("sustainability", "")
                partnerships = st.session_state.project_data.get("partnerships", "")
                risks = st.session_state.project_data.get("risks", "")
            
            submitted = st.form_submit_button("💾 Save Project Plan", type="primary")
            
            if submitted:
                # Save all form data
                st.session_state.project_data = {
                    "project_name": project_name,
                    "org_name": org_name,
                    "budget_range": budget_range,
                    "problem": problem,
                    "beneficiaries": beneficiaries,
                    "activities": activities,
                    "outcomes": outcomes,
                    "timeline": timeline,
                    "urgency": urgency,
                    "sustainability": sustainability,
                    "partnerships": partnerships,
                    "risks": risks,
                    "created_at": datetime.now().isoformat(),
                    "experience_level": experience_level
                }
                st.success("✅ Project plan saved! Check the other tabs to see your brief and next steps.")
    
    with tab2:
        st.header("Your Project Brief")
        
        if st.session_state.get("project_data"):
            data = st.session_state.project_data
            
            # Generate and display the brief
            brief = render_project_brief(data)
            
            st.markdown("### Project Summary")
            st.info(brief)
            
            # Additional details
            if data.get("budget_range"):
                st.markdown(f"**Estimated Budget**: {data['budget_range']}")
            
            if data.get("urgency"):
                st.markdown(f"**Timeline Priority**: {data['urgency']}")
            
            # Export options
            st.markdown("### Export Your Brief")
            col1, col2 = st.columns(2)
            
            with col1:
                # Text export
                export_text = f"""PROJECT BRIEF: {data.get('project_name', 'Untitled Project')}
Organization: {data.get('org_name', 'Not specified')}
Budget Range: {data.get('budget_range', 'Not specified')}

SUMMARY:
{brief}

PROBLEM:
{data.get('problem', 'Not specified')}

BENEFICIARIES:
{data.get('beneficiaries', 'Not specified')}

ACTIVITIES:
{data.get('activities', 'Not specified')}

EXPECTED OUTCOMES:
{data.get('outcomes', 'Not specified')}

TIMELINE: {data.get('timeline', 'Not specified')}
URGENCY: {data.get('urgency', 'Not specified')}

Generated by GrantScope Project Planner on {datetime.now().strftime('%Y-%m-%d')}
"""
                
                st.download_button(
                    label="📄 Download as Text",
                    data=export_text,
                    file_name=f"project_brief_{data.get('project_name', 'untitled').replace(' ', '_')}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # JSON export
                st.download_button(
                    label="💾 Download as JSON",
                    data=json.dumps(data, indent=2),
                    file_name=f"project_plan_{data.get('project_name', 'untitled').replace(' ', '_')}.json",
                    mime="application/json"
                )
        
        else:
            st.info("💡 Complete the project planning form in the first tab to see your brief here.")
    
    with tab3:
        st.header("Your Next Steps")
        
        if st.session_state.get("project_data"):
            data = st.session_state.project_data
            
            # Generate checklist
            checklist = generate_starter_checklist(data, experience_level)
            
            st.markdown("### Recommended Action Items")
            st.markdown("*Based on your experience level and project details*")
            
            for item in checklist:
                st.markdown(item)
            
            # Additional resources based on experience level
            if is_newbie_user:
                st.markdown("### Resources for Beginners")
                st.info("""
                **First-time grant writer?** Here's what to do next:
                1. Find a mentor or experienced grant writer in your community
                2. Look up grants your organization has received before
                3. Start small - apply for grants under $25,000 first
                4. Join your local nonprofit association for workshops
                """)
            
            # Timeline planning help
            if data.get("urgency") == "Very urgent (immediate need)":
                st.warning("""
                ⚠️ **Urgent Timeline Alert**
                
                With an urgent timeline, focus on:
                - Grants with rolling deadlines or quick turnaround
                - Emergency funding opportunities
                - Simplified application processes
                - Building your case for immediate need
                """)
            
            # Budget-specific advice
            budget = data.get("budget_range", "")
            if "Under $5,000" in budget:
                st.success("""
                💡 **Small Grant Strategy**
                
                For smaller grants:
                - Look for local community foundations
                - Check corporate giving programs
                - Consider crowdfunding for community support
                - Focus on clear, simple project descriptions
                """)
            elif "Over $500,000" in budget:
                st.info("""
                🎯 **Large Grant Strategy**
                
                For major funding:
                - Target federal agencies and large foundations
                - Expect 6-12 month application processes
                - Build strong partnerships and letters of support
                - Consider hiring professional grant writers
                """)
        
        else:
            st.info("💡 Complete your project plan to see personalized next steps.")


if __name__ == "__main__":
    main()
