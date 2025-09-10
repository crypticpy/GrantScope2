"""
Budget Reality Check page for GrantScope.
Helps users compare their budget to common grant amounts and find risks.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from utils.app_state import get_session_profile, init_session_state, is_newbie, sidebar_controls
from utils.help import render_page_help_panel

st.set_page_config(page_title="Budget Reality Check - GrantScope", page_icon="💰")


@dataclass
class BudgetLine:
    category: str
    amount: float


def analyze_budget(
    budget_lines: list[BudgetLine], indirect_rate: float, match_available: bool
) -> dict:
    """Analyze the budget and return flags and guidance."""
    total = sum(line.amount for line in budget_lines)

    # Calculate indirect costs
    indirect_costs = total * (indirect_rate / 100)
    grand_total = total + indirect_costs

    # Identify risk flags
    flags = []
    guidance = []

    # Check for missing common categories
    categories = {line.category.lower() for line in budget_lines}
    common_missing = []
    if "staff" not in categories and "personnel" not in categories:
        common_missing.append("Staff/Personnel")
    if "supplies" not in categories and "materials" not in categories:
        common_missing.append("Supplies/Materials")
    if "evaluation" not in categories:
        common_missing.append("Evaluation")
    if "admin" not in categories and "administration" not in categories and indirect_rate == 0:
        common_missing.append("Administrative/Indirect")

    if common_missing:
        flags.append(f"Missing common budget categories: {', '.join(common_missing)}")
        guidance.append("Add these to make your budget complete and realistic.")

    # Check for risky assumptions
    if not match_available and any("match" in line.category.lower() for line in budget_lines):
        flags.append("Match funding listed but you indicated none is available")
        guidance.append("Remove match items or identify a match source.")

    # Check for rounding issues
    if any(line.amount % 1 != 0 for line in budget_lines):
        guidance.append("Use round numbers when possible. It makes your budget easier to read.")

    # Check for category balance
    if total > 0:
        staff_amount = sum(
            line.amount for line in budget_lines if line.category.lower() in {"staff", "personnel"}
        )
        if staff_amount / total > 0.8:
            flags.append("Staff costs are more than 80% of budget")
            guidance.append("Add other costs like supplies or reduce staff hours.")

    return {
        "total_direct": total,
        "indirect_costs": indirect_costs,
        "grand_total": grand_total,
        "flags": flags,
        "guidance": guidance,
    }


def main():
    """Main Budget Reality Check page function."""
    init_session_state()

    # Guided pages are always available; no feature flag gate

    # Get user profile for customization
    profile = get_session_profile()
    is_newbie_user = is_newbie(profile)

    st.title("💰 Budget Reality Check")
    st.markdown("**See if your budget matches common grant sizes and fix common issues.**")

    # Newbie help panel (always enabled; show only to newbie users)
    if is_newbie_user:
        render_page_help_panel("budget_reality_check", audience="new")

    # Sidebar controls
    sidebar_controls()

    # Simple form for budget inputs
    with st.form("budget_form"):
        st.subheader("Your Budget")

        # Budget line items using a simple dynamic input
        num_lines = st.number_input(
            "How many budget lines?", min_value=1, max_value=20, value=4, step=1
        )

        categories = []
        amounts = []

        default_categories = ["Staff", "Supplies", "Travel", "Evaluation"]

        for i in range(num_lines):
            col1, col2 = st.columns([2, 1])
            with col1:
                category = st.text_input(
                    f"Category {i+1}",
                    value=default_categories[i] if i < len(default_categories) else "",
                    key=f"cat_{i}",
                )
            with col2:
                amount = st.number_input(
                    f"Amount {i+1}",
                    min_value=0.0,
                    value=1000.0 if i < len(default_categories) else 0.0,
                    step=100.0,
                    key=f"amt_{i}",
                )
            categories.append(category)
            amounts.append(amount)

        col1, col2, col3 = st.columns(3)

        with col1:
            indirect_rate = st.number_input(
                "Indirect rate (%)", min_value=0.0, max_value=60.0, value=10.0, step=1.0
            )
        with col2:
            match_available = (
                st.selectbox("Do you have match funding?", options=["No", "Yes"]) == "Yes"
            )
        with col3:
            typical_amount = st.selectbox(
                "Typical grant amount for your project",
                options=[
                    "Under $5,000",
                    "$5,000 - $25,000",
                    "$25,000 - $100,000",
                    "$100,000 - $500,000",
                    "Over $500,000",
                ],
                index=2,
            )

        submitted = st.form_submit_button("🔎 Check My Budget", type="primary")

        if submitted:
            # Create budget lines
            lines = []
            for cat, amt in zip(categories, amounts, strict=False):
                if cat.strip() and amt > 0:
                    lines.append(BudgetLine(category=cat.strip(), amount=float(amt)))

            if not lines:
                st.error("Please add at least one budget line with an amount greater than 0.")
                return

            # Analyze budget
            results = analyze_budget(lines, indirect_rate, match_available)

            # Persist standardized budget_* keys in session_state
            try:
                st.session_state["budget_indirect_rate_pct"] = float(indirect_rate)
                st.session_state["budget_match_available"] = bool(match_available)
                st.session_state["budget_total_direct"] = float(results.get("total_direct", 0.0))
                st.session_state["budget_indirect_costs"] = float(
                    results.get("indirect_costs", 0.0)
                )
                st.session_state["budget_grand_total"] = float(results.get("grand_total", 0.0))
                st.session_state["budget_flags"] = (
                    list(results.get("flags", [])) if isinstance(results.get("flags"), list) else []
                )
            except Exception:
                # Session persistence is best-effort; ignore failures in constrained contexts
                pass

            # Display results
            st.subheader("Results")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Direct Costs", f"${results['total_direct']:,.2f}")
            with col2:
                st.metric("Indirect Costs", f"${results['indirect_costs']:,.2f}")
            with col3:
                st.metric("Total Budget", f"${results['grand_total']:,.2f}")

            # Compare to typical grant sizes
            st.subheader("How your budget compares")

            ranges = {
                "Under $5,000": (0, 5000),
                "$5,000 - $25,000": (5000, 25000),
                "$25,000 - $100,000": (25000, 100000),
                "$100,000 - $500,000": (100000, 500000),
                "Over $500,000": (500000, float("inf")),
            }

            total = results["grand_total"]
            low, high = ranges[typical_amount]

            if total < low:
                st.warning(
                    """
                **Your budget is below the typical range.**
                
                This might be fine, but consider if you're missing important costs like staff time, supplies, or evaluation.
                """
                )
            elif total > high and typical_amount != "Over $500,000":
                st.warning(
                    """
                **Your budget is above the typical range.**
                
                Consider lowering costs or looking for larger grants. You might also split the project into phases.
                """
                )
            else:
                st.success("**Your budget is within a common range for this project type.**")

            # Flags and guidance
            if results["flags"]:
                st.subheader("Potential Issues to Fix")
                for flag in results["flags"]:
                    st.markdown(f"- {flag}")

            if results["guidance"]:
                st.subheader("Tips to Improve Your Budget")
                for tip in results["guidance"]:
                    st.markdown(f"- {tip}")

            # Next steps
            st.subheader("Next Steps")
            st.markdown(
                """
            - Compare your budget to sample funded projects in your area
            - Check the funder's guidelines for any caps or special rules  
            - Get a finance person to review the numbers
            - Adjust your project scope if needed
            """
            )


if __name__ == "__main__":
    main()
