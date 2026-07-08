from pathlib import Path

from src.portfolio.equity import (
    equity_monitor,
    load_equity_holdings,
    parse_money,
    parse_number,
    parse_percent,
)


def test_parse_money_handles_export_formats():
    assert parse_money("USD 15,046,159") == 15046159
    assert parse_money("-USD 1,881,090") == -1881090
    assert parse_money("(USD 1,234)") == -1234
    assert parse_money("#N/A Invalid") is None


def test_parse_percent_and_number_handle_common_formats():
    assert parse_percent("31.48%") == 31.48
    assert parse_number("3,241,000") == 3241000
    assert parse_number("") is None


def test_equity_holdings_csv_parses_actual_values():
    holdings = load_equity_holdings()
    meta = next(item for item in holdings if item["holding"] == "Meta Wolf AG")
    assert len(holdings) == 16
    assert meta["current_value"] == 127069520
    assert meta["ytd_pnl"] == 28932017
    assert meta["ytd_pct"] == 29.48
    assert meta["pricing_mode"] == "manual"
    assert meta["has_usable_pricing"] is True
    assert meta["is_manual_pricing"] is False


def test_equity_monitor_calculates_portfolio_metrics():
    monitor = equity_monitor(load_equity_holdings())
    assert monitor["total_equity_portfolio_value_usd"] == 171598778
    assert monitor["total_ytd_equity_pnl_usd"] == 30616737
    assert monitor["best_contributor"] == "Meta Wolf AG"
    assert monitor["worst_contributor"] == "Bayerische Motoren Werke AG"
    assert monitor["largest_sector_exposure"] == "Capital Goods"
    assert monitor["largest_currency_exposure"] == "EUR"
    assert monitor["usable_equity_pricing_count"] == 16
    assert monitor["missing_pricing_count"] == 0


def test_equity_exposure_tables_are_populated():
    monitor = equity_monitor(load_equity_holdings())
    assert monitor["sector_exposure"][0]["name"] == "Capital Goods"
    assert monitor["sector_exposure"][0]["current_value_display"] == "USD 127.1m"
    assert monitor["currency_exposure"][0]["name"] == "EUR"
    assert monitor["currency_exposure"][0]["weight_display"] == "85%"


def test_manual_pricing_with_missing_values_is_flagged(tmp_path: Path):
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "stock_name,currency,current_investment_value_usd,ytd_performance_usd,ytd_performance_pct,industry_sector,pricing_mode\n"
        "Private Co,USD,,,,Technology,manual\n",
        encoding="utf-8",
    )
    holding = load_equity_holdings(csv_path)[0]
    assert holding["pricing_mode"] == "manual"
    assert holding["has_usable_pricing"] is False
    assert holding["is_manual_pricing"] is True
