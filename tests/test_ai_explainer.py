"""
Tests for the AI explainer functionality and gating.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from utils.ai_explainer import render_ai_explainer, _audience_preface


class TestAIExplainer:
    """Test the AI explainer functionality."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample dataframe for testing."""
        return pd.DataFrame({
            'grant_key': ['g1', 'g2', 'g3'],
            'funder_name': ['Funder A', 'Funder B', 'Funder C'],
            'amount_usd': [10000, 5000, 15000],
        })

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('streamlit.info')
    def test_ai_disabled_no_key(self, mock_info, mock_get_key, sample_df):
        """Test that render_ai_explainer does nothing when no API key is present."""
        mock_get_key.return_value = None
        
        # Should not render anything
        render_ai_explainer(sample_df, "test prompt")
        
        # Should not show any UI components
        mock_info.assert_not_called()

    @patch('utils.ai_explainer.config.get_openai_api_key')
    def test_ai_disabled_explicit(self, mock_get_key, sample_df):
        """Test that render_ai_explainer respects explicit ai_enabled=False."""
        mock_get_key.return_value = "test-key"
        
        # Should not render anything when explicitly disabled
        render_ai_explainer(sample_df, "test prompt", ai_enabled=False)
        
        # No assertions needed - just checking it doesn't crash

    @patch('utils.ai_explainer.get_session_profile')
    def test_audience_preface_newbie(self, mock_profile):
        """Test that audience preface adapts to newbie experience level."""
        mock_prof = MagicMock()
        mock_prof.experience_level = "new"
        mock_profile.return_value = mock_prof
        
        preface = _audience_preface()
        assert "new to grants" in preface.lower()
        assert "short sentences" in preface.lower()
        assert "next steps" in preface.lower()

    @patch('utils.ai_explainer.get_session_profile')
    def test_audience_preface_pro(self, mock_profile):
        """Test that audience preface adapts to professional experience level."""
        mock_prof = MagicMock()
        mock_prof.experience_level = "pro"
        mock_profile.return_value = mock_prof
        
        preface = _audience_preface()
        assert "concise" in preface.lower()
        assert "experienced" in preface.lower()

    @patch('utils.ai_explainer.get_session_profile')
    def test_audience_preface_no_profile(self, mock_profile):
        """Test that audience preface handles missing profile gracefully."""
        mock_profile.return_value = None
        
        preface = _audience_preface()
        assert "concise" in preface.lower()  # Should default to pro style

    @patch('utils.ai_explainer.get_session_profile')
    def test_audience_preface_exception(self, mock_profile):
        """Test that audience preface handles exceptions gracefully."""
        mock_profile.side_effect = Exception("Profile error")
        
        preface = _audience_preface()
        assert "concise" in preface.lower()  # Should default to pro style

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('utils.ai_explainer.tool_query')
    @patch('streamlit.expander')
    @patch('streamlit.caption')
    @patch('streamlit.markdown')
    def test_ai_enabled_success(self, mock_markdown, mock_caption, mock_expander, mock_tool_query, mock_get_key, sample_df):
        """Test successful AI explainer rendering."""
        mock_get_key.return_value = "test-key"
        mock_tool_query.return_value = "This is an AI explanation"
        
        # Mock streamlit expander context manager
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()
        
        render_ai_explainer(sample_df, "test prompt", chart_id="test.chart")
        
        # Should call tool_query
        mock_tool_query.assert_called_once()
        
        # Should render expander
        mock_expander.assert_called_once_with("🤖 AI Explainer", expanded=False)
        
        # Should show chart ID and content
        mock_caption.assert_called_once_with("Context: test.chart")
        mock_markdown.assert_called_once_with("This is an AI explanation")

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('utils.ai_explainer.tool_query')
    @patch('streamlit.info')
    def test_ai_query_error(self, mock_info, mock_tool_query, mock_get_key, sample_df):
        """Test handling of tool_query errors."""
        mock_get_key.return_value = "test-key"
        mock_tool_query.side_effect = Exception("Query failed")
        
        render_ai_explainer(sample_df, "test prompt")
        
        # Should show error message
        mock_info.assert_called_once_with("AI explainer unavailable: Query failed")

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('utils.ai_explainer.tool_query')
    @patch('utils.ai_explainer._audience_preface')
    def test_prompt_construction(self, mock_preface, mock_tool_query, mock_get_key, sample_df):
        """Test that prompts are constructed properly with audience context."""
        mock_get_key.return_value = "test-key"
        mock_preface.return_value = "Be simple and clear."
        mock_tool_query.return_value = "Test response"
        
        render_ai_explainer(sample_df, "base prompt", extra_ctx="extra context")
        
        # Verify tool_query was called with constructed prompt
        args, kwargs = mock_tool_query.call_args
        df_arg, query_arg, prompt_arg, extra_arg = args
        
        assert df_arg is sample_df
        assert query_arg == "Explain this view."
        assert "Be simple and clear." in prompt_arg
        assert "base prompt" in prompt_arg
        assert "What it shows" in prompt_arg  # Part of instruction
        assert extra_arg == "extra context"

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('utils.ai_explainer.tool_query')
    def test_sample_df_usage(self, mock_tool_query, mock_get_key, sample_df):
        """Test that sample_df is used when provided."""
        mock_get_key.return_value = "test-key"
        mock_tool_query.return_value = "Test response"
        
        sample_subset = sample_df.head(1)
        render_ai_explainer(sample_df, "test prompt", sample_df=sample_subset)
        
        # Should use sample_subset instead of full df
        args, kwargs = mock_tool_query.call_args
        df_arg = args[0]
        assert len(df_arg) == 1  # Should be the sample subset

    @patch('utils.ai_explainer.config.get_openai_api_key')
    @patch('utils.ai_explainer.tool_query')
    @patch('streamlit.expander')
    def test_custom_title(self, mock_expander, mock_tool_query, mock_get_key, sample_df):
        """Test that custom title is used."""
        mock_get_key.return_value = "test-key"
        mock_tool_query.return_value = "Test response"
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()
        
        render_ai_explainer(sample_df, "test prompt", title="Custom Title")
        
        mock_expander.assert_called_once_with("Custom Title", expanded=False)

    @patch('utils.ai_explainer.config.get_openai_api_key')
    def test_exception_handling(self, mock_get_key, sample_df):
        """Test that the function handles exceptions gracefully."""
        mock_get_key.side_effect = Exception("Config error")
        
        # Should not raise an exception
        try:
            render_ai_explainer(sample_df, "test prompt")
        except Exception as e:
            pytest.fail(f"render_ai_explainer raised an exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
