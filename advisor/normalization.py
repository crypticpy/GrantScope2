from __future__ import annotations

"""
Normalization and filtering helpers for Advisor pipeline.

Exports:
- _tokens_lower(tokens)
- _contains_any(series, tokens)
- _expand_token_variants(token, kind)
- _expand_terms(terms, kind)
- _canonical_value_samples(df)
- _apply_needs_filters(df, needs)
"""

import re
from typing import Any

import pandas as pd


def _tokens_lower(tokens: list[str]) -> list[str]:
    """Normalize tokens to lower-case trimmed strings."""
    out: list[str] = []
    for t in tokens or []:
        try:
            if s := str(t).strip().lower():
                out.append(s)
        except Exception:
            continue
    return out


def _sanitize_tokens_for_contains(tokens: list[Any]) -> list[str]:
    """Minimal token normalization for regex search within _contains_any:
    - Cast each token to str and strip surrounding whitespace
    - Drop only empty strings (do NOT drop falsy values like 0 or False)
    - Deduplicate while preserving input order
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for t in tokens or []:
        try:
            s = str(t).strip()
        except Exception:
            # If casting to string fails for a token, skip it
            continue
        if s and s not in seen:
            cleaned.append(s)
            seen.add(s)
    return cleaned


def _contains_any(series: pd.Series, tokens: list[str]) -> pd.Series:
    """Case-insensitive substring match for any token; safe on missing values.

    Implementation notes:
    - Uses a non-capturing regex group (?:...) for slight performance gain.
    - Chunks very large token lists to avoid overly long regex patterns.
    - Relies on case-insensitive regex (case=False) to avoid copying/allocating
      a lowercased Series.
    - On any unexpected error, returns an all-True mask (graceful degradation).
    """
    if not tokens:
        return pd.Series([True] * len(series), index=series.index)
    try:
        # Normalize input tokens minimally and drop empties
        cleaned = _sanitize_tokens_for_contains(tokens)
        if not cleaned:
            return pd.Series([True] * len(series), index=series.index)

        # Prepare the string Series once (avoid repeated astype/allocations)
        s = series.astype(str)

        # Build regex patterns with escaping. Chunk if token list is large to prevent
        # pathological regex sizes.
        CHUNK_SIZE = 100
        if len(cleaned) <= CHUNK_SIZE:
            pattern = "|".join(re.escape(t) for t in cleaned)
            if not pattern:
                return pd.Series([True] * len(series), index=series.index)
            pattern = f"(?:{pattern})"
            return s.str.contains(pattern, na=False, regex=True, case=False)

        # Chunked evaluation; combine with bitwise OR
        result_mask = pd.Series(False, index=series.index)
        for i in range(0, len(cleaned), CHUNK_SIZE):
            chunk = cleaned[i : i + CHUNK_SIZE]
            chunk_pattern = "|".join(re.escape(t) for t in chunk)
            if not chunk_pattern:
                continue
            chunk_pattern = f"(?:{chunk_pattern})"
            result_mask = result_mask | s.str.contains(
                chunk_pattern, na=False, regex=True, case=False
            )
        return result_mask
    except Exception:
        # In case of unexpected dtype/pathological data, disable filter (do no harm)
        return pd.Series([True] * len(series), index=series.index)


def _expand_token_variants(token: str, kind: str = "generic") -> list[str]:
    """
    Expand a normalized token into a list of likely textual variants to improve matching.
    - Generate separator variants across underscores, hyphens, and spaces.
    - Add lightweight domain synonyms for select terms.
    - For geographies, map common codes to full names (e.g., 'tx' -> 'texas', 'us' -> 'united states').
    Notes:
    - All variants are lowercased; matching is handled case-insensitively upstream.
    """
    t = (token or "").strip().lower()
    if not t:
        return []

    variants: set[str] = set()

    # Separator variants: split into chunks and re-join using _, -, and space
    parts = [p for p in re.split(r"[_\-\s]+", t) if p]
    if parts:
        for sep in ("_", "-", " "):
            variants.add(sep.join(parts))
    # Always include the original normalized token too
    variants.add(t)

    # Domain-specific lightweight synonyms (kept minimal and fast)
    syns: set[str] = set()
    if kind in {"population", "subject", "generic"}:
        syn_index: dict[str, list[str]] = {
            "low_income": ["low income", "low-income", "low income people", "low-income people"],
            "low income": ["low income", "low-income", "low income people", "low-income people"],
            "low-income": ["low income", "low-income", "low income people", "low-income people"],
            "after_school": ["after school", "after-school", "out-of-school", "out of school"],
            "after school": ["after school", "after-school", "out-of-school", "out of school"],
            "after-school": ["after school", "after-school", "out-of-school", "out of school"],
            "youth": ["youth", "children and youth", "young people"],
            "children and youth": ["youth", "children and youth", "young people"],
            "students": ["students", "student"],
            "stem": ["stem", "science technology engineering mathematics"],
            "technology": ["technology", "information and communications", "it"],
            "education": [
                "education",
                "education services",
                "elementary and secondary education",
                "youth development",
            ],
            "youth_education": [
                "education",
                "education services",
                "elementary and secondary education",
                "youth development",
            ],
            "youth education": [
                "education",
                "education services",
                "elementary and secondary education",
                "youth development",
            ],
        }
        if t in syn_index:
            syns.update(syn_index[t])

    if kind == "geography":
        # Enhanced US mapping with cities and regions
        geo_map: dict[str, list[str]] = {
            "us": ["united states", "u.s.", "usa"],
            "tx": ["texas", "austin", "dallas", "houston", "san antonio", "fort worth"],
            "ca": [
                "california",
                "los angeles",
                "san francisco",
                "san diego",
                "sacramento",
                "oakland",
            ],
            "ny": ["new york", "new york city", "brooklyn", "queens", "manhattan", "albany"],
            "fl": ["florida", "miami", "orlando", "tampa", "jacksonville", "tallahassee"],
            "il": ["illinois", "chicago", "springfield", "rockford"],
            "wa": ["washington", "seattle", "spokane", "tacoma", "olympia"],
            "ma": ["massachusetts", "boston", "cambridge", "worcester", "springfield"],
            # Add reverse mappings for major cities
            "austin": ["texas", "tx"],
            "dallas": ["texas", "tx"],
            "houston": ["texas", "tx"],
            "los angeles": ["california", "ca"],
            "san francisco": ["california", "ca"],
            "chicago": ["illinois", "il"],
            "seattle": ["washington", "wa"],
            "boston": ["massachusetts", "ma"],
            "miami": ["florida", "fl"],
            "new york city": ["new york", "ny"],
        }
        if t in geo_map:
            syns.update(geo_map[t])

        # Additional geographic descriptors (t already lowercased)
        if "texas" in t or t == "tx":
            syns.update(["austin", "texas", "tx"])
        elif (
            "california" in t
            or t == "ca"
            or "austin" not in t
            and ("los angeles" in t or "san francisco" in t)
        ):
            syns.update(["california", "ca"])
        elif "austin" in t:
            syns.update(["texas", "tx", "austin"])
    # Merge synonyms into variants
    variants.update(s.strip().lower() for s in syns if s)

    # Remove empties and return deterministic ordering for stability
    result = [v for v in variants if v]
    result.sort()
    return result


def _expand_terms(terms: list[str], kind: str) -> list[str]:
    """Expand a list of normalized terms into a deduplicated list of variants."""
    out: list[str] = []
    for t in terms or []:
        out.extend(_expand_token_variants(t, kind=kind))
    # Deduplicate while preserving order
    seen = set()
    dedup: list[str] = []
    for v in out:
        if v not in seen:
            dedup.append(v)
            seen.add(v)
    return dedup


def _canonical_value_samples(df: pd.DataFrame) -> dict[str, list[str]]:
    """
    Collect small samples of canonical values from key columns to guide tool usage.
    Returns a dict of column -> list of example values (lowercased for hints).
    """
    result: dict[str, list[str]] = {}
    try:
        for col in ("grant_subject_tran", "grant_population_tran", "grant_geo_area_tran"):
            if col in df.columns:
                ser = df[col].dropna().astype(str).str.strip().str.lower()
                # Split semicolon-delimited subjects into atomic tokens for better hints
                if col == "grant_subject_tran":
                    ser = ser.str.split(";").explode().astype(str).str.strip().str.lower()
                top = ser.value_counts().head(12).index.tolist()
                # Clean empties and extremely short noise
                examples = [x for x in top if x and x not in ("nan", "none", "null") and len(x) > 1]
                result[col] = examples[:10]
    except Exception:
        return result
    return result


def _apply_needs_filters(df: pd.DataFrame, needs: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply StructuredNeeds-derived filters to the dataframe with robust normalization.

    Strategy:
    - Expand user-provided tokens into likely textual variants (underscores, hyphens,
      spaces, synonyms).
    - For 'grant_subject_tran', also consider semicolon-delimited lists in the cell
      values via substring match.
    - For geographies, translate common codes (e.g., 'tx', 'us') to names
      ('texas', 'united states').
    - If any filter would eliminate all rows, skip that filter (graceful degradation).
    """
    used: dict[str, Any] = {}
    if df is None or df.empty:
        return df, {"filters_applied": False}

    mask = pd.Series(True, index=df.index)

    # Subjects -> grant_subject_tran
    subj_in = _tokens_lower(getattr(needs, "subjects", []))
    subj_terms = _expand_terms(subj_in, kind="subject") if subj_in else []
    if "grant_subject_tran" in df.columns and subj_terms:
        m_subj = _contains_any(df["grant_subject_tran"], subj_terms)
        if m_subj.any() and bool(m_subj.sum()):
            mask &= m_subj
            used["subjects"] = subj_terms

    # Populations -> grant_population_tran
    pop_in = _tokens_lower(getattr(needs, "populations", []))
    pop_terms = _expand_terms(pop_in, kind="population") if pop_in else []
    if "grant_population_tran" in df.columns and pop_terms:
        m_pop = _contains_any(df["grant_population_tran"], pop_terms)
        if m_pop.any() and bool(m_pop.sum()):
            mask &= m_pop
            used["populations"] = pop_terms

    # Geographies -> grant_geo_area_tran
    geo_in = _tokens_lower(getattr(needs, "geographies", []))
    geo_terms = _expand_terms(geo_in, kind="geography") if geo_in else []
    if "grant_geo_area_tran" in df.columns and geo_terms:
        m_geo = _contains_any(df["grant_geo_area_tran"], geo_terms)
        if m_geo.any() and bool(m_geo.sum()):
            mask &= m_geo
            used["geographies"] = geo_terms

    try:
        filtered = df[mask]
        if filtered.empty:
            # Graceful degradation: if filters remove all rows, fall back to unfiltered df
            return df, {"filters_applied": False}
        used["filters_applied"] = bool(used)
        return filtered, used
    except Exception:
        return df, {"filters_applied": False}


__all__ = [
    "_tokens_lower",
    "_contains_any",
    "_expand_token_variants",
    "_expand_terms",
    "_canonical_value_samples",
    "_apply_needs_filters",
]
