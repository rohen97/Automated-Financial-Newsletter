from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_newsletter  # noqa: E402
from src.io.serialization import write_bytes_atomic  # noqa: E402
from src.llm.schemas import Newsletter  # noqa: E402
from src.render.assemble_newsletter import render_newsletter_html  # noqa: E402
from src.utils.io import write_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a newsletter design preview.")
    parser.add_argument("--input", type=Path, help="Optional validated newsletter JSON input.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/design_preview/newsletter_preview.html"),
    )
    parser.add_argument(
        "--chart",
        type=Path,
        default=Path("output/latest/chart_of_the_week.png"),
    )
    args = parser.parse_args()
    latest_json = Path("output/latest/newsletter.json")
    if args.input:
        newsletter = Newsletter.model_validate_json(args.input.read_text(encoding="utf-8"))
    elif latest_json.exists():
        newsletter = Newsletter.model_validate_json(latest_json.read_text(encoding="utf-8"))
    else:
        newsletter = build_newsletter()
    html = render_newsletter_html(newsletter)
    output_path = args.output
    write_text(output_path, html)
    chart_source = args.chart
    if chart_source.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(
            output_path.parent / "chart_of_the_week.png",
            chart_source.read_bytes(),
        )
    print(f"Design preview saved to {output_path}")


if __name__ == "__main__":
    main()
