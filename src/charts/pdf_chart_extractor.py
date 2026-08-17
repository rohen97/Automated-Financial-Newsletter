from __future__ import annotations

from pathlib import Path

import requests

from src.charts.image_cache import copy_chart_to_archive
from src.utils.io import project_path


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def render_pdf_chart_page(pdf_url: str, output_filename: str = "chart_of_the_week.png", archive_day: str | None = None) -> Path:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - depends on optional package availability
        raise RuntimeError("PyMuPDF is required for PDF chart extraction.") from exc

    response = requests.get(pdf_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    pdf_bytes = response.content
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(document) == 0:
        raise ValueError("Downloaded PDF has no pages.")

    best_page_index = 0
    best_score = -1
    for page_index in range(min(len(document), 8)):
        page = document[page_index]
        score = len(page.get_images(full=True)) * 3 + len(page.get_drawings())
        if score > best_score:
            best_score = score
            best_page_index = page_index

    page = document[best_page_index]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
    latest_path = project_path("output", "latest", output_filename)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(latest_path))
    copy_chart_to_archive(latest_path, archive_day)
    return latest_path
