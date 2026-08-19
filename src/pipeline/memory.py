from __future__ import annotations

from dataclasses import dataclass
import os
import tracemalloc
from typing import Any


ARTICLE_FIELDS = {
    "title",
    "source",
    "published_at",
    "date",
    "url",
    "summary",
    "description",
    "snippet",
    "category",
    "asset_class",
    "region",
    "tags",
    "tickers",
    "entities",
    "importance_score",
    "portfolio_relevance",
    "portfolio_adjusted_score",
    "portfolio_relevance_score",
    "source_quality_provider",
    "source_quality_score",
    "market_relevance_score",
    "novelty_score",
    "recency_score",
    "regional_balance_score",
    "matched_holdings",
    "matched_issuers",
    "matched_sectors",
    "matched_currencies",
}


@dataclass
class MemoryTracker:
    before_mb: float = 0.0
    after_mb: float = 0.0
    peak_mb: float = 0.0
    _started_here: bool = False

    def start(self) -> None:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_here = True
        current, peak = tracemalloc.get_traced_memory()
        self.before_mb = _bytes_to_mb(current)
        self.peak_mb = _bytes_to_mb(peak)

    def stop(self) -> dict[str, float]:
        current, peak = tracemalloc.get_traced_memory()
        self.after_mb = _bytes_to_mb(current)
        self.peak_mb = max(self.peak_mb, _bytes_to_mb(peak))
        metrics = {
            "memory_before_mb": round(self.before_mb, 3),
            "memory_after_mb": round(self.after_mb, 3),
            "peak_memory_mb": round(self.peak_mb, 3),
        }
        if self._started_here:
            tracemalloc.stop()
            self._started_here = False
        return metrics


def compact_articles(articles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    compacted = []
    removed_fields = 0
    for article in articles:
        row = {key: value for key, value in article.items() if key in ARTICLE_FIELDS}
        removed_fields += max(0, len(article) - len(row))
        compacted.append(row)
    return compacted, {"article_rows": len(compacted), "article_fields_removed": removed_fields}


def optimize_dataframe_memory(dataframe: Any) -> tuple[Any, dict[str, int]]:
    """Downcast numeric columns and categorize repeated strings without copying twice."""
    try:
        import pandas as pd
    except ImportError:
        return dataframe, {"before_bytes": 0, "after_bytes": 0, "saved_bytes": 0}
    if not isinstance(dataframe, pd.DataFrame):
        return dataframe, {"before_bytes": 0, "after_bytes": 0, "saved_bytes": 0}

    before = int(dataframe.memory_usage(deep=True).sum())
    optimized = dataframe.copy(deep=False)
    for column in optimized.columns:
        series = optimized[column]
        if pd.api.types.is_integer_dtype(series):
            optimized[column] = pd.to_numeric(series, downcast="integer")
        elif pd.api.types.is_float_dtype(series):
            optimized[column] = pd.to_numeric(series, downcast="float")
        elif pd.api.types.is_object_dtype(series):
            unique_ratio = series.nunique(dropna=False) / max(len(series), 1)
            if unique_ratio <= 0.5:
                optimized[column] = series.astype("category")
    after = int(optimized.memory_usage(deep=True).sum())
    return optimized, {
        "before_bytes": before,
        "after_bytes": after,
        "saved_bytes": max(0, before - after),
    }


def _bytes_to_mb(value: int) -> float:
    return value / (1024 * 1024)


def recommended_cpu_workers(configured: Any = "auto") -> int:
    if configured != "auto":
        return max(1, int(configured))
    return max(1, min(4, (os.cpu_count() or 2) - 1))
