from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.schemas import Newsletter
from src.charts.chart_renderer import chart_metadata_matches, chart_metadata_path
from src.main import build_newsletter
from src.render.review_v2 import render_review_v2_html
from src.utils.io import write_text


def main() -> None:
    latest_json = ROOT / "output" / "latest" / "newsletter.json"
    if latest_json.exists():
        newsletter = Newsletter.model_validate_json(latest_json.read_text(encoding="utf-8"))
    else:
        newsletter = build_newsletter()

    chart_source = ROOT / "output" / "latest" / "chart_of_the_week.png"
    chart_section = newsletter.sections.get("chart_of_the_week")
    chart = chart_section.model_dump(mode="json") if hasattr(chart_section, "model_dump") else (chart_section or {})
    if chart.get("embedded_image"):
        if not chart_source.exists():
            raise RuntimeError("Chart image is missing. Run 'python -m src.main' before building V2.")
        metadata_path = chart_metadata_path(chart_source)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if not chart_metadata_matches(chart, metadata):
            raise RuntimeError(
                "Chart image metadata does not match newsletter.json. Run 'python -m src.main' before building V2."
            )

    output_path = ROOT / "output" / "review_v2" / "newsletter_v2.html"
    write_text(output_path, render_review_v2_html(newsletter))

    if chart.get("embedded_image"):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chart_source, output_path.parent / "chart_of_the_week.png")
        shutil.copy2(metadata_path, output_path.parent / metadata_path.name)

    print(f"V2 review saved to {output_path}")


if __name__ == "__main__":
    main()
