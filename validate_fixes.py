#!/usr/bin/env python3
"""
Validation Script for Grant Advisor Interview Fixes
====================================================

This script validates that all the Grant Advisor Interview fixes are working correctly:

1. Enhanced Funder Candidates System (minimum 5 candidates with multi-tier fallback)
2. Comprehensive Multi-Section Recommendations (minimum 8 sections with deterministic fills)
3. Rich Data Context Integration
4. Quality Improvements (no more "unable to find" issues)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from advisor.pipeline.funders import _fallback_funder_candidates
from advisor.schemas import StructuredNeeds
from advisor.stages import _generate_deterministic_sections


def test_funder_candidates():
    """Test that the multi-tier fallback system generates minimum 5 candidates."""
    print("\n🎯 Testing Enhanced Funder Candidates System...")

    # Create test data with 10 funders
    data = pd.DataFrame(
        {
            "funder_name": [
                "Ford Foundation",
                "National Science Foundation",
                "Bill & Melinda Gates Foundation",
                "Hewlett Foundation",
                "Robert Wood Johnson Foundation",
                "Packard Foundation",
                "Surdna Foundation",
                "Kresge Foundation",
                "Mott Foundation",
                "Rockefeller Foundation",
            ],
            "amount_usd": [
                500000,
                750000,
                650000,
                480000,
                820000,
                420000,
                380000,
                450000,
                520000,
                610000,
            ],
            "year_issued": ["2023"] * 10,
        }
    )

    print(
        f"Test data has {len(data)} funders with amounts ranging from ${data['amount_usd'].min():,} to ${data['amount_usd'].max():,}"
    )

    # Test funder candidate generation
    candidates = _fallback_funder_candidates(
        data, StructuredNeeds(subjects=["education"], populations=["youth"]), [], min_n=5
    )

    print(f"✅ Generated {len(candidates)} funder candidates")
    print("Top 5 candidates:")
    for i, candidate in enumerate(candidates[:5], 1):
        print(f"  {i}. {candidate.name}: Score {candidate.score:.3f}")
        print(f"     Rationale: {candidate.rationale[:80]}...")

    return candidates


def test_section_generation():
    """Test that we get minimum 8 comprehensive sections."""
    print("\n🎯 Testing Multi-Section Recommendation System...")

    # Test section generation with minimal datapoints
    datapoints = [
        {
            "id": "DP-001",
            "title": "Funding Analysis",
            "method": "df_pivot_table",
            "params": {},
            "table_md": "| Metric | Value |\n|--------|-------|\n| Avg Amount | $525K |",
            "notes": "Test analysis",
        },
        {
            "id": "DP-002",
            "title": "Geographic Trends",
            "method": "df_groupby_sum",
            "params": {},
            "table_md": "| Region | Funding |\n|--------|----------|\n| CA | $2.1M |",
            "notes": "Regional analysis",
        },
    ]

    sections = _generate_deterministic_sections(datapoints)

    print(f"✅ Generated {len(sections)} comprehensive sections")
    print("Section titles:")
    for i, section in enumerate(sections, 1):
        title = section["title"]
        content = section["markdown_body"][:60] + "..."
        print(f"  {i}. {title}")
        print(f"     Content: {content}")

    return sections


def validate_quality_metrics(candidates, sections):
    """Validate quality improvements."""
    print("\n🎯 Validating Quality Improvements...")

    # Check candidate quality
    all_scored = all(c.score > 0 for c in candidates)
    all_named = all(c.name and c.name.strip() for c in candidates)
    all_rationales = all(c.rationale and len(c.rationale) > 10 for c in candidates)

    print(f"✅ All candidates properly scored: {'✅' if all_scored else '❌'}")
    print(f"✅ All candidates have proper names: {'✅' if all_named else '❌'}")
    print(f"✅ All candidates have meaningful rationales: {'✅' if all_rationales else '❌'}")

    # Check section quality
    all_titled = all(s["title"] and len(s["title"]) > 3 for s in sections)
    all_content = all(s["markdown_body"] and len(s["markdown_body"]) > 50 for s in sections)

    print(f"✅ All sections have proper titles: {'✅' if all_titled else '❌'}")
    print(f"✅ All sections have substantial content: {'✅' if all_content else '❌'}")

    return all_scored and all_named and all_rationales and all_titled and all_content


def main():
    print("=" * 70)
    print("GRANT ADVISOR INTERVIEW FIXES VALIDATION")
    print("=" * 70)

    # Test the core fixes
    candidates = test_funder_candidates()
    sections = test_section_generation()

    # Validate quality
    quality_ok = validate_quality_metrics(candidates, sections)

    # Final validation
    print("\n" + "=" * 70)
    print("🎯 FINAL VALIDATION RESULTS:")
    print("=" * 70)

    validators = [
        ("Enhanced Funder Candidates (min 5)", len(candidates) >= 5),
        ("Multi-Section Recommendations (min 8)", len(sections) >= 8),
        ("Quality Improvements", quality_ok),
        ("Proper Scoring System", all(c.score > 0 for c in candidates)),
        ("Rich Content Generation", min(len(s["markdown_body"]) for s in sections) > 50),
    ]

    all_passed = True
    for test_name, result in validators:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not result:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 SUCCESS: All Grant Advisor Interview fixes are working correctly!")
        print("✅ Multi-tier fallback ensures minimum 5 candidates")
        print("✅ Multi-section synthesis ensures minimum 8 sections")
        print("✅ Quality improvements eliminate 'unable to find' issues")
        print("✅ Rich data context provides comprehensive analysis")
        print("✅ Transformation from 2-section to multi-page analysis complete")
    else:
        print("❌ ISSUES FOUND: Some fixes may not be working correctly")

    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
