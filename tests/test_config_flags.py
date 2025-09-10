"""
Tests for config flags functionality.
"""

import os
from unittest.mock import patch

import config


def test_default_flag_values():
    """Test that new flags have correct default values."""
    assert config.is_enabled("GS_ENABLE_NEWBIE_MODE") is False
    assert config.is_enabled("GS_ENABLE_PLAIN_HELPERS") is False
    assert config.is_enabled("GS_ENABLE_NEW_PAGES") is False
    assert config.is_enabled("GS_ENABLE_AI_AUGMENTATION") is False


def test_is_enabled_helper():
    """Test the is_enabled helper function."""
    # Test with existing flag
    assert config.is_enabled("GS_ENABLE_CHAT_STREAMING") is False

    # Test with nonexistent flag
    assert config.is_enabled("NONEXISTENT_FLAG") is False


def test_feature_flags_dict():
    """Test that feature_flags dict contains all expected flags."""
    flags = config.feature_flags()

    expected_flags = {
        "GS_ENABLE_CHAT_STREAMING",
        "GS_ENABLE_LEGACY_ROUTER",
        "GS_ENABLE_NEWBIE_MODE",
        "GS_ENABLE_PLAIN_HELPERS",
        "GS_ENABLE_NEW_PAGES",
        "GS_ENABLE_AI_AUGMENTATION",
    }

    assert set(flags.keys()) == expected_flags

    # All should be False by default
    for flag, value in flags.items():
        assert value is False


@patch.dict(os.environ, {"GS_ENABLE_NEWBIE_MODE": "1"})
def test_env_override():
    """Test that environment variables can enable flags."""
    config.refresh_cache()  # Clear cache to pick up env changes
    assert config.is_enabled("GS_ENABLE_NEWBIE_MODE") is True


@patch.dict(os.environ, {"GS_ENABLE_NEWBIE_MODE": "true"})
def test_env_override_various_truthy():
    """Test that various truthy values work."""
    config.refresh_cache()
    assert config.is_enabled("GS_ENABLE_NEWBIE_MODE") is True


@patch.dict(os.environ, {"GS_ENABLE_NEWBIE_MODE": "false"})
def test_env_override_falsy():
    """Test that falsy values work."""
    config.refresh_cache()
    assert config.is_enabled("GS_ENABLE_NEWBIE_MODE") is False


def test_require_flag_enabled():
    """Test require_flag returns True when flag is enabled."""
    with patch("config.is_enabled", return_value=True):
        result = config.require_flag("TEST_FLAG", "Test message")
        assert result is True


def test_require_flag_disabled():
    """Test require_flag returns False when flag is disabled."""
    with patch("config.is_enabled", return_value=False):
        result = config.require_flag("TEST_FLAG", "Test message")
        assert result is False


def test_cache_refresh():
    """Test that cache refresh works without errors."""
    config.refresh_cache()  # Should not raise any exceptions
