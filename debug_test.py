#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.getcwd())

from advisor.pipeline.funders import _fallback_funder_candidates
from advisor.schemas import StructuredNeeds

try:
    from GrantScope.loaders.data_loader import load_data, preprocess_data  # type: ignore
except Exception:  # pragma: no cover
    from loaders.data_loader import load_data, preprocess_data  # type: ignore

def test_recommendations_realistic_rankings():
    """Test that funder candidates have realistic rankings and rationales."""
    grants = load_data(file_path="data/sample.json")
    sample_data, _grouped_df = preprocess_data(grants)
    
    # Test that we can generate candidates with proper ranking logic
    candidates = _fallback_funder_candidates(
        sample_data,
        StructuredNeeds(subjects=["arts", "education"], populations=["youth"], geographies=["ny"]),
        [],
        min_n=5
    )
    
    print(f"Generated {len(candidates)} candidates")
    
    # Should have proper scoring hierarchy
    if len(candidates) > 1:
        scores = [c.score for c in candidates]
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1)), f"Scores not properly ordered: {scores}"
    
    # All candidates should have meaningful rationales
    failed_candidates = []
    for i, candidate in enumerate(candidates):
        print(f"\nCandidate {i+1}: {candidate.name}")
        print(f"  Score: {candidate.score}")
        print(f"  Rationale: '{candidate.rationale}'")
        
        # Check rationale length
        if not (candidate.rationale and len(candidate.rationale) > 20):
            failed_candidates.append(f"  {candidate.name}: Rationale too short ({len(candidate.rationale) if candidate.rationale else 0} chars)")
            continue
        
        # Check for funder/foundation keyword
        has_funder = "funder" in candidate.rationale.lower() or "foundation" in candidate.rationale.lower()
        if not has_funder:
            failed_candidates.append(f"  {candidate.name}: Missing funder/foundation keyword")
            
        # Should reference data sources
        keywords = ["data", "analysis", "funding", "grants", "amount", "count"]
        has_data = any(word in candidate.rationale.lower() for word in keywords)
        found_keywords = [word for word in keywords if word in candidate.rationale.lower()]
        
        if not has_data:
            failed_candidates.append(f"  {candidate.name}: Missing data keywords. Rationale: '{candidate.rationale}'")
        
        print(f"  Has funder keyword: {has_funder}")
        print(f"  Has data keywords: {has_data} {found_keywords}")
    
    if failed_candidates:
        print(f"\n❌ FAILED CANDIDATES ({len(failed_candidates)}):")
        for failure in failed_candidates:
            print(failure)
        return False
    else:
        print("\n✅ ALL CANDIDATES PASS")
        return True

if __name__ == "__main__":
    success = test_recommendations_realistic_rankings()
    sys.exit(0 if success else 1)
