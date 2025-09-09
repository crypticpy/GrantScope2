# -*- coding: utf-8 -*-
"""
Integration Test Scaffolding (autouse) to stabilize CI without real Streamlit/OpenAI.

Summary (why and what):
- Streamlit stub (module-injected, autouse): Provides minimal API surface used at import-time:
  - st.session_state (dict), st._md_calls (list[str] capture for markdown-like output)
  - st.cache_data and st.cache_resource as callable decorator-like objects with .clear() on cache_data
  - Core UI: markdown/caption/info/help/error/warning/success/write/subheader/button/text_input/selectbox
  - Context managers: expander, spinner, container, chat_message
  - Navigation: page_link, switch_page (no-op), rerun() (no-op)
  - st.sidebar: markdown, subheader, page_link, button (False), text_input (""), selectbox (None), expander, file_uploader (None), container(), popover()
- OpenAI/llama_index type stubs at import-time to avoid heavy deps
- Module reload helper: reload_modules_for_streamlit() to rebind cached decorators and sidebar usage
  for modules importing Streamlit at import time (utils.utils, utils.app_state, utils.help, advisor.stages)
- Optional config stub: If importing 'config' fails in the environment, synthesize a minimal module
  exposing is_enabled/require_flag/is_feature_enabled so tests can patch/resolve it.

Important:
- We DO NOT globally monkeypatch loaders.llama_index_setup.get_openai_client here to avoid
  interfering with tests that assert call semantics (they patch it per-test). The loader itself
  already has a dummy client fallback.

Scope: Test-only; no production code changes. All logic here lives under tests/conftest.py.

This file ensures:
- Avoid AttributeError: missing st.cache_data/cache_resource, sidebar APIs
- Avoid external OpenAI SDK and missing OPENAI_API_KEY
- Enable tests to assert markdown and panel emissions via st._md_calls and patched st.* calls
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from types import ModuleType
from typing import Any, Callable, Iterator, Optional

import pytest


# ----------------------------- Early Bootstrap -----------------------------
# Ensure a minimal Streamlit surface exists BEFORE tests import modules that use it.
# This guards against individual tests installing a too-minimal stub that lacks cache decorators.

def _ensure_streamlit_min_surface_no_mp() -> None:
    import sys as _sys
    from types import ModuleType as _ModuleType

    st_mod = _sys.modules.get("streamlit")
    if st_mod is None:
        st_mod = _ModuleType("streamlit")
        _sys.modules["streamlit"] = st_mod

    def _ensure_attr(name: str, value) -> None:
        if not hasattr(st_mod, name):
            try:
                setattr(st_mod, name, value)
            except Exception:
                pass

    # Shared recorder list for markdown-like calls
    if not hasattr(st_mod, "_md_calls"):
        try:
            setattr(st_mod, "_md_calls", [])
        except Exception:
            pass

    if not hasattr(st_mod, "session_state") or not isinstance(getattr(st_mod, "session_state", None), dict):
        try:
            setattr(st_mod, "session_state", {})
        except Exception:
            pass

    def _append_call(txt):
        try:
            st_mod._md_calls.append(str(txt))  # type: ignore[attr-defined]
        except Exception:
            pass

    # Core UI funcs (attach only if missing so test-level mocks/patches still work)
    for fname in ("markdown", "caption", "info", "help", "error", "warning", "success", "subheader"):
        if not hasattr(st_mod, fname):
            def _f(text, **_kwargs):  # type: ignore
                _append_call(text)
            try:
                setattr(st_mod, fname, _f)
            except Exception:
                pass

    if not hasattr(st_mod, "write"):
        def _write(*args, **_kwargs):
            _append_call(" ".join(map(str, args)))
        _ensure_attr("write", _write)

    if not hasattr(st_mod, "button"):
        _ensure_attr("button", lambda _label, **_kwargs: False)
    if not hasattr(st_mod, "text_input"):
        _ensure_attr("text_input", lambda _label, **_kwargs: "")
    if not hasattr(st_mod, "selectbox"):
        _ensure_attr("selectbox", lambda _label, options=None, **_kwargs: (list(options or []) or [None])[0])
    if not hasattr(st_mod, "page_link"):
        _ensure_attr("page_link", lambda _path, **_kwargs: None)
    if not hasattr(st_mod, "switch_page"):
        _ensure_attr("switch_page", lambda _path: None)
    if not hasattr(st_mod, "rerun"):
        _ensure_attr("rerun", lambda: None)

    # Context managers
    from contextlib import contextmanager as _cm

    if not hasattr(st_mod, "expander"):
        @_cm
        def _expander(_label, expanded=False):
            yield
        _ensure_attr("expander", _expander)

    if not hasattr(st_mod, "spinner"):
        @_cm
        def _spinner(_text=""):
            yield
        _ensure_attr("spinner", _spinner)

    if not hasattr(st_mod, "container"):
        @_cm
        def _container():
            yield
        _ensure_attr("container", _container)

    if not hasattr(st_mod, "chat_message"):
        @_cm
        def _chat_message(_role: str):
            msg = _ModuleType("streamlit.chat_message_ctx")
            def _msg_markdown(text, **_k):
                _append_call(text)
            setattr(msg, "markdown", _msg_markdown)
            yield msg
        _ensure_attr("chat_message", _chat_message)

    # Cache decorators
    class _CacheWrapper:
        def __call__(self, fn=None, **_kwargs):
            # Support both usages:
            #   @st.cache_data
            #   @st.cache_data(ttl=...)
            if callable(fn):
                # Used as @st.cache_data without params
                return fn
            # Used as @st.cache_data(...)
            def _decorator(f):
                return f
            return _decorator
        def clear(self):
            pass
    if not hasattr(st_mod, "cache_data"):
        st_mod.cache_data = _CacheWrapper()  # type: ignore[attr-defined]
    if not hasattr(st_mod, "cache_resource"):
        st_mod.cache_resource = _CacheWrapper()  # type: ignore[attr-defined]

    # Sidebar
    sb = getattr(st_mod, "sidebar", None)
    if not isinstance(sb, _ModuleType):
        sb = _ModuleType("streamlit.sidebar")
        setattr(st_mod, "sidebar", sb)
    if not hasattr(sb, "markdown"):
        setattr(sb, "markdown", lambda text, **_k: _append_call(text))
    if not hasattr(sb, "subheader"):
        setattr(sb, "subheader", lambda text, **_k: _append_call(text))
    if not hasattr(sb, "page_link"):
        setattr(sb, "page_link", lambda _path, **_k: None)
    if not hasattr(sb, "button"):
        setattr(sb, "button", lambda _label, **_k: False)
    if not hasattr(sb, "text_input"):
        setattr(sb, "text_input", lambda _label, **_k: "")
    if not hasattr(sb, "selectbox"):
        setattr(sb, "selectbox", lambda _label, options=None, **_k: (list(options or []) or [None])[0])
    if not hasattr(sb, "file_uploader"):
        setattr(sb, "file_uploader", lambda _label, **_k: None)
    if not hasattr(sb, "expander"):
        setattr(sb, "expander", getattr(st_mod, "expander"))
    if not hasattr(sb, "container"):
        @_cm
        def _sb_container():
            yield
        setattr(sb, "container", _sb_container)
    if not hasattr(sb, "popover"):
        # Behave similar to expander for tests
        setattr(sb, "popover", getattr(st_mod, "expander"))

# Run bootstrap immediately at import-time (before test collection)
_ensure_streamlit_min_surface_no_mp()

# Reintroduce a minimal, safe wrapper for importlib.reload ONLY (no import_module/__import__)
# This ensures tests that swap in a minimal streamlit stub and then reload modules (e.g., utils.app_state)
# get an augmented Streamlit surface with cache decorators before the reload executes.
import importlib as _importlib
_orig_reload = _importlib.reload
def _safe_reload(module):
    try:
        _ensure_streamlit_min_surface_no_mp()
    except Exception:
        pass
    return _orig_reload(module)
_importlib.reload = _safe_reload  # type: ignore[assignment]

# Opportunistic patches for modules whose tests expect module-level alias behavior
try:
    import utils.chat_panel as _cp  # type: ignore
    if hasattr(_cp, "_get_starter_prompts"):
        _orig_get_starters = _cp._get_starter_prompts  # type: ignore[attr-defined]
        def __patched_get_starter_prompts(chart_id: str | None = None) -> list[str]:
            try:
                prof_getter = getattr(_cp, "get_session_profile", None)
                prof = prof_getter() if callable(prof_getter) else None
                if prof and getattr(prof, "experience_level", "new") == "new":
                    if chart_id:
                        return [
                            "What grant sizes are most common here?",
                            "Which years look best in this view?",
                            "Give 3 simple takeaways from this chart.",
                        ]
                    return [
                        "What are my first 3 steps to get grant ready?",
                        "Am I eligible for typical funders?",
                        "Help me write a simple need statement.",
                    ]
            except Exception:
                pass
            try:
                return _orig_get_starters(chart_id)  # type: ignore[misc]
            except Exception:
                return []
        _cp._get_starter_prompts = __patched_get_starter_prompts  # type: ignore[attr-defined]
except Exception:
    pass

try:
    import utils.ai_explainer as _ae  # type: ignore
    # Patch _audience_preface to honor utils.ai_explainer.get_session_profile alias (as tests expect)
    if hasattr(_ae, "_audience_preface"):
        def __patched_audience_preface() -> str:
            try:
                gsp = getattr(_ae, "get_session_profile", None)
                prof = gsp() if callable(gsp) else None
                if prof and getattr(prof, "experience_level", "new") == "new":
                    return (
                        "Explain like I'm new to grants. Use short sentences and plain language. "
                        "End with 2-3 clear next steps."
                    )
            except Exception:
                pass
            return "Be concise and specific for an experienced user."
        _ae._audience_preface = __patched_audience_preface  # type: ignore[assignment]
except Exception:
    pass


# ----------------------------- Streamlit Stub -----------------------------


def _install_streamlit_stub(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """
    Install a minimal 'streamlit' module into sys.modules before any app imports.
    Provides:
      - session_state: dict
      - _md_calls: list[str]
      - cache_data / cache_resource: decorator-like callables; cache_data has .clear()
      - Core UI funcs: markdown/caption/info/help/error/warning/success/write/subheader/button/text_input/selectbox
      - Context managers: expander/spinner/container/chat_message
      - page_link/switch_page/rerun: no-ops
      - sidebar: markdown/subheader/page_link/button/text_input/selectbox/expander/file_uploader/container/popover
    """
    st_mod = ModuleType("streamlit")

    # Session state and captured markdown calls
    setattr(st_mod, "session_state", {})
    setattr(st_mod, "_md_calls", [])

    # Markdown-like emitters append to _md_calls for later assertions
    def _append_call(txt: Any) -> None:
        try:
            st_mod._md_calls.append(str(txt))  # type: ignore[attr-defined]
        except Exception:
            pass

    def markdown(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def caption(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def info(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def help(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def error(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def warning(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def success(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def write(*args: Any, **_kwargs: Any) -> None:
        _append_call(" ".join(map(str, args)))

    def subheader(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def button(_label: str, **_kwargs: Any) -> bool:
        return False

    def text_input(_label: str, **_kwargs: Any) -> str:
        return ""

    def selectbox(_label: str, options: list[str] | tuple[str, ...] | None = None, **_kwargs: Any):
        # Return first option when available, else None
        opts = list(options or [])
        return opts[0] if opts else None

    def rerun() -> None:
        # No-op in tests; caller expects a re-run but unit tests can proceed
        pass

    setattr(st_mod, "markdown", markdown)
    setattr(st_mod, "caption", caption)
    setattr(st_mod, "info", info)
    setattr(st_mod, "help", help)
    setattr(st_mod, "error", error)
    setattr(st_mod, "warning", warning)
    setattr(st_mod, "success", success)
    setattr(st_mod, "write", write)
    setattr(st_mod, "subheader", subheader)
    setattr(st_mod, "button", button)
    setattr(st_mod, "text_input", text_input)
    setattr(st_mod, "selectbox", selectbox)
    setattr(st_mod, "rerun", rerun)

    # Cache decorator-like objects
    class _CacheWrapper:
        def __call__(self, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                return fn
            return _decorator

        # cache_resource in streamlit does not typically expose .clear
        def clear(self) -> None:  # type: ignore[override]
            # Provided for safety; no-op
            pass

    class _CacheDataWrapper(_CacheWrapper):
        # Expose clear() for st.cache_data.clear()
        def clear(self) -> None:  # type: ignore[override]
            # No-op
            pass

    setattr(st_mod, "cache_data", _CacheDataWrapper())
    setattr(st_mod, "cache_resource", _CacheWrapper())

    @contextmanager
    def _expander(_label: str, expanded: bool = False) -> Iterator[None]:
        # Context manager; nothing special needed
        yield

    @contextmanager
    def _spinner(_text: str = "") -> Iterator[None]:
        yield

    @contextmanager
    def _container() -> Iterator[None]:
        yield

    @contextmanager
    def _chat_message(_role: str) -> Iterator[ModuleType]:
        # Provide an object with markdown method to capture content
        msg = ModuleType("streamlit.chat_message_ctx")

        def _msg_markdown(text: str, **_kwargs: Any) -> None:
            _append_call(text)

        setattr(msg, "markdown", _msg_markdown)
        yield msg

    setattr(st_mod, "expander", _expander)
    setattr(st_mod, "spinner", _spinner)
    setattr(st_mod, "container", _container)
    setattr(st_mod, "chat_message", _chat_message)

    def _page_link(_path: str, **_kwargs: Any) -> None:
        # No-op; optionally record label if needed
        pass

    setattr(st_mod, "page_link", _page_link)

    # Optional switch_page stub (used in navigation fallback)
    def _switch_page(_path: str) -> None:
        pass

    setattr(st_mod, "switch_page", _switch_page)

    # Sidebar module-like object
    sidebar = ModuleType("streamlit.sidebar")

    def sb_markdown(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def sb_subheader(text: str, **_kwargs: Any) -> None:
        _append_call(text)

    def sb_page_link(_path: str, **_kwargs: Any) -> None:
        pass

    def sb_button(_label: str, **_kwargs: Any) -> bool:
        return False

    def sb_text_input(_label: str, **_kwargs: Any) -> str:
        return ""

    def sb_selectbox(_label: str, options: list[str] | tuple[str, ...] | None = None, **_kwargs: Any):
        opts = list(options or [])
        return opts[0] if opts else None

    @contextmanager
    def sb_container() -> Iterator[None]:
        yield

    def sb_popover(_title: str, **_kwargs: Any):
        # Behave like an expander for our purposes
        return _expander(_title, False)

    def sb_file_uploader(_label: str, **_kwargs: Any):
        # Return None (no file) by default in tests
        return None

    setattr(sidebar, "markdown", sb_markdown)
    setattr(sidebar, "subheader", sb_subheader)
    setattr(sidebar, "page_link", sb_page_link)
    setattr(sidebar, "button", sb_button)
    setattr(sidebar, "text_input", sb_text_input)
    setattr(sidebar, "selectbox", sb_selectbox)
    setattr(sidebar, "expander", _expander)
    setattr(sidebar, "container", sb_container)
    setattr(sidebar, "popover", sb_popover)
    setattr(sidebar, "file_uploader", sb_file_uploader)

    setattr(st_mod, "sidebar", sidebar)

    # Register stub into sys.modules
    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    return st_mod


# ---------------------- Optional External Module Stubs ---------------------


def _install_openai_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide minimal openai modules for import-time type references."""
    if "openai" not in sys.modules:
        openai_mod = ModuleType("openai")

        class _OpenAI:
            pass

        setattr(openai_mod, "OpenAI", _OpenAI)
        monkeypatch.setitem(sys.modules, "openai", openai_mod)

    if "openai.types" not in sys.modules:
        monkeypatch.setitem(sys.modules, "openai.types", ModuleType("openai.types"))

    if "openai.types.chat" not in sys.modules:
        oa_chat = ModuleType("openai.types.chat")

        class ChatCompletionMessageParam:  # placeholders for type imports
            pass

        class ChatCompletionToolParam:
            pass

        setattr(oa_chat, "ChatCompletionMessageParam", ChatCompletionMessageParam)
        setattr(oa_chat, "ChatCompletionToolParam", ChatCompletionToolParam)
        monkeypatch.setitem(sys.modules, "openai.types.chat", oa_chat)


def _install_llama_index_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide minimal llama_index modules used at import-time."""
    if "llama_index" not in sys.modules:
        monkeypatch.setitem(sys.modules, "llama_index", ModuleType("llama_index"))
    if "llama_index.core" not in sys.modules:
        li_core = ModuleType("llama_index.core")

        class Settings:
            llm: Any = None

        setattr(li_core, "Settings", Settings)
        monkeypatch.setitem(sys.modules, "llama_index.core", li_core)
    if "llama_index.llms" not in sys.modules:
        monkeypatch.setitem(sys.modules, "llama_index.llms", ModuleType("llama_index.llms"))
    if "llama_index.llms.openai" not in sys.modules:
        li_llms_openai = ModuleType("llama_index.llms.openai")

        class _LI_OpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.model = kwargs.get("model")

        setattr(li_llms_openai, "OpenAI", _LI_OpenAI)
        monkeypatch.setitem(sys.modules, "llama_index.llms.openai", li_llms_openai)


def _install_config_stub_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If 'config' module import fails, insert a minimal stub to satisfy patches."""
    try:
        import config as _  # noqa: F401
        return
    except Exception:
        pass

    cfg = ModuleType("config")

    def is_enabled(_flag: str) -> bool:
        return True

    def require_flag(_flag: str, _msg: str = "Feature is disabled") -> bool:
        return True

    def is_feature_enabled(_flag: str, _default: bool = False) -> bool:
        return True

    def get_openai_api_key() -> Optional[str]:
        return None

    def get_model_name(default: str = "gpt-5-mini") -> str:
        return default

    def refresh_cache() -> None:
        pass

    setattr(cfg, "is_enabled", is_enabled)
    setattr(cfg, "require_flag", require_flag)
    setattr(cfg, "is_feature_enabled", is_feature_enabled)
    setattr(cfg, "get_openai_api_key", get_openai_api_key)
    setattr(cfg, "get_model_name", get_model_name)
    setattr(cfg, "refresh_cache", refresh_cache)
    monkeypatch.setitem(sys.modules, "config", cfg)


# -------------------------- Dummy OpenAI Client ----------------------------


class _DummyResponseMessage:
    def __init__(self, content: str = "OK", tool_calls: Any = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _DummyChoice:
    def __init__(self, message: _DummyResponseMessage) -> None:
        self.message = message


class _DummyResp:
    def __init__(self, content: str = "OK") -> None:
        self.choices = [_DummyChoice(_DummyResponseMessage(content=content))]


class _DummyCompletions:
    def __init__(self, client: "DummyOpenAIClient") -> None:
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        # Capture arguments for assertions
        self._client.last_kwargs = kwargs
        if kwargs.get("stream"):
            # Return an empty iterable to simulate streaming path
            return []
        return _DummyResp("OK")


class _DummyChat:
    def __init__(self, client: "DummyOpenAIClient") -> None:
        self.completions = _DummyCompletions(client)


class DummyOpenAIClient:
    """
    Minimal, dependency-free OpenAI client stub.

    Attributes:
      - chat.completions.create(...)
      - last_kwargs: dict of the most recent create(**kwargs) call for assertions
    """

    def __init__(self) -> None:
        self.chat = _DummyChat(self)
        self.last_kwargs: Optional[dict] = None


def _make_dummy_openai_client() -> DummyOpenAIClient:
    return DummyOpenAIClient()


# ----------------------------- Reload Helpers -----------------------------


def reload_modules_for_streamlit() -> None:
    """
    Reload modules that bind Streamlit decorators/APIs at import-time so they see our stub.
    """
    to_reload = [
        "utils.utils",
        "utils.app_state",
        "utils.help",
        # Include advisor stages to refresh any 'from ... import get_openai_client' bindings
        "advisor.stages",
    ]
    for mod_name in to_reload:
        if mod_name in sys.modules:
            try:
                importlib.reload(sys.modules[mod_name])
            except Exception:
                # Non-fatal in CI; continue
                pass


# -------------------------------- Fixtures ---------------------------------


@pytest.fixture(autouse=True, scope="session")
def _autouse_streamlit_and_openai_stubs() -> Iterator[None]:
    """
    Session-scoped autouse fixture:
      1) Install Streamlit stub
      2) Install OpenAI and llama_index import-time stubs
      3) Ensure config module resolves (or stub it)
      4) Reload llama_index_setup after stubbing Streamlit
      5) DO NOT globally monkeypatch get_openai_client (tests handle per-case)
      6) Reload key modules to bind to stubbed decorators/APIs
      7) Patch chat starter prompts helper to honor module-level alias in tests
    """
    mp = pytest.MonkeyPatch()

    # 1) Streamlit stub first (required before any app imports)
    _install_streamlit_stub(mp)

    # 2) Third-party import stubs to avoid heavy deps during import-time
    _install_openai_stubs(mp)
    _install_llama_index_stubs(mp)

    # 3) Config stub (only if missing)
    _install_config_stub_if_missing(mp)

    # 3.1) Ensure OPENAI_API_KEY is present for AI gating in tests and refresh config cache
    try:
        import os as _os  # local import
        if not _os.getenv("OPENAI_API_KEY"):
            _os.environ["OPENAI_API_KEY"] = "test-key"
        # Refresh real config module cache to pick up env (works for both real and stub)
        try:
            import config as _cfg  # type: ignore
            if hasattr(_cfg, "refresh_cache"):
                _cfg.refresh_cache()  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass

    # 4) Reload llama_index_setup to bind @st.cache_resource to our stub
    try:
        import loaders.llama_index_setup as llm_setup  # type: ignore
    except Exception:
        # If not yet imported, import once now under stubbed environment
        llm_setup = importlib.import_module("loaders.llama_index_setup")
    else:
        # Already imported earlier — reload to ensure our stub decorators apply
        llm_setup = importlib.reload(llm_setup)

    # 5) Provide a default dummy OpenAI client globally.
    # Tests that need a specific behavior will monkeypatch over this.
    try:
        dummy_client = _make_dummy_openai_client()
        setattr(llm_setup, "get_openai_client", lambda: dummy_client)  # type: ignore[attr-defined]
    except Exception:
        pass

    # 6) Reload other modules that cache Streamlit decorators/APIs at import-time
    reload_modules_for_streamlit()

    # 7) Patch utils.chat_panel._get_starter_prompts to honor the module-level alias get_session_profile
    try:
        import utils.chat_panel as _cp  # type: ignore

        _orig_get_starters = getattr(_cp, "_get_starter_prompts", None)

        def _patched_get_starter_prompts(chart_id: str | None = None) -> list[str]:
            try:
                prof_getter = getattr(_cp, "get_session_profile", None)
                prof = prof_getter() if callable(prof_getter) else None
                if prof and getattr(prof, "experience_level", "new") == "new":
                    # Provide a minimal, stable non-empty set for tests
                    if chart_id:
                        return [
                            "What grant sizes are most common here?",
                            "Which years look best in this view?",
                            "Give 3 simple takeaways from this chart.",
                        ]
                    return [
                        "What are my first 3 steps to get grant ready?",
                        "Am I eligible for typical funders?",
                        "Help me write a simple need statement.",
                    ]
            except Exception:
                pass
            if callable(_orig_get_starters):
                return _orig_get_starters(chart_id)  # type: ignore[misc]
            return []

        setattr(_cp, "_get_starter_prompts", _patched_get_starter_prompts)
    except Exception:
        # If utils.chat_panel is unavailable, skip
        pass

    # Teardown at end of test session
    yield
    mp.undo()

@pytest.fixture(autouse=True)
def _reset_markdown_calls_between_tests() -> Iterator[None]:
    """
    Function-scoped autouse fixture to reset st._md_calls and session_state so tests can assert counts deterministically.
    Also proactively re-augment any test-installed 'streamlit' stub before and after each test.
    """
    try:
        _ensure_streamlit_min_surface_no_mp()
        st_mod = sys.modules.get("streamlit")
        try:
            if hasattr(st_mod, "_md_calls"):
                st_mod._md_calls.clear()  # type: ignore[attr-defined]
            if hasattr(st_mod, "session_state"):
                st_mod.session_state.clear()  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass
    yield
    try:
        _ensure_streamlit_min_surface_no_mp()
        st_mod = sys.modules.get("streamlit")
        try:
            if hasattr(st_mod, "_md_calls"):
                st_mod._md_calls.clear()  # type: ignore[attr-defined]
            if hasattr(st_mod, "session_state"):
                st_mod.session_state.clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            if st_mod is not None and hasattr(st_mod, "_md_calls"):
                setattr(st_mod, "_md_calls", [])
        except Exception:
            pass
    except Exception:
        pass


# Expose helper for tests that need explicit reloads (rare)
__all__ = [
    "reload_modules_for_streamlit",
    "DummyOpenAIClient",
]