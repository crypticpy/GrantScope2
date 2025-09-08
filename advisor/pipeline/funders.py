from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from .imports import StructuredNeeds, DataPoint, FunderCandidate, _apply_needs_filters
from .convert import _is_nan_like

def _derive_grounded_dp_ids(datapoints: List[DataPoint]) -> List[str]:
    """
    Heuristically collect DataPoint IDs that look like funder-level aggregates.
    """
    out: List[str] = []
    for dp in datapoints or []:
        try:
            method = str(getattr(dp, "method", ""))
            params = getattr(dp, "params", {}) or {}
            by = params.get("by") or []
            if method == "df_groupby_sum" and isinstance(by, list) and "funder_name" in by:
                out.append(str(dp.id))
        except Exception:
            continue
    return out[:3]

def _coerce_funder_candidate(it: Any) -> Optional[FunderCandidate]:
    """
    Coerce various inputs into a valid FunderCandidate or return None to skip.
    """
    try:
        if isinstance(it, FunderCandidate):
            nm = getattr(it, "name", None)
            if _is_nan_like(nm):
                return None
            name_str = str(nm).strip()
            if name_str != it.name:
                return FunderCandidate(
                    name=name_str,
                    score=float(getattr(it, "score", 0.0) or 0.0),
                    rationale=str(getattr(it, "rationale", "") or ""),
                    grounded_dp_ids=list(getattr(it, "grounded_dp_ids", []) or []),
                )
            return it

        if isinstance(it, str):
            s = it.strip()
            if not s:
                return None
            return FunderCandidate(name=s, score=0.0, rationale="")

        if isinstance(it, dict):
            name_val = it.get("name")
            if _is_nan_like(name_val):
                name_val = it.get("funder_name")
            if _is_nan_like(name_val):
                name_val = it.get("label")
            if _is_nan_like(name_val):
                return None
            name_str = str(name_val).strip()

            score_raw = it.get("score", 0.0)
            try:
                score_val = float(score_raw)
            except Exception:
                score_val = 0.0

            rationale_raw = it.get("rationale", "")
            try:
                rationale_val = str(rationale_raw) if rationale_raw is not None else ""
            except Exception:
                rationale_val = ""

            g_raw = it.get("grounded_dp_ids", [])
            grounded: List[str] = []
            if isinstance(g_raw, (list, tuple)):
                for g in g_raw:
                    try:
                        gs = str(g)
                        if gs:
                            grounded.append(gs)
                    except Exception:
                        continue

            return FunderCandidate(
                name=name_str,
                score=score_val,
                rationale=rationale_val,
                grounded_dp_ids=grounded,
            )
    except Exception:
        return None
    return None

def _fallback_funder_candidates(
    df: pd.DataFrame,
    needs: StructuredNeeds,
    datapoints: List[DataPoint],
    min_n: int = 5,
) -> List[FunderCandidate]:
    """
    Robust fallback: aggregate directly from df to produce ranked funder candidates.
    """
    candidates: List[FunderCandidate] = []
    if df is None or df.empty or "funder_name" not in df.columns:
        return candidates

    filtered_df, used = _apply_needs_filters(df, needs)

    try:
        fn_str = filtered_df["funder_name"].astype(str).str.strip()
        mask_valid_fn = filtered_df["funder_name"].notna() & fn_str.ne("") & ~fn_str.str.lower().isin(["nan", "none", "null"])
        filtered_df = filtered_df[mask_valid_fn]
    except Exception:
        try:
            filtered_df = filtered_df[filtered_df["funder_name"].notna()]
        except Exception:
            pass

    use_amount = "amount_usd" in filtered_df.columns
    try:
        if use_amount:
            series = pd.to_numeric(filtered_df["amount_usd"], errors="coerce").fillna(0.0)
            grouped = filtered_df.assign(_val=series).groupby("funder_name")["_val"].sum()
            basis = "total amount"
        else:
            grouped = filtered_df.groupby("funder_name").size().rename("count")
            basis = "grant count"

        grouped = grouped.sort_values(ascending=False)
        if grouped.empty:
            return candidates

        top_n = max(min_n, 10)
        top = grouped.head(top_n)
        max_val = float(top.max())
        if max_val <= 0:
            max_val = 1.0

        grounded_ids = _derive_grounded_dp_ids(datapoints)
        rationale_parts: List[str] = []
        if used.get("filters_applied"):
            if "subjects" in used and used["subjects"]:
                rationale_parts.append(f"subjects: {', '.join(map(str, used['subjects'][:3]))}")
            if "populations" in used and used["populations"]:
                rationale_parts.append(f"populations: {', '.join(map(str, used['populations'][:3]))}")
            if "geographies" in used and used["geographies"]:
                rationale_parts.append(f"geographies: {', '.join(map(str, used['geographies'][:3]))}")

        for funder_name, val in top.items():
            name_str = str(funder_name).strip() if funder_name is not None else ""
            if not name_str or name_str.lower() in ("nan", "none", "null"):
                continue
            raw_score = float(val) / max_val if max_val > 0 else 0.0
            score = max(0.01, raw_score)
            if rationale_parts:
                rationale = f"Top funder by {basis} for " + "; ".join(rationale_parts)
            else:
                rationale = f"Top funder overall by {basis}"
            candidates.append(
                FunderCandidate(
                    name=name_str,
                    score=round(score, 4),
                    rationale=rationale,
                    grounded_dp_ids=list(grounded_ids),
                )
            )
            if len(candidates) >= top_n:
                break

        if len(candidates) < min_n:
            try:
                if "amount_usd" in df.columns:
                    series_all = pd.to_numeric(df["amount_usd"], errors="coerce").fillna(0.0)
                    df_all = df.assign(_val=series_all)
                    fn_all = df_all["funder_name"].astype(str).str.strip()
                    mask_valid_all = df_all["funder_name"].notna() & fn_all.ne("") & ~fn_all.str.lower().isin(["nan", "none", "null"])
                    df_all_valid = df_all[mask_valid_all]
                    grouped_all = df_all_valid.groupby("funder_name")["_val"].sum().sort_values(ascending=False)
                    basis_all = "total amount"
                else:
                    df_all = df.copy()
                    fn_all = df_all["funder_name"].astype(str).str.strip()
                    mask_valid_all = df_all["funder_name"].notna() & fn_all.ne("") & ~fn_all.str.lower().isin(["nan", "none", "null"])
                    df_all_valid = df_all[mask_valid_all]
                    grouped_all = df_all_valid.groupby("funder_name").size().rename("count").sort_values(ascending=False)
                    basis_all = "grant count"

                head_all = grouped_all.head(max(min_n * 2, 10))
                max_val_all = float(head_all.max()) if len(head_all) else 1.0
                if max_val_all <= 0:
                    max_val_all = 1.0

                existing_names = {c.name for c in candidates}
                for funder_name, val in grouped_all.items():
                    if len(candidates) >= min_n:
                        break
                    name_str_all = str(funder_name).strip() if funder_name is not None else ""
                    if not name_str_all or name_str_all.lower() in ("nan", "none", "null"):
                        continue
                    if name_str_all in existing_names:
                        continue
                    raw_score = float(val) / max_val_all if max_val_all > 0 else 0.0
                    score = max(0.01, raw_score)
                    rationale_extra = f"Top funder overall by {basis_all} (broadened beyond filters)"
                    candidates.append(
                        FunderCandidate(
                            name=name_str_all,
                            score=round(score, 4),
                            rationale=rationale_extra,
                            grounded_dp_ids=[],
                        )
                    )
                    existing_names.add(name_str_all)
            except Exception:
                pass
    except Exception:
        return []
    return candidates
