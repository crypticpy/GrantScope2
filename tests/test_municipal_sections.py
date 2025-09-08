from advisor.stages import _generate_municipal_section


def test_generate_municipal_section_titles():
    # Smoke test ensures municipal section generator returns expected structure
    section = _generate_municipal_section("Your Funding Landscape", "funding_landscape", [])
    assert isinstance(section, dict)
    assert "title" in section and "markdown_body" in section
    assert "Funding Landscape" in section["title"] or "Funding" in section["title"]
