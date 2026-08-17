from datetime import date, timedelta

from src.fetchers import fx
from src.fetchers.market_data import market_row
from src.fetchers.provider_audit import source_counts


def test_yahoo_market_row_includes_week_month_and_ytd(monkeypatch):
    today = date.today()
    history = [
        {"date": (today - timedelta(days=days)).isoformat(), "close": 100.0 + index}
        for index, days in enumerate(range(360, -1, -30))
    ]
    monkeypatch.setattr("src.fetchers.market_data.fetch_yahoo_history", lambda *args, **kwargs: history)
    monkeypatch.setattr("src.fetchers.market_data.record_provider", lambda provider: None)

    row = market_row("Test", "TEST", "", "https://finance.yahoo.com/quote/TEST")

    assert row["source"]["name"] == "Yahoo Finance"
    assert {"one_week_change", "one_month_change", "ytd_change", "latest_date"} <= row.keys()


def test_fx_uses_yahoo_before_sample_fallback(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(fx, "alpha_market_row", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("limit")))
    monkeypatch.setattr(
        fx,
        "market_row",
        lambda *args, **kwargs: {
            "label": "AUD/USD",
            "last": 0.7,
            "one_week_change": 1.0,
            "one_month_change": 2.0,
            "ytd_change": 3.0,
            "source": {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/quote/AUDUSD=X"},
        },
    )
    fallback_calls = []
    monkeypatch.setattr(fx, "record_fallback", lambda: fallback_calls.append(True))

    rows = fx.fetch_fx_data({"fx": [{"label": "AUD/USD", "symbol": "AUDUSD=X"}]})

    assert rows[0]["source"]["name"] == "Yahoo Finance"
    assert fallback_calls == []


def test_source_counts_does_not_double_count_nested_sources():
    counts = source_counts(
        {
            "rows": [
                {"source": {"name": "Sample Data", "url": "https://example.com/wolf-research/sample"}},
                {"source": {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/quote/TEST"}},
            ]
        }
    )

    assert counts == {"fallback_source_count": 1, "real_source_url_count": 1}
