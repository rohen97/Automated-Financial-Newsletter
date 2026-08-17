from __future__ import annotations

import math
import os
from datetime import date, datetime, timezone
from pathlib import Path

from src.charts.image_cache import copy_chart_to_archive
from src.utils.io import project_path, write_json


def render_fred_chart(
    selected: dict,
    output_filename: str = "chart_of_the_week.png",
    output_directory: Path | None = None,
    archive: bool | None = None,
) -> Path:
    candidate = selected["candidate"]
    rows_by_series = selected["rows_by_series"]
    _validate_chart_contract(candidate, rows_by_series)

    is_test_run = bool(os.getenv("PYTEST_CURRENT_TEST"))
    target_dir = output_directory or project_path("output", "test" if is_test_run else "latest")
    latest_path = target_dir / output_filename
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    render_mode = "matplotlib"

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9.8, 5.2), dpi=170)
        fig.patch.set_facecolor("#ffffff")
        colors = ["#0B1F3A", "#D7B56D", "#52627A"]
        for idx, series_id in enumerate(candidate.get("series", [])):
            rows = rows_by_series.get(series_id, [])
            if not rows:
                continue
            label = _series_label(series_id, candidate)
            ax.plot([row["date"] for row in rows], [row["value"] for row in rows], color=colors[idx % len(colors)], linewidth=2.2, label=label)
            latest = rows[-1]
            ax.annotate(
                f"{latest['value']:.2f}",
                xy=(latest["date"], latest["value"]),
                xytext=(8, 0),
                textcoords="offset points",
                fontsize=8,
                color=colors[idx % len(colors)],
            )
        ax.set_title(candidate.get("title", "Chart of the Week"), loc="left", fontsize=13, color="#071A33", pad=12)
        ax.set_xlabel("")
        if candidate.get("unit_label"):
            ax.set_ylabel(candidate["unit_label"], fontsize=8, color="#52627A")
        ax.grid(True, axis="y", color="#E2E7EF", linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines["left"].set_color("#DCE2EA")
        ax.spines["bottom"].set_color("#DCE2EA")
        ax.tick_params(axis="both", labelsize=8, colors="#52627A")
        ax.legend(frameon=False, loc="best", fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(latest_path, format="png", bbox_inches="tight")
        plt.close(fig)
    except Exception:
        render_mode = "plain_fallback"
        _render_plain_png(candidate, latest_path)

    metadata_path = chart_metadata_path(latest_path)
    write_json(metadata_path, _chart_metadata(candidate, rows_by_series, render_mode))
    should_archive = not is_test_run if archive is None else archive
    if should_archive:
        copy_chart_to_archive(latest_path, date.today().isoformat())
        copy_chart_to_archive(metadata_path, date.today().isoformat())
    return latest_path


def chart_metadata_path(chart_path: Path) -> Path:
    return chart_path.with_suffix(".meta.json")


def chart_metadata_matches(chart: dict, metadata: dict) -> bool:
    return bool(metadata) and (
        metadata.get("chart_id") == chart.get("chart_id")
        and metadata.get("title") == chart.get("title")
        and metadata.get("series") == chart.get("series_used", [])
        and metadata.get("transformation") == (chart.get("transformation_used") or {})
        and metadata.get("render_mode") == "matplotlib"
    )


def _series_label(series_id: str, candidate: dict) -> str:
    if series_id == "CPIAUCSL" and candidate.get("transformation", {}).get(series_id) == "yoy_pct_change":
        return "CPI YoY %"
    labels = {
        "DGS10": "US 10Y yield",
        "T10Y2Y": "10Y-2Y Treasury spread",
        "BAMLH0A0HYM2": "High-yield spread",
        "STLFSI4": "St. Louis Financial Stress Index",
        "UNRATE": "Unemployment rate",
        "DFII10": "10Y real yield",
        "FEDFUNDS": "Fed Funds",
    }
    return labels.get(series_id, series_id)


def _validate_chart_contract(candidate: dict, rows_by_series: dict[str, list[dict]]) -> None:
    series = candidate.get("series", [])
    if not series:
        raise ValueError("Chart candidate has no configured FRED series.")
    for series_id in series:
        rows = rows_by_series.get(series_id, [])
        if not rows:
            raise ValueError(f"Chart candidate {candidate.get('id')} has no observations for {series_id}.")
        if not all(math.isfinite(float(row["value"])) for row in rows):
            raise ValueError(f"Chart candidate {candidate.get('id')} contains non-finite values for {series_id}.")


def _chart_metadata(candidate: dict, rows_by_series: dict[str, list[dict]], render_mode: str) -> dict:
    latest_values = {
        series_id: rows[-1]["value"]
        for series_id in candidate.get("series", [])
        if (rows := rows_by_series.get(series_id, []))
    }
    return {
        "contract_version": 1,
        "chart_id": candidate.get("id"),
        "title": candidate.get("title"),
        "series": candidate.get("series", []),
        "transformation": candidate.get("transformation", {}) or {},
        "latest_values": latest_values,
        "render_mode": render_mode,
        "rendered_at": datetime.now(timezone.utc).isoformat(),
    }


def _render_plain_png(candidate: dict, latest_path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 650), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 94), fill="#071A33")
    draw.text((40, 28), candidate.get("title", "Chart of the Week"), fill="#FFFFFF")
    draw.text((40, 140), "Chart rendering fallback. See newsletter JSON for selected FRED series.", fill="#52627A")
    image.save(latest_path, format="PNG")
