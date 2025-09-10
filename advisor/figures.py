from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def _to_list_lower(xs: Any) -> list[str]:
    try:
        if xs is None:
            return []
        if isinstance(xs, (list, tuple, set)):
            return [str(x).strip() for x in xs if str(x).strip()]
        # allow single string
        s = str(xs or "").strip()
        return [s] if s else []
    except Exception:
        return []


def _needs_dict(needs: Any) -> dict[str, Any]:
    # Accept pydantic model, dataclass, dict
    try:
        if isinstance(needs, dict):
            return needs
        if hasattr(needs, "model_dump"):
            return needs.model_dump()
        if hasattr(needs, "dict"):
            return needs.dict()  # type: ignore[attr-defined]
        if hasattr(needs, "__dict__"):
            return dict(needs.__dict__)
    except Exception:
        pass
    return {}


def _apply_needs_soft(df: pd.DataFrame, needs: Any) -> pd.DataFrame:
    """
    Soft-filter df using whatever fields are available in needs.
    Does not fail if fields/columns are missing; returns df unchanged when filters can't be applied.
    """
    try:
        nd = _needs_dict(needs)
        subs = _to_list_lower(nd.get("subjects") or nd.get("keywords"))
        pops = _to_list_lower(nd.get("populations"))
        geos = _to_list_lower(nd.get("geographies") or nd.get("geography"))

        out = df
        # Subject filter (columns commonly *_tran)
        if subs and any(
            col in out.columns for col in ("grant_subject_tran", "subject", "subjects")
        ):
            for col in ("grant_subject_tran", "subject", "subjects"):
                if col in out.columns:
                    out = out[out[col].astype(str).str.lower().isin(set(subs)) | (out[col].isna())]
                    break

        # Population filter
        if pops and any(
            col in out.columns for col in ("grant_population_tran", "population", "populations")
        ):
            for col in ("grant_population_tran", "population", "populations"):
                if col in out.columns:
                    out = out[out[col].astype(str).str.lower().isin(set(pops)) | (out[col].isna())]
                    break

        # Geography filter (handle state codes, city names, regions)
        if geos and any(
            col in out.columns for col in ("grant_geo_area_tran", "geography", "region", "state")
        ):
            for col in ("grant_geo_area_tran", "geography", "region", "state"):
                if col in out.columns:
                    # Normalize both sides for simple contains/in
                    ocol = out[col].astype(str).str.lower()
                    mask = False
                    for g in geos:
                        # allow contains for city/region names
                        mask = mask | ocol.str.contains(str(g).lower(), na=False)
                    out = out[mask | out[col].isna()]
                    break

        return out
    except Exception:
        return df


# --------------------------
# Top Funders (bar)
# --------------------------
def _prep_top_funders(df: pd.DataFrame, needs: Any, n: int = 10) -> pd.DataFrame:
    df2 = _apply_needs_soft(df, needs)
    if "funder_name" not in df2.columns or "amount_usd" not in df2.columns:
        return pd.DataFrame(columns=["funder_name", "amount_usd"])
    grp = (
        df2.dropna(subset=["funder_name", "amount_usd"])
        .groupby("funder_name", as_index=False)["amount_usd"]
        .sum()
    )
    grp = grp.sort_values("amount_usd", ascending=False).head(int(n))
    return grp


def figure_top_funders_bar(df: pd.DataFrame, needs: Any):
    """
    Return a Plotly bar chart of top funders by total amount_usd.
    """
    data = _prep_top_funders(df, needs, n=10)
    if data.empty:
        # Return minimal empty chart to keep downstream consistent
        return px.bar(
            pd.DataFrame({"funder_name": [], "amount_usd": []}),
            x="funder_name",
            y="amount_usd",
            title="Top Funders by Total Amount",
        )
    fig = px.bar(
        data,
        x="funder_name",
        y="amount_usd",
        title="Top Funders by Total Amount",
    )
    fig.update_layout(
        xaxis_title="Funder Name",
        yaxis_title="Total Grant Amount (USD)",
        margin=dict(l=10, r=10, t=50, b=40),
    )
    return fig


# --------------------------
# Amount Distribution (histogram)
# --------------------------
def _prep_distribution(df: pd.DataFrame, needs: Any) -> pd.DataFrame:
    df2 = _apply_needs_soft(df, needs)
    if "amount_usd" not in df2.columns:
        return pd.DataFrame(columns=["amount_usd"])
    out = df2[["amount_usd"]].dropna()
    return out


def figure_amount_distribution(df: pd.DataFrame, needs: Any):
    """
    Return a Plotly histogram of amount_usd.
    """
    data = _prep_distribution(df, needs)
    if data.empty:
        return px.histogram(
            pd.DataFrame({"amount_usd": []}), x="amount_usd", title="Grant Amount Distribution"
        )
    # Heuristic for bin count
    nbins = max(10, min(60, int(len(data) ** 0.5)))
    fig = px.histogram(
        data,
        x="amount_usd",
        nbins=nbins,
        title="Grant Amount Distribution",
    )
    fig.update_layout(
        xaxis_title="Grant Amount (USD)",
        yaxis_title="Count",
        margin=dict(l=10, r=10, t=50, b=40),
    )
    return fig


# --------------------------
# Time Trend (line)
# --------------------------
def _prep_time_trend(df: pd.DataFrame, needs: Any) -> pd.DataFrame:
    df2 = _apply_needs_soft(df, needs)
    if "year_issued" not in df2.columns or "amount_usd" not in df2.columns:
        return pd.DataFrame(columns=["year_issued", "amount_usd"])
    dft = (
        df2.dropna(subset=["year_issued", "amount_usd"])
        .groupby("year_issued", as_index=False)["amount_usd"]
        .sum()
        .sort_values("year_issued")
    )
    return dft


def figure_time_trend(df: pd.DataFrame, needs: Any):
    """
    Return a Plotly line chart of total amount_usd by year_issued.
    """
    data = _prep_time_trend(df, needs)
    if data.empty:
        return px.line(
            pd.DataFrame({"year_issued": [], "amount_usd": []}),
            x="year_issued",
            y="amount_usd",
            title="Funding Trends Over Time",
        )
    fig = px.line(
        data,
        x="year_issued",
        y="amount_usd",
        markers=True,
        title="Funding Trends Over Time",
    )
    fig.update_layout(
        xaxis_title="Year Issued",
        yaxis_title="Total Amount Awarded (USD)",
        margin=dict(l=10, r=10, t=50, b=40),
    )
    return fig


# Export helpers used by figures_wrap
__all__ = [
    "_prep_top_funders",
    "figure_top_funders_bar",
    "_prep_distribution",
    "figure_amount_distribution",
    "_prep_time_trend",
    "figure_time_trend",
]
