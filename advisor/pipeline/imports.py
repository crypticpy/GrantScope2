"""
Centralized, defensive imports so downstream modules can just do:
from .imports import <Name>
"""

# Schemas / models
try:
    from GrantScope.advisor.schemas import (  # type: ignore
        InterviewInput,
        StructuredNeeds,
        AnalysisPlan,
        MetricRequest,
        DataPoint,
        Recommendations,
        ReportSection,
        ReportBundle,
        ChartSummary,
        FigureArtifact,
        FunderCandidate,
        TuningTip,
        SearchQuery,
        stable_hash_for_obj,
    )
except Exception:  # pragma: no cover
    from advisor.schemas import (  # type: ignore
        InterviewInput,
        StructuredNeeds,
        AnalysisPlan,
        MetricRequest,
        DataPoint,
        Recommendations,
        ReportSection,
        ReportBundle,
        ChartSummary,
        FigureArtifact,
        FunderCandidate,
        TuningTip,
        SearchQuery,
        stable_hash_for_obj,
    )

# Prompts
try:
    from GrantScope.advisor.prompts import (  # type: ignore
        system_guardrails,
        stage0_intake_summary_user,
        stage1_normalize_user,
        stage2_plan_user,
        stage4_synthesize_user,
        stage5_recommend_user,
        chart_interpretation_user,
        WHITELISTED_TOOLS,
    )
except Exception:  # pragma: no cover
    from advisor.prompts import (  # type: ignore
        system_guardrails,
        stage0_intake_summary_user,
        stage1_normalize_user,
        stage2_plan_user,
        stage4_synthesize_user,
        stage5_recommend_user,
        chart_interpretation_user,
        WHITELISTED_TOOLS,
    )

# Utils
try:
    from GrantScope.utils.utils import generate_page_prompt  # type: ignore
except Exception:  # pragma: no cover
    from utils.utils import generate_page_prompt  # type: ignore

# Loaders / tool execution wiring
try:
    from GrantScope.loaders.llama_index_setup import (  # type: ignore
        get_openai_client,
        tool_query,
        resolve_chart_context,
    )
except Exception:  # pragma: no cover
    from loaders.llama_index_setup import (  # type: ignore
        get_openai_client,
        tool_query,
        resolve_chart_context,
    )

# Normalization helpers
try:
    from GrantScope.advisor.normalization import (  # type: ignore
        _tokens_lower,
        _contains_any,
        _expand_token_variants,
        _expand_terms,
        _canonical_value_samples,
        _apply_needs_filters,
    )
except Exception:  # pragma: no cover
    from advisor.normalization import (  # type: ignore
        _tokens_lower,
        _contains_any,
        _expand_token_variants,
        _expand_terms,
        _canonical_value_samples,
        _apply_needs_filters,
    )

# Stages (LLM-cached helpers)
try:
    from GrantScope.advisor.stages import (  # type: ignore
        _stage0_intake_summary_cached,
        _stage1_normalize_cached,
        _stage2_plan_cached,
        _stage4_synthesize_cached,
        _interpret_chart_cached,
        _stage5_recommend_cached,
    )
except Exception:  # pragma: no cover
    from advisor.stages import (  # type: ignore
        _stage0_intake_summary_cached,
        _stage1_normalize_cached,
        _stage2_plan_cached,
        _stage4_synthesize_cached,
        _interpret_chart_cached,
        _stage5_recommend_cached,
    )

# Optional config
try:
    from GrantScope import config as _cfg  # type: ignore
except Exception:  # pragma: no cover
    try:
        import config as _cfg  # type: ignore
    except Exception:
        _cfg = None  # type: ignore

__all__ = [
    # Schemas
    "InterviewInput", "StructuredNeeds", "AnalysisPlan", "MetricRequest", "DataPoint",
    "Recommendations", "ReportSection", "ReportBundle", "ChartSummary", "FigureArtifact",
    "FunderCandidate", "TuningTip", "SearchQuery", "stable_hash_for_obj",
    # Prompts
    "system_guardrails", "stage0_intake_summary_user", "stage1_normalize_user",
    "stage2_plan_user", "stage4_synthesize_user", "stage5_recommend_user",
    "chart_interpretation_user", "WHITELISTED_TOOLS",
    # Utils & tools
    "generate_page_prompt", "get_openai_client", "tool_query", "resolve_chart_context",
    # Normalization
    "_tokens_lower", "_contains_any", "_expand_token_variants", "_expand_terms",
    "_canonical_value_samples", "_apply_needs_filters",
    # Stages
    "_stage0_intake_summary_cached", "_stage1_normalize_cached", "_stage2_plan_cached",
    "_stage4_synthesize_cached", "_interpret_chart_cached", "_stage5_recommend_cached",
    # Config
    "_cfg",
]
