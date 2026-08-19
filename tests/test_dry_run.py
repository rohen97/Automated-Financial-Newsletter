import json

from src.main import build_newsletter, save_outputs


def test_dry_run_output_generation(tmp_path, monkeypatch):
    monkeypatch.setattr("src.main.project_path", lambda *parts: tmp_path.joinpath(*parts))
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    assert "html" in rendered
    assert (tmp_path / "output/latest/newsletter.json").exists()
    assert (tmp_path / "output/latest/source_audit.json").exists()
    assert (tmp_path / "output/latest/manifest.json").exists()
    assert (tmp_path / "output/latest/chart_of_the_week.meta.json").exists()

    newsletter_payload = json.loads(
        (tmp_path / "output/latest/newsletter.json").read_text(encoding="utf-8")
    )
    audit = json.loads(
        (tmp_path / "output/latest/audit_log.json").read_text(encoding="utf-8")
    )
    assert "chart_of_the_week" in newsletter_payload["sections"]
    assert "fixed_income_monitor" not in newsletter_payload["sections"]
    assert "raw_payload" not in json.dumps(newsletter_payload)
    assert audit["stage_timings"]
    assert "cache_hits" in audit
    assert "provider_status" in audit
