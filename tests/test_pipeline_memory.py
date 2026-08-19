import pytest

from src.pipeline.memory import compact_articles, optimize_dataframe_memory


def test_article_compaction_drops_raw_provider_payloads():
    articles, report = compact_articles(
        [
            {
                "title": "Rates reprice",
                "url": "https://example.test/rates",
                "region": "US",
                "raw_payload": {"large": "unused"},
            }
        ]
    )

    assert articles == [
        {
            "title": "Rates reprice",
            "url": "https://example.test/rates",
            "region": "US",
        }
    ]
    assert report["article_fields_removed"] == 1


def test_dataframe_optimization_reduces_repeated_string_memory():
    pd = pytest.importorskip("pandas")
    dataframe = pd.DataFrame(
        {
            "region": ["APAC", "US"] * 500,
            "source": ["FRED"] * 1000,
            "score": list(range(1000)),
        }
    )

    optimized, report = optimize_dataframe_memory(dataframe)

    assert str(optimized["region"].dtype) == "category"
    assert str(optimized["source"].dtype) == "category"
    assert report["saved_bytes"] > 0
    assert report["after_bytes"] < report["before_bytes"]
