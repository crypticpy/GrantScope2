"""
Tests for help/glossary functionality.
"""

import pytest

from utils.help import get_term, search_terms, BUILT_IN_GLOSSARY


def test_get_term_exists():
    """Test getting an existing term."""
    term = get_term("funder")
    assert term is not None
    assert term["term"] == "funder"
    assert "organization that gives money" in term["simple_definition"]


def test_get_term_case_insensitive():
    """Test that get_term is case insensitive."""
    term1 = get_term("FUNDER")
    term2 = get_term("funder")
    term3 = get_term("Funder")
    
    assert term1 == term2 == term3


def test_get_term_nonexistent():
    """Test getting a nonexistent term."""
    term = get_term("nonexistent_term")
    assert term is None


def test_search_terms_basic():
    """Test basic term searching."""
    results = search_terms("grant")
    assert len(results) > 0
    
    # Should find terms containing "grant"
    term_names = [r["term"] for r in results]
    assert any("grant" in name.lower() for name in term_names)


def test_search_terms_empty():
    """Test search with empty query."""
    results = search_terms("")
    assert results == []


def test_search_terms_definition():
    """Test that search looks in definitions too."""
    results = search_terms("money")
    assert len(results) > 0
    
    # Should find terms that mention money in definition
    for result in results:
        definition = result["simple_definition"].lower()
        assert "money" in definition or "grant" in result["term"].lower()


def test_built_in_glossary_structure():
    """Test that built-in glossary has proper structure."""
    for key, entry in BUILT_IN_GLOSSARY.items():
        assert "term" in entry
        assert "simple_definition" in entry  
        assert "also_known_as" in entry
        assert "related_terms" in entry
        
        # Check types
        assert isinstance(entry["term"], str)
        assert isinstance(entry["simple_definition"], str)
        assert isinstance(entry["also_known_as"], list)
        assert isinstance(entry["related_terms"], list)


def test_search_results_deduplicated():
    """Test that search results don't contain duplicates."""
    results = search_terms("grant")
    
    terms_seen = set()
    for result in results:
        term = result["term"]
        assert term not in terms_seen, f"Duplicate term found: {term}"
        terms_seen.add(term)


def test_search_also_known_as():
    """Test that search finds terms by also_known_as aliases."""
    # Look for "grantor" which should find "funder"
    results = search_terms("grantor")
    assert len(results) > 0
    
    # Should find funder
    term_names = [r["term"] for r in results]
    assert "funder" in term_names
