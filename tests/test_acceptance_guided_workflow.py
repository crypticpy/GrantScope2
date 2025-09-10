import base64
import importlib
import sys
from types import ModuleType

# ---------- Shared fakes ----------


def _install_fake_streamlit(monkeypatch):
    """
    Create a minimal 'streamlit' module for tests:
    - session_state: dict
    - markdown(): records calls for assertions
    """
    st_mod = ModuleType("streamlit")
    st_mod.session_state = {}
    st_mod._md_calls = []

    def _markdown(txt: str, **_kwargs):
        st_mod._md_calls.append(str(txt))

    # Provide minimal sidebar object to satisfy imports if needed
    sidebar = ModuleType("streamlit.sidebar")
    st_mod.sidebar = sidebar

    st_mod.markdown = _markdown
    monkeypatch.setitem(sys.modules, "streamlit", st_mod)
    return st_mod


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
        # Capture last call arguments for assertions
        self._client.last_kwargs = kwargs
        return DummyResponse(DummyResponseMessage(content="OK", tool_calls=None))


class DummyChat:
    def __init__(self, client):
        self.completions = DummyChatCompletions(client)


class DummyOpenAIClient:
    def __init__(self):
        self.chat = DummyChat(self)
        self.last_kwargs: dict | None = None


# ---------- Tests ----------


class TestPlannerBudgetSummaries:
    def test_get_planner_summary_and_budget_summary_from_session(self, monkeypatch):
        # Arrange: fake streamlit
        st_mod = _install_fake_streamlit(monkeypatch)

        # Populate planner_* keys (pages/9_Project_Planner.py behavior)
        ss = st_mod.session_state  # type: ignore[attr-defined]
        ss["planner_project_name"] = "Project X"
        ss["planner_outcomes"] = "Improve reading scores for middle school students in the district"
        ss["planner_timeline"] = "6 months"
        ss["planner_budget_range"] = "$25,000 - $100,000"

        # Populate budget_* keys (pages/12_Budget_Reality_Check.py behavior)
        ss["budget_grand_total"] = float(120000)
        ss["budget_indirect_rate_pct"] = float(10)
        ss["budget_match_available"] = True
        ss["budget_flags"] = ["Missing Evaluation", "High Staff %"]

        # Import after patch (reload to ensure our fake streamlit is used)
        import utils.app_state as _app_state  # type: ignore

        importlib.reload(_app_state)
        from utils.app_state import get_budget_summary, get_planner_summary  # type: ignore

        # Act
        p = get_planner_summary(max_len=220) or ""
        b = get_budget_summary(max_len=220) or ""

        # Assert planner summary structure
        assert p.startswith("Planner: ")
        assert "name=Project X" in p
        assert "outcomes=" in p
        assert "timeline=6 months" in p
        assert "budget=$25,000 - $100,000" in p

        # Assert budget summary structure
        assert b.startswith("Budget: ")
        assert "total=$120,000" in b
        assert "indirect_rate=10%" in b
        assert "match=yes" in b
        assert "flags=2" in b

        # Clean up session state for subsequent tests in this class
        all_keys = list(ss.keys())
        for key in all_keys:
            if key.startswith(("planner_", "budget_")):
                del ss[key]

    def test_get_planner_summary_returns_none_when_no_fields(self, monkeypatch):
        st_mod = _install_fake_streamlit(monkeypatch)
        # Clear any existing planner_* keys to ensure clean test
        ss = st_mod.session_state
        planner_keys = [k for k in ss.keys() if k.startswith("planner_")]
        for key in planner_keys:
            del ss[key]
        from utils.app_state import get_planner_summary  # type: ignore

        assert get_planner_summary(max_len=220) is None

    def test_get_budget_summary_returns_none_when_no_fields(self, monkeypatch):
        st_mod = _install_fake_streamlit(monkeypatch)
        # Clear any existing budget_* keys to ensure clean test
        ss = st_mod.session_state
        budget_keys = [k for k in ss.keys() if k.startswith("budget_")]
        for key in budget_keys:
            del ss[key]
        from utils.app_state import get_budget_summary  # type: ignore

        assert get_budget_summary(max_len=220) is None


class TestDownloadHelpers:
    def test_download_text_returns_href_and_calls_markdown(self, monkeypatch):
        # Arrange: fake streamlit
        st_mod = _install_fake_streamlit(monkeypatch)
        # Reload utils to bind to our fake streamlit before import
        import utils.utils as _utils_mod  # type: ignore

        importlib.reload(_utils_mod)
        from utils.utils import download_text  # type: ignore

        # Act
        content = "Hello World"
        href = download_text(content, "workbook.md", mime="text/markdown")

        # Assert href structure
        assert href.startswith('<a href="data:text/markdown;base64,')
        assert 'download="workbook.md"' in href
        # Verify base64 payload decodes to our content
        prefix = "data:text/markdown;base64,"
        encoded = href.split(prefix, 1)[1].split('"', 1)[0]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == content

        # Assert markdown was called once with the same href
        assert len(st_mod._md_calls) == 1  # type: ignore[attr-defined]
        assert href in st_mod._md_calls[0]  # type: ignore[index]


class TestUserContextWedgeOnce:
    def test_query_data_injects_user_context_exactly_once(self, monkeypatch):
        # Arrange: deterministic wedge, no chart ctx
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: "User Context: org_type=nonprofit, region=CA.",
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
        monkeypatch.setattr(
            "loaders.llama_index_setup.setup_llama_index",
            lambda: None,
            raising=False,
        )

        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import query_data  # type: ignore

        # Act
        _ = query_data(DF(), "Show trends", pre_prompt="Analyze")

        # Assert: user message includes wedge exactly once
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        user_msg = msgs[1]
        content = user_msg["content"]
        assert content.count("User Context:") == 1
        assert "Analyze" in content and "Show trends" in content

    def test_tool_query_injects_user_context_exactly_once(self, monkeypatch):
        monkeypatch.setattr(
            "loaders.llama_index_setup._build_user_context_wedge",
            lambda: "User Context: org_type=school, region=WA.",
            raising=False,
        )
        dummy_client = DummyOpenAIClient()
        monkeypatch.setattr(
            "loaders.llama_index_setup.get_openai_client",
            lambda: dummy_client,
            raising=False,
        )
        # Keep summary deterministic
        monkeypatch.setattr(
            "loaders.llama_index_setup._summarize_df",
            lambda _df: "DF Summary: columns=amount_usd, year_issued",
            raising=False,
        )

        class DF:
            columns = ["amount_usd", "year_issued"]

        from loaders.llama_index_setup import tool_query  # type: ignore

        # Act
        _ = tool_query(DF(), "Top years?", pre_prompt="Pre", extra_ctx="Ctx")

        # Assert: user content contains wedge once
        assert dummy_client.last_kwargs is not None
        msgs = dummy_client.last_kwargs.get("messages") or []
        user_msg = msgs[1]
        content = user_msg["content"]
        assert content.count("User Context:") == 1
        assert (
            "Pre" in content
            and "Top years?" in content
            and "Additional Chart Context: Ctx" in content
        )
