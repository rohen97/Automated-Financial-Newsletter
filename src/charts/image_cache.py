from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.utils.io import project_path


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def copy_chart_to_archive(source_path: Path, archive_day: str | None = None) -> Path:
    target_dir = project_path("output", "archive", archive_day or date.today().isoformat())
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source_path.name
    target.write_bytes(source_path.read_bytes())
    return target


def cache_image_url(image_url: str, output_filename: str = "chart_of_the_week.png", archive_day: str | None = None) -> Path:
    response = requests.get(image_url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    suffix = Path(urlparse(image_url).path).suffix.lower()
    if "image" not in content_type and suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"URL did not return an image content type: {content_type or 'unknown'}")
    latest_path = project_path("output", "latest", output_filename)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    _normalise_image(response.content, latest_path)
    copy_chart_to_archive(latest_path, archive_day)
    return latest_path


def save_png_bytes(content: bytes, output_filename: str = "chart_of_the_week.png", archive_day: str | None = None) -> Path:
    latest_path = project_path("output", "latest", output_filename)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    _normalise_image(content, latest_path)
    copy_chart_to_archive(latest_path, archive_day)
    return latest_path


def _normalise_image(content: bytes, target: Path) -> None:
    try:
        from PIL import Image
        from io import BytesIO

        image = Image.open(BytesIO(content))
        image.load()
        if image.width > 1200:
            ratio = 1200 / image.width
            image = image.resize((1200, max(1, int(image.height * ratio))))
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        image.save(target, format="PNG", optimize=True)
    except Exception:
        target.write_bytes(content)
