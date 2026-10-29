"""The validation anchors, reproduced or explained; nothing tuned."""

import pytest

from voyage import anchors


def test_baltic_2017_td3c_days_and_fuel_reproduce():
    out = anchors.baltic_2017()
    for key, published in out["published"].items():
        assert out["computed"][key] == pytest.approx(published, abs=0.006), key


def test_lump_sum_anchors_reproduce_within_six_percent_when_bunkers_are_from_the_same_week():
    summary = anchors.lump_sum_summary()
    rows = summary["fresh"]
    assert len(rows) >= 5
    before = [r for r in rows if r["week_ending"] < "2026-03-02"]
    after = [r for r in rows if r["week_ending"] >= "2026-03-02"]
    assert before and after
    for r in rows + summary["week_old"]:
        # The engine leaves out port charges and canal tolls, which the Baltic includes: it reads high.
        assert 0.0 < r["error"] < 0.06, (r["week_ending"], r["route"], r["error"])
    # The two weeks after the closure of Hormuz are named, not hidden: same week tables, far above.
    assert {r["week_ending"] for r in summary["exception"]} == set(anchors.POST_CLOSURE_WEEKS)
    assert all(r["bunker_age_days"] == 0 and r["error"] > 0.06 for r in summary["exception"])


def test_a_reprinted_bunker_row_is_dated_by_its_first_printing():
    summary = anchors.lump_sum_summary()
    rows = {(r["route"], r["week_ending"]): r for r in summary["rows"]}
    # Star Asia's week 9 table repeats week 8's in every cell; week 16's Houston row is week 12's.
    assert rows[("TD22", "2026-02-27")]["bunkers_first_printed"] == "2026-02-20"
    assert rows[("TD22", "2026-04-17")]["bunkers_first_printed"] == "2026-03-20"
    assert rows[("TD22", "2026-04-17")] in summary["stale"]


def test_the_gap_to_the_baltic_grows_with_freight():
    summary = anchors.lump_sum_summary()
    assert summary["gap_high"]["row"]["rate_value"] > summary["gap_low"]["row"]["rate_value"]
    assert summary["gap_high"]["gap_usd_day"] > 2.0 * summary["gap_low"]["gap_usd_day"]


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
    # One seven day period: a TD3C voyage spends about six and a half days inside the Gulf.
    assert war["war_risk_periods"] == 1.0 and 6.0 < war["war_risk_days_inside"] < 7.0
    assert war["war_risk_usd"] == pytest.approx(0.025 * 120e6)
    assert war["engine_tce_with_war_risk_usd_day"] < war["engine_tce_usd_day"]


def test_the_july_spot_5tc_is_the_180000_t_basis():
    basis = anchors.capesize_basis_2026_07_03()
    assert basis["basis"] == "180"
    assert round(basis["bci_if_180"]) == basis["bci_published"]
    assert round(basis["bdi_if_180"]) == basis["bdi_published"]
    assert round(basis["bci_if_182"]) != basis["bci_published"]


def test_dry_gaps_are_taken_gross_against_the_182000_t_ship():
    for r in anchors.dry_weekly():
        assert r["engine_tce_gross_usd_day"] == pytest.approx(r["engine_tce_usd_day"] / 0.95)
        assert r["gap_usd_day"] == pytest.approx(r["engine_tce_gross_usd_day"] - r["benchmark_182_usd_day"])
        if r["benchmark"] == "C5TC_usd_day":
            assert r["benchmark_182_usd_day"] == r["benchmark_usd_day"] + 3503.0
