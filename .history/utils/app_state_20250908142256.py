import os
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Literal, Optional
import streamlit as st
from loaders.data_loader import load_data, preprocess_data
from utils.utils import build_sample_grants_json, download_text

# Type definitions for user profiles and experience levels
ExperienceLevel = Literal["new", "some", "pro"]
OrgType = Literal["nonprofit", "school", "business", "government", "other"]


@dataclass
class UserProfile:
    """User profile containing preferences, experience level, and onboarding state."""
    user_id: str
    experience_level: ExperienceLevel
    org_type: OrgType
    primary_goal: str
    region: str
    newsletter_opt_in: bool
    completed_onboarding: bool
    created_at: datetime

    def to_dict(self) -> Dict:
        """Convert profile to dict for persistence."""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        """Create profile from dict, handling datetime conversion."""
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


# Centralized config for secrets/flags (supports package and direct execution contexts)
try:
    from GrantScope import config  # when executed via package context
except Exception:
    try:
        import config  # fallback when executed inside GrantScope/ directly
    except Exception:
        config = None  # type: ignore


def role_label(experience_level: ExperienceLevel) -> str:
    """Convert experience level to user-facing label."""
    labels = {
        "new": "I'm new to grants",
        "some": "I have some experience", 
        "pro": "I'm a grant professional"
    }
    return labels[experience_level]


def is_newbie(profile: Optional[UserProfile]) -> bool:
    """Check if user profile indicates newbie status."""
    if profile is None:
        return True  # Default to newbie if no profile
    return profile.experience_level == "new"


def get_session_profile() -> Optional[UserProfile]:
    """Get user profile from session state."""
    try:
        profile_data = st.session_state.get("user_profile")
        if profile_data and isinstance(profile_data, dict):
            return UserProfile.from_dict(profile_data)
        return None
    except Exception:
        return None


def set_session_profile(profile: UserProfile) -> None:
    """Store user profile in session state."""
    try:
        st.session_state.user_profile = profile.to_dict()
    except Exception:
        pass  # Fail silently if session state unavailable


def init_session_state():
    """Initialize shared session state and clear cached data once per session."""
    if "cache_initialized" not in st.session_state:
        st.session_state.cache_initialized = False
    if not st.session_state.cache_initialized:
        st.cache_data.clear()
        st.session_state.cache_initialized = True

    # Ensure global user role key exists for cross-page persistence
    if "user_role" not in st.session_state:
        st.session_state.user_role = "Grant Analyst/Writer"


def _map_experience_to_role(exp_level: str) -> str:
    """Map experience level to legacy role labels used across pages."""
    return "Grant Analyst/Writer" if exp_level == "pro" else "Normal Grant User"


def sidebar_controls():
    """Render the shared sidebar controls and return (uploaded_file, selected_role, ai_enabled)."""
    # Decide capabilities for navigation (compat across Streamlit versions)
    has_switch = hasattr(st, "switch_page")
    has_page_link = hasattr(st.sidebar, "page_link") or hasattr(st, "page_link")

    # Hide the default Streamlit multipage sidebar list only if we have an alternative
    try:
        if has_switch or has_page_link:
            st.sidebar.markdown(
                "<style>div[data-testid='stSidebarNav'] { display: none; }</style>",
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    # Navigation dropdown (sidebar) — compact and navigates without callbacks
    try:
        st.sidebar.subheader("Navigate")
        # Get profile to filter pages by experience level
        profile = get_session_profile()
        experience_level = profile.experience_level if profile else "new"

        # Show profile summary when available (and feature flag enabled)
        if config is not None and config.is_enabled("GS_ENABLE_NEWBIE_MODE") and profile:
            try:
                st.sidebar.markdown("**Experience:** " + role_label(experience_level))
            except Exception:
                pass
        
        # Base pages available to all users
        pages = {
            "Grant Advisor Interview": "0_Grant_Advisor_Interview.py",
            "Data Summary": "1_Data_Summary.py",
            "Grant Amount Distribution": "2_Grant_Amount_Distribution.py",
            "Grant Amount Heatmap": "3_Grant_Amount_Heatmap.py",
            "Grant Amount Scatter Plot": "4_Grant_Amount_Scatter_Plot.py",
            "Grant Description Word Clouds": "5_Grant_Description_Word_Clouds.py",
            "Treemaps with Extended Analysis": "6_Treemaps_Extended_Analysis.py",
            "General Analysis of Relationships": "7_General_Analysis_of_Relationships.py",
            "Top Categories by Unique Grant Count": "8_Top_Categories_Unique_Grants.py",
        }
        
        # Add newbie-friendly pages if enabled
        if config is not None and config.is_enabled("GS_ENABLE_NEW_PAGES"):
            new_pages = {
                "Project Planner": "9_Project_Planner.py",
                "Timeline Advisor": "10_Timeline_Advisor.py",
                "Success Stories": "11_Success_Stories.py",
                "Budget Reality Check": "12_Budget_Reality_Check.py",
            }
            
            # Filter pages based on experience level
            if experience_level == "new":
                # Newbies get all the helpful tools
                pages.update(new_pages)
            elif experience_level == "some":
                # Experienced users get planning tools
                pages.update({
                    "Project Planner": "9_Project_Planner.py",
                    "Timeline Advisor": "10_Timeline_Advisor.py",
                    "Budget Reality Check": "12_Budget_Reality_Check.py",
                })
            # Pros don't get the guided pages by default

        # The explicit "Go to page" dropdown and single-page link were removed
        # in favor of a simpler Quick navigation section below, which is more
        # reliable across Streamlit versions and avoids duplicate navigation UI.

        # Optional: quick links to all pages when page_link exists
        if has_page_link:
            with st.sidebar.expander("Quick navigation", expanded=False):
                for label, fname in pages.items():
                    try:
                        st.page_link(f"pages/{fname}", label=label)
                    except Exception:
                        # Some versions only support sidebar.page_link
                        try:
                            st.sidebar.page_link(f"pages/{fname}", label=label)
                        except Exception:
                            pass
    except Exception:
        # Navigation dropdown is optional; ignore failures on older Streamlit versions
        pass

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

    # Prefer st.secrets before any UI input; then fall back to env/.env via config
    resolved_key = None
    if config is not None:
        try:
            resolved_key = config.get_openai_api_key()
        except Exception:
            resolved_key = None

    user_key = None
    if not resolved_key:
        user_key = st.sidebar.text_input("Enter your OpenAI API Key:", type="password")
        if user_key:
            # Do not persist in session or secrets; set process env for current run only
            if not os.getenv("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = user_key
            # Optionally refresh config cache so downstream getters see the newly-set env
            if config is not None:
                try:
                    config.refresh_cache()
                except Exception:
                    pass

    ai_enabled = bool(resolved_key or user_key)
    if not ai_enabled:
        st.sidebar.warning(
            "AI features are disabled. Provide an API key via Streamlit secrets, environment, "
            "or one-time input to enable AI-assisted analysis. Keys are never persisted."
        )

    # Determine selected_role based on profile if Newbie Mode is enabled
    if config is not None and config.is_enabled("GS_ENABLE_NEWBIE_MODE"):
        prof = get_session_profile()
        if prof is not None:
            selected_role = _map_experience_to_role(prof.experience_level)
        else:
            # Fallback to legacy selector if no profile yet
            user_roles = ["Grant Analyst/Writer", "Normal Grant User"]
            selected_role = st.sidebar.selectbox(
                "Select User Role",
                options=user_roles,
                index=user_roles.index(st.session_state.get("user_role", user_roles[0])),
                key="user_role",
            )
    else:
        # Legacy role selector when Newbie Mode disabled
        user_roles = ["Grant Analyst/Writer", "Normal Grant User"]
        selected_role = st.sidebar.selectbox(
            "Select User Role",
            options=user_roles,
            index=user_roles.index(st.session_state.get("user_role", user_roles[0])),
            key="user_role",
        )

    # Add help/glossary access if enabled
    if config is not None and config.is_enabled("GS_ENABLE_PLAIN_HELPERS"):
        try:
            from utils.help import render_glossary_search
            render_glossary_search()
        except Exception:
            pass
    
    # Add reset onboarding button for testing/user preference
    if config is not None and config.is_enabled("GS_ENABLE_NEWBIE_MODE") and profile:
        st.sidebar.markdown("---")
        if st.sidebar.button("🔄 Reset Setup", help="Start the setup process again"):
            try:
                from utils.onboarding import OnboardingWizard
                OnboardingWizard.reset_onboarding()
                st.rerun()
            except Exception:
                pass
    
    # Flexible spacer to push the chat panel to the bottom of the sidebar viewport
    try:
        st.sidebar.markdown('<div class="gs-sidebar-spacer"></div>', unsafe_allow_html=True)
    except Exception:
        pass

    return uploaded_file, selected_role, ai_enabled


@st.cache_data
def _load_and_preprocess(file_path: str | None, file_bytes):
    grants = load_data(file_path=file_path, uploaded_file=file_bytes)
    return preprocess_data(grants)


def get_data(uploaded_file):
    try:
        if uploaded_file is not None:
            df, grouped_df = _load_and_preprocess(None, uploaded_file)
        else:
            df, grouped_df = _load_and_preprocess('data/sample.json', None)
        return df, grouped_df, None
    except (OSError, ValueError, KeyError) as e:
        return None, None, str(e)


def set_selected_chart(chart_id: str) -> None:
    """Set the globally selected chart identifier for the current page/view."""
    try:
        st.session_state["selected_chart_id"] = str(chart_id)
    except Exception:
        # If session state is unavailable, fail silently
        pass


def get_selected_chart(default: str | None = None) -> str | None:
    """Get the globally selected chart identifier, or the provided default if unset."""
    try:
        val = st.session_state.get("selected_chart_id", default)
        return str(val) if val is not None else None
    except Exception:
        return default
