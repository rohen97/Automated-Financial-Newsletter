from datetime import UTC, datetime

from src.fetchers import tiingo
from src.fetchers.provider_audit import provider_audit_snapshot, reset_provider_audit
from src.processing.rank import rank_articles


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_tiingo_uses_header_auth_and_normalises_articles(monkeypatch):
    captured = {}
    published = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def fake_get(url, *, headers, params, timeout):
        captured.update({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return FakeResponse(
            [
                {
                    "id": 42,
                    "title": "Fed policy and oil prices shape global markets",
                    "url": "https://www.reuters.com/markets/example",
                    "description": "Rates and commodities moved as investors assessed policy signals.",
                    "publishedDate": published,
                    "crawlDate": published,
                    "source": "reuters.com",
                    "tickers": ["SPY", "XLE"],
                    "tags": ["Federal Reserve", "Oil"],
                }
            ]
        )

    monkeypatch.setenv("TIINGO_API_KEY", "test-tiingo-key")
    monkeypatch.setenv("TIINGO_NEWS_ENABLED", "true")
    monkeypatch.setenv("TIINGO_ALLOW_PERSISTENCE", "true")
    monkeypatch.setattr(tiingo.requests, "get", fake_get)
    reset_provider_audit()

    articles = tiingo.fetch_tiingo_articles(
        {
            "enabled": True,
            "include_general_feed": False,
            "ticker_groups": [{"name": "Portfolio", "tickers": ["SPY", "XLE"]}],
            "max_requests": 1,
        }
    )

    assert captured["url"] == tiingo.TIINGO_NEWS_URL
    assert captured["headers"]["Authorization"] == "Token test-tiingo-key"
    assert "token" not in captured["params"]
    assert captured["params"]["tickers"] == "SPY,XLE"
    assert len(articles) == 1
    assert articles[0]["source"] == "Reuters"
    assert articles[0]["tickers"] == ["SPY", "XLE"]
    assert articles[0]["discovery_provider"] == "Tiingo"
    assert set(articles[0]["tickers"]).issubset(articles[0]["entities"])

    ranked = rank_articles(articles, {"Tiingo": 0.74, "Sample Data": 0.55})
    assert ranked[0]["source_quality_score"] == 0.74
    audit = provider_audit_snapshot()
    assert "tiingo" in audit["providers_used"]
    assert audit["tiingo_requests_run"] == ["Portfolio"]
    assert audit["tiingo_articles_fetched"] == 1
    assert audit["tiingo_status"] == "ok"


def test_tiingo_requires_persistence_acknowledgement(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "test-tiingo-key")
    monkeypatch.setenv("TIINGO_NEWS_ENABLED", "true")
    monkeypatch.setenv("TIINGO_ALLOW_PERSISTENCE", "false")
    monkeypatch.setattr(
        tiingo.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tiingo should not be called before persistence is acknowledged")
        ),
    )
    reset_provider_audit()

    assert tiingo.fetch_tiingo_articles({"enabled": True}) == []
    assert provider_audit_snapshot()["tiingo_status"] == "blocked_by_persistence_guard"


def test_tiingo_requires_api_key(monkeypatch):
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    monkeypatch.setattr(
        tiingo.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tiingo should not be called without a key")
        ),
    )
    reset_provider_audit()

    assert tiingo.fetch_tiingo_articles({"enabled": True}) == []
    assert provider_audit_snapshot()["tiingo_status"] == "missing_api_key"
