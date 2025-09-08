"""
Prompt templates and system guardrails for the Advisor interview pipeline.

This module provides small, focused helpers that return strings used as
system/user messages for each stage of the pipeline. Stages are:
- Stage 0: Intake summary (2 sentences)
- Stage 1: Normalize interview → StructuredNeeds (strict schema)
- Stage 2: Plan → AnalysisPlan (whitelisted tool calls)
- Stage 4: Synthesize markdown sections with grounded citations
- Stage 5: Recommend funders and response tuning
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from textwrap import dedent


WHITELISTED_TOOLS: tuple[str, ...] = (
    "df_describe",
    "df_groupby_sum",
    "df_top_n",
    "df_value_counts",
    "df_unique",
    "df_filter_equals",
    "df_filter_in",
    "df_filter_range",
    "df_pivot_table",
    "df_corr_top",
    "df_sql_select",
    "get_chart_state",
)


def system_guardrails() -> str:
    """Return a universal system prompt aligning with app-wide constraints."""
    return dedent(
        """
        You are a helpful grant analysis assistant. You must follow these guardrails:
        - Only use information grounded in the dataset Known Columns and tool outputs.
        - Never fabricate columns or data. If a requested field is unavailable, state that clearly.
        - Do not execute arbitrary code. Only use the provided whitelisted tools when planning or analyzing data.
        - Respond in concise Markdown, unless a JSON-only response is explicitly requested.
        - Avoid including any PII in outputs; redact if present in free-text inputs.
        """
    ).strip()


def stage0_intake_summary_user(interview_dict: dict[str, Any]) -> str:
    """User message for Stage 0: concise intake summary."""
    return dedent(
        f"""
        Summarize the following grant-seeking interview input in exactly two sentences.
        Focus on program area, populations, geography, budget/timeframe, and overall intent.

        InterviewInput (JSON):
        ```json
        {interview_dict}
        ```
        """
    ).strip()


def stage1_normalize_user(interview_dict: dict[str, Any]) -> str:
    """User message for Stage 1: normalize into StructuredNeeds JSON (strict schema)."""
    return dedent(
        f"""
        Normalize the following interview into a strict JSON object with this schema:

        StructuredNeeds:
        {{
          "subjects": string[],          // top subject taxonomy terms derived from program_area/keywords
          "populations": string[],       // normalized population keywords
          "geographies": string[],       // normalized region/state/country codes or names
          "weights": {{                   // optional emphasis weights for keys above
            "subjects.education": 0.7    // example
          }}
        }}

        - Only include the keys shown above.
        - Use lowercase snake-cased tokens for normalized taxonomy where possible.
        - Reject unknown fields (ignore anything not in the schema).
        - Return JSON only (no Markdown).

        InterviewInput (JSON):
        ```json
        {interview_dict}
        ```
        """
    ).strip()


def stage2_plan_user(needs: dict[str, Any]) -> str:
    """User message for Stage 2: produce an AnalysisPlan with whitelisted tool calls only."""
    tools = ", ".join(WHITELISTED_TOOLS)
    return dedent(
        f"""
        Produce an AnalysisPlan as JSON with:
        - "metric_requests": an array of objects {{ "tool": string, "params": object, "title": string }}
          The "tool" must be one of: {tools}
          "params" must be small and safe (column names, group-by lists, ranges, simple SQL SELECT/WITH for 'df_sql_select').
        - "narrative_outline": an array of section titles describing how to synthesize findings.

        Guidance:
        - Prioritize tools that illuminate subjects, geographies, populations, and time trends (e.g., df_groupby_sum, df_value_counts, df_pivot_table).
        - When 'subjects', 'populations', or 'geographies' appear in StructuredNeeds, include at least one funder-level metric:
          use "df_groupby_sum" with params.by including "funder_name" (optionally also "grant_subject_tran", "grant_geo_area_tran",
          "grant_population_tran") and value "amount_usd", with a small top N (e.g., n=10). Title example: "Top Funders by Amount".
        - Prefer value discovery before filtering: use "df_value_counts" or "df_unique" on "grant_subject_tran", "grant_population_tran",
          and "grant_geo_area_tran" to identify actual values present in the dataset, then filter using those.
        - Avoid exact equality/IN checks on categorical text fields that may contain compound values (e.g., semicolon-separated subjects).
          Prefer tools like "df_filter_in" only with values you have confirmed exist, or use "df_sql_select" with case-insensitive LIKE/ILIKE
          patterns against lower() to match substrings.
        - Translate common geo codes to names where needed (e.g., "TX" -> "Texas"). Prefer city/state names present in the data (e.g., "Austin", "Texas").
        - Keep each metric title short and human-friendly. Avoid large outputs; prefer top-10 lists and small tables.

        Return JSON only (no Markdown).

        StructuredNeeds (JSON):
        ```json
        {needs}
        ```
        """
    ).strip()


def stage4_synthesize_user(
    plan: dict[str, Any],
    datapoints_index: list[dict[str, Any]],
) -> str:
    """User message for Stage 4: synthesize markdown sections using DataPoints."""
    return dedent(
        f"""
        Draft a comprehensive report with a minimum of 8 detailed sections in Markdown using the provided DataPoints for grounding.
        
        Requirements:
        - Create exactly 8 sections covering different aspects of the analysis
        - Use clear headings and short paragraphs
        - Cite DataPoints explicitly with their IDs (e.g., (DP-001)) wherever relevant
        - Include actual data values, statistics, and rankings from the DataPoints
        - Avoid restating full tables; briefly summarize and reference
        - Do not invent data. If something isn't supported by DataPoints, say so
        - Each section should provide actionable insights
        
        Section Types Required:
        1. Overview - Executive summary of findings
        2. Funding Patterns - Analysis of funding distribution
        3. Key Players - Identification of major funders
        4. Populations - Focus on beneficiary demographics
        5. Geographies - Geographic distribution analysis
        6. Time Trends - Temporal analysis of funding
        7. Actionable Insights - Strategic recommendations
        8. Next Steps - Concrete actions for grant seekers
        
        Provide an array of sections, each with:
        {{
          "title": string,
          "markdown_body": string
        }}
        
        Include actual aggregated values and rankings in your analysis. For example:
        - "Funder X ranks 1st with $2.3M in grants (DP-001)"
        - "Education grants account for 35% of total funding (DP-002)"
        - "Texas received 12% of all grants in the dataset (DP-003)"
        
        Inputs:
        AnalysisPlan (JSON):
        ```json
        {plan}
        ```
        
        DataPoints (JSON):
        ```json
        {datapoints_index}
        ```
        """
    ).strip()


def chart_interpretation_user(summary: dict[str, Any], interview: dict[str, Any]) -> str:
    """User message to generate a concise, grounded interpretation for a single chart.

    Requirements:
    - 1–3 sentences, concise and suitable for reports.
    - Ground every statement in the provided ChartSummary (labels/series/highlights/stats) and InterviewInput.
    - Never invent columns or data. If a field is unavailable in 'summary' or 'interview', explicitly state it is unavailable.
    - Maintain neutral, professional tone. Avoid prescriptive language unless clearly supported by data.
    """
    return dedent(
        f"""
        Write a short interpretation titled "What this means" in 1–3 sentences.

        Constraints:
        - Ground the interpretation ONLY in the provided ChartSummary and InterviewInput.
        - If any important field is missing (e.g., no year_issued, no amount_usd), explicitly note "field unavailable".
        - Do NOT fabricate numbers or trends not present in the stats.
        - Keep style concise and professional, suitable for export/print.

        ChartSummary (JSON):
        ```json
        {summary}
        ```

        InterviewInput (JSON):
        ```json
        {interview}
        ```
        """
    ).strip()


def stage5_recommend_user(
    needs: dict[str, Any],
    datapoints_index: list[dict[str, Any]],
) -> str:
    """User message for Stage 5: recommend funders and response tuning tips."""
    return dedent(
        f"""
        Generate comprehensive structured recommendations grounded in the DataPoints:
        - "funder_candidates": Minimum 5 ranked items with fields {{ "name", "score", "rationale", "grounded_dp_ids": string[] }}
        - "response_tuning": Minimum 7 concise tips with fields {{ "text", "grounded_dp_ids": string[] }}
        - "search_queries": Minimum 5 short query strings for further research.

        Funder Candidates Requirements:
        - Provide actual aggregated data values in rationales (e.g., "Awarded $2.3M across 45 grants from 2020-2024")
        - Include rankings where applicable (e.g., "Ranks 3rd among education funders in the dataset")
        - Reference specific DataPoint IDs for grounding
        - Scores are 0.0–1.0 and should reflect relative fit based on actual data
        
        Response Tuning Requirements:
        - Provide data-driven tips grounded in actual dataset statistics
        - Include specific values from DataPoints (e.g., "Emphasize outcomes in X subject area, which accounts for 35% of funding")
        - Reference population and geography data where relevant
        - Include actionable advice based on time trends
        
        Search Queries Requirements:
        - Generate specific queries based on actual dataset values
        - Include funder names, subject areas, and geographic regions from the data
        - Focus on recent grants and current funding priorities

        Rules:
        - Use only signals derivable from the dataset context and DataPoints. No external assumptions.
        - Scores are 0.0–1.0 and should reflect relative fit based on actual data values.
        - Cite relevant DataPoint IDs for each item.
        - Include actual aggregated values and rankings in all responses.

        Return JSON only (no Markdown).

        StructuredNeeds (JSON):
        ```json
        {needs}
        ```

        DataPoints (JSON):
        ```json
        {datapoints_index}
        ```
        """
    ).strip()