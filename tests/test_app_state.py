"""
Tests for app_state profile functionality.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from utils.app_state import UserProfile, role_label, is_newbie


def test_user_profile_creation():
    """Test creating a UserProfile."""
    profile = UserProfile(
        user_id="test123",
        experience_level="new",
        org_type="nonprofit",
        primary_goal="Fund programs",
        region="California",
        newsletter_opt_in=True,
        completed_onboarding=True,
        created_at=datetime.now()
    )
    
    assert profile.user_id == "test123"
    assert profile.experience_level == "new"
    assert profile.org_type == "nonprofit"


def test_user_profile_serialization():
    """Test UserProfile to_dict and from_dict."""
    now = datetime.now()
    profile = UserProfile(
        user_id="test123",
        experience_level="some",
        org_type="school",
        primary_goal="Education funding",
        region="New York",
        newsletter_opt_in=False,
        completed_onboarding=True,
        created_at=now
    )
    
    # Test to_dict
    data = profile.to_dict()
    assert isinstance(data, dict)
    assert data["user_id"] == "test123"
    assert data["experience_level"] == "some"
    assert isinstance(data["created_at"], str)  # Should be ISO string
    
    # Test from_dict
    restored = UserProfile.from_dict(data)
    assert restored.user_id == profile.user_id
    assert restored.experience_level == profile.experience_level
    assert restored.created_at.replace(microsecond=0) == now.replace(microsecond=0)


def test_role_label():
    """Test role_label function."""
    assert role_label("new") == "I'm new to grants"
    assert role_label("some") == "I have some experience"
    assert role_label("pro") == "I'm a grant professional"


def test_is_newbie():
    """Test is_newbie function."""
    # None profile should be considered newbie
    assert is_newbie(None) is True
    
    # New experience level should be newbie
    profile_new = UserProfile(
        user_id="test",
        experience_level="new",
        org_type="nonprofit",
        primary_goal="test",
        region="test",
        newsletter_opt_in=False,
        completed_onboarding=True,
        created_at=datetime.now()
    )
    assert is_newbie(profile_new) is True
    
    # Other experience levels should not be newbie
    profile_some = UserProfile(
        user_id="test",
        experience_level="some",
        org_type="nonprofit",
        primary_goal="test",
        region="test",
        newsletter_opt_in=False,
        completed_onboarding=True,
        created_at=datetime.now()
    )
    assert is_newbie(profile_some) is False
    
    profile_pro = UserProfile(
        user_id="test",
        experience_level="pro",
        org_type="nonprofit",
        primary_goal="test",
        region="test",
        newsletter_opt_in=False,
        completed_onboarding=True,
        created_at=datetime.now()
    )
    assert is_newbie(profile_pro) is False


def test_profile_functions_logic():
    """Test the core logic of profile functions without Streamlit dependencies."""
    # Test that profile serialization works correctly
    now = datetime.now()
    profile = UserProfile(
        user_id="test123",
        experience_level="new",
        org_type="nonprofit",
        primary_goal="Test goal",
        region="Test region",
        newsletter_opt_in=True,
        completed_onboarding=True,
        created_at=now
    )
    
    # Test serialization round trip
    data = profile.to_dict()
    restored = UserProfile.from_dict(data)
    
    assert restored.user_id == profile.user_id
    assert restored.experience_level == profile.experience_level
    assert restored.org_type == profile.org_type
    assert restored.primary_goal == profile.primary_goal
