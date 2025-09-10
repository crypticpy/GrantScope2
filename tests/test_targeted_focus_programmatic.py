import pandas as pd

from advisor.pipeline.metrics import _metric_targeted_focus
from advisor.schemas import StructuredNeeds


def test_metric_targeted_focus_programmatic():
    df = pd.DataFrame(
        [
            {
                "grant_subject_tran": "Education services",
                "grant_population_tran": "Students",
                "grant_geo_area_tran": "Austin",
                "amount_usd": 55000,
            },
            {
                "grant_subject_tran": "Education services",
                "grant_population_tran": "Students",
                "grant_geo_area_tran": "Austin",
                "amount_usd": 55593,
            },
            {
                "grant_subject_tran": "Youth development",
                "grant_population_tran": "Children and youth",
                "grant_geo_area_tran": "Austin",
                "amount_usd": 80000,
            },
        ]
    )
    needs = StructuredNeeds(subjects=["education"], populations=["students"], geographies=["TX"])
    md = _metric_targeted_focus(df, needs)
    assert "Education services" in md
    assert "Students" in md
    assert "Total Amount" in md
