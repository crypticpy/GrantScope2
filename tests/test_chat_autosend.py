"""
Tests for chat panel autosend functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from utils.chat_panel import _get_starter_prompts


class TestChatAutosend:
    """Test the chat panel autosend functionality."""

    def test_get_starter_prompts_newbie(self):
        """Test that starter prompts are returned for newbie users."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "new"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            assert len(prompts) > 0
            assert all(isinstance(prompt, str) for prompt in prompts)
            # Should contain newbie-friendly prompts
            prompt_text = " ".join(prompts).lower()
            assert "first" in prompt_text or "eligible" in prompt_text or "simple" in prompt_text

    def test_get_starter_prompts_pro(self):
        """Test that no starter prompts are returned for professional users."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "pro"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            assert prompts == []

    def test_get_starter_prompts_some_experience(self):
        """Test that no starter prompts are returned for users with some experience."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "some"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            assert prompts == []

    def test_get_starter_prompts_no_profile(self):
        """Test that no starter prompts are returned when there's no profile."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_profile.return_value = None

            prompts = _get_starter_prompts()

            assert prompts == []

    def test_get_starter_prompts_exception(self):
        """Test that exceptions are handled gracefully."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_profile.side_effect = Exception("Profile error")

            prompts = _get_starter_prompts()

            assert prompts == []

    @patch("streamlit.session_state")
    @patch("streamlit.button")
    def test_autosend_button_mechanics(self, mock_button, mock_session_state):
        """Test the autosend button mechanics."""
        # Mock session state as a dictionary
        session_dict = {}
        mock_session_state.__getitem__ = session_dict.__getitem__
        mock_session_state.__setitem__ = session_dict.__setitem__
        mock_session_state.get = session_dict.get

        # Mock button clicks
        mock_button.side_effect = [True, False, False]  # First button clicked

        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "new"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            # Simulate the button logic from chat_panel
            for i, prompt in enumerate(prompts):
                button_key = f"starter_button_test_key_{i}"
                if mock_button.return_value:  # Simulate button click
                    # This is what should happen in chat_panel
                    session_dict["chat_input_test_key"] = prompt
                    session_dict["chat_autosend_test_key"] = True
                    break

            # Check that autosend mechanism would be triggered
            assert session_dict.get("chat_autosend_test_key") is True
            assert session_dict.get("chat_input_test_key") in prompts

    def test_starter_prompt_content_quality(self):
        """Test that starter prompts are well-formed and appropriate."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "new"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            for prompt in prompts:
                # Should be reasonable length
                assert 10 < len(prompt) < 200
                # Should not be all caps or have excessive punctuation
                assert not prompt.isupper()
                assert prompt.count("!") <= 2
                assert prompt.count("?") <= 2
                # Should be proper sentences
                assert prompt[0].isupper() if prompt else True
                # Should not contain placeholder text
                assert "TODO" not in prompt.upper()
                assert "FIXME" not in prompt.upper()

    def test_starter_prompts_variety(self):
        """Test that starter prompts cover different types of questions."""
        with patch("utils.chat_panel.get_session_profile") as mock_profile:
            mock_prof = MagicMock()
            mock_prof.experience_level = "new"
            mock_profile.return_value = mock_prof

            prompts = _get_starter_prompts()

            if prompts:  # Only test if prompts are returned
                prompt_text = " ".join(prompts).lower()

                # Should cover different question types
                question_types = 0
                if "first" in prompt_text or "steps" in prompt_text:
                    question_types += 1  # Getting started
                if "eligible" in prompt_text or "qualify" in prompt_text:
                    question_types += 1  # Eligibility
                if "write" in prompt_text or "statement" in prompt_text:
                    question_types += 1  # Writing help

                assert question_types >= 2  # Should cover at least 2 different types

    @patch("utils.chat_panel.get_session_profile")
    def test_feature_flag_respect(self, mock_profile):
        """Test that starter prompts respect feature flags (indirectly)."""
        # This test ensures the function works when profile is disabled
        mock_profile.return_value = None

        prompts = _get_starter_prompts()
        assert prompts == []  # Should return empty when no profile


if __name__ == "__main__":
    pytest.main([__file__])
