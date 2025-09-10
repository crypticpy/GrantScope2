"""
Advisor pipeline package.

Public API:
 - run_interview_pipeline(interview: InterviewInput, df: pd.DataFrame) -> ReportBundle
 - compute_data_signature(df: pd.DataFrame) -> str
 - cache_key_for(interview: Any, df: pd.DataFrame) -> str

Compatibility:
 - Exposes internal stage helpers and tool_query on the package namespace so tests and
   downstream callers can monkeypatch advisor.pipeline.* as before the refactor.
 - The run_interview_pipeline wrapper rebinds orchestrator/metrics/figures_wrap symbols
   to current package attributes at call time to honor monkeypatches.
"""

from __future__ import annotations

# Re-export cache helpers
from .cache import cache_key_for, compute_data_signature

# Re-export stage helpers and tools for test monkeypatch compatibility
from .imports import (  # type: ignore
    WHITELISTED_TOOLS,
    _interpret_chart_cached,
    _stage0_intake_summary_cached,
    _stage1_normalize_cached,
    _stage2_plan_cached,
    _stage4_synthesize_cached,
    _stage5_recommend_cached,
    tool_query,
)


def run_interview_pipeline(interview, df):
    """Compatibility wrapper that rebinds internals before delegating to the orchestrator."""
    # Local imports to avoid circular dependencies at module import time
    from . import (
        figures_wrap as _figs,  # type: ignore
        metrics as _metrics,  # type: ignore
        orchestrator as _orc,  # type: ignore
    )

    # Rebind stage functions so monkeypatches applied to advisor.pipeline.* are respected
    try:
        _orc._stage0_intake_summary_cached = _stage0_intake_summary_cached  # type: ignore[attr-defined]
        _orc._stage1_normalize_cached = _stage1_normalize_cached  # type: ignore[attr-defined]
        _orc._stage2_plan_cached = _stage2_plan_cached  # type: ignore[attr-defined]
        _orc._stage4_synthesize_cached = _stage4_synthesize_cached  # type: ignore[attr-defined]
        _orc._stage5_recommend_cached = _stage5_recommend_cached  # type: ignore[attr-defined]
    except Exception:
        pass

    # Rebind tool entry used by metrics execution
    try:
        _metrics.tool_query = tool_query  # type: ignore[attr-defined]
    except Exception:
        pass

    # Rebind chart interpretation helper used by figures
    try:
        _figs._interpret_chart_cached = _interpret_chart_cached  # type: ignore[attr-defined]
    except Exception:
        pass

    return _orc.run_interview_pipeline(interview, df)


def _figures_default(df, interview, needs):
    """Compatibility wrapper around figures_wrap._figures_default honoring pipeline monkeypatches."""
    from . import figures_wrap as _figs  # type: ignore

    try:
        _figs._interpret_chart_cached = _interpret_chart_cached  # type: ignore[attr-defined]
    except Exception:
        pass
    return _figs._figures_default(df, interview, needs)


__all__ = [
    "run_interview_pipeline",
    "compute_data_signature",
    "cache_key_for",
    # Exposed for tests/backward-compat monkeypatching:
    "_figures_default",
    "_stage0_intake_summary_cached",
    "_stage1_normalize_cached",
    "_stage2_plan_cached",
    "_stage4_synthesize_cached",
    "_stage5_recommend_cached",
    "_interpret_chart_cached",
    "tool_query",
    "WHITELISTED_TOOLS",
]
