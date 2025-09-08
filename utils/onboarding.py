"""
Onboarding wizard for GrantScope newbie mode.
Guides first-time users through a simple, friendly setup process.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Optional, Tuple

import streamlit as st

from config import is_enabled
from utils.app_state import UserProfile, ExperienceLevel, OrgType, role_label


class OnboardingWizard:
    """Multi-step onboarding wizard with newbie-friendly language."""
    
    def __init__(self):
        self.steps = [
            self._step_welcome,
            self._step_experience,
            self._step_organization,
            self._step_preferences,
            self._step_review
        ]
        self.step_titles = [
            "Welcome to GrantScope!",
            "What's your experience with grants?",
            "Tell us about your work",
            "Your preferences",
            "All set!"
        ]
    
    def render(self, profile: Optional[UserProfile] = None) -> Tuple[Optional[UserProfile], bool]:
        """
        Render the onboarding wizard.
        Returns (profile, completed) tuple.
        """
        if not is_enabled("GS_ENABLE_NEWBIE_MODE"):
            st.info("Onboarding is currently disabled.")
            return profile, profile is not None and profile.completed_onboarding
        
        # Initialize session state for wizard
        if "onboarding_step" not in st.session_state:
            st.session_state.onboarding_step = 0
        if "onboarding_data" not in st.session_state:
            st.session_state.onboarding_data = {}
        
        current_step = st.session_state.onboarding_step
        
        # Display progress
        self._show_progress(current_step)
        
        # Render current step
        if current_step < len(self.steps):
            completed = self.steps[current_step]()
            if completed and current_step < len(self.steps) - 1:
                # Move to next step
                st.session_state.onboarding_step += 1
                st.rerun()
            elif completed and current_step == len(self.steps) - 1:
                # Final step completed
                profile = self._create_profile_from_data()
                return profile, True
        
        return None, False
    
    def _show_progress(self, current_step: int) -> None:
        """Show progress indicator."""
        progress = (current_step + 1) / len(self.steps)
        st.progress(progress, text=f"Step {current_step + 1} of {len(self.steps)}")
        st.markdown("---")
    
    def _step_welcome(self) -> bool:
        """Welcome step with friendly introduction."""
        st.title(self.step_titles[0])
        
        st.markdown("""
        ### Great to see you here! 👋
        
        **GrantScope helps you find and understand grant opportunities.**
        
        We'll ask a few quick questions to give you the best experience. 
        This takes about 2 minutes.
        
        #### What you'll get:
        - Simple explanations of grant data
        - Step-by-step guidance for beginners  
        - Tools to plan your grant application
        - Smart recommendations based on your needs
        """)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            return st.button("Let's get started!", use_container_width=True, type="primary")
    
    def _step_experience(self) -> bool:
        """Experience level selection."""
        st.title(self.step_titles[1])
        
        st.markdown("""
        **Choose the option that best describes you:**
        
        This helps us show the right amount of detail and guidance.
        """)
        
        options = ["new", "some", "pro"]
        labels = [role_label(opt) for opt in options]
        descriptions = [
            "Perfect! We'll explain everything step by step.",
            "Great! We'll give you helpful tips along the way.",
            "Excellent! We'll keep things efficient and detailed."
        ]
        
        selected = st.radio(
            "Your grant experience:",
            options=options,
            format_func=lambda x: role_label(x),
            key="experience_selection"
        )
        
        # Show description for selected option
        if selected:
            idx = options.index(selected)
            st.info(descriptions[idx])
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Back"):
                st.session_state.onboarding_step = max(0, st.session_state.onboarding_step - 1)
                st.rerun()
        
        with col2:
            if st.button("Continue →", type="primary", disabled=not selected):
                st.session_state.onboarding_data["experience_level"] = selected
                return True
        
        return False
    
    def _step_organization(self) -> bool:
        """Organization and goals."""
        st.title(self.step_titles[2])
        
        st.markdown("**Help us understand your work so we can show relevant opportunities.**")
        
        # Organization type
        org_types = ["nonprofit", "school", "business", "government", "other"]
        org_labels = {
            "nonprofit": "Nonprofit organization", 
            "school": "School or university",
            "business": "Business or for-profit",
            "government": "Government agency",
            "other": "Other"
        }
        
        org_type = st.selectbox(
            "What type of organization do you work with?",
            options=org_types,
            format_func=lambda x: org_labels[x],
            key="org_type_selection"
        )
        
        # Primary goal
        primary_goal = st.text_area(
            "What's your main goal with grants? (optional)",
            placeholder="Example: Fund after-school programs, support research, expand services...",
            help="This helps us recommend relevant opportunities.",
            key="primary_goal_input"
        )
        
        # Region
        region = st.text_input(
            "What region are you in?",
            placeholder="Example: California, New York City, Rural Ohio...",
            help="Some grants are location-specific.",
            key="region_input"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Back"):
                st.session_state.onboarding_step -= 1
                st.rerun()
        
        with col2:
            can_continue = bool(org_type and region)
            if st.button("Continue →", type="primary", disabled=not can_continue):
                st.session_state.onboarding_data.update({
                    "org_type": org_type,
                    "primary_goal": primary_goal or "",
                    "region": region
                })
                return True
        
        return False
    
    def _step_preferences(self) -> bool:
        """Preferences and consent."""
        st.title(self.step_titles[3])
        
        st.markdown("**A couple final preferences:**")
        
        # Newsletter opt-in
        newsletter = st.checkbox(
            "I'd like tips and updates about grants (optional)",
            help="We'll send helpful grant-writing tips and funding opportunities."
        )
        
        # Privacy notice
        st.markdown("""
        #### Privacy Notice
        
        - Your preferences stay on your device
        - We don't sell or share your information
        - You can reset these settings anytime
        """)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Back"):
                st.session_state.onboarding_step -= 1
                st.rerun()
        
        with col2:
            if st.button("Finish setup →", type="primary"):
                st.session_state.onboarding_data["newsletter_opt_in"] = newsletter
                return True
        
        return False
    
    def _step_review(self) -> bool:
        """Final review and completion."""
        st.title(self.step_titles[4])
        
        data = st.session_state.onboarding_data
        
        st.success("🎉 **Welcome to GrantScope!**")
        
        st.markdown(f"""
        Here's what we set up for you:
        
        - **Experience level**: {role_label(data.get('experience_level', 'new'))}
        - **Organization type**: {data.get('org_type', '').title()}
        - **Region**: {data.get('region', '')}
        - **Goal**: {data.get('primary_goal', 'Not specified')}
        """)
        
        st.markdown("""
        ### What's next?
        
        1. **Explore the data** - Start with Data Summary to see what's available
        2. **Plan your project** - Use Project Planner to organize your thoughts  
        3. **Ask questions** - Chat with our AI assistant on any page
        4. **Find opportunities** - Look for grants that match your needs
        
        You can change these settings anytime in the sidebar.
        """)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Back"):
                st.session_state.onboarding_step -= 1
                st.rerun()
        
        with col2:
            if st.button("Start exploring! 🚀", type="primary"):
                return True
        
        return False
    
    def _create_profile_from_data(self) -> UserProfile:
        """Create UserProfile from collected data."""
        data = st.session_state.onboarding_data
        
        # Generate a simple user ID based on session
        session_id = st.session_state.get("session_id", str(uuid.uuid4()))
        if "session_id" not in st.session_state:
            st.session_state.session_id = session_id
        
        # Create a deterministic but private user ID
        user_id = hashlib.sha256(f"gs_user_{session_id}".encode()).hexdigest()[:16]
        
        return UserProfile(
            user_id=user_id,
            experience_level=data.get("experience_level", "new"),
            org_type=data.get("org_type", "other"),
            primary_goal=data.get("primary_goal", ""),
            region=data.get("region", ""),
            newsletter_opt_in=data.get("newsletter_opt_in", False),
            completed_onboarding=True,
            created_at=datetime.now()
        )
    
    @staticmethod
    def reset_onboarding() -> None:
        """Reset onboarding state for testing or user preference."""
        keys_to_reset = ["onboarding_step", "onboarding_data", "user_profile"]
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
