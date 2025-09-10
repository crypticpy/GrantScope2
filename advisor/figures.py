"""
Figure builders for the Advisor pipeline.

These functions return Plotly figure objects. The pipeline will wrap them
into FigureArtifact with PNG/HTML for export as needed.
"""

from __future__ import annotations

from typing import Any

# Use centralized normalization for consistent filtering between metrics and figures
try:
    from GrantScope.advisor.normalization import _apply_needs_filters  # type: ignore
except Exception:  # pragma: no cover
    from advisor.normalization import _apply_needs_filters  # type: ignore

import pandas as pd

# Plotly import with defensive fallback to avoid hard failures during tests
px: Any  # Help static analyzers; will be set by import below

try:
    import plotly.express as px  # type: ignore
except Exception:  # pragma: no cover
    px = None  # type: ignore

# Streamlit (optional) for caching deterministic prep steps
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover

    class _NoStreamlit:  # type: ignore
        def cache_data(self, show_spinner: bool = False):
            def decorator(fn):
                return fn

            return decorator

    st = _NoStreamlit()  # type: ignore

# Apply a professional Plotly template and color palette globally (if Plotly is available)
try:
    if px is not None:
        px.defaults.template = "seaborn"
        # Use a qualitative palette with good print/export legibility
        from plotly.colors import qualitative as _qual  # type: ignore

        px.defaults.color_discrete_sequence = _qual.Set2
except Exception:
    # Ignore palette errors; figures will fall back to Plotly defaults
    pass


def _ensure_plotly() -> None:
    if px is None:  # pragma: no cover
        raise RuntimeError("plotly is not available. Install plotly to render Advisor figures.")


def _has_field(df: pd.DataFrame, col: str, min_nonnull_ratio: float = 0.01) -> bool:
    """Return True if a column exists and has at least a minimal fraction of non-null values."""
    try:
        return (col in df.columns) and (df[col].notna().mean() >= min_nonnull_ratio)
    except Exception:
        return col in df.columns


def _safe_copy_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return df.copy()
    except Exception:
        return df


def _filter_by_needs(df: pd.DataFrame, needs) -> pd.DataFrame:
    """Apply the same normalization filter used by metrics to keep figures consistent.

    This delegates to advisor.normalization._apply_needs_filters, which expands tokens
    (e.g., tx->Texas/Austin; education->Education services) and gracefully degrades if
    filters would eliminate all rows.
    """
    try:
        filtered, _used = _apply_needs_filters(df, needs)
        return filtered
    except Exception:
        return df


@st.cache_data(show_spinner=False)
def _prep_top_funders(df: pd.DataFrame, needs) -> pd.DataFrame:
    """Deterministic prep: aggregate top funders by amount."""
    data = _filter_by_needs(df, needs)
    if "funder_name" not in data.columns or "amount_usd" not in data.columns:
        return pd.DataFrame({"funder_name": ["N/A"], "amount_usd": [0.0]})
    try:
        grp = (
            data.groupby("funder_name", dropna=False)["amount_usd"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        return grp
    except Exception:
        return pd.DataFrame({"funder_name": ["N/A"], "amount_usd": [0.0]})


@st.cache_data(show_spinner=False)
def _prep_distribution(df: pd.DataFrame, needs) -> pd.DataFrame:
    """Deterministic prep: ensure a clean numeric series for amount_usd."""
    data = _filter_by_needs(df, needs)
    if "amount_usd" not in data.columns:
        return pd.DataFrame({"amount_usd": [0.0]})
    try:
        s = pd.to_numeric(data["amount_usd"], errors="coerce").dropna()
        return pd.DataFrame({"amount_usd": s})
    except Exception:
        return pd.DataFrame({"amount_usd": [0.0]})


@st.cache_data(show_spinner=False)
def _prep_time_trend(df: pd.DataFrame, needs) -> pd.DataFrame:
    """Deterministic prep: sum of amounts by year_issued."""
    data = _filter_by_needs(df, needs)
    if "year_issued" not in data.columns or "amount_usd" not in data.columns:
        return pd.DataFrame({"year_issued": [], "amount_usd": []})
    try:
        yrs = pd.to_numeric(data["year_issued"], errors="coerce")
        tmp = data.copy()
        tmp["__year__"] = yrs
        agg = (
            tmp.groupby("__year__", dropna=False)["amount_usd"]
            .sum()
            .reset_index()
            .rename(columns={"__year__": "year_issued"})
        )
        agg = agg.dropna(subset=["year_issued"])
        try:
            agg["year_issued"] = agg["year_issued"].astype(int)
        except Exception:
            pass
        return agg
    except Exception:
        return pd.DataFrame({"year_issued": ["N/A"], "amount_usd": [0.0]})


def figure_top_funders_bar(df: pd.DataFrame, needs) -> Any:
    """Bar chart: Top funders by total amount."""
    _ensure_plotly()
    data = _prep_top_funders(df, needs)
    fig = px.bar(
        data,
        x="amount_usd",
        y="funder_name",
        orientation="h",
        title="Top Funders by Total Amount (Top 10)",
        labels={"amount_usd": "Total Amount (USD)", "funder_name": "Funder"},
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=80, r=20, t=60, b=40),
        legend_title_text="",
    )
    # Currency formatting for readability
    try:
        fig.update_xaxes(tickprefix="$", separatethousands=True)
    except Exception:
        pass
    return fig


def figure_amount_distribution(df: pd.DataFrame, needs) -> Any:
    """Histogram of grant amounts with marginal box plot."""
    _ensure_plotly()
    data = _prep_distribution(df, needs)
    fig = px.histogram(
        data,
        x="amount_usd",
        nbins=30,
        title="Distribution of Grant Amounts",
        labels={"amount_usd": "Amount (USD)"},
        marginal="box",
    )
    fig.update_layout(margin=dict(l=40, r=20, t=60, b=40), bargap=0.05)
    try:
        fig.update_xaxes(tickprefix="$", separatethousands=True)
    except Exception:
        pass
    return fig


def figure_time_trend(df: pd.DataFrame, needs) -> Any:
    """Line chart: Sum of amounts by year_issued."""
    _ensure_plotly()
    data = _prep_time_trend(df, needs)
    fig = px.line(
        data,
        x="year_issued",
        y="amount_usd",
        markers=True,
        title="Total Amount by Year Issued",
        labels={"year_issued": "Year", "amount_usd": "Total Amount (USD)"},
    )
    fig.update_layout(margin=dict(l=40, r=20, t=60, b=40))
    try:
        fig.update_yaxes(tickprefix="$", separatethousands=True)
    except Exception:
        pass
    return fig
