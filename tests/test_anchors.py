"""The validation anchors, reproduced or explained; nothing tuned."""

import pytest

from voyage import anchors


def test_baltic_2017_td3c_days_and_fuel_reproduce():
    out = anchors.baltic_2017()
    for key, published in out["published"].items():
        assert out["computed"][key] == pytest.approx(published, abs=0.006), key


def test_lump_sum_anchors_reproduce_within_six_percent_when_bunkers_are_from_the_same_week():
    rows = [r for r in anchors.tanker_weekly() if r["reproducible"] and r["bunkers"] == "week of " + r["week_ending"]]
    assert len(rows) >= 5
    before = [r for r in rows if r["week_ending"] < "2026-03-02"]
    after = [r for r in rows if r["week_ending"] >= "2026-03-02"]
    assert before and after
    for r in rows:
        # The engine leaves out port charges and canal tolls, which the Baltic includes: it reads high.
        assert 0.0 < r["error"] < 0.06, (r["week_ending"], r["route"], r["error"])


def test_worldscale_anchors_are_recorded_as_not_reproducible():
    rows = [r for r in anchors.tanker_weekly() if r["rate_basis"] == "ws"]
    assert len(rows) > 40
    assert all(not r["reproducible"] and "flat rate" in r["reason"] for r in rows)
    routes = {r["route"] for r in rows}
    assert {"TD3C", "TD20", "TD25", "TC1", "TC2_37"} <= routes


def test_distance_checks_hold_for_at_least_ten_pairs():
    d = anchors.distances()
    assert d["tolerance"] == 0.02
    assert d["within"] >= 10


def test_early_march_rates_price_through_the_engine():
    rows = {r["id"]: r for r in anchors.early_march()}
    assert (
        rows["platts_pg_china_2026_03_02"]["engine_tce_usd_day"]
        > rows["platts_pg_china_2025_12_12"]["engine_tce_usd_day"]
    )
    war = rows["platts_pg_china_2026_03_02"]
    assert war["war_risk_usd"] == pytest.approx(0.025 * 120e6)
    assert war["engine_tce_with_war_risk_usd_day"] < war["engine_tce_usd_day"]
