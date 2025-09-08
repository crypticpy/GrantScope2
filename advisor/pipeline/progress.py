from datetime import datetime
import streamlit as st
from .imports import ReportBundle

def _push_progress(report_id: str, message: str) -> None:
    try:
        prog = st.session_state.setdefault("advisor_progress", {})
        arr = prog.setdefault(report_id, [])
        arr.append(f"[{datetime.utcnow().isoformat()}Z] {message}")
    except Exception:
        pass

def _persist_report(report_id: str, report: ReportBundle) -> None:
    try:
        store = st.session_state.setdefault("advisor_store", {})
        store[report_id] = report
    except Exception:
        pass
