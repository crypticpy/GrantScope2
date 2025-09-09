import sys
from types import ModuleType
import pytest


def _install_fake_streamlit(monkeypatch):
    """
    Install a minimal fake 'streamlit' module to satisfy utils.navigation dependencies.
    Provides a dict-like session_state and no-op UI functions.
    """
    st_mod = ModuleType("streamlit")
    # Minimal session_state
    setattr(st_mod, "session_state", {})

    # No-op UI helpers possibly touched by navigation fallbacks
    def _info(*_args, **_kwargs):
        return None

    def _page_link(*_args, **_kwargs):
        return None

    # Sidebar container placeholder
    sidebar = ModuleType("streamlit.sidebar")
    setattr(sidebar, "page_link", _page_link)
    setattr(st_mod, "sidebar", sidebar)

    setattr(st_mod, "info", _info)
    setattr(st_mod, "page_link", _page_link)

    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    return st_mod


class TestNavigationFlow:
    def test_get_recommended_next_and_breadcrumbs(self, monkeypatch):
        # Arrange: fake Streamlit
        st_mod = _install_fake_streamlit(monkeypatch)

        # Import after faking streamlit
        import utils.navigation as nav  # type: ignore

        # Start clean
        nav.clear_breadcrumbs()

        # Act: push three steps in the guided flow
        nav.push_breadcrumb("Data Summary", "pages/1_Data_Summary.py")
        nav.push_breadcrumb("Grant Amount Distribution", "pages/2_Grant_Amount_Distribution.py")
        nav.push_breadcrumb("Scatter (over time)", "pages/4_Grant_Amount_Scatter_Plot.py")

        # Assert: breadcrumbs order and derived slugs
        bc = nav.get_breadcrumbs()
        assert isinstance(bc, list) and len(bc) == 3
        assert bc[0]["page"] == "pages/1_Data_Summary.py"
        assert bc[1]["page"] == "pages/2_Grant_Amount_Distribution.py"
        assert bc[2]["page"] == "pages/4_Grant_Amount_Scatter_Plot.py"

        # Last/next slug sync
        import sys
        ss = getattr(sys.modules.get("streamlit"), "session_state", {})
        assert ss.get("last_page_slug") == "grant_amount_scatter"
        # Next after scatter should be Heatmap per mapping
        assert ss.get("next_page_slug") == "grant_amount_heatmap"

        # Recommended next API (slug and file)
        next_file = nav.get_recommended_next_page("grant_amount_scatter")
        assert next_file == "pages/3_Grant_Amount_Heatmap.py"
        next_file_from_file = nav.get_recommended_next_page("pages/4_Grant_Amount_Scatter_Plot.py")
        assert next_file_from_file == "pages/3_Grant_Amount_Heatmap.py"

    def test_compute_continue_state(self):
        import utils.navigation as nav  # type: ignore

        # Enabled state with next label
        enabled, tip = nav.compute_continue_state(True, next_label="Heatmap")
        assert enabled is True
        assert tip == "Next: Heatmap"

        # Disabled state fallback tooltip
        enabled2, tip2 = nav.compute_continue_state(False)
        assert enabled2 is False
        assert tip2.startswith("Load your data to continue.")