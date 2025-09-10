import sys
from types import ModuleType


def _install_fake_streamlit(monkeypatch):
    """
    Install a minimal fake 'streamlit' module that captures markdown calls and supports expander().
    """
    st_mod = ModuleType("streamlit")

    # Storage for assertions
    st_mod._md_calls = []

    # Minimal session_state
    st_mod.session_state = {}

    # expander context manager
    class _Expander:
        def __init__(self, label: str, expanded: bool = False):
            self.label = label
            self.expanded = expanded

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _expander(label: str, expanded: bool = False):
        # Return a dummy context manager; content inside uses st.markdown(), not self.markdown()
        return _Expander(label, expanded)

    def _markdown(txt: str, **_kwargs):
        st_mod._md_calls.append(str(txt))

    # Sidebar placeholder (not used but present for parity)
    sidebar = ModuleType("streamlit.sidebar")

    st_mod.expander = _expander
    st_mod.markdown = _markdown
    st_mod.sidebar = sidebar

    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    return st_mod


def _install_fake_config(monkeypatch, enabled: bool):
    """
    Provide a lightweight 'config' module whose is_enabled(flag) returns enabled.
    """
    cfg = ModuleType("config")

    def is_enabled(_flag: str) -> bool:
        return bool(enabled)

    cfg.is_enabled = is_enabled
    monkeypatch.setitem(sys.modules, "config", cfg)
    return cfg


class TestHelpPanels:
    def test_render_page_help_panel_newbie_renders_copy(self, monkeypatch):
        # Arrange: fake streamlit and config with helpers enabled
        st_mod = _install_fake_streamlit(monkeypatch)
        _install_fake_config(monkeypatch, enabled=True)

        # Import after patching
        from utils.help import render_page_help_panel  # type: ignore

        # Act: render help for a known page slug with audience 'new'
        render_page_help_panel("project_planner", audience="new")

        # Assert: markdown content was emitted and includes the expected heading/title
        out = "\n".join(st_mod._md_calls)  # type: ignore[attr-defined]
        assert out, "Expected markdown to be emitted for newbie help panel"
        assert "### Project Planner" in out or "Project Planner" in out
        # Basic bullet presence from Writer Pack-aligned content
        assert "-" in out, "Expected bullet content in help panel"

    def test_render_page_help_panel_disabled_no_output(self, monkeypatch):
        # Arrange: fake streamlit and disable helpers
        st_mod = _install_fake_streamlit(monkeypatch)
        _install_fake_config(monkeypatch, enabled=False)

        # Import and override (safety if help was previously imported)
        import importlib

        help_mod = importlib.import_module("utils.help")  # type: ignore
        # Force is_enabled to return False regardless of config module cache
        monkeypatch.setattr(help_mod, "is_enabled", lambda _flag: False, raising=False)

        # Clear any previous calls
        st_mod._md_calls.clear()  # type: ignore[attr-defined]

        # Act
        help_mod.render_page_help_panel("project_planner", audience="new")  # type: ignore[attr-defined]

        # Assert: no markdown output when disabled
        assert len(st_mod._md_calls) == 0  # type: ignore[attr-defined]
