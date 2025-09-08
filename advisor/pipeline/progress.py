from datetime import datetime
import streamlit as st
from typing import Optional, Dict, Any, List

from .imports import ReportBundle

def _push_progress(report_id: str, message: str) -> None:
    """Enhanced progress push that also updates UI progress state."""
    try:
        # Store detailed progress log (existing functionality)
        prog = st.session_state.setdefault("advisor_progress", {})
        arr = prog.setdefault(report_id, [])
        arr.append(f"[{datetime.utcnow().isoformat()}Z] {message}")
        
        # Update UI progress state if available
        try:
            from advisor.ui_progress import get_stage_info
            stage_info = get_stage_info(message)
            if stage_info:
                progress_key = f"advisor_progress_{report_id}"
                progress_data = st.session_state.get(progress_key, {})
                progress_data.update({
                    "current_stage": stage_info["id"],
                    "status": "running",
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
