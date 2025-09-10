from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, cast

from .json_utils import _json_dumps_stable, _json_loads


def _safe_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return cast(dict[str, Any], obj.model_dump(mode="json"))  # pydantic v2
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return cast(dict[str, Any], obj.dict())  # pydantic v1
        except Exception:
            pass
    if is_dataclass(obj) and not isinstance(obj, type):
        return cast(dict[str, Any], asdict(obj))
    return cast(dict[str, Any], _json_loads(_json_dumps_stable(obj)))


def _is_nan_like(value: Any) -> bool:
    """
    True if value is None/NaN/empty/null-ish string.
    """
    try:
        if value is None:
            return True
        try:
            import pandas as _pd

            if _pd.isna(value):
                return True
        except Exception:
            pass
        s = str(value).strip().lower()
        return s in ("", "nan", "none", "null")
    except Exception:
        return True
