from src.analysis.market_moves import describe_change, summarize_market_table


def test_describe_change():
    assert describe_change(1) == "higher"
    assert describe_change(-1) == "lower"
    assert describe_change(0) == "unchanged"


def test_summarize_market_table():
    rows = [{"label": "USD/SGD", "one_week_change": 0.01}]
    assert "USD/SGD" in summarize_market_table(rows)[0]
