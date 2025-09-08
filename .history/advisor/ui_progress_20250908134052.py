"""Live progress tracking UI components for the grant advisor pipeline."""

import streamlit as st
from typing import Dict, Optional
import threading
from advisor.pipeline.progress import get_progress_state  # type: ignore

_LOCK = threading.Lock()


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
    return next((s for s in STAGES if s["backend_name"] in backend_name), None)


def create_progress_callback(report_id: str) -> callable:
    """Create a callback function that updates the UI progress state."""
    
    def update_progress(stage_index: int, status: str, message: str = "") -> None:
        """Update the progress state in session_state."""
        from contextlib import suppress
        with suppress(Exception):
            with _LOCK:
                _ = (report_id, stage_index, status, message)
    
    return update_progress


def render_live_progress_tracker(report_id: str, show_estimates: bool = True) -> None:
    """Render the animated step tracker with live progress."""
    
    progress_data = get_progress_state(report_id)
    current_stage = progress_data.get("current_stage", -1)
    status = progress_data.get("status", "pending")
    
    st.markdown("### Analysis Progress")
    
    # Create a container for the progress tracker
    progress_container = st.container()
    
    with progress_container:
        for i, stage in enumerate(STAGES):
            # Determine the stage status
            if i < current_stage:
                # Completed stage
                col1, col2 = st.columns([1, 20])
                with col1:
                    st.success("✅")
                with col2:
                    st.success(f"{stage['icon']} {stage['title']}")
                    
            elif i == current_stage:
                # Current stage - show with animation
                col1, col2 = st.columns([1, 20])
                with col1:
                    if status == "running":
                        # Use a spinner for the current stage
                        with st.spinner(""):
                            st.write("🔄")
                    elif status == "error":
                        st.error("❌")
                    else:
                        st.info("⏳")
                        
                with col2:
                    if status == "running":
                        st.info(f"{stage['icon']} {stage['title']}...")
                        st.caption(f"📝 {stage['description']}")
                        if show_estimates:
                            st.caption(f"⏱️ Estimated: {stage['estimated_time']}")
                    elif status == "error":
                        st.error(f"{stage['icon']} {stage['title']} - Error occurred")
                    else:
                        st.warning(f"{stage['icon']} {stage['title']} - Waiting...")
                        
            else:
                # Pending stage
                col1, col2 = st.columns([1, 20])
                with col1:
                    st.write("⏸️")
                with col2:
                    st.caption(f"{stage['icon']} {stage['title']}")
    
    # Show overall progress bar
    if current_stage >= 0:
        progress_pct = min((current_stage + 1) / len(STAGES), 1.0)
        st.progress(progress_pct, f"Step {current_stage + 1} of {len(STAGES)} complete")


def render_minimal_progress(report_id: str) -> None:
    """Render a minimal progress indicator for tight spaces."""
    
    progress_data = get_progress_state(report_id)
    current_stage = progress_data.get("current_stage", -1)
    
    if current_stage >= 0 and current_stage < len(STAGES):
        stage = STAGES[current_stage]
        with st.spinner(f"{stage['icon']} {stage['title']}..."):
            st.caption(f"Step {current_stage + 1} of {len(STAGES)}")


def cleanup_progress_state(report_id: str) -> None:
    """Clean up progress state after completion."""
    from contextlib import suppress
    with suppress(Exception):
        _ = report_id