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

from typing import Any, Dict, List, Tuple
import re

import pandas as pd


def _tokens_lower(tokens: List[str]) -> List[str]:
    """Normalize tokens to lower-case trimmed strings."""
    out: List[str] = []
    for t in tokens or []:
        try:
            s = str(t).strip().lower()
            if s:
                out.append(s)
        except Exception:
            continue
    return out


def _contains_any(series: pd.Series, tokens: List[str]) -> pd.Series:
    """Case-insensitive string contains for any of the tokens; safe on missing values."""
    if not tokens:
        return pd.Series([True] * len(series), index=series.index)
    try:
        pattern = "|".join(re.escape(t) for t in tokens if t)
        if not pattern:
            return pd.Series([True] * len(series), index=series.index)
        s = series.astype(str).str.lower()
        return s.str.contains(pattern, na=False)
    except Exception:
        # In case of unexpected dtype/pathological data, disable filter (do no harm)
        return pd.Series([True] * len(series), index=series.index)


def _expand_token_variants(token: str, kind: str = "generic") -> List[str]:
    """
    Expand a normalized token into a list of likely textual variants to improve matching.
    - Replaces underscores with spaces/hyphens and vice versa.
    - Adds common synonyms for select domain terms.
    - For geographies, map common codes to full names (e.g., 'tx' -> 'texas', 'us' -> 'united states').
    """
    t = (token or "").strip().lower()
    if not t:
        return []
    variants = {t}
    # Underscore / hyphen / space variants
    variants.add(t.replace("_", " "))
    variants.add(t.replace("_", "-"))
    variants.add(t.replace("-", " "))
    variants.add(t.replace("-", "_"))

    # Domain-specific lightweight synonyms
    syns: List[str] = []
    if kind in ("population", "subject", "generic"):
        if t in ("low_income", "low income", "low-income"):
            syns += ["low income", "low-income", "low income people", "low-income people"]
        if t in ("after_school", "after school", "after-school"):
            syns += ["after school", "after-school", "out-of-school", "out of school"]
        if t in ("youth", "children and youth"):
            syns += ["youth", "children and youth", "young people"]
        if t in ("students",):
            syns += ["students", "student"]
        if t in ("stem",):
            syns += ["stem", "science technology engineering mathematics"]
        if t in ("technology",):
            syns += ["technology", "information and communications", "it"]
        if t in ("education", "youth_education", "youth education"):
            syns += ["education", "education services", "elementary and secondary education", "youth development"]
    if kind == "geography":
        # Enhanced US mapping with cities and regions
        geo_map = {
            "us": ["united states", "u.s.", "usa"],
            "tx": ["texas", "austin", "dallas", "houston", "san antonio", "fort worth"],
            "ca": ["california", "los angeles", "san francisco", "san diego", "sacramento", "oakland"],
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
            syns += geo_map[t]
        # Also add capitalized versions (city/state names often are capitalized in text)
        syns += [s.title() for s in syns if s]
        
        # Add common geographic descriptors
        if "texas" in t or "tx" in t:
            syns += ["austin", "texas", "tx"]
        elif "california" in t or "ca" in t:
            syns += ["california", "ca"]
        elif "austin" in t.lower():
            syns += ["texas", "tx", "austin"]
        elif "los angeles" in t.lower() or "san francisco" in t.lower():
            syns += ["california", "ca"]

    for s in syns:
        if s:
            variants.add(s.lower())

    return list({v for v in variants if v})


def _expand_terms(terms: List[str], kind: str) -> List[str]:
    """Expand a list of normalized terms into a deduplicated list of variants."""
    out: List[str] = []
    for t in terms or []:
        out.extend(_expand_token_variants(t, kind=kind))
    # Deduplicate while preserving order
    seen = set()
    dedup: List[str] = []
    for v in out:
        if v not in seen:
            dedup.append(v)
            seen.add(v)
    return dedup


def _canonical_value_samples(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Collect small samples of canonical values from key columns to guide tool usage.
    Returns a dict of column -> list of example values (lowercased for hints).
    """
    result: Dict[str, List[str]] = {}
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


def _apply_needs_filters(df: pd.DataFrame, needs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply StructuredNeeds-derived filters to the dataframe with robust normalization.

    Strategy:
    - Expand user-provided tokens into likely textual variants (underscores, hyphens, spaces, synonyms).
    - For 'grant_subject_tran', also consider semicolon-delimited lists in the cell values via substring match.
    - For geographies, translate common codes (e.g., 'tx', 'us') to names ('texas', 'united states').
    - If any filter would eliminate all rows, skip that filter (graceful degradation).
    """
    used: Dict[str, Any] = {}
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