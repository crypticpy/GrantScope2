"""
Help system and glossary for GrantScope.
Provides contextual help and plain-English definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict, cast

import streamlit as st

from config import is_enabled


class GlossaryEntry(TypedDict):
    """Structure for glossary entries."""

    term: str
    simple_definition: str
    also_known_as: list[str]
    related_terms: list[str]


# Built-in glossary data - can be extended or loaded from file
BUILT_IN_GLOSSARY: dict[str, GlossaryEntry] = {
    "funder": {
        "term": "funder",
        "simple_definition": "The organization that gives money for grants. Examples: foundations, government agencies, corporations.",
        "also_known_as": ["grantor", "funding organization", "donor"],
        "related_terms": ["grant", "recipient", "funding opportunity"],
    },
    "recipient": {
        "term": "recipient",
        "simple_definition": "The organization that receives grant money. This could be a nonprofit, school, government agency, or business.",
        "also_known_as": ["grantee", "awardee", "beneficiary organization"],
        "related_terms": ["funder", "grant", "application"],
    },
    "grant_amount": {
        "term": "grant_amount",
        "simple_definition": "How much money is given in a grant. Can range from hundreds to millions of dollars.",
        "also_known_as": ["award amount", "funding amount", "grant size"],
        "related_terms": ["budget", "funding", "amount_usd"],
    },
    "funder_type": {
        "term": "funder_type",
        "simple_definition": "What kind of organization gives the grant. Common types: foundation, government, corporation, individual.",
        "also_known_as": ["grantor type", "funding source type"],
        "related_terms": ["foundation", "government", "corporate giving"],
    },
    "grant_subject": {
        "term": "grant_subject",
        "simple_definition": "What the grant money is for. Examples: education, health, arts, environment, social services.",
        "also_known_as": ["program area", "focus area", "funding category"],
        "related_terms": ["program", "project", "initiative"],
    },
    "amount_usd": {
        "term": "amount_usd",
        "simple_definition": "The grant amount converted to US dollars. Makes it easy to compare grants from different countries.",
        "also_known_as": ["dollar amount", "USD amount", "funding in dollars"],
        "related_terms": ["grant_amount", "budget", "funding"],
    },
    "year_issued": {
        "term": "year_issued",
        "simple_definition": "The year when the grant was given out. Helps you see funding trends over time.",
        "also_known_as": ["award year", "grant year", "funding year"],
        "related_terms": ["timeline", "trends", "historical data"],
    },
    "application": {
        "term": "application",
        "simple_definition": "The formal request you submit to ask for grant money. Usually includes your project plan and budget.",
        "also_known_as": ["grant proposal", "funding request", "grant application"],
        "related_terms": ["proposal", "budget", "project plan"],
    },
    "deadline": {
        "term": "deadline",
        "simple_definition": "The last day you can submit your grant application. Missing the deadline means you can't apply.",
        "also_known_as": ["application deadline", "submission date", "due date"],
        "related_terms": ["timeline", "application", "submission"],
    },
    "match_funding": {
        "term": "match_funding",
        "simple_definition": "Money your organization must contribute to get the grant. For example, if a grant requires 25% match and awards $10,000, you must provide $2,500.",
        "also_known_as": ["matching funds", "cost share", "match requirement"],
        "related_terms": ["budget", "contribution", "cost sharing"],
    },
}


HelpVariant = Literal["tooltip", "expander", "sidebar"]
HelpAudience = Literal["new", "some", "pro"]


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_term(term_key: str) -> GlossaryEntry | None:
    """Get a specific glossary term."""
    # Try built-in glossary first
    if term_key.lower() in BUILT_IN_GLOSSARY:
        return BUILT_IN_GLOSSARY[term_key.lower()]

    # Try loading from external file if it exists
    try:
        glossary_path = Path("data/glossary.json")
        if glossary_path.exists():
            with open(glossary_path, encoding="utf-8") as f:
                external_glossary = json.load(f)
                if term_key.lower() in external_glossary:
                    return external_glossary[term_key.lower()]
    except Exception:
        pass  # Fall back to built-in only

    return None


@st.cache_data(ttl=600)  # Cache for 10 minutes
def search_terms(query: str) -> list[GlossaryEntry]:
    """Search glossary terms by query string."""
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    matches = []

    # Search built-in glossary
    for entry in BUILT_IN_GLOSSARY.values():
        # Check term name
        if query_lower in entry["term"].lower():
            matches.append(entry)
            continue
        # Check definition
        if query_lower in entry["simple_definition"].lower():
            matches.append(entry)
            continue
        # Check also_known_as
        for aka in entry["also_known_as"]:
            if query_lower in aka.lower():
                matches.append(entry)
                break

    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for entry in matches:
        if entry["term"] not in seen:
            seen.add(entry["term"])
            unique_matches.append(entry)

    return unique_matches[:10]  # Limit results


@st.cache_data(ttl=300)  # Cache for 5 minutes
def _load_external_glossary() -> dict[str, GlossaryEntry]:
    """Load external glossary file with caching."""
    try:
        glossary_path = Path("data/glossary.json")
        if glossary_path.exists():
            with open(glossary_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def render_help(
    topic_key: str, audience: HelpAudience = "new", variant: HelpVariant = "expander"
) -> None:
    """
    Render contextual help for a specific topic.

    Args:
        topic_key: The term to explain
        audience: Experience level of user (affects detail level)
        variant: How to display the help (tooltip, expander, sidebar)
    """
    if not is_enabled("GS_ENABLE_PLAIN_HELPERS"):
        return

    entry = get_term(topic_key)
    if not entry:
        return

    # Adjust content based on audience
    if audience == "pro":
        # Professionals get concise, technical info
        content = f"**{entry['term'].title()}**: {entry['simple_definition']}"
        if entry["also_known_as"]:
            content += f" (Also: {', '.join(entry['also_known_as'])})"
    elif audience == "some":
        # Experienced users get helpful details
        content = f"**{entry['term'].title()}**\n\n{entry['simple_definition']}"
        if entry["also_known_as"]:
            content += f"\n\n*Also called*: {', '.join(entry['also_known_as'])}"
    else:  # audience == "new"
        # Newbies get full explanation
        content = f"### {entry['term'].title()}\n\n{entry['simple_definition']}"
        if entry["also_known_as"]:
            content += f"\n\n**Also called**: {', '.join(entry['also_known_as'])}"
        if entry["related_terms"]:
            content += f"\n\n**Related terms**: {', '.join(entry['related_terms'])}"

    # Render based on variant
    if variant == "tooltip":
        st.help(content)
    elif variant == "expander":
        with st.expander(f"ℹ️ What is {entry['term']}?", expanded=False):
            st.markdown(content)
    elif variant == "sidebar":
        st.sidebar.markdown(content)


def render_glossary_search() -> None:
    """Render a searchable glossary panel for the sidebar."""
    if not is_enabled("GS_ENABLE_PLAIN_HELPERS"):
        return

    with st.sidebar.expander("📖 Glossary", expanded=False):
        st.markdown("**Quick definitions for grant terms**")

        query = st.text_input(
            "Search terms:", placeholder="Type to search...", key="glossary_search"
        )

        if query:
            matches = search_terms(query)
            if matches:
                for entry in matches:
                    st.markdown(f"**{entry['term'].title()}**")
                    st.markdown(entry["simple_definition"])
                    if entry["also_known_as"]:
                        st.caption(f"Also: {', '.join(entry['also_known_as'])}")
                    st.markdown("---")
            else:
                st.info("No matches found. Try a different term.")
        else:
            # Show a few common terms when no search
            common_terms = ["funder", "recipient", "grant_amount", "application"]
            st.markdown("**Common terms:**")
            for term in common_terms:
                entry = get_term(term)
                if entry:
                    st.markdown(
                        f"• **{entry['term'].title()}**: {entry['simple_definition'][:60]}..."
                    )


def render_contextual_help_buttons(terms: list[str], audience: HelpAudience = "new") -> None:
    """Render help buttons for multiple terms in a row."""
    if not is_enabled("GS_ENABLE_PLAIN_HELPERS") or not terms:
        return

    cols = st.columns(len(terms))
    for i, term in enumerate(terms):
        with cols[i]:
            entry = get_term(term)
            if entry:
                if st.button(f"❓ {term.title()}", key=f"help_{term}_{i}"):
                    render_help(term, audience, "expander")


def get_page_help() -> dict[str, dict[str, object]]:
    """Return per-page help mapping aligned to Writer Pack slugs and bullets."""
    return {
        "data_summary": {
            "title": "Data Summary",
            "content": """
- See what you loaded and the biggest numbers at a glance.
- Notice where most grants fall (common sizes or totals).
- If something looks off, check your file or try the sample data.
- Next: Continue to Grant Amount Distribution.
""",
            "related_terms": ["funder", "grant_amount", "year_issued"],
        },
        "grant_amount_distribution": {
            "title": "Grant Amount Distribution",
            "content": """
- Shows how many grants fall into each dollar range.
- Find the “typical” grant size for work like yours.
- Spot very large or very small grants worth a closer look.
- Decide your realistic range before planning.
- Next: Continue to Scatter (over time).
""",
            "related_terms": ["amount_usd", "grant_amount", "cluster"],
        },
        "grant_amount_scatter": {
            "title": "Scatter (over time)",
            "content": """
- Each dot is a grant placed by date and amount.
- Look for trends (going up, steady, or down).
- Do you see seasons or spikes? Note them for planning.
- Outliers are fine—focus on the overall pattern.
- Next: Continue to Heatmap.
""",
            "related_terms": ["year_issued", "trend", "outlier"],
        },
        "grant_amount_heatmap": {
            "title": "Heatmap",
            "content": """
- Darker cells mean more grants or more dollars in that spot.
- Find where activity is strong (by year, topic, or region).
- Use strong areas to pick focus topics and timing.
- Next: Continue to Treemaps.
""",
            "related_terms": ["subject", "population", "geography"],
        },
        "treemaps_extended": {
            "title": "Treemaps",
            "content": """
- Bigger boxes mean more funding or more grants for that category.
- Compare categories quickly to see what matters most.
- Pick the top few that match your goal and audience.
- Next: Continue to Word Clouds.
""",
            "related_terms": ["category", "subject", "funding_share"],
        },
        "grant_description_word_clouds": {
            "title": "Word Clouds",
            "content": """
- Bigger words appear more often in your grant text.
- Grab helpful terms for your plan and story.
- Avoid buzzwords—pick simple words that match your work.
- Next: Continue to Relationships.
""",
            "related_terms": ["keyword", "description", "term_frequency"],
        },
        "general_analysis_relationships": {
            "title": "Relationships",
            "content": """
- Shows which fields often appear together (like funders and topics).
- Use pairs you see often to shape your plan and partners.
- Note ideas you want to test later in the Advisor step.
- Next: Continue to Top Categories.
""",
            "related_terms": ["correlation", "co_occurrence", "funder", "subject"],
        },
        "top_categories_unique_grants": {
            "title": "Top Categories",
            "content": """
- A ranked list of frequent categories.
- Choose the top few that fit your goal and who you serve.
- Use these as tags in your plan and future searches.
- Next: Continue to Budget Reality Check.
""",
            "related_terms": ["category", "rank", "unique_count"],
        },
        "budget_reality_check": {
            "title": "Budget Reality Check",
            "content": """
- Pick a budget that fits your capacity and the data.
- See a typical range for similar work and area.
- Note costs you must include (like indirect or match).
- Save your choice—used in Planner and Advisor.
- Next: Continue to Project Planner.
""",
            "related_terms": ["indirect_costs", "match", "amount_usd"],
        },
        "project_planner": {
            "title": "Project Planner",
            "content": """
- Write a simple problem, solution, and who benefits.
- List 3–5 key activities with a timeline.
- Link your budget to what you will do.
- Save before you continue.
- Next: Continue to Advisor Report.
""",
            "related_terms": ["problem", "beneficiaries", "activities", "outcomes", "timeline"],
        },
        "advisor_report": {
            "title": "Advisor Report",
            "content": """
- Get suggested funders and focus areas based on your inputs.
- See next steps tailored to your goal and region.
- Download your workbook when ready or go back to refine.
- You can return here anytime.
""",
            "related_terms": ["recommendations", "funders", "next_steps"],
        },
    }


def render_page_help_panel(page_name: str, audience: HelpAudience = "new") -> None:
    """Render help panel specific to a page."""
    if not is_enabled("GS_ENABLE_PLAIN_HELPERS"):
        return

    page_help = get_page_help()
    help_info = page_help.get(page_name)
    if not help_info:
        return

    with st.expander("📋 Page Guide", expanded=audience == "new"):
        st.markdown(f"### {help_info['title']}")
        st.markdown(str(help_info["content"]))

        related_terms = cast(list[str], help_info.get("related_terms") or [])
        if related_terms:
            st.markdown("**Key terms on this page:**")
            render_contextual_help_buttons(related_terms, audience)


def add_help_sidebar_button() -> None:
    """Add a help/glossary access button to the sidebar."""
    if not is_enabled("GS_ENABLE_PLAIN_HELPERS"):
        return

    st.sidebar.markdown("---")
    if st.sidebar.button("❓ Help & Glossary"):
        render_glossary_search()
