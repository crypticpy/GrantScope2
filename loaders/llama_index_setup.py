import importlib
import os
from collections.abc import Iterable
from typing import Any, cast

import streamlit as st
from llama_index.core import Settings

# from llama_index.experimental.query_engine import PandasQueryEngine  # disabled: avoids safe_eval-based code execution
from llama_index.llms.openai import OpenAI as LI_OpenAI
from openai import OpenAI as OpenAIClient
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam


def _disable_pandas_query_engine() -> None:
    """Disable LlamaIndex PandasQueryEngine by stubbing it with a clear error."""
    try:
        exp_mod = importlib.import_module("llama_index.experimental.query_engine")

        class _DisabledPandasQueryEngine:  # pragma: no cover - defensive stub
            def __init__(self, *args, **kwargs):
                raise RuntimeError(
                    "PandasQueryEngine is disabled for safety in this build. "
                    "Use the tool_query() pipeline (function-calling tools) instead."
                )

        exp_mod.PandasQueryEngine = _DisabledPandasQueryEngine
    except Exception:
        # If experimental package not present or structure changes, ignore silently
        pass


_disable_pandas_query_engine()

# Centralized config for secrets/flags (supports package and direct execution contexts)
try:
    from GrantScope import config  # when executed via package context
except Exception:
    try:
        import config  # fallback when executed inside GrantScope/ directly
    except Exception:
        config = None  # type: ignore

# If OPENAI_API_KEY is available only via st.secrets/config, export to env for OpenAI SDK
if config is not None:
    try:
        _key = config.get_openai_api_key()
        if _key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = _key
    except Exception:
        # Do not fail module import if secrets are unavailable
        pass


# Setup LlamaIndex with specific model and settings
@st.cache_resource(show_spinner=False)
def setup_llama_index():
    """Initialize and cache the LLM settings for LlamaIndex."""
    model_name = "gpt-5-mini"
    if config is not None:
        try:
            model_name = config.get_model_name()
        except Exception:
            # Fall back to default if config lookup fails
            model_name = "gpt-5-mini"
    try:
        Settings.llm = LI_OpenAI(model=model_name)
        return Settings.llm
    except Exception:
        # In constrained CI/test environments without full llama_index stack, skip wiring
        return None


@st.cache_resource(show_spinner=False)
def get_openai_client() -> OpenAIClient:
    """Create and cache an OpenAI client (SDK v1.x reads OPENAI_API_KEY from env).

    In test/CI environments where OPENAI_API_KEY is not set, return a lightweight
    dummy client that satisfies the interface used by query_data/tool_query to
    avoid external network calls and flakiness.
    """
    try:
        key = os.getenv("OPENAI_API_KEY")
    except Exception:
        key = None

    if not key:
        # Minimal, dependency-free dummy client
        class _DummyMsg:
            def __init__(self, content: str = "OK"):
                self.content = content

        class _DummyChoice:
            def __init__(self, message):
                self.message = message

        class _DummyResp:
            def __init__(self, content: str = "OK"):
                self.choices = [_DummyChoice(_DummyMsg(content))]

        class _DummyCompletions:
            def create(self, **kwargs):
                # Support both streaming and non-streaming paths
                if kwargs.get("stream"):
                    # Return an empty iterable; consumers handle empty streams defensively
                    return []
                return _DummyResp("OK")

        class _DummyChat:
            def __init__(self):
                self.completions = _DummyCompletions()

        class _DummyClient:
            def __init__(self):
                self.chat = _DummyChat()

        return _DummyClient()  # type: ignore[return-value]

    # The OpenAI Python SDK v1+ uses environment variable OPENAI_API_KEY automatically.
    # We still import the class at module import time (see top) to avoid runtime import costs.
    try:
        return OpenAIClient()
    except Exception:
        # Fallback to a minimal dummy client when OpenAI SDK cannot initialize (e.g., missing API key)
        class _DummyMsg:
            def __init__(self, content: str = "OK"):
                self.content = content

        class _DummyChoice:
            def __init__(self, message):
                self.message = message

        class _DummyResp:
            def __init__(self, content: str = "OK"):
                self.choices = [_DummyChoice(_DummyMsg(content))]

        class _DummyStream(list):
            # Behaves like an empty iterable for streaming paths
            pass

        class _DummyCompletions:
            def create(self, **kwargs):
                if kwargs.get("stream"):
                    return _DummyStream()
                return _DummyResp("OK")

        class _DummyChat:
            def __init__(self):
                self.completions = _DummyCompletions()

        class _DummyClient:
            def __init__(self):
                self.chat = _DummyChat()

        return _DummyClient()


def resolve_chart_context(chart_id: str) -> str | None:
    """Return additional chart-specific context text based on a stable chart identifier.

    This is a lightweight resolver intended to enrich prompts with chart-specific
    hints/metadata. It can be extended to return LlamaIndex nodes/documents later.
    """
    context_map = {
        # Data Summary
        "data_summary.top_funders": (
            "Chart Focus: Top Funders by total grant amount. Use the displayed aggregate table "
            "to reason about which funders contribute the most overall."
        ),
        "data_summary.general": (
            "Chart Focus: General dataset overview. Consider overall distributions, common fields, "
            "and high-level trends without focusing on a specific visualization."
        ),
        "data_summary.funder_type": (
            "Chart Focus: Distribution of total grant amount by funder type. Smaller categories may be "
            "aggregated into 'Other' on pages with many funder types."
        ),
        "data_summary.subject_area": (
            "Chart Focus: Top grant subject areas by total amount. Use bar lengths to compare emphasis "
            "across subjects."
        ),
        "data_summary.population": (
            "Chart Focus: Top populations served by total amount. Compare which populations receive "
            "more funding."
        ),
        # Distribution
        "distribution.main": (
            "Chart Focus: Distribution of grant amounts across USD clusters. Reference the selected "
            "clusters and sorting to keep the answer grounded."
        ),
        # Scatter
        "scatter.main": (
            "Chart Focus: Scatter of grant amounts across years, colored by USD cluster. Consider the "
            "selected year range and clusters."
        ),
        # Heatmap
        "heatmap.main": (
            "Chart Focus: Heatmap of total grant amount across two categorical dimensions. Use rows/columns "
            "to reason about intersections."
        ),
        # Treemaps
        "treemaps.main": (
            "Chart Focus: Treemap of total grant amounts grouped by a selected categorical dimension "
            "(one of grant_strategy_tran, grant_subject_tran, grant_population_tran) and filtered by a "
            "selected USD range label. Use the hierarchical boxes to describe relative contributions and "
            "highlight top segments. Consider the current analyze_column and selected_label."
        ),
        # Word Clouds
        "wordclouds.main": (
            "Chart Focus: Word clouds generated from grant descriptions. Treat these as qualitative signals "
            "of frequent terms; do not fabricate data outside the provided descriptions."
        ),
        # Relationships
        "relationships.description_vs_amount": (
            "Chart Focus: Scatter of grant description word count vs award amount. Discuss correlation "
            "patterns and outliers; do not assume causation."
        ),
        "relationships.avg_by_factor": (
            "Chart Focus: Average award amount by a selected categorical factor (bar or box plot). "
            "Reference the selected factor and summarize differences."
        ),
        "relationships.funder_affinity": (
            "Chart Focus: Funder affinity across a chosen categorical dimension, summing total amounts "
            "for the selected funder. Highlight top categories."
        ),
        # Top Categories
        "top_categories.main": (
            "Chart Focus: Unique grant counts across the selected categorical variable (bar/pie/treemap). "
            "Discuss which categories account for most unique grants."
        ),
    }
    return context_map.get(str(chart_id).strip() or "", None)


# Compact "User Context" wedge builder (centralized helper)
def _build_user_context_wedge(max_len: int = 160) -> str | None:
    """Construct a compact 'User Context:' wedge using org_type, region, and a short goal.
    Returns None when the profile is absent or fields are empty. The result is capped to max_len.
    """
    try:
        # Defer import to avoid hard dependency during non-UI tests
        try:
            from utils.app_state import get_session_profile  # type: ignore
        except Exception:
            try:
                from GrantScope.utils.app_state import get_session_profile  # type: ignore
            except Exception:
                return None

        prof = get_session_profile()
        if not prof:
            return None

        org = getattr(prof, "org_type", "") or ""
        region = getattr(prof, "region", "") or ""
        goal = getattr(prof, "primary_goal", "") or ""

        bits: list[str] = []
        if org:
            bits.append(f"org_type={org}")
        if region:
            bits.append(f"region={region}")
        if goal:
            # Deterministic short summary: collapse whitespace and take the first N tokens
            goal_clean = " ".join(str(goal).split())
            goal_short = " ".join(goal_clean.split()[:10])
            if goal_short:
                bits.append(f"goal={goal_short}")

        if not bits:
            return None

        wedge = f"User Context: {', '.join(bits)}."
        if len(wedge) > max_len:
            # Hard cap to max_len without leaking extra text; trim trailing separators
            wedge = wedge[:max_len].rstrip()
            wedge = wedge.rstrip(",; ")

        return wedge
    except Exception:
        # Fail closed; context injection is optional
        return None


def _build_planner_budget_wedge(max_len: int = 240) -> str | None:
    """Construct a compact wedge summarizing planner and budget when present.

    Uses utils.app_state.get_planner_summary/get_budget_summary to avoid duplicating logic.
    Returns None when neither summary exists. Caps the total length to max_len.
    """
    try:
        try:
            from utils.app_state import get_budget_summary, get_planner_summary  # type: ignore
        except Exception:
            try:
                from GrantScope.utils.app_state import (  # type: ignore
                    get_budget_summary,
                    get_planner_summary,
                )
            except Exception:
                return None

        pb: list[str] = []
        try:
            ps = get_planner_summary()  # type: ignore[call-arg]
        except Exception:
            ps = None
        try:
            bs = get_budget_summary()  # type: ignore[call-arg]
        except Exception:
            bs = None

        if ps:
            pb.append(str(ps))
        if bs:
            pb.append(str(bs))
        if not pb:
            return None

        txt = " ".join(pb)
        if len(txt) > max_len:
            txt = txt[:max_len].rstrip(",; ")
        return txt
    except Exception:
        return None


# Function to query data (non-streaming) without executing generated Pandas code
def query_data(df, query_text, pre_prompt):
    """Return a full, non-streamed answer using direct OpenAI chat completion (no Pandas code execution).

    Adds a compact 'User Context:' wedge (<=160 chars) when a session profile exists, and includes
    Known Columns and any chart-specific context if available.
    """
    # Ensure LLM (Settings.llm) is initialized for consistency
    setup_llama_index()

    # System prompt aligned with stream_query to keep behavior consistent
    system_prompt = (
        "You are a helpful data analyst. Only answer using information grounded in the provided "
        "Known Columns and any Sample Context included in the prompt. If the user asks about a "
        "column or field that is not listed under Known Columns, you MUST clearly state that the "
        "information is not available in the dataset. Respond in concise Markdown."
    )

    # Optionally enrich pre_prompt with known columns for grounding
    try:
        known_cols = ", ".join(map(str, getattr(df, "columns", [])))
        pre_prompt_eff = f"{pre_prompt} Known Columns: {known_cols}".strip()
    except Exception:
        pre_prompt_eff = pre_prompt

    # Resolve chart context if available (best-effort)
    extra_ctx = None
    try:
        try:
            from utils.app_state import get_selected_chart as _get_sel  # type: ignore
        except Exception:
            try:
                from GrantScope.utils.app_state import (
                    get_selected_chart as _get_sel,  # type: ignore
                )
            except Exception:
                _get_sel = None  # type: ignore
        if _get_sel is not None:
            try:
                cid = _get_sel(None)
                if cid:
                    extra_ctx = resolve_chart_context(cid)
            except Exception:
                extra_ctx = None
    except Exception:
        extra_ctx = None

    # Build user message content with compact user context wedge first
    ctx_parts: list[str] = []
    wedge = _build_user_context_wedge()
    if wedge:
        try:
            print("[AI][user_context_injected]=true", flush=True)
        except Exception:
            pass
        ctx_parts.append(wedge)
    # Compact planner/budget wedge (when present)
    try:
        pb_wedge = _build_planner_budget_wedge()
    except Exception:
        pb_wedge = None
    if pb_wedge:
        ctx_parts.append(pb_wedge)
    if extra_ctx:
        ctx_parts.append(f"Additional Chart Context: {extra_ctx}")
    ctx_parts.append(pre_prompt_eff)
    user_content = " ".join(p for p in ctx_parts if p).strip()
    if query_text:
        user_content = f"{user_content} {query_text}".strip()

    # Resolve model name from central config (env/secrets override supported), default gpt-5-mini
    model_name = "gpt-5-mini"
    if config is not None:
        try:
            model_name = config.get_model_name()
        except Exception:
            model_name = "gpt-5-mini"

    client = get_openai_client()
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        try:
            content = resp.choices[0].message.content or ""
        except Exception:
            content = str(resp)
        return (content or "").replace("$", "\\$")
    except Exception as e:
        return f"Query error (non-streaming): {e}"


def stream_query(df, query_text, pre_prompt):
    """Yield assistant tokens using OpenAI streaming. Cancelling is handled by the consumer."""
    # Ensure LLM is initialized (cached) for consistent model/temperature settings (best-effort)
    try:
        setup_llama_index()
    except Exception:
        pass

    system_prompt = (
        "You are a helpful data analyst. Only answer using information grounded in the provided "
        "Known Columns and any Sample Context included in the prompt. If the user asks about a "
        "column or field that is not listed under Known Columns, you MUST clearly state that the "
        "information is not available in the dataset. Respond in concise Markdown."
    )

    # Resolve model name from central config (env/secrets override supported), default gpt-5-mini
    model_name = "gpt-5-mini"
    if config is not None:
        try:
            model_name = config.get_model_name()
        except Exception:
            model_name = "gpt-5-mini"

    client = get_openai_client()
    try:
        stream = client.chat.completions.create(
            model=model_name,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{pre_prompt} {query_text}".strip()},
            ],
        )
        for chunk in stream:
            # Each chunk is a ChatCompletionChunk with .choices[0].delta.content possibly set
            try:
                delta = chunk.choices[0].delta.content or ""
            except Exception:
                delta = ""
            if delta:
                # Escape $ for Streamlit Markdown rendering safety
                yield delta.replace("$", "\\$")
    except Exception as e:
        # Fallback single message if streaming path fails
        yield f"[streaming unavailable] {e}"


def _safe_markdown_table(df, max_rows: int = 20) -> str:
    """Render a small table snippet in Markdown; fallback to plain text if unavailable."""
    try:
        return df.head(max_rows).to_markdown(index=False)
    except Exception:
        try:
            return df.head(max_rows).to_string(index=False)
        except Exception as e:
            return f"[table render error] {e}"


def _summarize_df(df) -> str:
    """Return a lightweight textual summary of the dataframe for grounding."""
    try:
        cols = list(map(str, getattr(df, "columns", [])))
        parts = []
        if cols:
            parts.append(f"Known Columns: {', '.join(cols)}")
        # Common numeric column summary if present
        try:
            if "amount_usd" in df.columns:
                s = df["amount_usd"]
                parts.append(
                    "amount_usd stats: "
                    f"count={int(s.count())}, sum={float(s.sum()):,.2f}, "
                    f"mean={float(s.mean()):,.2f}, min={float(s.min()):,.2f}, "
                    f"max={float(s.max()):,.2f}"
                )
        except Exception:
            pass
        return " | ".join(parts)
    except Exception:
        return ""


def _df_describe_tool(df, columns=None) -> str:
    """Tool: describe numeric columns or a provided subset of columns."""
    try:
        if columns:
            use_cols = [c for c in columns if c in df.columns]
            if use_cols:
                target = df[use_cols]
            else:
                target = df.select_dtypes(include="number")
        else:
            target = df.select_dtypes(include="number")
        if target.shape[1] == 0:
            return "No numeric columns available for describe()."
        desc = target.describe().reset_index()
        return _safe_markdown_table(desc)
    except Exception as e:
        return f"[df_describe error] {e}"


def _df_groupby_sum_tool(df, by, value, n: int = 10, ascending: bool = False) -> str:
    """Tool: group by 'by' columns, sum 'value', sort, and return top n groups."""
    try:
        use_by = [c for c in (by or []) if c in df.columns]
        if not use_by or value not in df.columns:
            return f"[df_groupby_sum error] invalid columns; by={by}, value={value}"
        res = (
            df.groupby(use_by, dropna=False)[value]
            .sum()
            .sort_values(ascending=ascending)
            .head(max(int(n or 10), 1))
            .reset_index()
        )
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_groupby_sum error] {e}"


def _df_top_n_tool(df, by, n: int = 10, ascending: bool = False) -> str:
    """Tool: return the top n rows sorted by a numeric or sortable column."""
    try:
        if by not in df.columns:
            return f"[df_top_n error] invalid column: {by}"
        res = df.sort_values(by=by, ascending=ascending).head(max(int(n or 10), 1))
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_top_n error] {e}"


def tool_query(df, query_text: str, pre_prompt: str, extra_ctx: str | None = None) -> str:
    """Non-streaming, tool-assisted query with safe, whitelisted DataFrame operations.

    This provides the LLM with function-call tools instead of executing generated Python code.
    It preserves the 'investigate the data' capability without using eval/safe_eval.
    """
    # Initialize model settings (best-effort)
    try:
        setup_llama_index()
    except Exception:
        pass
    try:
        print("[AI][tool_query] active", flush=True)
    except Exception:
        pass

    system_prompt = (
        "You are a helpful data analyst. Use the provided tools to inspect the dataframe "
        "when you need specific numbers or slices. Only answer using information grounded "
        "in the Known Columns, the tool outputs, and any Additional Chart Context. If the "
        "user asks about a column not listed, clearly state that it is not available. "
        "Respond in concise Markdown."
    )

    # Resolve model
    model_name = "gpt-5-mini"
    if config is not None:
        try:
            model_name = config.get_model_name()
        except Exception:
            model_name = "gpt-5-mini"

    # Build grounded user content (prepend compact 'User Context' when available)
    df_summary = _summarize_df(df)
    ctx_parts: list[str] = []
    wedge = _build_user_context_wedge()
    if wedge:
        try:
            print("[AI][user_context_injected]=true", flush=True)
        except Exception:
            pass
        ctx_parts.append(wedge)
    # Compact planner/budget wedge (when present)
    try:
        pb_wedge = _build_planner_budget_wedge()
    except Exception:
        pb_wedge = None
    if pb_wedge:
        ctx_parts.append(pb_wedge)
    ctx_parts.append(pre_prompt)
    if extra_ctx:
        ctx_parts.append(f"Additional Chart Context: {extra_ctx}")
    if df_summary:
        ctx_parts.append(df_summary)
    user_content = " ".join(p for p in ctx_parts if p).strip()
    if query_text:
        user_content = f"{user_content} {query_text}".strip()

    # Define tool schemas for OpenAI function calling
    tools = [
        {
            "type": "function",
            "function": {
                "name": "df_describe",
                "description": "Describe basic statistics for numeric columns (or specific columns).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of column names to include.",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_groupby_sum",
                "description": "Group by columns, sum a numeric column, sort and return the top n groups.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "by": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of columns to group by.",
                        },
                        "value": {
                            "type": "string",
                            "description": "Numeric column to aggregate via sum.",
                        },
                        "n": {
                            "type": "integer",
                            "description": "Number of groups to return.",
                            "default": 10,
                            "minimum": 1,
                        },
                        "ascending": {
                            "type": "boolean",
                            "description": "Sort ascending if true; default descending.",
                            "default": False,
                        },
                    },
                    "required": ["by", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_top_n",
                "description": "Return the top n rows sorted by a given column.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "by": {"type": "string", "description": "Column name to sort by."},
                        "n": {
                            "type": "integer",
                            "description": "Number of rows to return.",
                            "default": 10,
                            "minimum": 1,
                        },
                        "ascending": {
                            "type": "boolean",
                            "description": "Sort ascending if true; default descending.",
                            "default": False,
                        },
                    },
                    "required": ["by"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_value_counts",
                "description": "Frequency distribution for a categorical field (optionally normalized).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "n": {"type": "integer", "default": 20, "minimum": 1},
                        "normalize": {"type": "boolean", "default": False},
                    },
                    "required": ["column"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_unique",
                "description": "Sample of unique values from a column.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "n": {"type": "integer", "default": 100, "minimum": 1},
                    },
                    "required": ["column"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_filter_equals",
                "description": "Filter rows where df[column] == value (exact match).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "value": {
                            "anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]
                        },
                        "limit": {"type": "integer", "default": 50, "minimum": 1},
                    },
                    "required": ["column", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_filter_in",
                "description": "Filter rows where df[column] is in a list of values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "values": {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "boolean"},
                                ]
                            },
                            "description": "Non-empty list of values to match.",
                        },
                        "limit": {"type": "integer", "default": 50, "minimum": 1},
                    },
                    "required": ["column", "values"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_filter_range",
                "description": "Numeric range filter for a column between min_value and max_value.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "min_value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                        "max_value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                        "limit": {"type": "integer", "default": 50, "minimum": 1},
                    },
                    "required": ["column"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_pivot_table",
                "description": "Pivot across index x columns for a numeric value with an aggregation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "array", "items": {"type": "string"}, "default": []},
                        "columns": {"type": "array", "items": {"type": "string"}, "default": []},
                        "value": {"type": "string"},
                        "agg": {
                            "type": "string",
                            "enum": ["sum", "mean", "count"],
                            "default": "sum",
                        },
                        "top": {"type": "integer", "default": 20, "minimum": 1},
                    },
                    "required": ["value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_corr_top",
                "description": "Top absolute correlations with a numeric target.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "n": {"type": "integer", "default": 5, "minimum": 1},
                    },
                    "required": ["target"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "df_sql_select",
                "description": "Run read-only SELECT/WITH SQL on the dataframe via DuckDB (table name: t). Returns a small table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SELECT/WITH query referencing table 't'",
                        },
                        "limit": {"type": "integer", "default": 50, "minimum": 1},
                    },
                    "required": ["sql"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_chart_state",
                "description": "Return JSON describing current chart state (chart_id and placeholders for filters).",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]

    client = get_openai_client()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=cast(Iterable[ChatCompletionMessageParam], messages),
            tools=cast(Iterable[ChatCompletionToolParam], tools),
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            # Preserve assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": (msg.content or ""),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Dispatch each tool call safely
            for tc in tool_calls:
                name = tc.function.name
                try:
                    print(f"[AI][tool_query] dispatch: {name}", flush=True)
                except Exception:
                    pass
                try:
                    import json  # local import to avoid global import changes

                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}

                if name == "df_describe":
                    content = _df_describe_tool(df, args.get("columns"))
                elif name == "df_groupby_sum":
                    content = _df_groupby_sum_tool(
                        df,
                        args.get("by", []),
                        args.get("value") or "",
                        args.get("n", 10),
                        args.get("ascending", False),
                    )
                elif name == "df_top_n":
                    content = _df_top_n_tool(
                        df,
                        args.get("by") or "",
                        args.get("n", 10),
                        args.get("ascending", False),
                    )
                elif name == "df_value_counts":
                    content = _df_value_counts_tool(
                        df,
                        args.get("column") or "",
                        args.get("n", 20),
                        args.get("normalize", False),
                    )
                elif name == "df_unique":
                    content = _df_unique_tool(
                        df,
                        args.get("column") or "",
                        args.get("n", 100),
                    )
                elif name == "df_filter_equals":
                    content = _df_filter_equals_tool(
                        df,
                        args.get("column") or "",
                        args.get("value"),
                        args.get("limit", 50),
                    )
                elif name == "df_filter_in":
                    content = _df_filter_in_tool(
                        df,
                        args.get("column") or "",
                        args.get("values") or [],
                        args.get("limit", 50),
                    )
                elif name == "df_filter_range":
                    content = _df_filter_range_tool(
                        df,
                        args.get("column") or "",
                        args.get("min_value"),
                        args.get("max_value"),
                        args.get("limit", 50),
                    )
                elif name == "df_pivot_table":
                    content = _df_pivot_table_tool(
                        df,
                        args.get("index") or [],
                        args.get("columns") or [],
                        args.get("value") or "",
                        args.get("agg", "sum"),
                        args.get("top", 20),
                    )
                elif name == "df_corr_top":
                    content = _df_corr_top_tool(
                        df,
                        args.get("target") or "",
                        args.get("n", 5),
                    )
                elif name == "df_sql_select":
                    content = _df_sql_select_tool(
                        df,
                        args.get("sql", ""),
                        args.get("limit", 50),
                    )
                elif name == "get_chart_state":
                    content = _get_chart_state_tool()
                else:
                    content = f"[unknown tool: {name}]"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content,
                    }
                )

            # Get the final model answer after tool outputs
            resp2 = client.chat.completions.create(
                model=model_name,
                messages=cast(Iterable[ChatCompletionMessageParam], messages),
            )
            content = getattr(resp2.choices[0].message, "content", "") or ""
            return content.replace("$", "\\$")
        else:
            # No tool calls; just return the content
            content = getattr(msg, "content", "") or ""
            return content.replace("$", "\\$")
    except Exception as e:
        return f"Tool-assisted query error: {e}"


def _df_value_counts_tool(df, column: str, n: int = 20, normalize: bool = False) -> str:
    """Tool: value counts for a column (optionally normalized)."""
    try:
        if column not in df.columns:
            return f"[df_value_counts error] invalid column: {column}"
        try:
            import pandas as pd  # local import to avoid global side-effects
        except Exception:
            return "[df_value_counts error] pandas not available"
        s = df[column]
        vc = s.value_counts(normalize=bool(normalize), dropna=False).head(max(int(n or 20), 1))
        col_name = "proportion" if normalize else "count"
        res = pd.DataFrame({str(column): vc.index.astype(str), col_name: vc.values})
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_value_counts error] {e}"


def _df_unique_tool(df, column: str, n: int = 100) -> str:
    """Tool: sample of unique values from a column (up to n)."""
    try:
        if column not in df.columns:
            return f"[df_unique error] invalid column: {column}"
        try:
            import pandas as pd
        except Exception:
            return "[df_unique error] pandas not available"
        uniq = df[column].dropna().astype(str).unique().tolist()
        uniq = uniq[: max(int(n or 100), 1)]
        res = pd.DataFrame({"value": uniq})
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_unique error] {e}"


def _df_filter_equals_tool(df, column: str, value: Any, limit: int = 50) -> str:
    """Tool: filter rows where df[column] == value (exact match)."""
    try:
        if column not in df.columns:
            return f"[df_filter_equals error] invalid column: {column}"
        res = df[df[column] == value].head(max(int(limit or 50), 1))
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_filter_equals error] {e}"


def _df_filter_in_tool(df, column: str, values: list[Any] | None = None, limit: int = 50) -> str:
    """Tool: filter rows where df[column] is in values (list)."""
    try:
        if column not in df.columns:
            return f"[df_filter_in error] invalid column: {column}"
        if not isinstance(values, list) or not values:
            return "[df_filter_in error] 'values' must be a non-empty list"
        res = df[df[column].isin(values)].head(max(int(limit or 50), 1))
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_filter_in error] {e}"


def _df_filter_range_tool(
    df, column: str, min_value: float | None = None, max_value: float | None = None, limit: int = 50
) -> str:
    """Tool: numeric range filter for df[column] between min_value and max_value."""
    try:
        if column not in df.columns:
            return f"[df_filter_range error] invalid column: {column}"
        try:
            import pandas as pd
        except Exception:
            return "[df_filter_range error] pandas not available"
        s = pd.to_numeric(df[column], errors="coerce")
        # If conversion failed (object), try coercing to numeric with NaNs allowed
        if not hasattr(s, "dtype") or getattr(s.dtype, "kind", "") not in ("i", "u", "f"):
            s = pd.to_numeric(df[column], errors="coerce")
        mask = s.notna()
        if min_value is not None:
            try:
                mask &= s >= float(min_value)
            except Exception:
                return f"[df_filter_range error] min_value not comparable: {min_value}"
        if max_value is not None:
            try:
                mask &= s <= float(max_value)
            except Exception:
                return f"[df_filter_range error] max_value not comparable: {max_value}"
        res = df[mask].head(max(int(limit or 50), 1))
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_filter_range error] {e}"


def _df_pivot_table_tool(
    df,
    index: list[str] | None = None,
    columns: list[str] | None = None,
    value: str | None = None,
    agg: str = "sum",
    top: int = 20,
) -> str:
    """Tool: pivot table across index x columns for a numeric value with an aggregation."""
    try:
        try:
            import pandas as pd
        except Exception:
            return "[df_pivot_table error] pandas not available"
        index = index or []
        columns = columns or []
        if value is None or value not in df.columns:
            return f"[df_pivot_table error] invalid value column: {value}"
        allowed_aggs = {"sum": "sum", "mean": "mean", "count": "count"}
        aggfunc_param = cast(Any, allowed_aggs.get(str(agg).lower(), "sum"))
        pt = pd.pivot_table(df, index=index, columns=columns, values=value, aggfunc=aggfunc_param)
        pt = pt.fillna(0)
        # Flatten columns for readability
        if hasattr(pt.columns, "levels"):
            pt.columns = [" | ".join(map(str, c)).strip() for c in pt.columns.values]
        else:
            pt.columns = [str(c) for c in pt.columns]
        res = pt.reset_index().head(max(int(top or 20), 1))
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_pivot_table error] {e}"


def _df_corr_top_tool(df, target: str, n: int = 5) -> str:
    """Tool: top |corr| with target (numeric-only)."""
    try:
        if target not in df.columns:
            return f"[df_corr_top error] invalid target column: {target}"
        try:
            pass
        except Exception:
            return "[df_corr_top error] pandas not available"
        num = df.select_dtypes(include="number")
        if target not in num.columns:
            return f"[df_corr_top error] target is not numeric: {target}"
        corr = num.corr(numeric_only=True)
        if target not in corr.columns:
            return f"[df_corr_top error] cannot compute correlations for: {target}"
        s = corr[target].drop(labels=[target], errors="ignore").dropna()
        if s.empty:
            return "[df_corr_top] no numeric columns to correlate with target"
        s_abs = s.abs().sort_values(ascending=False).head(max(int(n or 5), 1))
        res = s_abs.reset_index()
        res.columns = ["feature", "abs_corr_to_target"]
        return _safe_markdown_table(res)
    except Exception as e:
        return f"[df_corr_top error] {e}"


def _df_sql_select_tool(df, sql: str, limit: int = 50) -> str:
    """Tool: run a read-only SELECT/WITH query via DuckDB against registered table 't'."""
    try:
        lower = str(sql or "").strip().lower()
        if not (lower.startswith("select") or lower.startswith("with")):
            return "[df_sql_select error] only SELECT/WITH queries are allowed"
        if ";" in lower:
            return "[df_sql_select error] semicolons are not allowed"
        forbidden = (
            " insert ",
            " update ",
            " delete ",
            " create ",
            " alter ",
            " drop ",
            " attach ",
            " copy ",
            " replace ",
            " merge ",
            " vacuum ",
            " pragma ",
        )
        if any(tok in f" {lower} " for tok in forbidden):
            return "[df_sql_select error] disallowed keyword detected"
        try:
            import duckdb  # type: ignore
        except Exception:
            return "[df_sql_select error] duckdb not installed. Try: pip install duckdb"
        con = duckdb.connect()
        try:
            con.register("t", df)
            capped = max(int(limit or 50), 1)
            safe_sql = f"SELECT * FROM ({sql}) AS sub LIMIT {capped}"
            res_df = con.execute(safe_sql).df()
        finally:
            con.close()
        return _safe_markdown_table(res_df)
    except Exception as e:
        return f"[df_sql_select error] {e}"


def _get_chart_state_tool() -> str:
    """Tool: return JSON describing current chart state (chart_id and known page-level filters)."""
    try:
        import json
        from typing import Any

        # Try both import paths for app_state getter
        try:
            from utils.app_state import get_selected_chart as _get_sel  # type: ignore
        except Exception:
            try:
                from GrantScope.utils.app_state import (
                    get_selected_chart as _get_sel,  # type: ignore
                )
            except Exception:
                _get_sel = None  # type: ignore

        # Resolve chart id from global app state
        try:
            cid = _get_sel(None) if _get_sel is not None else None
        except Exception:
            cid = None

        filters: dict[str, Any] = {}
        try:
            # Distribution page filters
            if cid == "distribution.main":
                filters = {
                    "metric": st.session_state.get("dist_metric"),
                    "top_n": st.session_state.get("dist_top_n"),
                    "log_y": st.session_state.get("dist_log_y"),
                    "sort_dir": st.session_state.get("dist_sort_dir"),
                    "selected_clusters": st.session_state.get("dist_selected_clusters"),
                }
            # Scatter page filters
            elif cid == "scatter.main":
                filters = {
                    "start_year": st.session_state.get("scatter_start_year"),
                    "end_year": st.session_state.get("scatter_end_year"),
                    "selected_clusters": st.session_state.get("scatter_clusters"),
                    "marker_size": st.session_state.get("scatter_marker_size"),
                    "opacity": st.session_state.get("scatter_opacity"),
                    "log_y": st.session_state.get("scatter_log_y"),
                }
            # Heatmap page filters
            elif cid == "heatmap.main":
                filters = {
                    "dimension1": st.session_state.get("heatmap_dimension1"),
                    "dimension2": st.session_state.get("heatmap_dimension2"),
                    "selected_values1": st.session_state.get("heatmap_values1"),
                    "selected_values2": st.session_state.get("heatmap_values2"),
                    "normalize": st.session_state.get("heatmap_normalize"),
                    "colorscale": st.session_state.get("heatmap_colorscale"),
                }
            # Treemaps page filters
            elif cid == "treemaps.main":
                filters = {
                    "analyze_column": st.session_state.get("treemap_analyze_column"),
                    "selected_label": st.session_state.get("treemap_selected_label"),
                }
            # Data Summary — Top Funders
            elif cid == "data_summary.top_funders":
                filters = {
                    "top_n": st.session_state.get("ds_top_n"),
                }
            # Relationships page filters
            elif cid == "relationships.description_vs_amount":
                filters = {}
            elif cid == "relationships.avg_by_factor":
                filters = {
                    "selected_factor": st.session_state.get("rel_selected_factor"),
                    "chart_type": st.session_state.get("rel_chart_type"),
                }
            elif cid == "relationships.funder_affinity":
                filters = {
                    "selected_funder": st.session_state.get("rel_selected_funder"),
                    "affinity_factor": st.session_state.get("rel_selected_affinity_factor"),
                }
            # Top Categories page filters
            elif cid == "top_categories.main":
                filters = {
                    "selected_categorical": st.session_state.get("topcat_selected_categorical"),
                    "top_n": st.session_state.get("topcat_top_n"),
                    "chart_type": st.session_state.get("topcat_chart_type"),
                    "sort_order": st.session_state.get("topcat_sort_order"),
                }
            else:
                filters = {}
        except Exception:
            filters = {}

        payload = {
            "chart_id": cid,
            "filters": filters,
            "user_role": st.session_state.get("user_role"),
        }
        return json.dumps(payload)
    except Exception as e:
        return f'{{"error": "get_chart_state failed: {e}"}}'
