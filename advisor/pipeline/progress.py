from datetime import datetime
import streamlit as st
from typing import Optional, Dict, Any, List
import threading

_LOCK = threading.Lock()

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

def get_stage_info(backend_name: str) -> Optional[Dict]:
    """Map backend progress messages to stage info."""
    for stage in STAGES:
        if stage["backend_name"].lower() in backend_name.lower():
            return stage
    return None


def create_progress_callback(report_id: str) -> callable:
    """Create a callback function that updates the UI progress state."""
    
    def update_progress(stage_index: int, status: str, message: str = "") -> None:
        """Update the progress state in session_state."""
        try:
            progress_key = f"advisor_progress_{report_id}"
            progress_data = st.session_state.get(progress_key, {})
            
            progress_data.update({
                "current_stage": stage_index,
                "status": status,  # 'running', 'completed', 'error'
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            st.session_state[progress_key] = progress_data
            
        except Exception:
            # Don't let progress updates break the pipeline
            pass
    
    return update_progress


def _push_progress(report_id: str, message: str) -> None:
    """Enhanced progress push that also updates UI progress state."""
    try:
        with _LOCK:
            # Store detailed progress log (existing functionality)
            prog = st.session_state.setdefault("advisor_progress", {})
            arr = prog.setdefault(report_id, [])
            arr.append(f"[{datetime.utcnow().isoformat()}Z] {message}")
            
            # Update UI progress state conservatively (do not override callback status)
            try:
                from advisor.ui_progress import get_stage_info
                stage_info = get_stage_info(message)
                if stage_info:
                    progress_key = f"advisor_progress_{report_id}"
                    progress_data = st.session_state.get(progress_key, {})
                    # Do not override completed/error states set by callback
                    if progress_data.get("status") in {"completed", "error"}:
                        st.session_state[progress_key] = progress_data
                    else:
                        progress_data.update({
                            "current_stage": stage_info["id"],
                            "status": progress_data.get("status", "running"),
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        st.session_state[progress_key] = progress_data
            except ImportError:
                # UI progress module not available yet
                pass
            
    except Exception:
        # Don't let progress updates break the pipeline
        pass

def _persist_report(report_id: str, report: ReportBundle) -> None:
    try:
        store = st.session_state.setdefault("advisor_store", {})
        store[report_id] = report
    except Exception:
        pass

def get_progress_log(report_id: str) -> List[str]:
    """Get the progress log for a report."""
    try:
        prog = st.session_state.get("advisor_progress", {})
        return prog.get(report_id, [])
    except Exception:
        return []

def cleanup_progress_data(report_id: str) -> None:
    """Clean up progress data for a report."""
    try:
        # Clean up detailed log
        prog = st.session_state.get("advisor_progress", {})
        if report_id in prog:
            del prog[report_id]
            
        # Clean up UI progress state
        progress_key = f"advisor_progress_{report_id}"
        if progress_key in st.session_state:
            del st.session_state[progress_key]
            
    except Exception:
        pass
