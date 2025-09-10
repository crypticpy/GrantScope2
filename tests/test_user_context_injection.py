import sys
from types import ModuleType

import pytest


# --- Test scaffolding: stub external modules so imports succeed without heavy deps ---
def _install_fake_ai_modules(monkeypatch):
    import sys
    from types import ModuleType

    # Stub streamlit with minimal surface used at import-time
    st_mod = ModuleType("streamlit")

    def _cache_resource(**_kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    st_mod.cache_resource = _cache_resource
    st_mod.session_state = {}  # simple dict-like
    monkeypatch.setitem(sys.modules, "streamlit", st_mod)

    # Stub openai and nested types.chat
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
def _auto_stub_ai_modules(monkeypatch):
    # Ensure stubs are in place before each test executes imports
    _install_fake_ai_modules(monkeypatch)
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


def _install_fake_profile_module(monkeypatch, profile_obj):
    """
    Install a fake 'utils.app_state' module into sys.modules with a get_session_profile()
    that returns profile_obj (or None). This works with the deferred import inside the helper.
    """
    fake_mod = ModuleType("utils.app_state")

    def _get_session_profile():
        return profile_obj

    fake_mod.get_session_profile = _get_session_profile
    # Ensure 'utils' package exists as a module so 'utils.app_state' resolves
    if "utils" not in sys.modules:
        sys.modules["utils"] = ModuleType("utils")
    monkeypatch.setitem(sys.modules, "utils.app_state", fake_mod)


# --------------------- Tests ---------------------


class TestUserContextWedge:
    def test_wedge_present_and_capped_160(self, monkeypatch):
        # Arrange: fake profile with long goal to exercise cap
        class P:
            org_type = "nonprofit"
            region = "California"
            primary_goal = " ".join(
                ["expand after school programs for underserved communities"] * 5
            )

        _install_fake_profile_module(monkeypatch, P())
        from loaders.llama_index_setup import _build_user_context_wedge  # import after patch

        # Act
        wedge = _build_user_context_wedge(max_len=160)

        # Assert
        assert wedge is not None
        assert wedge.startswith("User Context:")
        assert "org_type=nonprofit" in wedge
        assert "region=California" in wedge
        assert len(wedge) <= 160  # hard cap
        # goal present but truncated (not the full repeated string)
        assert "goal=" in wedge

    def test_wedge_absent_when_no_profile(self, monkeypatch):
        _install_fake_profile_module(monkeypatch, None)
        from loaders.llama_index_setup import _build_user_context_wedge

        wedge = _build_user_context_wedge(max_len=160)
        assert wedge is None


class TestPromptAssemblyInjection:
    def test_query_data_includes_user_context_when_available(self, monkeypatch):
        # Arrange
        # Patch wedge builder to avoid sys.modules trick here
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: "User Context: org_type=nonprofit, region=CA.",
            raising=False,
        )
        # Avoid chart context variability
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

        # Minimal df stub with columns attribute
        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import query_data

        # Act
        _ = query_data(DF(), "What trends?", pre_prompt="Analyze this view.")

        # Assert: messages were sent and include our wedge and known columns and query text
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        assert len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert "User Context:" in content
        assert "Known Columns:" in content
        assert "Analyze this view." in content
        assert "What trends?" in content

    def test_tool_query_includes_user_context_and_extra_ctx(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: "User Context: org_type=nonprofit, region=WA.",
            raising=False,
        )
        # Provide deterministic df summary and avoid heavy computations
        monkeypatch.setattr(
            "loaders.llama_index_setup._summarize_df",
            lambda _df: "DF Summary: columns=amount_usd, year_issued",
            raising=False,
        )
        dummy_client = DummyOpenAIClient()
        monkeypatch.setattr(
            "loaders.llama_index_setup.get_openai_client",
            lambda: dummy_client,
            raising=False,
        )

        class DF:
            # For safety, include minimal attributes referenced indirectly
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import tool_query

        # Act
        _ = tool_query(DF(), "Show top years", pre_prompt="Pre", extra_ctx="Extra chart context")

        # Assert
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        assert len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert "User Context:" in content
        assert "Additional Chart Context: Extra chart context" in content
        assert "Pre" in content
        # DF summary presence is optional; assert not required to avoid coupling
        assert "Show top years" in content


class TestPromptAssemblyAbsence:
    def test_query_data_no_user_context_when_absent(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: None,
            raising=False,
        )
        monkeypatch.setattr(
            "loaders.llama_index_setup.resolve_chart_context",
            lambda _cid: None,
            raising=False,
        )
        dummy_client = DummyOpenAIClient()
        monkeypatch.setattr(
            "loaders.llama_index_setup.get_openai_client",
            lambda: dummy_client,
            raising=False,
        )

        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import query_data

        # Act
        _ = query_data(DF(), "What trends?", pre_prompt="Analyze this view.")

        # Assert: should not include 'User Context:' when wedge is absent
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        assert len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert "User Context:" not in content
        assert "Known Columns:" in content
        assert "Analyze this view." in content
        assert "What trends?" in content

    def test_tool_query_no_user_context_when_absent(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: None,
            raising=False,
        )
        dummy_client = DummyOpenAIClient()
        monkeypatch.setattr(
            "loaders.llama_index_setup.get_openai_client",
            lambda: dummy_client,
            raising=False,
        )
        monkeypatch.setattr(
            "loaders.llama_index_setup._summarize_df",
            lambda _df: "DF Summary",
            raising=False,
        )

        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import tool_query

        # Act
        _ = tool_query(DF(), "Show top years", pre_prompt="Pre", extra_ctx="Extra chart context")

        # Assert: should not include 'User Context:' when wedge is absent
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        assert len(msgs) >= 2
        user_msg = msgs[1]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert "User Context:" not in content
        assert "Additional Chart Context: Extra chart context" in content
        assert "Pre" in content
        assert "Show top years" in content


if __name__ == "__main__":
    pytest.main([__file__])
