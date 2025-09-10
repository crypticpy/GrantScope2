# sourcery skip: all
import io
import json
import os
from dataclasses import asdict, dataclass, fields

import numpy as np
import pandas as pd
import streamlit as st


@dataclass
class Grant:
    funder_key: str
    funder_profile_url: str
    funder_name: str
    funder_city: str
    funder_state: str
    funder_country: str
    funder_type: str
    funder_zipcode: str
    funder_country_code: str
    funder_ein: str
    funder_gs_profile_update_level: str
    recip_key: str
    recip_name: str
    recip_city: str
    recip_state: str
    recip_country: str
    recip_zipcode: str
    recip_country_code: str
    recip_ein: str
    recip_organization_code: str
    recip_organization_tran: str
    recip_gs_profile_link: str
    recip_gs_profile_update_level: str
    grant_key: str
    amount_usd: int
    grant_subject_code: str
    grant_subject_tran: str
    grant_population_code: str
    grant_population_tran: str
    grant_strategy_code: str
    grant_strategy_tran: str
    grant_transaction_code: str
    grant_transaction_tran: str
    grant_geo_area_code: str
    grant_geo_area_tran: str
    year_issued: str
    grant_duration: str
    grant_description: str
    last_updated: str


@dataclass
class Grants:
    grants: list[Grant]


@st.cache_data
def load_data(file_path=None, uploaded_file=None):
    if uploaded_file is not None:
        data = json.load(io.BytesIO(uploaded_file.read()))
    elif file_path is not None:
        # Try provided path first; if not found, resolve relative to package root (GrantScope/)
        try:
            with open(file_path, encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            pkg_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
            alt_path = os.path.normpath(os.path.join(pkg_root, str(file_path)))
            with open(alt_path, encoding="utf-8") as file:
                data = json.load(file)
    else:
        raise ValueError("Either file_path or uploaded_file must be provided.")

    # Basic schema validation
    if not isinstance(data, dict) or "grants" not in data or not isinstance(data["grants"], list):
        st.error("Invalid input format: expected a JSON object with a 'grants' array.")
        raise ValueError("Invalid input format: expected a JSON object with a 'grants' array.")

    required_fields = {f.name for f in fields(Grant)}
    missing_counts = 0
    validated_grants = []
    for i, grant in enumerate(data["grants"]):
        if not isinstance(grant, dict):
            error_text = f"Invalid grant at index {i}: expected an object."
            st.error(error_text)
            raise ValueError(error_text)
        missing = required_fields - set(grant.keys())
        if missing:
            # Count but attempt to continue by filling with defaults
            missing_counts += 1
            for key in missing:
                # Reasonable defaults
                grant[key] = "" if key not in ("amount_usd",) else 0
        try:
            validated_grants.append(Grant(**grant))
        except TypeError as e:
            st.error(f"Grant at index {i} failed validation: {e}")
            raise

    if missing_counts:
        st.warning(
            f"Detected {missing_counts} grants with missing fields; filled with defaults. Consider validating your export."
        )

    return Grants(grants=validated_grants)


@st.cache_data
def preprocess_data(grants):
    """Create a normalized DataFrame with exploded categorical dimensions and a grouped one-row-per-grant view.

    Returns a tuple: (df_exploded, df_grouped_by_grant)
    """

    df = pd.DataFrame([asdict(grant) for grant in grants.grants])

    # Base keys and types
    df["grant_index"] = df["grant_key"]
    df["year_issued"] = pd.to_numeric(df["year_issued"], errors="coerce").fillna(0).astype(int)
    df["amount_usd"] = pd.to_numeric(df["amount_usd"], errors="coerce")
    df = df.dropna(subset=["amount_usd"])

    # Fill numeric/categorical columns appropriately
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if numeric_cols:
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median(numeric_only=True))
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    if categorical_cols:
        df[categorical_cols] = df[categorical_cols].fillna("Unknown")

    # Ensure description is string-like; coerce non-strings
    df["grant_description"] = df["grant_description"].astype(str).fillna("")

    # Helper to split a semicolon string into list (or ['Unknown'] if empty)
    def split_semicolons(val: str) -> list[str]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ["Unknown"]
        s = str(val).strip()
        if not s:
            return ["Unknown"]
        parts = [p.strip() for p in s.split(";") if p.strip()]
        return parts or ["Unknown"]

    # Helper to align two lists to the same length and zip as pairs
    def align_zip(a: list[str], b: list[str]) -> list[tuple[str, str]]:
        m = max(len(a), len(b))
        a += ["Unknown"] * (m - len(a))
        b += ["Unknown"] * (m - len(b))
        return list(zip(a, b, strict=False))

    # Explode paired code/tran dimensions while preserving alignment
    pairs = [
        ("grant_subject_code", "grant_subject_tran"),
        ("grant_population_code", "grant_population_tran"),
        ("grant_strategy_code", "grant_strategy_tran"),
        ("grant_transaction_code", "grant_transaction_tran"),
        ("grant_geo_area_code", "grant_geo_area_tran"),
    ]

    for code_col, tran_col in pairs:
        if code_col in df.columns and tran_col in df.columns:
            pair_col = f"__{code_col}_pair"
            codes = df[code_col].apply(split_semicolons)
            trans = df[tran_col].apply(split_semicolons)
            df[pair_col] = [align_zip(c, t) for c, t in zip(codes, trans, strict=False)]
            df = df.explode(pair_col, ignore_index=True)
            # Expand back into the two columns
            expanded = pd.DataFrame(
                df[pair_col].tolist(), columns=[code_col, tran_col], index=df.index
            )
            df[code_col] = expanded[code_col]
            df[tran_col] = expanded[tran_col]
            df.drop(columns=[pair_col], inplace=True)

    # Amount clusters
    bins = [0, 50_000, 100_000, 500_000, 1_000_000, np.inf]
    names = ["0-50k", "50k-100k", "100k-500k", "500k-1M", "1M+"]
    df["amount_usd_cluster"] = pd.cut(df["amount_usd"], bins, labels=names, include_lowest=True)

    # De-duplicate on (year, grant_key) to reduce exact duplicates from source
    df = df.drop_duplicates(
        subset=[
            "year_issued",
            "grant_key",
            "grant_subject_tran",
            "grant_population_tran",
            "grant_strategy_tran",
            "grant_transaction_tran",
            "grant_geo_area_tran",
        ]
    )

    # Group to one row per grant (best-effort first occurrence per exploded combos)
    grouped_df = df.groupby("grant_index", as_index=False).first().set_index("grant_index")

    # Add aggregated data summaries for rich context
    df = _add_aggregated_summaries(df)

    return df, grouped_df


def _add_aggregated_summaries(df: pd.DataFrame) -> pd.DataFrame:
    """Add aggregated data summaries for rich context."""
    # Add summary statistics columns
    df["_total_amount"] = df["amount_usd"].sum()
    df["_grant_count"] = len(df)
    df["_avg_amount"] = df["amount_usd"].mean()
    df["_median_amount"] = df["amount_usd"].median()

    # Add funder-level aggregations
    funder_stats = (
        df.groupby("funder_name")["amount_usd"].agg(["sum", "count", "mean"]).reset_index()
    )
    funder_stats.columns = [
        "funder_name",
        "_funder_total_amount",
        "_funder_grant_count",
        "_funder_avg_amount",
    ]
    funder_stats["_funder_rank_by_amount"] = funder_stats["_funder_total_amount"].rank(
        method="dense", ascending=False
    )
    funder_stats["_funder_rank_by_count"] = funder_stats["_funder_grant_count"].rank(
        method="dense", ascending=False
    )

    # Merge back to main dataframe
    df = df.merge(funder_stats, on="funder_name", how="left")

    # Add subject-level aggregations
    if "grant_subject_tran" in df.columns:
        subject_stats = (
            df.groupby("grant_subject_tran")["amount_usd"].agg(["sum", "count"]).reset_index()
        )
        subject_stats.columns = [
            "grant_subject_tran",
            "_subject_total_amount",
            "_subject_grant_count",
        ]
        subject_stats["_subject_rank_by_amount"] = subject_stats["_subject_total_amount"].rank(
            method="dense", ascending=False
        )
        subject_stats["_subject_rank_by_count"] = subject_stats["_subject_grant_count"].rank(
            method="dense", ascending=False
        )
        subject_stats["_subject_percentage_of_total"] = (
            subject_stats["_subject_total_amount"] / df["amount_usd"].sum()
        ) * 100

        # Merge back to main dataframe
        df = df.merge(subject_stats, on="grant_subject_tran", how="left")

    # Add population-level aggregations
    if "grant_population_tran" in df.columns:
        population_stats = (
            df.groupby("grant_population_tran")["amount_usd"].agg(["sum", "count"]).reset_index()
        )
        population_stats.columns = [
            "grant_population_tran",
            "_population_total_amount",
            "_population_grant_count",
        ]
        population_stats["_population_rank_by_amount"] = population_stats[
            "_population_total_amount"
        ].rank(method="dense", ascending=False)
        population_stats["_population_rank_by_count"] = population_stats[
            "_population_grant_count"
        ].rank(method="dense", ascending=False)
        population_stats["_population_percentage_of_total"] = (
            population_stats["_population_total_amount"] / df["amount_usd"].sum()
        ) * 100

        # Merge back to main dataframe
        df = df.merge(population_stats, on="grant_population_tran", how="left")

    # Add geography-level aggregations
    if "grant_geo_area_tran" in df.columns:
        geo_stats = (
            df.groupby("grant_geo_area_tran")["amount_usd"].agg(["sum", "count"]).reset_index()
        )
        geo_stats.columns = ["grant_geo_area_tran", "_geo_total_amount", "_geo_grant_count"]
        geo_stats["_geo_rank_by_amount"] = geo_stats["_geo_total_amount"].rank(
            method="dense", ascending=False
        )
        geo_stats["_geo_rank_by_count"] = geo_stats["_geo_grant_count"].rank(
            method="dense", ascending=False
        )
        geo_stats["_geo_percentage_of_total"] = (
            geo_stats["_geo_total_amount"] / df["amount_usd"].sum()
        ) * 100

        # Merge back to main dataframe
        df = df.merge(geo_stats, on="grant_geo_area_tran", how="left")

    # Add time trend aggregations
    if "year_issued" in df.columns:
        year_stats = df.groupby("year_issued")["amount_usd"].agg(["sum", "count"]).reset_index()
        year_stats.columns = ["year_issued", "_year_total_amount", "_year_grant_count"]
        year_stats["_year_rank_by_amount"] = year_stats["_year_total_amount"].rank(
            method="dense", ascending=False
        )
        year_stats["_year_rank_by_count"] = year_stats["_year_grant_count"].rank(
            method="dense", ascending=False
        )

        # Merge back to main dataframe
        df = df.merge(year_stats, on="year_issued", how="left")

    return df
