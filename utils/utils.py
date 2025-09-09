import base64
from io import BytesIO

import os
from typing import Any

import pandas as pd
import streamlit as st
import json

# Fallback cache decorator for test environments without full Streamlit runtime
try:
    _cache_data = st.cache_data  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - testing fallback
    def _cache_data(**_kwargs):  # type: ignore[misc]
        def _decorator(fn):
            return fn
        return _decorator

def download_excel(df, filename, sheet_name: str = 'Sheet1'):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel File</a>'
    st.markdown(href, unsafe_allow_html=True)
    return href


def download_csv(df, filename):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href


def is_feature_enabled(name: str, default: bool = False) -> bool:
    """Return True if the given env var is truthy ('1','true','yes','on')."""
    val = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return val in ("1", "true", "yes", "on")


def summarize_filters(filters: dict | None) -> str:
    """Create a compact, stable summary string for a filters dict."""
    if not filters:
        return "None"
    parts: list[str] = []
    try:
        for k, v in filters.items():
            if isinstance(v, (list, tuple, set)):
                v = list(v)
            parts.append(f"{k}={v}")
        return ", ".join(parts)
    except Exception:
        return str(filters)


def compact_sample(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Return a compact CSV preview of the first N rows, truncated if large."""
    try:
        sample = df.head(max_rows)
        csv = sample.to_csv(index=False)
        if len(csv) > 4000:
            csv = csv[:4000] + "\n# [truncated]"
        return csv
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def _build_prompt_cached(
    selected_chart: str,
    selected_role: str,
    additional_context: str,
    columns: tuple[str, ...],
    data_types_items: tuple[tuple[str, str], ...],
    num_records: int,
    num_funders: int,
    num_recipients: int,
    min_date: str,
    max_date: str,
    top_states: tuple[str, ...],
    total_amount: float,
    avg_amount: float,
    median_amount: float,
    filter_summary: str,
    sample_text: str,
) -> str:
    columns_str = ", ".join(columns)
    data_type_info = ", ".join([f"{col}: {dtype}" for col, dtype in data_types_items])
    geographical_info = (
        f"The dataset covers grants from {len(top_states)} states in the USA. "
        f"The top states by grant count are {', '.join(top_states[:3])}."
    )
    observations = (
        f"The dataset contains {num_records} records, with {num_funders} unique funders and "
        f"{num_recipients} unique recipients."
    )
    date_info = f"The dataset covers grants from {min_date} to {max_date}."
    aggregated_stats = (
        f"The total grant amount is ${total_amount:,.2f}, with an average grant amount of "
        f"${avg_amount:,.2f} and a median grant amount of ${median_amount:,.2f}."
    )
    chart_description = (
        f"The current chart is a {selected_chart}, which visualizes the grant data based on "
        f"{additional_context}."
    )
    role_description = (
        f"The user is a {selected_role} who is exploring the grant data to gain insights and "
        f"inform their work."
    )
    guardrails = (
        "Guardrails:\n"
        "- Only answer questions using the dataset columns listed under 'Known Columns'.\n"
        "- If a requested column is not listed, explicitly state that this information is not available in the dataset.\n"
        "- Do not invent columns or values. Stay within the provided context.\n"
        "- Respond in Markdown format only."
    )

    parts: list[str] = []
    parts.append("The Candid API provides comprehensive data on grants and funding in the USA.")
    parts.append(f"Known Columns: {columns_str}")
    parts.append(f"Data types: {data_type_info}.")
    parts.append(observations)
    parts.append(date_info)
    parts.append(geographical_info)
    parts.append(aggregated_stats)
    parts.append(chart_description)
    parts.append(role_description)
    parts.append(f"Current Filters: {filter_summary}")
    if sample_text:
        parts.append("Sample Context (CSV, head):\n```csv\n" + sample_text + "\n```")
    parts.append(guardrails)
    parts.append("The user's prompt is:")
    return " ".join(parts)


def generate_page_prompt(
    df,
    _grouped_df,
    selected_chart,
    selected_role,
    additional_context,
    current_filters: dict | None = None,
    sample_df: pd.DataFrame | None = None,
):
    """Build a grounded, memoized prompt including known columns, filters, and a compact sample."""
    # Extract primitives for caching
    columns_tuple = tuple([str(c) for c in df.columns])
    dtypes_items = tuple((str(col), str(dtype.name)) for col, dtype in df.dtypes.items())
    num_records = int(len(df))

    # Defensive numeric computations
    total_amount = float(df["amount_usd"].sum()) if "amount_usd" in df.columns else 0.0
    avg_amount = float(df["amount_usd"].mean()) if "amount_usd" in df.columns else 0.0
    median_amount = float(df["amount_usd"].median()) if "amount_usd" in df.columns else 0.0

    num_funders = int(df["funder_name"].nunique()) if "funder_name" in df.columns else 0
    num_recipients = int(df["recip_name"].nunique()) if "recip_name" in df.columns else 0

    # Dates
    if "last_updated" in df.columns:
        min_date_val = df["last_updated"].min()
        max_date_val = df["last_updated"].max()
        min_date = str(min_date_val)
        max_date = str(max_date_val)
    else:
        min_date = "N/A"
        max_date = "N/A"

    # States
    if "funder_state" in df.columns:
        top_states = tuple([str(s) for s in df["funder_state"].dropna().astype(str).unique().tolist()])
    else:
        top_states = tuple()

    filter_summary = summarize_filters(current_filters)
    sample_text = compact_sample(sample_df if sample_df is not None else df, 50)

    return _build_prompt_cached(
        str(selected_chart),
        str(selected_role),
        str(additional_context),
        columns_tuple,
        dtypes_items,
        num_records,
        num_funders,
        num_recipients,
        min_date,
        max_date,
        top_states,
        total_amount,
        avg_amount,
        median_amount,
        filter_summary,
        sample_text,
    )


def download_multi_sheet_excel(sheets: dict, filename: str):
    """Create a single Excel file with multiple sheets from a dict of {sheet_name: df}.

    Returns an href download link; also prints it via st.markdown for convenience.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for name, df in sheets.items():
            safe_name = str(name)[:31] if name else 'Sheet1'
            df.to_excel(writer, index=False, sheet_name=safe_name)
    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel File</a>'
    st.markdown(href, unsafe_allow_html=True)
    return href


def download_text(content: str, filename: str, mime: str = "text/plain") -> str:
    """Return a Streamlit download link for arbitrary text content.

    Also renders the link via st.markdown; returns the href string for reuse.
    """
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:{mime};base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    return href


def build_sample_grants_json() -> str:
    """Produce a minimal, valid sample grants JSON payload matching the expected schema."""
    sample = {
        "grants": [
            {
                "funder_key": "FUND-001",
                "funder_profile_url": "https://example.org/funders/FUND-001",
                "funder_name": "Example Foundation",
                "funder_city": "New York",
                "funder_state": "NY",
                "funder_country": "USA",
                "funder_type": "Foundation",
                "funder_zipcode": "10001",
                "funder_country_code": "US",
                "funder_ein": "12-3456789",
                "funder_gs_profile_update_level": "basic",
                "recip_key": "RECIP-001",
                "recip_name": "Community Org",
                "recip_city": "Austin",
                "recip_state": "TX",
                "recip_country": "USA",
                "recip_zipcode": "73301",
                "recip_country_code": "US",
                "recip_ein": "98-7654321",
                "recip_organization_code": "NPO",
                "recip_organization_tran": "Nonprofit",
                "recip_gs_profile_link": "https://example.org/recipients/RECIP-001",
                "recip_gs_profile_update_level": "basic",
                "grant_key": "GRANT-0001",
                "amount_usd": 250000,
                "grant_subject_code": "EDU;HLTH",
                "grant_subject_tran": "Education;Health",
                "grant_population_code": "YOUTH",
                "grant_population_tran": "Youth",
                "grant_strategy_code": "CAP",
                "grant_strategy_tran": "Capacity Building",
                "grant_transaction_code": "NEW",
                "grant_transaction_tran": "New Grant",
                "grant_geo_area_code": "TX;US",
                "grant_geo_area_tran": "Texas;United States",
                "year_issued": "2023",
                "grant_duration": "12",
                "grant_description": "Support for expanding youth education programs.",
                "last_updated": "2024-12-31"
            }
        ]
    }
    return json.dumps(sample, indent=2)
