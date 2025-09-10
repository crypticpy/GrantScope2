import pandas as pd

from utils.utils import generate_page_prompt


def test_generate_page_prompt_includes_guardrails_and_known_columns():
    df = pd.DataFrame(
        {
            "funder_name": ["A", "B"],
            "recip_name": ["X", "Y"],
            "amount_usd": [100.0, 200.0],
            "last_updated": ["2024-01-01", "2024-02-01"],
            "funder_state": ["TX", "CA"],
            "grant_key": ["G1", "G2"],
        }
    )

    prompt = generate_page_prompt(
        df=df,
        _grouped_df=df,
        selected_chart="Data Summary",
        selected_role="Grant Analyst/Writer",
        additional_context="testing",
        current_filters={"example_filter": "value"},
        sample_df=df.head(1),
    )

    # Guardrails and schema grounding
    assert "Known Columns:" in prompt
    assert "Guardrails:" in prompt
    assert "not available in the dataset" in prompt

    # Context grounding
    assert "Current Filters:" in prompt
    assert "Sample Context" in prompt
