from datetime import date, timedelta

from src.fetchers import commodities, fx
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


def test_dxy_uses_the_index_symbol_instead_of_the_uup_etf(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    alpha_calls = []
    monkeypatch.setattr(fx, "alpha_market_row", lambda *args, **kwargs: alpha_calls.append(args))
    monkeypatch.setattr(
        fx,
        "market_row",
        lambda label, symbol, *_args, **_kwargs: {
            "label": label,
            "last": 99.6,
            "one_week_change": -0.2,
            "one_month_change": -1.0,
            "ytd_change": 1.3,
            "source": {"name": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{symbol}"},
        },
    )

    rows = fx.fetch_fx_data({"fx": [{"label": "DXY", "symbol": "DX-Y.NYB"}]})

    assert alpha_calls == []
    assert rows[0]["last"] == 99.6
    assert rows[0]["source"]["url"].endswith("DX-Y.NYB")


def test_commodity_levels_use_configured_futures_not_etf_proxies(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    symbols = []

    def fake_market_row(label, symbol, *_args, **_kwargs):
        symbols.append(symbol)
        return {
            "label": label,
            "last": 91.5,
            "one_week_change": 2.0,
            "one_month_change": 3.0,
            "ytd_change": 4.0,
            "source": {"name": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{symbol}"},
        }

    monkeypatch.setattr(commodities, "market_row", fake_market_row)

    rows = commodities.fetch_commodities_data(
        {"commodities": [{"label": "Brent", "symbol": "BZ=F"}]}
    )

    assert symbols == ["BZ=F"]
    assert rows[0]["last"] == 91.5
    assert rows[0]["source"]["url"].endswith("BZ=F")


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
