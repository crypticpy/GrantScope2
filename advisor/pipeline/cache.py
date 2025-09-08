from __future__ import annotations
from typing import Any
import pandas as pd

from .imports import stable_hash_for_obj
from .convert import _safe_to_dict

def compute_data_signature(df: pd.DataFrame) -> str:
    """Return a simple signature for caching: rows + sum(amount_usd)."""
    try:
        rows = int(len(df))
    except Exception:
        rows = 0
    try:
        if "amount_usd" in df.columns:
            s = pd.to_numeric(df["amount_usd"], errors="coerce")
            total = float(s.fillna(0).sum())
        else:
            total = 0.0
    except Exception:
        total = 0.0
    return f"{rows}:{total:.2f}"

def cache_key_for(interview: Any, df: pd.DataFrame) -> str:
    try:
        ihash = interview.stable_hash()
    except Exception:
        ihash = stable_hash_for_obj(_safe_to_dict(interview))
    return f"{ihash}::{compute_data_signature(df)}"
