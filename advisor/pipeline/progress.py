import threading
from datetime import datetime
from typing import Any

_LOCK = threading.Lock()
_PROGRESS_STATE: dict[str, dict[str, Any]] = {}
_PROGRESS_LOGS: dict[str, list[str]] = {}
_REPORT_STORE: dict[str, "ReportBundle"] = {}

from .imports import ReportBundle

# Stage definitions for progress tracking
STAGES = [
    {
        "id": 0,
        "icon": "📋",
        "title": "Understanding your requirements",
        "description": "Reading your inputs to understand what you need",
        "estimated_time": "30-45 seconds",
        "backend_name": "Summarizing intake",
    },
    {
        "id": 1,
        "icon": "🔍",
        "title": "Analyzing your data patterns",
        "description": "Finding trends that match your criteria",
        "estimated_time": "45-60 seconds",
        "backend_name": "Normalizing interview into StructuredNeeds",
    },
    {
        "id": 2,
        "icon": "🎯",
        "title": "Planning analysis approach",
        "description": "Deciding which calculations will be most helpful",
        "estimated_time": "30-45 seconds",
        "backend_name": "Planning analysis (tools)",
    },
    {
        "id": 3,
        "icon": "📊",
        "title": "Running calculations",
        "description": "Computing metrics and insights from your data",
        "estimated_time": "60-90 seconds",
        "backend_name": "Executing planned metrics",
    },
    {
        "id": 4,
        "icon": "✍️",
        "title": "Writing personalized recommendations",
        "description": "Creating tailored advice based on your specific needs",
        "estimated_time": "45-75 seconds",
        "backend_name": "Synthesizing report sections",
    },
    {
        "id": 5,
        "icon": "🏦",
        "title": "Identifying potential funders",
        "description": "Finding foundations and grants that match your project",
        "estimated_time": "30-60 seconds",
        "backend_name": "Generating recommendations",
    },
    {
        "id": 6,
        "icon": "📈",
        "title": "Creating final report",
        "description": "Building charts and formatting your complete analysis",
        "estimated_time": "30-45 seconds",
        "backend_name": "Building figures and finalizing",
    },
]


def get_stage_info(backend_name: str) -> dict | None:
    """Map backend progress messages to stage info."""
    lowered = backend_name.lower()
    return next((s for s in STAGES if s["backend_name"].lower() in lowered), None)


def create_progress_callback(report_id: str) -> callable:
    """Create a callback function that updates the progress store (thread-safe)."""

    def update_progress(stage_index: int, status: str, message: str = "") -> None:
        data = {
            "current_stage": stage_index,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with _LOCK:
            existing = _PROGRESS_STATE.get(report_id, {})
            existing.update(data)
            _PROGRESS_STATE[report_id] = existing

    return update_progress


def _push_progress(report_id: str, message: str) -> None:
    """Append progress log and gently advance stage in the store (thread-safe)."""
    with _LOCK:
        # Detailed log
        logs = _PROGRESS_LOGS.setdefault(report_id, [])
        logs.append(f"[{datetime.utcnow().isoformat()}Z] {message}")

        # Stage inference from message
        # Lazy resolve stage mapping; tolerate absence during early import
        stage_info: dict | None
        try:
            from advisor.ui_progress import get_stage_info as _ui_get_stage_info  # type: ignore

            stage_info = _ui_get_stage_info(message)
        except ImportError:
            stage_info = get_stage_info(message)

        state = _PROGRESS_STATE.get(report_id, {})
        # Do not override terminal states
        if state.get("status") not in {"completed", "error"}:
            if stage_info:
                state.update(
                    {
                        "current_stage": stage_info["id"],
                        # Always mark as running when advancing/informing a stage
                        "status": "running",
                        "message": message,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            else:
                # No stage mapping, still ensure status reflects active work
                state.update(
                    {
                        "status": "running",
                        "message": message,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            _PROGRESS_STATE[report_id] = state


def _persist_report(report_id: str, report: ReportBundle) -> None:
    """Persist the final report in an in-memory store (thread-safe)."""
    with _LOCK:
        _REPORT_STORE[report_id] = report


def get_progress_log(report_id: str) -> list[str]:
    """Get the progress log for a report (thread-safe)."""
    with _LOCK:
        return list(_PROGRESS_LOGS.get(report_id, []))


def get_progress_state(report_id: str) -> dict[str, Any]:
    """Get the progress state for a report (thread-safe)."""
    with _LOCK:
        return dict(_PROGRESS_STATE.get(report_id, {}))


def get_report(report_id: str) -> ReportBundle | None:
    """Get the persisted report if available (thread-safe)."""
    with _LOCK:
        return _REPORT_STORE.get(report_id)


def cleanup_progress_data(report_id: str) -> None:
    """Clean up progress data and report (thread-safe)."""
    with _LOCK:
        _PROGRESS_LOGS.pop(report_id, None)
        _PROGRESS_STATE.pop(report_id, None)
        _REPORT_STORE.pop(report_id, None)
