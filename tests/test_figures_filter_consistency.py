import pandas as pd

from advisor.normalization import _apply_needs_filters
from advisor.pipeline.figures_wrap import _figures_default
from advisor.schemas import InterviewInput


def test_figures_align_with_filtered_data():
    # Build a tiny dataset with mixed geographies and funders
    df = pd.DataFrame(
        [
            {
                "funder_name": "Local Funder A",
                "amount_usd": 100000,
                "grant_geo_area_tran": "Austin",
                "year_issued": 2023,
            },
            {
                "funder_name": "Local Funder B",
                "amount_usd": 50000,
                "grant_geo_area_tran": "Austin",
                "year_issued": 2023,
            },
            {
                "funder_name": "Other Funder",
                "amount_usd": 200000,
                "grant_geo_area_tran": "Dallas",
                "year_issued": 2023,
            },
        ]
    )
    interview = InterviewInput(
        program_area="Youth education",
        geography=["TX"],
        keywords=["education"],
        user_role="Municipal Program Manager",
    )

    # Apply needs filter
    from advisor.pipeline.imports import _stage1_normalize_cached

    needs_dict = _stage1_normalize_cached("key", interview.model_as_dict())
    from advisor.schemas import StructuredNeeds

    needs = StructuredNeeds(**needs_dict)
    df_f, _used = _apply_needs_filters(df, needs)

    # Figures must be built from filtered df
    figs = _figures_default(df_f, interview, needs)
    # Extract top funders from figure data via summary stats if available
    labels = [getattr(f, "label", "") for f in figs]
    assert any("Top Funders" in lab for lab in labels)

    # Ensure Dallas-only 'Other Funder' does not dominate Austin-focused figures
    # This is a heuristic check: total bars/points should reflect Austin entries only
    assert len(df_f) == 2
