from src.processing.validate import collect_source_urls, run_quality_checks, validate_required_sections


def test_required_section_validation():
    newsletter = {"sections": {"executive_snapshot": {"bullets": ["x"]}}}
    assert validate_required_sections(newsletter, ["executive_snapshot", "macro_news"]) == ["macro_news"]


def test_collect_source_urls():
    newsletter = {"sections": {"a": {"sources": [{"url": "https://example.com/source"}]}}}
    assert collect_source_urls(newsletter) == {"https://example.com/source"}


def test_quality_checks_block_bad_phrase():
    newsletter = {
        "sections": {"executive_snapshot": {"sources": [{"url": "https://example.com/1"}]}},
        "text": "as an AI",
    }
    warnings = run_quality_checks(newsletter, ["executive_snapshot"])
    assert any("Blocked phrases" in warning for warning in warnings)
