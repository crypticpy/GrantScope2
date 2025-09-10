"""
GrantScope Advisor package.
Provides interview-to-report pipeline and related utilities.
"""

from importlib import import_module

# Eagerly create names for linters; resolve lazily to avoid import errors during partial installs.
try:  # pragma: no cover - defensive import scaffolding
    from . import schemas as schemas  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    schemas = None  # type: ignore
try:  # pragma: no cover
    from . import prompts as prompts  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    prompts = None  # type: ignore
try:  # pragma: no cover
    from . import pipeline as pipeline  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    pipeline = None  # type: ignore
try:  # pragma: no cover
    from . import figures as figures  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    figures = None  # type: ignore
try:  # pragma: no cover
    from . import renderer as renderer  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    renderer = None  # type: ignore
try:  # pragma: no cover
    from . import persist as persist  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    persist = None  # type: ignore
try:  # pragma: no cover
    from . import demo as demo  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    demo = None  # type: ignore


def __getattr__(name: str):
    """Lazily import submodules when accessed.

    This keeps import-time light and avoids errors during partial deployments
    while still satisfying linters by defining the names above.
    """
    if name in __all__:
        module = import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "schemas",
    "prompts",
    "pipeline",
    "figures",
    "renderer",
    "persist",
    "demo",
]

__version__ = "0.1.0"
