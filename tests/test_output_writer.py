import hashlib
import json

from src.pipeline.output_writer import OutputWriter, text_artifact


def test_output_writer_publishes_latest_archive_and_manifest(tmp_path):
    latest = tmp_path / "latest"
    archive = tmp_path / "archive" / "2026-08-19"
    content = "<html><body>Wolf Research</body></html>"

    manifest = OutputWriter(latest, archive).write(
        [text_artifact("newsletter.html", content, "text/html")],
        provider_status={"fred": {"status": "ok"}},
        validation_status="ok",
        send_blocked=True,
        run_duration_seconds=1.25,
        generated_at="2026-08-19T09:00:00+08:00",
    )

    assert (latest / "newsletter.html").read_text(encoding="utf-8") == content
    assert (archive / "newsletter.html").read_text(encoding="utf-8") == content
    stored = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert expected in stored["checksums"].values()
    assert manifest.validation_status == "ok"
    assert not list(tmp_path.rglob("*.tmp"))
