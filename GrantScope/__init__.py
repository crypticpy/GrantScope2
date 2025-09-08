"""
Compatibility package to expose this repository's top-level modules under the
'GrantScope' namespace, matching tests and import patterns that expect
GrantScope.* to exist.

It aliases GrantScope.<subpkg> to the corresponding top-level package/module
(e.g., 'advisor', 'loaders', 'utils', 'plots', 'fetch', 'config').

This avoids relocating the source tree and keeps runtime imports and tests happy.
"""
from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Iterable

_ALIAS_SUBPACKAGES: Iterable[str] = (
    "advisor",
    "loaders",
    "utils",
    "plots",
    "fetch",
    "config",
)


def _alias(name: str) -> None:
    """Alias top-level module 'name' as 'GrantScope.name' in sys.modules if available."""
    try:
        mod = importlib.import_module(name)
        sys.modules[f"GrantScope.{name}"] = mod
        # Also attach as attribute for attribute-based access (e.g., GrantScope.advisor)
        setattr(sys.modules[__name__], name, mod)
    except Exception:
        # Safe to ignore if the submodule doesn't exist in this repo
        pass


for _n in _ALIAS_SUBPACKAGES:
    _alias(_n)

