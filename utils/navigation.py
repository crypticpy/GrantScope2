"""Navigation utilities for Newbie Mode: recommended next page, breadcrumbs, and programmatic navigation.

Public API (as per architecture/task):
- get_recommended_next_page(current_page_id: str, mode: str = "newbie") -> str
- push_breadcrumb(label: str, page_file: str) -> None
- get_breadcrumbs() -> list[dict]
- clear_breadcrumbs() -> None
- continue_to(page_file: str) -> None

Additional helpers (internal but exported for convenience/tests):
- get_page_label(identifier: str) -> str
- compute_continue_state(data_loaded: bool, next_label: str | None = None) -> tuple[bool, str]
"""

from __future__ import annotations

import sys

import streamlit as st

try:
    # Optional config integration (feature flags)
    from config import is_enabled as _is_enabled  # type: ignore
except Exception:

    def _is_enabled(_flag: str) -> bool:  # fallback
        return False


# Ordered guided flow: (slug, file, display label)
_PAGE_SEQUENCE: list[tuple[str, str, str]] = [
    ("data_summary", "pages/1_Data_Summary.py", "Data Summary"),
    (
        "grant_amount_distribution",
        "pages/2_Grant_Amount_Distribution.py",
        "Grant Amount Distribution",
    ),
    ("grant_amount_scatter", "pages/4_Grant_Amount_Scatter_Plot.py", "Scatter (over time)"),
    ("grant_amount_heatmap", "pages/3_Grant_Amount_Heatmap.py", "Heatmap"),
    ("treemaps_extended", "pages/6_Treemaps_Extended_Analysis.py", "Treemaps"),
    ("grant_description_word_clouds", "pages/5_Grant_Description_Word_Clouds.py", "Word Clouds"),
    (
        "general_analysis_relationships",
        "pages/7_General_Analysis_of_Relationships.py",
        "Relationships",
    ),
    ("top_categories_unique_grants", "pages/8_Top_Categories_Unique_Grants.py", "Top Categories"),
    ("budget_reality_check", "pages/12_Budget_Reality_Check.py", "Budget Reality Check"),
    ("project_planner", "pages/9_Project_Planner.py", "Project Planner"),
    ("advisor_report", "pages/0_Grant_Advisor_Interview.py", "Advisor Report"),
]

# Derived lookup maps
_SLUG_TO_FILE: dict[str, str] = {s: f for s, f, _ in _PAGE_SEQUENCE}
_FILE_TO_SLUG: dict[str, str] = {f: s for s, f, _ in _PAGE_SEQUENCE}
_SLUG_TO_LABEL: dict[str, str] = {s: lbl for s, _, lbl in _PAGE_SEQUENCE}
_FILE_TO_LABEL: dict[str, str] = {f: lbl for s, f, lbl in _PAGE_SEQUENCE}


def _normalize_identifier(identifier: str) -> str:
    """Normalize an identifier (slug or file path) to slug."""
    if identifier in _SLUG_TO_FILE:
        return identifier
    # Try to interpret as file
    if identifier in _FILE_TO_SLUG:
        return _FILE_TO_SLUG[identifier]
    # Try basename matching for some environments
    # e.g., "1_Data_Summary.py" -> "pages/1_Data_Summary.py"
    for file_path, slug in _FILE_TO_SLUG.items():
        base = file_path.split("/")[-1]
        if identifier == base:
            return slug
    # Unknown: return as-is (may result in no-op next-page)
    return identifier


def get_page_label(identifier: str) -> str:
    """Return the user-facing label for a given slug or file identifier."""
    slug = _normalize_identifier(identifier)
    label = _SLUG_TO_LABEL.get(slug)
    if label:
        return label
    # Fallback: if identifier is file
    if identifier in _FILE_TO_LABEL:
        return _FILE_TO_LABEL[identifier]
    # Last resort
    return identifier


def get_recommended_next_page(current_page_id: str, mode: str = "newbie") -> str:
    """Return the next page file path in the guided flow for the given current page id (slug or file).

    If current page is the last in the sequence or unknown, returns the same page file when possible.
    """
    # Mode currently only supports "newbie" vs "pro" (pro: same mapping but we gate UI elsewhere)
    _ = mode  # reserved for future use
    slug = _normalize_identifier(current_page_id)
    try:
        idx = [s for s, *_ in _PAGE_SEQUENCE].index(slug)
    except ValueError:
        # Unknown slug; try to interpret as file path directly
        if current_page_id in _FILE_TO_SLUG:
            slug = _FILE_TO_SLUG[current_page_id]
            idx = [s for s, *_ in _PAGE_SEQUENCE].index(slug)
        else:
            # Unknown: best effort no-op
            return _SLUG_TO_FILE.get(slug, current_page_id)

    if idx + 1 < len(_PAGE_SEQUENCE):
        next_slug = _PAGE_SEQUENCE[idx + 1][0]
        return _SLUG_TO_FILE[next_slug]
    # Already at last page; stay on current
    return _SLUG_TO_FILE.get(slug, current_page_id)


def push_breadcrumb(label: str, page_file: str) -> None:
    """Append a breadcrumb entry {label, page} to session state, avoiding duplicates and bounding length."""
    # Manage breadcrumb list defensively
    try:
        bc = st.session_state.get("breadcrumbs", [])
        if not isinstance(bc, list):
            bc = []
    except Exception:
        # Initialize session_state in extremely constrained environments (tests)
        try:
            if not hasattr(st, "session_state") or not isinstance(st.session_state, dict):
                st.session_state = {}  # type: ignore[attr-defined]
        except Exception:
            return
        bc = []

    entry = {"label": str(label), "page": str(page_file)}
    if not bc or bc[-1] != entry:
        bc.append(entry)
        # Bound breadcrumb length to the latest 10 entries
        if len(bc) > 10:
            bc = bc[-10:]
    st.session_state["breadcrumbs"] = bc

    # Compute and persist slugs (avoid exceptions; do not swallow silently)
    current_slug = _FILE_TO_SLUG.get(page_file) or _normalize_identifier(page_file)
    st.session_state["last_page_slug"] = current_slug

    next_file = get_recommended_next_page(current_slug)
    # Avoid evaluating default callable unnecessarily
    next_slug = _FILE_TO_SLUG.get(next_file) or _normalize_identifier(next_file)
    st.session_state["next_page_slug"] = next_slug

    # In stubbed/test environments, ensure sys.modules reference sees the updated dict
    try:
        mod = sys.modules.get("streamlit")
        if mod is not None:
            # Point module session_state to the same dict instance (or update it)
            try:
                # If it's a dict-like, update keys to ensure visibility
                mod.session_state.update(st.session_state)  # type: ignore[attr-defined]
            except Exception:
                # Fallback to direct assignment of the reference
                mod.session_state = st.session_state  # type: ignore[attr-defined]
    except Exception:
        # Non-fatal; navigation must not break page rendering
        pass


def get_breadcrumbs() -> list[dict[str, str]]:
    """Return the breadcrumbs list from session state, defaulting to empty list.

    Also ensures last_page_slug and next_page_slug are synced based on the
    latest breadcrumb, which helps in stubbed/test environments.
    """
    try:
        ss = getattr(st, "session_state", {})
    except Exception:
        ss = {}
    bc = ss.get("breadcrumbs", [])
    if isinstance(bc, list):
        # Ensure normalized shape
        cleaned: list[dict[str, str]] = []
        for item in bc:
            if isinstance(item, dict) and "label" in item and "page" in item:
                cleaned.append({"label": str(item["label"]), "page": str(item["page"])})
        # Derive and persist last/next slugs from the latest breadcrumb when possible
        if cleaned:
            current_file = cleaned[-1]["page"]
            current_slug = _FILE_TO_SLUG.get(current_file) or _normalize_identifier(current_file)
            try:
                next_file = get_recommended_next_page(current_slug)
                next_slug = _FILE_TO_SLUG.get(next_file) or _normalize_identifier(next_file)
            except Exception:
                next_slug = None  # type: ignore[assignment]
            # Persist directly to Streamlit session_state (works in tests with stubbed dict)
            try:
                st.session_state["last_page_slug"] = current_slug  # type: ignore[index]
                if next_slug is not None:
                    st.session_state["next_page_slug"] = next_slug  # type: ignore[index]
            except Exception:
                # Do not fail if session_state is not writable
                pass
            except Exception:
                # Do not fail breadcrumbs retrieval if slug derivation has issues
                pass
        return cleaned
    return []


def clear_breadcrumbs() -> None:
    """Clear breadcrumb-related session keys."""
    for key in ("breadcrumbs", "last_page_slug", "next_page_slug"):
        if key in st.session_state:
            del st.session_state[key]


def compute_continue_state(data_loaded: bool, next_label: str | None = None) -> tuple[bool, str]:
    """Determine if Continue should be enabled and the tooltip to show.

    Returns: (enabled, tooltip)
    - When enabled=True, tooltip follows Writer Pack: 'Next: {Next Page Name}'
    - When enabled=False, tooltip follows Writer Pack default: 'Load your data to continue.'
    """
    if data_loaded:
        tip = f"Next: {next_label}" if next_label else "Next step available"
        return True, tip
    # Disabled default tooltip from Writer Pack
    return False, "Load your data to continue."


def continue_to(page_file: str) -> None:
    """Navigate to the given page file if st.switch_page is available; otherwise provide a fallback hint.

    This function is safe to call from a button handler.
    """
    try:
        if hasattr(st, "switch_page"):
            # Newer Streamlit supports programmatic page navigation
            st.switch_page(page_file)  # type: ignore[attr-defined]
            return
    except Exception:
        # Fall through to fallback
        pass

    # Fallback: show a clickable link (works across Streamlit variants)
    try:
        if hasattr(st, "page_link"):
            st.page_link(page_file, label="Continue →")
        elif hasattr(st.sidebar, "page_link"):  # type: ignore[attr-defined]
            st.sidebar.page_link(page_file, label="Continue →")  # type: ignore[attr-defined]
        else:
            # As a last resort, display an instruction
            lbl = _FILE_TO_LABEL.get(page_file, page_file)
            st.info(f"Next: {lbl}. Use the sidebar to navigate.")
    except Exception:
        # Do not break the app if navigation helpers are unavailable
        lbl = _FILE_TO_LABEL.get(page_file, page_file)
        st.info(f"Next: {lbl}. Use the sidebar to navigate.")
