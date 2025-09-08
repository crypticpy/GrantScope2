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
        Produce a comprehensive AnalysisPlan as JSON with:
        - "metric_requests": an array of 8-12 analysis objects {{ "tool": string, "params": object, "title": string }}
          The "tool" must be one of: {tools}
          "params" must be small and safe (column names, group-by lists, ranges, simple SQL SELECT/WITH for 'df_sql_select').
        - "narrative_outline": an array of section titles describing how to synthesize findings.

        Required Analysis Components (include all):
        1. Funder Analysis: "df_groupby_sum" by ["funder_name"] to identify top funders
        2. Subject Analysis: "df_value_counts" on "grant_subject_tran" for subject distribution
        3. Population Analysis: "df_value_counts" on "grant_population_tran" for beneficiary analysis
        4. Geographic Analysis: "df_value_counts" on "grant_geo_area_tran" for location insights
        5. Temporal Analysis: "df_pivot_table" by ["year_issued"] to show funding trends over time
        6. Amount Distribution: "df_describe" on "amount_usd" for statistical overview
        7. Cross-Analysis: "df_groupby_sum" by ["grant_subject_tran", "grant_population_tran"] for intersection insights
        8. Funder-Subject Analysis: "df_pivot_table" with index=["funder_name"], columns=["grant_subject_tran"], value="amount_usd"
        
        Additional Guidance:
        - Use descriptive titles like "Top Funders by Total Amount", "Subject Area Distribution", "Geographic Funding Patterns"
        - For groupby operations, use n=10-15 to get meaningful samples
        - Include both amount-based and count-based analyses where applicable
        - Ensure geographic analysis covers all location data in the dataset
        - For pivot tables, use agg="sum" and top=15-20 for comprehensive views
        - Narrative outline should include 8-10 section titles covering different aspects

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
        Create a grant funding guide for municipal employees written at an 8th-grade reading level. 
        Use the DataPoints to create 8 practical sections that help non-experts understand their funding options.
        
        Writing Requirements:
        - Use simple, clear language (avoid jargon like "funder candidates", "aggregated data", "metrics")
        - Write short paragraphs (2-3 sentences max)
        - Include specific dollar amounts, percentages, and examples
        - Add "What This Means for You" explanations after data points
        - Use bullet points and numbered lists for clarity
        - Cite DataPoints as sources (e.g., "Based on our analysis (DP-001)")
        
        Required Sections (write exactly these 8):
        1. **Your Funding Landscape** - Simple overview of available funding
        2. **Types of Funders to Contact** - Categories of foundations/organizations that give money
        3. **How Much Money to Ask For** - Budget ranges that get approved most often
        4. **Best Times to Apply** - When to submit applications based on funding cycles
        5. **What Funders Want to See** - Most successful project types and requirements
        6. **Your Geographic Advantages** - Location-based funding opportunities
        7. **Positioning Your Project** - How to describe your work to get funded
        8. **Your 90-Day Action Plan** - Step-by-step tasks with deadlines
        
        For each section:
        - Start with a clear problem or opportunity
        - Present data in plain English ("75% of grants go to..." not "statistical analysis reveals")
        - Add practical guidance ("This means you should...")
        - Include specific examples and next steps
        
        Example format:
        "Looking at 500+ grants in our database, we found that programs serving children get funded 3x more often than adult programs. **What this means for you:** If your project helps kids, mention that prominently in your application. If it serves adults, consider adding a youth component."
        
        Return an array of sections with title and markdown_body.
        
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
        Create practical recommendations for municipal employees who are new to grant writing. Use plain language and focus on actionable next steps.

        Generate these 3 sections:
        - "funder_candidates": 8+ foundations to contact with {{ "name", "score", "rationale", "grounded_dp_ids": string[] }}
        - "response_tuning": 10+ practical tips with {{ "text", "grounded_dp_ids": string[] }} 
        - "search_queries": 8+ specific research terms for finding more opportunities

        **Funder Candidates ("Foundations to Contact"):**
        - Write rationales in simple language municipal employees understand
        - Include specific dollar amounts and what they typically fund
        - Explain WHY this funder is a good match (not just data rankings)
        - Add contact difficulty ("Easy to reach" vs "Requires relationship building")
        - Mix large and small funders for realistic options
        
        Examples:
        - "This foundation gave $2.3M to education projects like yours. They prefer programs serving kids and have funded similar cities. Start here - they're known for responding to new applicants."
        - "Corporate funder that supports communities where they have offices. Smaller grants ($5K-50K) but faster decisions. Good for equipment or training needs."

        **Response Tuning ("How to Write Better Applications"):**
        Write practical tips that help with actual grant writing:
        - Budget guidance ("Ask for $X based on similar successful projects")
        - Application timing ("Apply in March when they have the most money")
        - What to emphasize ("Highlight youth impact - 75% of their grants serve kids")
        - Common mistakes to avoid ("Don't ask for operating costs - they only fund programs")
        - Local advantages ("Mention your partnership with [local organization]")
        - Writing tips ("Use their exact language from their website")
        
        **Search Queries ("What to Google Next"):**
        Create specific search terms for:
        - Foundation directories ("Texas community foundations directory")
        - Specific funders ("[Funder Name] application guidelines 2024")
        - Similar projects ("after school program grants Austin successful")
        - Government programs ("Texas education grants municipalities")
        - Corporate giving ("[Company] community grants [your city]")

        Use actual data from DataPoints to support every recommendation. Reference dollar amounts, success rates, and specific examples.
        
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
