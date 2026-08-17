from datetime import date, timedelta

from src.charts.chart_renderer import chart_metadata_matches
from src.charts.fred_chart_fetcher import transform_series, z_score_series
from src.charts.fred_chart_selector import select_fred_chart
from src.charts.fred_chart_signals import market_move_score, news_relevance_score, portfolio_relevance_score


def test_yoy_cpi_transformation():
    rows = []
    for offset in range(25):
        year = 2024 + offset // 12
        month = (offset % 12) + 1
        rows.append({"date": date(year, month, 1), "value": 100 + offset})
    transformed = transform_series(rows, "yoy_pct_change")
    assert transformed
    assert transformed[0]["date"] == date(2025, 1, 1)
    assert round(transformed[0]["value"], 2) == 12.0


def test_chart_metadata_must_match_newsletter_contract():
    chart = {
        "chart_id": "us_10y_yield",
        "title": "Chart of the Week: US 10Y Yield",
        "series_used": ["DGS10"],
        "transformation_used": {},
    }
    metadata = {
        "chart_id": "us_10y_yield",
        "title": "Chart of the Week: US 10Y Yield",
        "series": ["DGS10"],
        "transformation": {},
        "render_mode": "matplotlib",
    }
    assert chart_metadata_matches(chart, metadata)
    assert not chart_metadata_matches(chart, {**metadata, "series": ["CPIAUCSL"]})


def test_z_score_series_returns_values():
    rows = [{"date": date.today() + timedelta(days=idx), "value": float(idx)} for idx in range(20)]
    transformed = z_score_series(rows)
    assert len(transformed) == 20
    assert transformed[-1]["value"] > 0


def test_signal_scores_are_bounded():
    rows = [{"date": date.today() + timedelta(days=idx), "value": float(idx)} for idx in range(80)]
    assert 0 <= market_move_score({"DGS10": rows}) <= 1
    assert news_relevance_score("us_10y_yield", [{"title": "Treasury yields rise as Fed repricing continues"}]) > 0
    assert portfolio_relevance_score("real_rates", {"sector_exposure": [{"name": "Technology"}]}) > 0


def test_chart_selection_ranking_uses_config():
    config = {
        "fred_chart_selector": {"avoid_repeat_weeks": 2, "allow_repeat_if_score_advantage_pct": 25},
        "fred_chart_candidates": [
            {"id": "us_10y_yield", "series": ["DGS10"], "lookback_months": 12, "chart_type": "line", "title": "US 10Y", "relevance": "Rates"},
            {"id": "inflation_path", "series": ["CPIAUCSL"], "lookback_months": 60, "chart_type": "line", "title": "Inflation", "relevance": "Inflation"},
        ],
    }
    selection = select_fred_chart(config, articles=[{"title": "Fed and Treasury yields dominate markets"}], equity_monitor={})
    assert selection["selected"]["candidate"]["id"] in {"us_10y_yield", "inflation_path"}
    assert selection["ranked"][0]["selection_score"] >= 0
