import sys
from types import ModuleType
import pytest


def _install_fake_streamlit(monkeypatch):
    """
    Install a minimal stub for the 'streamlit' module into sys.modules so that
    utils/navigation.py can import it without the real dependency.
    """
    st_mod = ModuleType("streamlit")
    # Simple dict-like session_state
    setattr(st_mod, "session_state", {})

    # Optional APIs referenced in utils/navigation (no-ops for tests)
    def _page_link(*_args, **_kwargs):
        return None

    def _info(*_args, **_kwargs):
        return None

    setattr(st_mod, "page_link", _page_link)
    setattr(st_mod, "info", _info)

    # Provide a stub 'sidebar' with a page_link attribute to satisfy fallbacks
    sidebar_mod = ModuleType("streamlit.sidebar")
    setattr(sidebar_mod, "page_link", _page_link)
    setattr(st_mod, "sidebar", sidebar_mod)

    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    return st_mod


@pytest.fixture(autouse=True)
def _auto_stub_streamlit(monkeypatch):
    _install_fake_streamlit(monkeypatch)
    # Ensure a clean session_state for each test
    sys.modules["streamlit"].session_state.clear()
    yield
    sys.modules["streamlit"].session_state.clear()


class TestNavigationFlow:
    def test_sequence_next_mapping(self):
        from utils.navigation import get_recommended_next_page

        # Current: data_summary -> Next: 2_Grant_Amount_Distribution
        nxt = get_recommended_next_page("data_summary")
        assert nxt.endswith("pages/2_Grant_Amount_Distribution.py")

        # Current: grant_amount_distribution -> Next: 4_Grant_Amount_Scatter_Plot
        nxt = get_recommended_next_page("grant_amount_distribution")
        assert nxt.endswith("pages/4_Grant_Amount_Scatter_Plot.py")

        # Current: grant_amount_scatter -> Next: 3_Grant_Amount_Heatmap
        nxt = get_recommended_next_page("grant_amount_scatter")
        assert nxt.endswith("pages/3_Grant_Amount_Heatmap.py")

    def test_breadcrumb_order_across_three_pages(self):
        from utils.navigation import clear_breadcrumbs, push_breadcrumb, get_breadcrumbs, get_page_label

        clear_breadcrumbs()

        # Simulate visiting three pages in order
        push_breadcrumb(get_page_label("data_summary"), "pages/1_Data_Summary.py")
        push_breadcrumb(get_page_label("grant_amount_distribution"), "pages/2_Grant_Amount_Distribution.py")
        push_breadcrumb(get_page_label("grant_amount_scatter"), "pages/4_Grant_Amount_Scatter_Plot.py")

        bc = get_breadcrumbs()
        assert isinstance(bc, list)
        labels = [item["label"] for item in bc]
        assert labels == ["Data Summary", "Grant Amount Distribution", "Scatter (over time)"]

        # Validate last/next slugs are tracked in session
        st = sys.modules["streamlit"]
        assert st.session_state.get("last_page_slug") == "grant_amount_scatter"
        # Next after scatter is heatmap
        assert st.session_state.get("next_page_slug") == "grant_amount_heatmap"

    def test_continue_state_tooltips_and_enablement(self):
        from utils.navigation import compute_continue_state

        enabled, tip = compute_continue_state(data_loaded=True, next_label="Grant Amount Distribution")
        assert enabled is True
        assert tip == "Next: Grant Amount Distribution"

        enabled, tip = compute_continue_state(data_loaded=False, next_label="Grant Amount Distribution")
        assert enabled is False
        assert tip == "Load your data to continue."

    def test_get_page_label_from_slug_and_file(self):
        from utils.navigation import get_page_label

        assert get_page_label("data_summary") == "Data Summary"
        assert get_page_label("pages/2_Grant_Amount_Distribution.py") == "Grant Amount Distribution"