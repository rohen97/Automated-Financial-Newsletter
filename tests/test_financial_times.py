from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from src.fetchers import financial_times
from src.fetchers.provider_audit import provider_audit_snapshot, reset_provider_audit


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_ft_search_uses_header_auth_and_normalises_articles(monkeypatch):
    captured = {}
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = {
        "results": [
            {
                "indexCount": 1,
                "results": [
                    {
                        "id": "article-id",
                        "title": {"title": "Global markets reassess the path for rates"},
                        "lifecycle": {
                            "initialPublishDateTime": now.isoformat().replace("+00:00", "Z"),
                            "lastPublishDateTime": now.isoformat().replace("+00:00", "Z"),
                        },
                        "location": {"uri": "https://www.ft.com/content/article-id"},
                        "summary": {"excerpt": "Investors reconsider inflation and central-bank policy."},
                    }
                ],
            }
        ]
    }

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(payload)

    monkeypatch.setenv("FT_API_KEY", "test-ft-key")
    monkeypatch.setenv("FT_API_ORG_NAME", "Wolf Research")
    monkeypatch.setenv("FT_API_TRACKING_SOURCE", "email")
    monkeypatch.setattr(financial_times.requests, "post", fake_post)
    reset_provider_audit()

    articles = financial_times.fetch_financial_times_articles(
        {
            "enabled": True,
            "max_results_per_query": 10,
            "request_timeout_seconds": 8,
            "queries": [{"name": "FT Markets", "query": "markets OR rates"}],
        },
        lookback_days=7,
    )

    assert captured["url"] == financial_times.FT_SEARCH_URL
    assert captured["headers"]["X-Api-Key"] == "test-ft-key"
    assert "test-ft-key" not in captured["url"]
    assert captured["json"]["resultContext"]["aspects"] == financial_times.FT_SEARCH_ASPECTS
    assert captured["json"]["resultContext"]["sortOrder"] == "DESC"
    assert "lastPublishDateTime:>" in captured["json"]["queryString"]
    assert captured["timeout"] == 8

    assert len(articles) == 1
    article = articles[0]
    assert article["source"] == "Financial Times"
    assert article["title"] == "Global markets reassess the path for rates"
    assert article["summary"] == "Investors reconsider inflation and central-bank policy."
    campaign = parse_qs(urlsplit(article["url"]).query)["FTCamp"][0]
    assert campaign == "engage/CAPI/email/Channel_Wolf_Research//B2B"

    audit = provider_audit_snapshot()
    assert "financial_times" in audit["providers_used"]
    assert audit["ft_queries_run"] == ["markets OR rates"]
    assert audit["ft_articles_fetched"] == 1


def test_ft_fetch_is_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("FT_API_KEY", raising=False)

    def unexpected_post(*args, **kwargs):
        raise AssertionError("FT API should not be called without FT_API_KEY")

    monkeypatch.setattr(financial_times.requests, "post", unexpected_post)
    assert financial_times.fetch_financial_times_articles({"enabled": True, "queries": ["markets"]}) == []
