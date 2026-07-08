from src.portfolio.fixed_income import fixed_income_monitor, load_fixed_income_issuers


def test_fixed_income_csv_loads_position_level_data():
    positions = load_fixed_income_issuers()
    amazon = next(item for item in positions if item["issuer"] == "AMAZON.COM INC")
    assert len(positions) == 151
    assert amazon["isin"] == "US023135BX34"
    assert amazon["currency"] == "USD"
    assert amazon["market_value_usd"] == 4979000
    assert amazon["maturity_date"] == "2026-05-12"


def test_fixed_income_monitor_uses_position_level_mode():
    monitor = fixed_income_monitor(load_fixed_income_issuers())
    assert monitor["mode"] == "position-level"
    assert monitor["position_count"] == 151
    assert monitor["issuer_count"] > 20
    assert monitor["total_market_value_usd"] > 200_000_000
    assert monitor["currency_exposure"]
    assert monitor["maturity_exposure"]
    assert "yield" in monitor["missing_bond_fields"]
