from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.charts.image_cache import HEADERS, cache_image_url
from src.charts.pdf_chart_extractor import render_pdf_chart_page


def fetch_external_chart(
    source_key: str,
    source_config: dict,
    output_filename: str = "chart_of_the_week.png",
    archive_day: str | None = None,
) -> dict:
    if source_key == "imf":
        return fetch_imf_chart(source_config, output_filename, archive_day)
    if source_key == "jpm":
        return fetch_jpm_chart(source_config, output_filename, archive_day)
    if source_key == "mckinsey":
        return fetch_mckinsey_chart(source_config, output_filename, archive_day)
    raise ValueError(f"Unsupported chart source: {source_key}")


def fetch_imf_chart(source_config: dict, output_filename: str, archive_day: str | None) -> dict:
    listing_url = source_config["url"]
    listing = _soup(listing_url)
    article_url = _first_link(listing, listing_url, ["/blogs/chart-of-the-week", "/blogs/"])
    article = _soup(article_url) if article_url else listing
    page_url = article_url or listing_url
    meta = _extract_article_meta(article, page_url)
    image_url = meta.get("image_url") or _first_image(article, page_url)
    if not image_url:
        raise ValueError("IMF chart image not found.")
    local_path = cache_image_url(image_url, output_filename, archive_day)
    return _chart_payload(
        source_name="IMF Chart of the Week",
        source_type="external_web",
        title=meta.get("title") or "IMF Chart of the Week",
        published_at=meta.get("published_at"),
        original_url=page_url,
        image_url=image_url,
        local_path=local_path,
        summary=meta.get("description") or "Latest IMF Chart of the Week selected from the configured source.",
        extraction_method="og_image" if meta.get("image_url") else "article_image",
        copyright_note="External chart cached for internal office preview. Review source rights before broad distribution.",
    )


def fetch_mckinsey_chart(source_config: dict, output_filename: str, archive_day: str | None) -> dict:
    page_url = source_config["url"]
    soup = _soup(page_url)
    meta = _extract_article_meta(soup, page_url)
    image_url = meta.get("image_url") or _first_image(soup, page_url)
    if not image_url:
        raise ValueError("McKinsey chart image not found in static HTML.")
    local_path = cache_image_url(image_url, output_filename, archive_day)
    return _chart_payload(
        source_name="McKinsey Week in Charts",
        source_type="external_web",
        title=meta.get("title") or "McKinsey Week in Charts",
        published_at=meta.get("published_at"),
        original_url=page_url,
        image_url=image_url,
        local_path=local_path,
        summary=meta.get("description") or "Latest McKinsey Week in Charts item selected from the configured source.",
        extraction_method="og_image" if meta.get("image_url") else "article_image",
        copyright_note="External chart cached for internal office preview. Review source rights before broad distribution.",
    )


def fetch_jpm_chart(source_config: dict, output_filename: str, archive_day: str | None) -> dict:
    page_url = source_config["url"]
    pdf_url = source_config.get("pdf_url")
    if not pdf_url:
        soup = _soup(page_url)
        pdf_url = _first_link(soup, page_url, [".pdf"])
    if not pdf_url:
        raise ValueError("JPM weekly recap PDF not found.")
    local_path = render_pdf_chart_page(pdf_url, output_filename, archive_day)
    return _chart_payload(
        source_name="J.P. Morgan Weekly Market Recap",
        source_type="external_pdf",
        title="J.P. Morgan Weekly Market Recap",
        published_at=None,
        original_url=page_url,
        image_url=pdf_url,
        local_path=local_path,
        summary="Selected page rendered from the configured J.P. Morgan weekly market recap PDF.",
        extraction_method="pdf_page_render",
        copyright_note="PDF page rendered for internal office preview. Review source rights before broad distribution.",
    )


def _soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.content, "lxml")


def _first_link(soup: BeautifulSoup, base_url: str, needles: list[str]) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        lowered = href.lower()
        if any(needle.lower() in lowered for needle in needles):
            return urljoin(base_url, href)
    return None


def _first_image(soup: BeautifulSoup, base_url: str) -> str | None:
    candidates = []
    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-src")
        if src:
            candidates.append(urljoin(base_url, src))
    return candidates[0] if candidates else None


def _extract_article_meta(soup: BeautifulSoup, base_url: str) -> dict:
    def content(selector: str) -> str | None:
        tag = soup.select_one(selector)
        if not tag:
            return None
        return tag.get("content") or tag.get_text(" ", strip=True)

    canonical = soup.select_one("link[rel='canonical']")
    return {
        "title": content("meta[property='og:title']") or content("title"),
        "description": content("meta[property='og:description']") or content("meta[name='description']"),
        "image_url": urljoin(base_url, content("meta[property='og:image']") or "") or None,
        "published_at": content("meta[property='article:published_time']") or content("time"),
        "canonical_url": urljoin(base_url, canonical.get("href")) if canonical and canonical.get("href") else base_url,
    }


def _chart_payload(
    *,
    source_name: str,
    source_type: str,
    title: str,
    published_at: str | None,
    original_url: str,
    image_url: str,
    local_path,
    summary: str,
    extraction_method: str,
    copyright_note: str,
) -> dict:
    return {
        "title": title,
        "source_name": source_name,
        "source_type": source_type,
        "published_at": published_at or date.today().isoformat(),
        "original_url": original_url,
        "image_url": image_url,
        "local_image_path": str(local_path),
        "image_src": "chart_of_the_week.png",
        "email_image_src": "cid:chart_of_the_week",
        "summary": summary,
        "portfolio_relevance": "Use as cross-asset context alongside portfolio exposure and macro watchlist items.",
        "extraction_method": extraction_method,
        "copyright_note": copyright_note,
        "compliance_approved": True,
        "embedded_image": True,
        "fallback_mode": False,
        "generated_at": date.today().isoformat(),
    }
