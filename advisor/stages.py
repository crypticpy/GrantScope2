from __future__ import annotations

"""
Stage helper functions for the Advisor pipeline.

This module centralizes the cached LLM-backed stages to keep
advisor.pipeline lean and under 300 lines per file where feasible.
It preserves behavior and public API by providing the same
stage helper functions previously defined in pipeline.py.
"""

from typing import Any, Dict, List
import json as _json

import streamlit as st

# Flexible imports to work when run as package or local
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

try:
    from GrantScope.loaders.llama_index_setup import get_openai_client  # type: ignore
except Exception:  # pragma: no cover
    from loaders.llama_index_setup import get_openai_client  # type: ignore

# Optional central config (model selection)
try:
    from GrantScope import config as _cfg  # type: ignore
except Exception:  # pragma: no cover
    try:
        import config as _cfg  # type: ignore
    except Exception:
        _cfg = None  # type: ignore


def _json_dumps_stable(obj: Any) -> str:
    return _json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _json_loads(text: str) -> Any:
    return _json.loads(text)


def _model_name() -> str:
    if _cfg is not None:
        try:
            return _cfg.get_model_name()
        except Exception:
            pass
    return "gpt-5-mini"


def _chat_completion_text(user_content: str) -> str:
    """Return assistant message content (non-streaming)."""
    client = get_openai_client()
    system = system_guardrails()
    resp = client.chat.completions.create(
        model=_model_name(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    try:
        content = resp.choices[0].message.content or ""
    except Exception:
        content = str(resp)
    return content


def _chat_completion_json(user_content: str) -> Any:
    """Return parsed JSON from an assistant response. If parsing fails, raise."""
    txt = _chat_completion_text(user_content)
    s = txt.strip()
    if "```" in s:
        try:
            start = s.index("```")
            rest = s[start + 3 :]
            if rest.lower().startswith("json"):
                rest = rest[4:]
            end = rest.index("```")
            s = rest[:end]
        except Exception:
            s = s
    try:
        return _json_loads(s)
    except Exception as e:
        raise ValueError(
            f"Assistant did not return valid JSON: {e}. Raw: {txt[:240]}"
        ) from e


@st.cache_data(show_spinner=True)
def _stage0_intake_summary_cached(key: str, interview_dict: Dict[str, Any]) -> str:
    try:
        return _chat_completion_text(stage0_intake_summary_user(interview_dict)).strip()
    except Exception:
        pa = interview_dict.get("program_area") or "a municipal program"
        geo = ", ".join(interview_dict.get("geography") or []) or "target geographies"
        return (
            f"This interview focuses on {pa} serving {geo}. "
            "The goal is to align needs with funders using historical grant data."
        )


@st.cache_data(show_spinner=True)
def _stage1_normalize_cached(key: str, interview_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage1_normalize_user(interview_dict))
        if isinstance(obj, dict):
            allowed = {"subjects", "populations", "geographies", "weights"}
            return {k: v for k, v in obj.items() if k in allowed}
    except Exception:
        pass
    subj: List[str] = []
    kw = interview_dict.get("keywords") or []
    if isinstance(kw, list):
        subj = [str(x).strip().lower().replace(" ", "_") for x in kw][:5]
    return {
        "subjects": subj,
        "populations": [
            str(x).lower().replace(" ", "_") for x in (interview_dict.get("populations") or [])
        ],
        "geographies": [str(x).upper() for x in (interview_dict.get("geography") or [])],
        "weights": {},
    }


@st.cache_data(show_spinner=True)
def _stage2_plan_cached(key: str, needs_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage2_plan_user(needs_dict))
        mr = obj.get("metric_requests", []) if isinstance(obj, dict) else []
        clean: List[Dict[str, Any]] = []
        for item in mr:
            try:
                tool = str(item.get("tool"))
                if tool not in WHITELISTED_TOOLS:
                    continue
                params = item.get("params") or {}
                title = str(item.get("title") or tool)
                clean.append({"tool": tool, "params": params, "title": title})
            except Exception:
                continue
        outline = obj.get("narrative_outline", []) if isinstance(obj, dict) else []
        return {"metric_requests": clean, "narrative_outline": outline}
    except Exception:
        return {
            "metric_requests": [
                {
                    "tool": "df_groupby_sum",
                    "params": {"by": ["funder_name"], "value": "amount_usd", "n": 15},
                    "title": "Top Funders by Total Amount",
                },
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_subject_tran", "n": 12},
                    "title": "Subject Area Distribution",
                },
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_population_tran", "n": 10},
                    "title": "Population Focus Analysis",
                },
                {
                    "tool": "df_value_counts",
                    "params": {"column": "grant_geo_area_tran", "n": 15},
                    "title": "Geographic Funding Patterns",
                },
                {
                    "tool": "df_pivot_table",
                    "params": {"index": ["year_issued"], "value": "amount_usd", "agg": "sum", "top": 15},
                    "title": "Funding Trends Over Time",
                },
                {
                    "tool": "df_describe",
                    "params": {"column": "amount_usd"},
                    "title": "Grant Amount Distribution",
                },
                {
                    "tool": "df_groupby_sum",
                    "params": {"by": ["grant_subject_tran", "grant_population_tran"], "value": "amount_usd", "n": 12},
                    "title": "Subject-Population Intersection Analysis",
                },
                {
                    "tool": "df_top_n",
                    "params": {"column": "amount_usd", "n": 10},
                    "title": "Largest Individual Grants",
                },
            ],
            "narrative_outline": [
                "Executive Summary",
                "Funding Landscape Analysis", 
                "Key Funders and Players",
                "Subject Area Insights",
                "Target Population Analysis",
                "Geographic Distribution",
                "Temporal Trends",
                "Strategic Recommendations",
                "Implementation Guidance",
                "Next Steps"
            ],
        }


def _get_planner_budget_sections() -> List[Dict[str, Any]]:
    """Return optional sections derived from session planner_/budget_ summaries.

    Uses utils.app_state.get_planner_summary/get_budget_summary when available.
    If unavailable or empty, returns an empty list. Sections are compact and
    beginner-friendly to lightly contextualize the advisor report.
    """
    try:
        try:
            from utils.app_state import get_planner_summary, get_budget_summary  # type: ignore
        except Exception:
            try:
                from GrantScope.utils.app_state import (  # type: ignore
                    get_planner_summary,
                    get_budget_summary,
                )
            except Exception:
                return []

        sections: List[Dict[str, Any]] = []
        ps: str | None = None
        bs: str | None = None
        try:
            ps = get_planner_summary()  # type: ignore[call-arg]
        except Exception:
            ps = None
        try:
            bs = get_budget_summary()  # type: ignore[call-arg]
        except Exception:
            bs = None

        if ps:
            sections.append(
                {
                    "title": "Your Project Plan Summary",
                    "markdown_body": str(ps),
                }
            )
        if bs:
            sections.append(
                {
                    "title": "Your Budget Summary",
                    "markdown_body": str(bs),
                }
            )
        return sections
    except Exception:
        # Optional enhancement only; fail closed
        return []
@st.cache_data(show_spinner=True)
def _stage4_synthesize_cached(key: str, plan_dict: Dict[str, Any], dps_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        obj = _chat_completion_json(stage4_synthesize_user(plan_dict, dps_index))
        if isinstance(obj, list):
            clean: List[Dict[str, Any]] = []
            for it in obj:
                if isinstance(it, dict) and "title" in it and "markdown_body" in it:
                    clean.append({"title": str(it["title"]), "markdown_body": str(it["markdown_body"])})
            if clean:
                # Ensure minimum 8 sections then append compact planner/budget summaries when available
                sections = _ensure_min_sections(clean, dps_index)
                try:
                    extras = _get_planner_budget_sections()
                    if extras:
                        sections.extend(extras)
                except Exception:
                    pass
                return sections
    except Exception:
        pass
    # Fallback with deterministic 8-section template + optional planner/budget summaries
    sections = _generate_deterministic_sections(dps_index)
    try:
        extras = _get_planner_budget_sections()
        if extras:
            sections.extend(extras)
    except Exception:
        pass
    return sections

def _ensure_min_sections(sections: List[Dict[str, Any]], dps_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure minimum 8 sections with deterministic fills if needed."""
    if len(sections) >= 8:
        return sections
    
    # Add deterministic sections to reach minimum of 8
    while len(sections) < 8:
        missing_section_type = _get_missing_section_type(sections)
        new_section = _generate_section_by_type(missing_section_type, dps_index, sections)
        sections.append(new_section)
    
    return sections

def _get_missing_section_type(sections: List[Dict[str, Any]]) -> str:
    """Determine what type of section is missing."""
    existing_titles = [s.get("title", "").lower() for s in sections]
    
    section_types = [
        "overview", "funding patterns", "key players", "populations",
        "geographies", "time trends", "actionable insights", "next steps",
        "risk factors", "opportunities", "recommendations", "conclusion"
    ]
    
    for section_type in section_types:
        if not any(section_type in title for title in existing_titles):
            return section_type
    
    # If all common types are covered, add a generic one
    return f"additional_insights_{len(sections) + 1}"

def _generate_section_by_type(section_type: str, dps_index: List[Dict[str, Any]], existing_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a section of a specific type with deterministic content."""
    title = section_type.title().replace("_", " ")
    
    # Create a citation string from datapoints
    citations = ""
    if dps_index:
        # Use up to 3 datapoints for citations
        cited_dps = dps_index[:3]
        citations = " (Grounded in " + ", ".join([f"{dp.get('title', '')} ({dp.get('id', '')})" for dp in cited_dps]) + ")"
    
    # Generate content based on section type
    content_map = {
        "overview": (
            "This comprehensive analysis synthesizes insights from the available grant data to inform strategic funding decisions. "
            f"The report examines key patterns in funding allocation, identifies major players in the space, and highlights opportunities for alignment.{citations}"
        ),
        "funding patterns": (
            "Analysis of funding patterns reveals concentration in specific subject areas and geographic regions. "
            "Understanding these patterns is crucial for positioning proposals effectively. "
            "Organizations should consider both competitive landscapes and underserved areas when developing strategies."
        ),
        "key players": (
            "Key players in the funding landscape include both established foundations and emerging donors. "
            "Building relationships with these entities requires understanding their historical giving patterns and strategic priorities. "
            "The data reveals both consistent funders and those with sporadic but significant giving."
        ),
        "populations": (
            "The dataset encompasses grants serving diverse populations, with particular emphasis on certain demographic groups. "
            "Organizations should align their beneficiary focus with funders' demonstrated interests while also identifying underserved populations "
            "that might represent untapped opportunities for funding."
        ),
        "geographies": (
            "Geographic distribution of funding shows concentration in specific regions, with variation by subject area and population focus. "
            "A geographic analysis of the data indicates patterns that can guide targeting decisions. "
            "Organizations should consider both local opportunities where they have existing presence and strategic expansion into new regions "
            "where their expertise aligns with funding priorities."
        ),
        "time trends": (
            "Temporal analysis reveals both consistent funding streams and emerging trends. "
            "Some subject areas show steady growth while others experience volatility. "
            "Understanding these trends is essential for long-term strategic planning and grant proposal timing."
        ),
        "actionable insights": (
            "Based on the data analysis, several actionable insights emerge for grant seekers: "
            "1) Diversify funder portfolios to reduce dependency on a few major sources, "
            "2) Align proposal themes with demonstrated funder interests, "
            "3) Consider timing of submissions relative to funder fiscal cycles, "
            "4) Develop compelling narratives that connect to funder priorities."
        ),
        "next steps": (
            "Based on the data analysis and synthesized findings, organizations should: "
            "1) Create a targeted funder prospect list based on alignment scores, "
            "2) Develop tailored messaging for top prospects, "
            "3) Establish systematic tracking of funder activities and priorities, "
            "4) Build relationships through non-grant interactions such as conferences and networking events."
        ),
        "risk factors": (
            "Several risk factors should be considered in funding strategies: "
            "1) Concentration risk from over-reliance on a few major funders, "
            "2) Timing risk from misalignment with funder cycles, "
            "3) Thematic risk from pursuing areas with declining interest, "
            "4) Geographic risk from focusing on oversaturated regions."
        ),
        "opportunities": (
            "The analysis identifies several opportunities for strategic positioning: "
            "1) Emerging funders with growing portfolios, "
            "2) Underserved populations or geographic areas, "
            "3) Cross-sector collaboration opportunities, "
            "4) Innovation in grantmaking approaches that align with organizational strengths."
        ),
        "recommendations": (
            "Based on the comprehensive analysis, the following recommendations are provided: "
            "1) Develop a diversified funding pipeline with 15-20 qualified prospects, "
            "2) Create funder-specific value propositions that highlight unique organizational strengths, "
            "3) Establish metrics for tracking funder relationship development, "
            "4) Invest in proposal development capabilities to match identified opportunities."
        ),
        "conclusion": (
            "This analysis provides a foundation for strategic grant-seeking activities. "
            "Success in securing funding requires both data-driven prospect identification and relationship-building efforts. "
            "Organizations should view funder engagement as a long-term investment in sustainability rather than a transactional activity."
        )
    }
    
    # Default content if section type not specifically mapped
    default_content = (
        f"This section provides additional analysis on {section_type.replace('_', ' ')}. "
        "The data analysis draws on available datapoints to offer actionable guidance for grant-seeking strategies. "
        "Organizations should consider these findings in the context of their specific mission and capacity."
    )
    
    content = content_map.get(section_type.lower(), default_content)
    
    return {
        "title": title,
        "markdown_body": content
    }

def _generate_deterministic_sections(dps_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate a deterministic set of 8 sections when LLM fails."""
    sections = []
    section_config = [
        ("Overview of Your Funding Opportunities", "overview"),
        ("Funding Patterns and Landscape", "funding_patterns"), 
        ("Target Populations Analysis", "populations"),
        ("Geographies and Funding Distribution", "geographies"),
        ("Key Funders to Contact", "key_players"),
        ("Actionable Insights for Success", "actionable_insights"),
        ("Time Trends and Opportunities", "time_trends"),
        ("Next Steps and Recommendations", "next_steps")
    ]
    
    for title, section_type in section_config:
        section = _generate_section_by_type(section_type, dps_index, sections)
        # Override title to be more user-friendly
        section["title"] = title
        sections.append(section)
    
    return sections

def _generate_municipal_section(title: str, section_type: str, dps_index: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate user-friendly sections for municipal employees."""
    
    # Extract useful data points for context
    data_context = ""
    if dps_index:
        sample_dps = dps_index[:2]  # Use first 2 datapoints for context
        for dp in sample_dps:
            if dp.get('table_md'):
                data_context += f"Based on our analysis of grant data (Source: {dp.get('title', 'Data Analysis')}), "
                break
    
    content_templates = {
        "funding_landscape": f"""
## Your Funding Landscape

**The Big Picture:** There are hundreds of foundations and organizations that give money to public projects like yours. {data_context}we can help you find the right ones.

**What's Available:**
• **Foundation Grants** - Private foundations that support community projects ($5,000 - $500,000+)
• **Corporate Giving** - Companies that fund local initiatives ($1,000 - $100,000)
• **Government Grants** - Federal and state programs ($10,000 - $1,000,000+)
• **Community Foundations** - Local organizations focused on your area ($2,000 - $50,000)

**What This Means for You:** You have multiple funding sources to choose from. Don't put all your eggs in one basket - apply to several different types of funders to increase your chances of success.

**Quick Tip:** Start with local foundations first. They know your community and are often easier to reach than large national foundations.
""",
        
        "funder_types": f"""
## Types of Funders to Contact

**Private Foundations** are your best bet for ongoing projects. {data_context}they typically give larger amounts and fund for multiple years.
• Look for foundations with names like "[Name] Foundation" or "[Name] Fund"
• They focus on specific issues (education, health, environment)
• Award amounts: Usually $25,000 - $500,000
• Application process: More formal, longer deadlines

**Corporate Foundations** are great for community visibility projects.
• Banks, utilities, and local businesses often have giving programs
• They like projects that make their company look good in the community
• Award amounts: Typically $1,000 - $50,000
• Application process: Shorter, faster decisions

**Community Foundations** know your local needs best.
• These are local organizations that pool donations from many people
• They focus on your specific city or county
• Award amounts: Usually $5,000 - $75,000
• Application process: Less formal, more relationship-based

**What This Means for You:** Match your project to the right funder type. Need $100,000 for a new program? Focus on private foundations. Need $10,000 for equipment? Try corporate giving.
""",
        
        "budget_guidance": f"""
## How Much Money to Ask For

**The Sweet Spot:** {data_context}most successful grants fall into specific ranges based on project type and duration.

**Typical Award Ranges:**
• **Small Projects (1 year):** $5,000 - $25,000
  - Equipment, training, small program improvements
  - Success rate: Higher (less competition)

• **Medium Projects (1-2 years):** $25,000 - $100,000
  - New programs, staff positions, facility improvements
  - Success rate: Moderate (most competitive range)

• **Large Projects (2-3 years):** $100,000 - $500,000+
  - Major initiatives, multiple staff, significant infrastructure
  - Success rate: Lower (requires extensive planning)

**What This Means for You:**
• **Start smaller** - If you're new to grants, ask for less money to build a track record
• **Match the funder** - A $500,000 foundation won't fund your $5,000 project
• **Be realistic** - Can you actually spend the money effectively in the timeframe?

**Budget Breakdown Tip:** Funders want to see exactly how you'll spend their money. Break it down: 60% staff, 25% programs, 10% equipment, 5% evaluation.
""",
        
        "timing_guidance": f"""
## Best Times to Apply

**Grant Calendar Basics:** {data_context}timing can make or break your application. Most foundations work on predictable schedules.

**Best Application Months:**
• **January - March:** Many foundations start their grant cycles
• **August - October:** Second round of funding for the year
• **Avoid:** November-December (holiday planning) and June-July (summer break)

**Planning Timeline:**
• **6 months before:** Research funders, start building relationships
• **3 months before:** Begin writing your proposal
• **1 month before:** Final edits, gather required documents
• **Application deadline:** Submit early (not on the last day!)

**What This Means for You:**
• **Plan ahead** - Good grants take months to prepare
• **Apply early in the cycle** - Funders have more money available
• **Build relationships first** - Call or email before you apply

**Pro Tip:** Many funders require a "Letter of Intent" 2-3 months before the full application. Don't miss these pre-deadlines.

**Your Action:** Start working on grants for next year THIS month. The best funding goes to those who plan ahead.
""",
        
        "project_requirements": f"""
## What Funders Want to See

**The Winning Formula:** {data_context}successful projects share common features that funders love to support.

**Must-Have Elements:**
• **Clear Problem** - What specific issue are you solving?
• **Measurable Results** - How will you prove success? (Number of people served, test scores improved, etc.)
• **Community Support** - Letters from partners, city council, community groups
• **Qualified Staff** - Show you have the right people to do the work
• **Reasonable Budget** - Every dollar should be justified

**Project Types That Get Funded Most:**
1. **Youth Programs** - Anything serving kids and teens
2. **Education Initiatives** - After school, literacy, STEM programs
3. **Community Health** - Prevention, wellness, access to care
4. **Economic Development** - Job training, small business support
5. **Environmental Projects** - Sustainability, clean energy, conservation

**What This Means for You:**
• **Focus on outcomes** - Don't just describe activities, explain the impact
• **Use data** - Include statistics about the problem you're solving
• **Tell stories** - Share examples of people who will benefit

**Red Flags to Avoid:**
• Vague goals ("help the community")
• No evaluation plan
• Unrealistic timelines
• Budgets that don't add up
""",
        
        "geographic_opportunities": f"""
## Your Geographic Advantages

**Location Matters:** {data_context}where you're located affects which funders will support your work and how much money is available.

**Your Local Advantages:**
• **Community Foundations** in your area know local needs and priorities
• **Corporate Funders** prefer to support communities where they have offices or customers
• **State and Federal Programs** often have set-aside funds for different regions

**Geographic Funding Strategies:**
• **Local First** - Start with foundations within 50 miles of your project
• **State Programs** - Check your state government's grant portal monthly
• **Regional Connections** - Look for foundations that historically fund your area
• **National Reach** - Only pursue national funders if your project has broad impact

**What This Means for You:**
• **Build local relationships** - Attend community foundation events and city council meetings
• **Leverage local connections** - Use your mayor, city council members, and chamber of commerce contacts
• **Highlight local impact** - Show how your project benefits the specific community

**Research Tip:** Search online for "[Your City] foundation directory" or "[Your County] grant opportunities" to find local funding sources.

**Partnership Power:** Team up with organizations in other cities for regional grants that require multiple locations.
""",
        
        "project_positioning": f"""
## Positioning Your Project

**Make It Irresistible:** {data_context}how you describe your project determines whether funders will pay attention or move on to the next application.

**Winning Positioning Strategies:**

**1. Lead with Impact**
• Bad: "We want to start an after-school program"
• Good: "We'll keep 75 at-risk kids safe and learning while their parents work"

**2. Use Compelling Statistics**
• "30% of our students read below grade level" (creates urgency)
• "Studies show after-school programs reduce juvenile crime by 40%" (proves effectiveness)

**3. Show Community Need**
• Include demographic data about your area
• Quote local leaders supporting your project
• Reference other successful similar programs

**4. Match Funder Priorities**
• Read the funder's website and recent grants
• Use their language in your proposal
• Connect your work to their stated goals

**What This Means for You:**
• **Research each funder** - Customize every application
• **Lead with benefits** - What problems will you solve?
• **Use their words** - If they say "evidence-based," use that term
• **Be specific** - Exact numbers are better than "many" or "most"

**Elevator Pitch Formula:** "We help [specific group] achieve [specific outcome] by [specific method], which will result in [measurable benefit] for our community."
""",
        
        "action_plan": f"""
## Your 90-Day Action Plan

**Ready to Get Started?** {data_context}follow this step-by-step plan to go from idea to submitted application in 90 days.

**Days 1-30: Foundation Building**
□ **Week 1:** Define your project in one paragraph
□ **Week 2:** Research 10-15 potential funders using foundation directories
□ **Week 3:** Create a simple budget breakdown
□ **Week 4:** Start gathering support letters from community partners

**Days 31-60: Relationship Building**
□ **Week 5-6:** Email or call your top 5 funders to introduce your project
□ **Week 7:** Attend local foundation events or city council meetings
□ **Week 8:** Set up meetings with 2-3 potential funders

**Days 61-90: Application Preparation**
□ **Week 9:** Write your first draft proposal
□ **Week 10:** Get feedback from colleagues and community partners
□ **Week 11:** Revise proposal and finalize budget
□ **Week 12:** Submit application (aim for 1 week before deadline)

**Your Weekly Tasks:**
• **Mondays:** Research one new funder
• **Wednesdays:** Work on proposal writing
• **Fridays:** Follow up on relationships and partnerships

**What This Means for You:**
• **Start now** - Don't wait until you have the "perfect" project
• **Work consistently** - 2 hours per week is better than 8 hours once a month
• **Build relationships** - Successful grant writers know their funders personally

**Success Metrics:** By day 90, you should have submitted 2-3 applications and have 5+ funders who know your organization.
"""
    }
    
    content = content_templates.get(section_type, 
        f"## {title}\n\nThis section provides guidance on {section_type.replace('_', ' ')}. {data_context}we recommend focusing on practical steps that will help your municipal organization secure funding.\n\n**Key Points:**\n• Research thoroughly before applying\n• Build relationships with funders\n• Focus on measurable community impact\n• Plan your applications well in advance\n\n**Next Steps:** Review the data provided and identify 2-3 specific actions you can take this month to move your funding goals forward.")
    
    return {
        "title": title,
        "markdown_body": content
    }


@st.cache_data(show_spinner=True)
def _interpret_chart_cached(key: str, summary: Dict[str, Any], interview_dict: Dict[str, Any]) -> str:
    """Return a short interpretation for a chart, grounded in the provided summary and interview."""
    try:
        user_msg = chart_interpretation_user(summary, interview_dict)
        txt = _chat_completion_text(user_msg).strip()
        if txt:
            return txt
    except Exception:
        pass
    hi = summary.get("highlights") or []
    if hi:
        base = "; ".join(map(str, hi[:2]))
        return f"What this means: {base}."
    missing: List[str] = []
    for field in ("stats", "label"):
        try:
            if not summary.get(field):
                missing.append(field)
        except Exception:
            missing.append(field)
    if missing:
        return f"What this means: Interpretation unavailable; missing fields: {', '.join(missing)}."
    return "What this means: Interpretation unavailable due to limited data."


@st.cache_data(show_spinner=True)
def _stage5_recommend_cached(key: str, needs_dict: Dict[str, Any], dps_index: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        obj = _chat_completion_json(stage5_recommend_user(needs_dict, dps_index))
        if isinstance(obj, dict):
            fc = obj.get("funder_candidates") or []
            rt = obj.get("response_tuning") or []
            sq = obj.get("search_queries") or []
            return {"funder_candidates": fc, "response_tuning": rt, "search_queries": sq}
    except Exception:
        pass
    return {"funder_candidates": [], "response_tuning": [], "search_queries": []}


__all__ = [
    "_stage0_intake_summary_cached",
    "_stage1_normalize_cached",
    "_stage2_plan_cached",
    "_stage4_synthesize_cached",
    "_interpret_chart_cached",
    "_stage5_recommend_cached",
]