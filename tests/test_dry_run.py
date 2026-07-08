from pathlib import Path

from src.main import build_newsletter, save_outputs


def test_dry_run_output_generation():
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    assert "html" in rendered
    assert Path("output/latest/newsletter.json").exists()
    assert Path("output/latest/source_audit.json").exists()
