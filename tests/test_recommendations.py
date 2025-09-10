"""
Tests for the recommendations engine.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from utils.recommendations import GrantRecommender, Recommendation


class TestGrantRecommender:
    """Test the recommendations engine."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample dataframe for testing."""
        return pd.DataFrame(
            {
                "grant_key": ["g1", "g2", "g3", "g4", "g5"],
                "funder_name": ["Funder A", "Funder B", "Funder A", "Funder C", "Funder A"],
                "amount_usd": [10000, 5000, 15000, 8000, 12000],
                "year_issued": [2023, 2022, 2023, 2021, 2023],
                "grant_subject_tran": ["Education", "Health", "Education", "Arts", "Health"],
            }
        )

    def test_top_funders_calculation(self, sample_df):
        """Test that top funders are calculated correctly."""
        recommender = GrantRecommender(sample_df)
        top_funders = recommender._top_funders(sample_df, n=3)

        # Funder A should be first with 37000 total
        # Funder C second with 8000
        # Funder B third with 5000
        assert len(top_funders) == 3
        assert top_funders[0] == "Funder A"
        assert "Funder B" in top_funders
        assert "Funder C" in top_funders

    def test_recent_year_calculation(self, sample_df):
        """Test that most recent year is found correctly."""
        recommender = GrantRecommender(sample_df)
        recent_year = recommender._recent_year(sample_df)
        assert recent_year == 2023

    def test_amount_stats_calculation(self, sample_df):
        """Test that amount statistics are calculated correctly."""
        recommender = GrantRecommender(sample_df)
        stats = recommender._amount_stats(sample_df)

        assert "median" in stats
        assert "p25" in stats
        assert "p75" in stats
        assert "min" in stats
        assert "max" in stats

        # Check values
        assert stats["min"] == 5000
        assert stats["max"] == 15000
        assert stats["median"] == 10000  # Middle value

    def test_data_first_recommendations(self, sample_df):
        """Test that data-first recommendations are generated."""
        recommender = GrantRecommender(sample_df)
        recommendations = recommender.data_first()

        assert len(recommendations) > 0
        assert all(isinstance(rec, Recommendation) for rec in recommendations)
        assert all(rec.source == "data" for rec in recommendations)

        # Check that we get expected recommendation types
        rec_ids = [rec.id for rec in recommendations]
        assert "budget_range" in rec_ids
        assert "top_funders" in rec_ids
        assert "recent_year" in rec_ids

    def test_data_first_with_context(self, sample_df):
        """Test that context affects recommendations."""
        recommender = GrantRecommender(sample_df)
        context = {"selected_clusters": ["Small", "Medium"]}
        recommendations = recommender.data_first(context)

        rec_ids = [rec.id for rec in recommendations]
        assert "clusters_focus" in rec_ids

    def test_empty_dataframe_handling(self):
        """Test that empty dataframes are handled gracefully."""
        empty_df = pd.DataFrame()
        recommender = GrantRecommender(empty_df)

        # These should return empty/default values without error
        assert recommender._top_funders(empty_df) == []
        assert recommender._recent_year(empty_df) is None
        assert recommender._amount_stats(empty_df) == {}
        assert recommender.data_first() == []

    def test_missing_columns_handling(self):
        """Test that missing columns are handled gracefully."""
        minimal_df = pd.DataFrame({"other_col": [1, 2, 3]})
        recommender = GrantRecommender(minimal_df)

        # These should return empty/default values without error
        assert recommender._top_funders(minimal_df) == []
        assert recommender._recent_year(minimal_df) is None
        assert recommender._amount_stats(minimal_df) == {}

    @patch("utils.recommendations.config.is_enabled")
    @patch("utils.recommendations.get_openai_client")
    def test_ai_augmentation_disabled_by_flag(self, mock_client, mock_is_enabled, sample_df):
        """Test that AI augmentation respects feature flag."""
        mock_is_enabled.return_value = False

        recommender = GrantRecommender(sample_df)
        base_recs = [Recommendation("test", "Test", "Test reason", 0.9, "data")]

        result = recommender.augment_with_ai(base_recs)
        assert result == base_recs  # Should return unchanged
        mock_client.assert_not_called()

    @patch("utils.recommendations.config.is_enabled")
    @patch("utils.recommendations.get_openai_client")
    def test_ai_augmentation_no_client(self, mock_client, mock_is_enabled, sample_df):
        """Test that AI augmentation handles missing client gracefully."""
        mock_is_enabled.return_value = True
        mock_client.side_effect = Exception("No API key")

        recommender = GrantRecommender(sample_df)
        base_recs = [Recommendation("test", "Test", "Test reason", 0.9, "data")]

        result = recommender.augment_with_ai(base_recs)
        assert result == base_recs  # Should return unchanged on error

    @patch("utils.recommendations.config.is_enabled")
    @patch("utils.recommendations.get_openai_client")
    @patch("utils.recommendations.config.get_model_name")
    def test_ai_augmentation_success(
        self, mock_model_name, mock_client, mock_is_enabled, sample_df
    ):
        """Test successful AI augmentation."""
        mock_is_enabled.return_value = True
        mock_model_name.return_value = "gpt-4"

        # Mock OpenAI client response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "AI-generated suggestion"
        mock_client.return_value.chat.completions.create.return_value = mock_response

        recommender = GrantRecommender(sample_df)
        base_recs = [Recommendation("test", "Test", "Test reason", 0.9, "data")]

        result = recommender.augment_with_ai(base_recs, {"experience_level": "new"})

        # Should have original plus AI recommendation
        assert len(result) == len(base_recs) + 1
        assert result[-1].source == "ai"
        assert result[-1].id == "ai_augmented"

    def test_recommendations_sorted_by_score(self, sample_df):
        """Test that recommendations are sorted by score in descending order."""
        recommender = GrantRecommender(sample_df)
        recommendations = recommender.data_first()

        # Check that scores are in descending order
        scores = [rec.score for rec in recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_recommendations_limited_count(self, sample_df):
        """Test that recommendations are limited to a reasonable number."""
        recommender = GrantRecommender(sample_df)
        recommendations = recommender.data_first()

        # Should not exceed 6 recommendations
        assert len(recommendations) <= 6

    @patch("streamlit.expander")
    @patch("streamlit.write")
    def test_render_panel_integration(self, mock_write, mock_expander, sample_df):
        """Test that the render_panel method can be called without error."""
        # This is an integration test to ensure the static method works
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        try:
            GrantRecommender.render_panel(sample_df)
        except Exception as e:
            # Should not raise exceptions during normal operation
            pytest.fail(f"render_panel raised an exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
