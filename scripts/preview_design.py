from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_newsletter
from src.render.assemble_newsletter import render_newsletter_html
from src.utils.io import write_text


def main() -> None:
    newsletter = build_newsletter()
    html = render_newsletter_html(newsletter)
    output_path = Path("output/design_preview/newsletter_preview.html")
    write_text(output_path, html)
    print(f"Design preview saved to {output_path}")


if __name__ == "__main__":
    main()
