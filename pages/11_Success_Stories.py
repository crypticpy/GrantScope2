"""
Success Stories page for GrantScope.
Shows inspiring examples of successful grant projects to help users learn.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from utils.app_state import get_session_profile, init_session_state, is_newbie, sidebar_controls

st.set_page_config(page_title="Success Stories - GrantScope", page_icon="🌟")


# Built-in success stories data (can be extended with external file)
BUILT_IN_STORIES = [
    {
        "title": "After-School Arts Program Saves the Day",
        "org_type": "nonprofit",
        "funder_type": "foundation",
        "amount_range": "$5,000 - $25,000",
        "region": "Urban",
        "lesson_one_liner": "Small grants can make a big difference when you show clear community need.",
        "story": "Lincoln Community Center needed $15,000 to keep their after-school arts program running. They showed how 200 kids would lose their only safe place to go after school. The local foundation loved their simple budget and strong letters from parents.",
        "key_success_factors": [
            "Clear community need",
            "Simple, realistic budget",
            "Strong community support",
        ],
        "tags": ["youth", "arts", "community", "after-school"],
    },
    {
        "title": "Rural Library Goes Digital",
        "org_type": "school",
        "funder_type": "government",
        "amount_range": "$25,000 - $100,000",
        "region": "Rural",
        "lesson_one_liner": "Government grants love projects that serve underserved areas with measurable outcomes.",
        "story": "Smalltown Library won $45,000 from the state to add computers and high-speed internet. They showed exactly how many people would benefit and promised to track usage numbers. The detailed timeline and partnerships with local schools sealed the deal.",
        "key_success_factors": ["Measurable outcomes", "Detailed timeline", "Strong partnerships"],
        "tags": ["digital access", "rural", "education", "technology"],
    },
    {
        "title": "Food Bank Doubles Capacity",
        "org_type": "nonprofit",
        "funder_type": "corporate",
        "amount_range": "$100,000 - $500,000",
        "region": "Suburban",
        "lesson_one_liner": "Corporate funders want to see business-like planning and community impact.",
        "story": "Valley Food Bank received $180,000 from a major grocery chain to expand their warehouse. They presented a business plan showing how they'd serve 50% more families. The company loved the professional approach and clear community benefit.",
        "key_success_factors": [
            "Business-like planning",
            "Scalable impact",
            "Aligned funder values",
        ],
        "tags": ["food security", "capacity building", "corporate giving"],
    },
    {
        "title": "School Garden Grows Success",
        "org_type": "school",
        "funder_type": "foundation",
        "amount_range": "Under $5,000",
        "region": "Urban",
        "lesson_one_liner": "Even tiny grants can create big impact when you have passionate volunteers.",
        "story": "Roosevelt Elementary won $3,500 to start a school garden. The teachers wrote a simple, heartfelt proposal showing how kids would learn science and nutrition. Parent volunteers made the small budget stretch twice as far.",
        "key_success_factors": ["Passionate leadership", "Volunteer support", "Educational value"],
        "tags": ["education", "nutrition", "small grant", "volunteers"],
    },
    {
        "title": "Senior Center Beats Isolation",
        "org_type": "nonprofit",
        "funder_type": "foundation",
        "amount_range": "$25,000 - $100,000",
        "region": "Rural",
        "lesson_one_liner": "Addressing urgent social issues with personal stories wins hearts and grants.",
        "story": "Mountain View Senior Center got $60,000 to create programs for isolated seniors. They shared real stories of lonely elders and showed exactly how group activities would help. The foundation was moved by the personal touch.",
        "key_success_factors": ["Personal stories", "Urgent social need", "Clear solution"],
        "tags": ["seniors", "social isolation", "mental health", "community"],
    },
    {
        "title": "Tech Training Changes Lives",
        "org_type": "nonprofit",
        "funder_type": "corporate",
        "amount_range": "$100,000 - $500,000",
        "region": "Urban",
        "lesson_one_liner": "Job training programs get funded when you show real employment outcomes.",
        "story": "Future Skills Center received $250,000 from a tech company to train unemployed adults in coding. They promised that 80% of graduates would get jobs within 6 months. The company wanted to support their local workforce.",
        "key_success_factors": ["Job placement goals", "Corporate alignment", "Skills gap focus"],
        "tags": ["job training", "technology", "employment", "workforce development"],
    },
]


@st.cache_data(ttl=300)
def load_success_stories() -> list[dict]:
    """Load success stories with caching."""
    stories = BUILT_IN_STORIES.copy()

    # Try to load external stories if available
    try:
        stories_path = Path("data/success_stories.json")
        if stories_path.exists():
            with open(stories_path, encoding="utf-8") as f:
                external_stories = json.load(f)
                if isinstance(external_stories, list):
                    stories.extend(external_stories)
    except Exception:
        pass  # Continue with built-in stories

    return stories


def filter_stories(
    stories: list[dict], org_type_filter: str | None = None, region_filter: str | None = None
) -> list[dict]:
    """Filter stories based on criteria."""
    filtered = stories

    if org_type_filter and org_type_filter != "All":
        filtered = [s for s in filtered if s.get("org_type", "").lower() == org_type_filter.lower()]

    if region_filter and region_filter != "All":
        filtered = [s for s in filtered if s.get("region", "").lower() == region_filter.lower()]

    return filtered


def render_story_card(story: dict, show_details: bool = False) -> None:
    """Render a single success story as a card."""
    with st.container():
        # Story header
        st.markdown(f"### 🌟 {story['title']}")

        # Metadata badges (using markdown for compatibility)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if hasattr(st, "badge"):
                st.badge(story.get("org_type", "").title(), type="secondary")
            else:
                st.markdown(f"`{story.get('org_type', '').title()}`")
        with col2:
            if hasattr(st, "badge"):
                st.badge(story.get("funder_type", "").title(), type="outline")
            else:
                st.markdown(f"`{story.get('funder_type', '').title()}`")
        with col3:
            if hasattr(st, "badge"):
                st.badge(story.get("amount_range", ""))
            else:
                st.markdown(f"`{story.get('amount_range', '')}`")
        with col4:
            if hasattr(st, "badge"):
                st.badge(story.get("region", ""))
            else:
                st.markdown(f"`{story.get('region', '')}`")

        # Key lesson
        st.info(f"💡 **Key Lesson**: {story.get('lesson_one_liner', 'No lesson provided')}")

        # Story content
        if show_details or st.button("Read Full Story", key=f"story_{hash(story['title'])}"):
            st.markdown(f"**The Story**: {story.get('story', 'No story provided')}")

            if story.get("key_success_factors"):
                st.markdown("**What Made It Work:**")
                for factor in story["key_success_factors"]:
                    st.markdown(f"• {factor}")

            if story.get("tags"):
                st.markdown("**Tags**: " + ", ".join(f"`{tag}`" for tag in story["tags"]))

        st.markdown("---")


def render_newbie_tips() -> None:
    """Render tips for newbies on how to learn from success stories."""
    with st.expander("📚 How to Learn from These Stories", expanded=True):
        st.markdown(
            """
        **These stories can help you win your own grant!**
        
        **What to look for:**
        1. **Similar organizations** - Find stories from groups like yours
        2. **Budget ranges** - See what amounts are realistic for your project size
        3. **Success factors** - Notice what made their applications strong
        4. **Funder types** - Learn which funders support your kind of work
        
        **How to use this:**
        - Copy their approach, not their exact words
        - Look for patterns in what wins grants
        - Use their budget ranges to set realistic goals
        - Contact similar organizations for advice
        """
        )


def main():
    """Main Success Stories page function."""
    init_session_state()

    # Guided pages are always available; no feature flag gate

    # Get user profile for customization
    profile = get_session_profile()
    is_newbie_user = is_newbie(profile)

    st.title("🌟 Success Stories")
    st.markdown("**Learn from organizations that have won grants successfully.**")

    # Show newbie tips
    if is_newbie_user:
        render_newbie_tips()

    # Sidebar controls
    sidebar_controls()

    # Load stories
    stories = load_success_stories()

    # Filters
    st.subheader("Find Stories Like Yours")

    col1, col2, col3 = st.columns(3)

    with col1:
        org_types = ["All"] + sorted(
            list(set(s.get("org_type", "").title() for s in stories if s.get("org_type")))
        )
        org_filter = st.selectbox("Organization Type", options=org_types)

    with col2:
        regions = ["All"] + sorted(
            list(set(s.get("region", "") for s in stories if s.get("region")))
        )
        region_filter = st.selectbox("Region", options=regions)

    with col3:
        amount_ranges = ["All"] + sorted(
            list(set(s.get("amount_range", "") for s in stories if s.get("amount_range")))
        )
        amount_filter = st.selectbox("Grant Amount", options=amount_ranges)

    # Filter stories
    filtered_stories = stories
    if org_filter != "All":
        filtered_stories = [
            s for s in filtered_stories if s.get("org_type", "").title() == org_filter
        ]
    if region_filter != "All":
        filtered_stories = [s for s in filtered_stories if s.get("region", "") == region_filter]
    if amount_filter != "All":
        filtered_stories = [
            s for s in filtered_stories if s.get("amount_range", "") == amount_filter
        ]

    # Show results
    st.markdown(
        f"**Found {len(filtered_stories)} stories** {f'(filtered from {len(stories)} total)' if len(filtered_stories) < len(stories) else ''}"
    )

    if not filtered_stories:
        st.info("No stories match your filters. Try selecting 'All' for some categories.")
        return

    # Display mode toggle
    show_all_details = st.checkbox("Show full details for all stories", value=False)

    # Display stories
    for story in filtered_stories:
        render_story_card(story, show_details=show_all_details)

    # Additional resources
    st.markdown("---")
    st.subheader("Want to Add Your Success Story?")

    if is_newbie_user:
        st.info(
            """
        **Won a grant recently?** We'd love to feature your story!
        
        Your story could help other newcomers learn what works. 
        Email us with your experience and lessons learned.
        """
        )
    else:
        st.info(
            """
        **Share Your Success**: Help build our community knowledge by submitting your grant success stories.
        Include the organization type, grant amount, key success factors, and lessons learned.
        """
        )

    # Quick analysis for insights
    if len(stories) > 3:
        st.subheader("Quick Insights")

        # Most common success factors
        all_factors = []
        for story in stories:
            if story.get("key_success_factors"):
                all_factors.extend(story["key_success_factors"])

        if all_factors:
            from collections import Counter

            top_factors = Counter(all_factors).most_common(5)

            st.markdown("**Most Common Success Factors:**")
            for factor, count in top_factors:
                st.markdown(f"• **{factor}** (appears in {count} stories)")

        # Organization type breakdown
        org_type_counts = {}
        for story in stories:
            org_type = story.get("org_type", "unknown").title()
            org_type_counts[org_type] = org_type_counts.get(org_type, 0) + 1

        if org_type_counts:
            st.markdown("**Stories by Organization Type:**")
            for org_type, count in sorted(org_type_counts.items()):
                st.markdown(f"• {org_type}: {count} stories")


if __name__ == "__main__":
    main()
