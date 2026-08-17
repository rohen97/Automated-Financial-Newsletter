from src.main import build_newsletter, save_outputs


def test_dry_run_output_generation(tmp_path, monkeypatch):
    monkeypatch.setattr("src.main.project_path", lambda *parts: tmp_path.joinpath(*parts))
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    assert "html" in rendered
    assert (tmp_path / "output/latest/newsletter.json").exists()
    assert (tmp_path / "output/latest/source_audit.json").exists()
