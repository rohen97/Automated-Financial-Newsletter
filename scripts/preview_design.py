from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_newsletter
from src.llm.schemas import Newsletter
from src.render.assemble_newsletter import render_newsletter_html
from src.utils.io import write_text


def main() -> None:
    latest_json = Path("output/latest/newsletter.json")
    if latest_json.exists():
        newsletter = Newsletter.model_validate_json(latest_json.read_text(encoding="utf-8"))
    else:
        newsletter = build_newsletter()
    html = render_newsletter_html(newsletter)
    output_path = Path("output/design_preview/newsletter_preview.html")
    write_text(output_path, html)
    chart_source = Path("output/latest/chart_of_the_week.png")
    if chart_source.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chart_source, output_path.parent / "chart_of_the_week.png")
    print(f"Design preview saved to {output_path}")


if __name__ == "__main__":
    main()
