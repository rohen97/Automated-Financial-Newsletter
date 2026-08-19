from src.analysis.weekly_delta import build_dislocation_watch, build_weekly_delta


def _source(name: str) -> dict:
    return {"name": name, "url": f"https://example.test/{name.lower().replace(' ', '-')}"}


def _inputs():
    macro = [
        {
            "series_id": "DGS10",
            "value": "4.50%",
            "value_numeric": 4.5,
            "weekly_change": 0.12,
            "source": _source("FRED"),
        },
        {
            "series_id": "NFCI",
            "value": "-0.40",
            "value_numeric": -0.4,
            "weekly_change": 0.05,
            "source": _source("FRED"),
        },
    ]
    fx = [
        {
            "label": "DXY",
            "last": 99.5,
            "one_week_change": -0.6,
            "one_month_change": -1.0,
            "source": _source("Market Data"),
        }
    ]
    commodities = [
        {
            "label": "Brent",
            "last": 91.0,
            "one_week_change": 3.0,
            "one_month_change": 4.0,
            "source": _source("Market Data"),
        },
        {
            "label": "Gold",
            "last": 2500.0,
            "one_week_change": 1.5,
            "one_month_change": 2.0,
            "source": _source("Market Data"),
        },
    ]
    sectors = {
        "regions": [
            {
                "region": "US",
                "label": "US Markets",
                "rows": [
                    {"sector": "Energy", "one_week": -2.0, "source": _source("Sector Data")},
                    {"sector": "Technology", "one_week": 1.0, "source": _source("Sector Data")},
                    {"sector": "Financials", "one_week": 1.0, "source": _source("Sector Data")},
                    {"sector": "Industrials", "one_week": 1.0, "source": _source("Sector Data")},
                    {"sector": "Utilities", "one_week": -1.0, "source": _source("Sector Data")},
                ],
            },
            {
                "region": "Europe",
                "label": "European Markets",
                "rows": [
                    {"sector": "Energy", "one_week": -1.0, "source": _source("Sector Data")},
                    {"sector": "Technology", "one_week": -1.0, "source": _source("Sector Data")},
                    {"sector": "Financials", "one_week": -1.0, "source": _source("Sector Data")},
                    {"sector": "Industrials", "one_week": 1.0, "source": _source("Sector Data")},
                    {"sector": "Utilities", "one_week": -1.0, "source": _source("Sector Data")},
                ],
            },
        ]
    }
    return macro, fx, commodities, sectors


def test_weekly_delta_builds_verified_cross_asset_rows():
    section = build_weekly_delta(*_inputs())

    assert [row["signal"] for row in section["rows"]] == [
        "US 10Y yield",
        "US financial conditions",
        "DXY",
        "Brent",
        "US sector breadth",
    ]
    assert section["rows"][0]["weekly_change_display"] == "+12bp"
    assert section["rows"][0]["state"] == "Tightening"
    assert section["rows"][2]["state"] == "USD softer"
    assert section["rows"][3]["state"] == "Inflationary"
    assert section["rows"][4]["current_display"] == "3/5 advancing"


def test_dislocation_watch_returns_only_two_threshold_qualified_items():
    section = build_dislocation_watch(*_inputs())

    assert len(section["items"]) == 2
    titles = {item["title"] for item in section["items"]}
    assert titles <= {
        "Treasury yields and the dollar diverged",
        "Gold resisted its usual yield relationship",
        "Oil and energy equities moved apart",
        "Regional participation split widened",
    }
    assert all(item["sources"] for item in section["items"])


def test_rates_and_dollar_divergence_is_detected_when_it_is_the_only_break():
    macro, fx, commodities, sectors = _inputs()
    commodities[0]["one_week_change"] = 0.2
    commodities[1]["one_week_change"] = -0.2
    for block in sectors["regions"]:
        for index, row in enumerate(block["rows"]):
            row["one_week"] = 1.0 if index < 3 else -1.0

    section = build_dislocation_watch(macro, fx, commodities, sectors)

    assert [item["title"] for item in section["items"]] == [
        "Treasury yields and the dollar diverged"
    ]


def test_dislocation_watch_can_be_empty_without_inventing_an_event():
    macro, fx, commodities, sectors = _inputs()
    macro[0]["weekly_change"] = 0.01
    fx[0]["one_week_change"] = 0.05
    commodities[0]["one_week_change"] = 0.2
    commodities[1]["one_week_change"] = 0.2
    for block in sectors["regions"]:
        for index, row in enumerate(block["rows"]):
            row["one_week"] = 1.0 if index < 3 else -1.0

    section = build_dislocation_watch(macro, fx, commodities, sectors)

    assert section["items"] == []
    assert "No material cross-asset dislocation" in section["empty_message"]
