#!/usr/bin/env python3
"""
Test script to demonstrate the new live progress tracking for Grant Advisor.
This simulates the pipeline stages to show how the UI updates.
"""

import streamlit as st
import time
import random
from advisor.ui_progress import render_live_progress_tracker, STAGES, create_progress_callback

def test_progress_tracking():
    """Test the new progress tracking system."""
    
    st.title("🚀 Grant Advisor Progress Tracker Demo")
    st.markdown("""
    This demo shows the new **live progress tracking** system for the Grant Advisor interview process.
    
    ### What's New:
    - 📋 **7 clear stages** with descriptive names and icons
    - 🔄 **Live animations** showing current activity  
    - ⏱️ **Time estimates** so users know what to expect
    - ✅ **Checkmarks** for completed stages
    - ⏸️ **Visual indicators** for pending stages
    - 📊 **Overall progress bar** showing completion percentage
    
    ---
    """)
    
    if st.button("🚀 Start Demo Analysis", type="primary"):
        # Generate a mock report ID
        import time
        report_id = f"DEMO-{int(time.time())}"
        
        # Create progress callback
        progress_callback = create_progress_callback(report_id)
        
        # Create placeholder for progress tracker
        progress_placeholder = st.empty()
        
        st.info("🎯 Starting analysis pipeline...")
        
        # Simulate the pipeline stages
        for i, stage in enumerate(STAGES):
            # Update progress
            progress_callback(i, 'running', f'Starting {stage["title"]}')
            
            # Show the progress tracker
            with progress_placeholder:
                render_live_progress_tracker(report_id, show_estimates=True)
            
            # Simulate work being done (with some randomness)
            work_time = random.uniform(2, 4)  # 2-4 seconds per stage
            
            # Show what's happening
            with st.spinner(f"🔄 {stage['icon']} {stage['title']}..."):
                st.caption(f"📝 {stage['description']}")
                st.caption(f"⏱️ Estimated: {stage['estimated_time']}")
                time.sleep(work_time)
            
            # Mark stage as complete
            progress_callback(i, 'completed', f'Finished {stage["title"]}')
            
            # Show completion message for this stage
            st.success(f"✅ {stage['icon']} {stage['title']} - Complete!")
            
            # Small pause between stages
            time.sleep(0.5)
        
        # Clear progress tracker and show completion
        progress_placeholder.empty()
        
        st.balloons()
        st.success("🎉 **Analysis Complete!** All stages finished successfully.")
        
        st.markdown("""
        ---
        ### Summary
        The new progress tracker provides:
        - **Clear visibility** into what the system is doing
        - **Educational context** for non-technical users  
        - **Time expectations** to manage user patience
        - **Visual feedback** that builds confidence
        - **Professional polish** that enhances the user experience
        """)

if __name__ == "__main__":
    test_progress_tracking()