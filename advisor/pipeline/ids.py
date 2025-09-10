from typing import Any

from .imports import stable_hash_for_obj


def _stable_dp_id(title: str, method: str, params: dict[str, Any]) -> str:
    h = stable_hash_for_obj({"t": title, "m": method, "p": params})
    return f"DP-{h[:8].upper()}"


def _stable_fig_id(label: str) -> str:
    h = stable_hash_for_obj({"label": label})
    return f"FIG-{h[:8].upper()}"
