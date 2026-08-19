from src.fetchers.macro import _observation_snapshot


def test_observation_snapshot_uses_a_week_ago_reference():
    snapshot = _observation_snapshot(
        "DGS10",
        [
            {"date": "2026-08-18", "value": "4.50"},
            {"date": "2026-08-17", "value": "4.49"},
            {"date": "2026-08-11", "value": "4.38"},
            {"date": "2026-08-10", "value": "4.35"},
        ],
    )

    assert snapshot["value"] == "4.50%"
    assert snapshot["observed_at"] == "2026-08-18"
    assert snapshot["reference_observed_at"] == "2026-08-11"
    assert snapshot["weekly_change"] == 0.12


def test_financial_conditions_are_rendered_as_an_index_not_a_percentage():
    snapshot = _observation_snapshot(
        "NFCI",
        [
            {"date": "2026-08-14", "value": "-0.40"},
            {"date": "2026-08-07", "value": "-0.45"},
        ],
    )

    assert snapshot["value"] == "-0.40"
