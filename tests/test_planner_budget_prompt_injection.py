import sys
from types import ModuleType

import pytest


# --- Minimal scaffolding to avoid heavy deps during import-time in tests ---
def _install_fake_runtime_modules(monkeypatch):
    # Stub streamlit with minimal surface used at import-time
    st_mod = ModuleType("streamlit")

    def _cache_resource(**_kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    def _cache_data(**_kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    st_mod.cache_resource = _cache_resource
    st_mod.cache_data = _cache_data
    st_mod.session_state = {}  # simple dict-like
    monkeypatch.setitem(sys.modules, "streamlit", st_mod)

    # Stub openai and nested types.chat used only for typing in loaders.llama_index_setup
    openai_mod = ModuleType("openai")

    class _OpenAI:  # placeholder class
        pass

    openai_mod.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    oa_types_mod = ModuleType("openai.types")
    oa_chat_mod = ModuleType("openai.types.chat")

    class ChatCompletionMessageParam:  # placeholders for type imports
        pass

    class ChatCompletionToolParam:
        pass

    oa_chat_mod.ChatCompletionMessageParam = ChatCompletionMessageParam
    oa_chat_mod.ChatCompletionToolParam = ChatCompletionToolParam
    monkeypatch.setitem(sys.modules, "openai.types", oa_types_mod)
    monkeypatch.setitem(sys.modules, "openai.types.chat", oa_chat_mod)

    # Stub llama_index modules referenced at import-time
    li_pkg = ModuleType("llama_index")
    li_core = ModuleType("llama_index.core")

    class Settings:
        llm = None

    li_core.Settings = Settings
    li_llms = ModuleType("llama_index.llms")
    li_llms_openai = ModuleType("llama_index.llms.openai")

    class _LI_OpenAI:
        def __init__(self, *args, **kwargs):
            self.model = kwargs.get("model")

    li_llms_openai.OpenAI = _LI_OpenAI

    monkeypatch.setitem(sys.modules, "llama_index", li_pkg)
    monkeypatch.setitem(sys.modules, "llama_index.core", li_core)
    monkeypatch.setitem(sys.modules, "llama_index.llms", li_llms)
    monkeypatch.setitem(sys.modules, "llama_index.llms.openai", li_llms_openai)


@pytest.fixture(autouse=True)
def _auto_env(monkeypatch):
    _install_fake_runtime_modules(monkeypatch)
    yield


# --- Minimal OpenAI client stub used to capture messages sent by our functions ---
class DummyResponseMessage:
    def __init__(self, content: str = "OK", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class DummyChoice:
    def __init__(self, message: DummyResponseMessage):
        self.message = message


class DummyResponse:
    def __init__(self, message: DummyResponseMessage | None = None):
        self.choices = [DummyChoice(message or DummyResponseMessage())]


class DummyChatCompletions:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        # Capture the last call arguments for assertions
        self._client.last_kwargs = kwargs
        # Return a simple response with no tool calls by default
        return DummyResponse(DummyResponseMessage(content="OK", tool_calls=None))


class DummyChat:
    def __init__(self, client):
        self.completions = DummyChatCompletions(client)


class DummyOpenAIClient:
    def __init__(self):
        self.chat = DummyChat(self)
        self.last_kwargs: dict | None = None


def _install_fake_app_state_with_summaries(
    monkeypatch, planner_text: str | None, budget_text: str | None
):
    """
    Install a fake 'utils.app_state' module into sys.modules with get_planner_summary/get_budget_summary
    returning provided strings (or None).
    """
    fake_mod = ModuleType("utils.app_state")

    def _get_planner_summary():
        return planner_text

    def _get_budget_summary():
        return budget_text

    fake_mod.get_planner_summary = _get_planner_summary
    fake_mod.get_budget_summary = _get_budget_summary
    # Ensure 'utils' package exists as a module so 'utils.app_state' resolves
    if "utils" not in sys.modules:
        sys.modules["utils"] = ModuleType("utils")
    monkeypatch.setitem(sys.modules, "utils.app_state", fake_mod)


# --------------------- Tests ---------------------


class TestPlannerBudgetWedge:
    def test_build_planner_budget_wedge_present(self, monkeypatch):
        # Arrange: provide fake summaries
        _install_fake_app_state_with_summaries(
            monkeypatch, "Planner: name=MyProj.", "Budget: total=$10,000."
        )
        # Import after patch
        from loaders.llama_index_setup import _build_planner_budget_wedge  # type: ignore

        # Act
        wedge = _build_planner_budget_wedge(max_len=240)

        # Assert
        assert wedge is not None
        assert "Planner:" in wedge
        assert "Budget:" in wedge

    def test_query_data_includes_planner_budget_when_available(self, monkeypatch):
        # Arrange: force a fixed planner/budget wedge and stable environment
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_planner_budget_wedge",
            lambda: "Planner: name=MyProj. Budget: total=$12,000.",
            raising=False,
        )
        monkeypatch.setattr(
            "loaders.llama_index_setup.resolve_chart_context",
            lambda _cid: None,
            raising=False,
        )
        # Patch OpenAI client
        dummy_client = DummyOpenAIClient()
        monkeypatch.setattr(
            "loaders.llama_index_setup.get_openai_client",
            lambda: dummy_client,
            raising=False,
        )
        # Avoid touching real llama_index settings
        monkeypatch.setattr(
            "loaders.llama_index_setup.setup_llama_index",
            lambda: None,
            raising=False,
        )

        # Minimal df stub with columns attribute
        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import query_data  # type: ignore

        # Act
        _ = query_data(DF(), "What trends?", pre_prompt="Analyze this view.")

        # Assert: messages were sent and include our planner/budget wedge
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        assert len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert "Planner: name=MyProj." in content
        assert "Budget: total=$12,000." in content
        assert "Analyze this view." in content
        assert "What trends?" in content
