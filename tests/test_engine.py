"""The engine's formulas against numbers worked by hand."""

import math

import pytest

from voyage import engine


def no_area():
    return {
        "premium_pct": 0.0,
        "entries": 0,
        "laden_nm": 0.0,
        "ballast_nm": 0.0,
        "port_activities": [],
        "ballast_transits": 0,
    }


def simple_voyage(**changes):
    """A voyage small enough to price on paper: see the comments in each test."""
    inputs = {
        "contract": "voyage",
        "freight_basis": "usd_t",
        "freight_value": 10.0,
        "flat_rate_usd_t": None,
        "cargo_t": 100000.0,
        "commission_pct": 5.0,
        "other_revenue_usd": 0.0,
        "sea_margin": 0.0,
        "laden": {"distance_nm": 2400.0, "speed_kn": 10.0, "eca_nm": 0.0, "ets_share": 0.0},
        "ballast": {"distance_nm": 2400.0, "speed_kn": 12.0, "eca_nm": 0.0, "ets_share": 0.0},
        "laden_curve": [[10.0, 30.0], [12.0, 40.0]],
        "ballast_curve": [[10.0, 20.0], [12.0, 30.0]],
        "mgo_at_sea_tpd": 0.0,
        "scrubber": False,
        "scrubber_in_eca": False,
        "vlsfo_class": "HFO",
        "port": {
            "load_days": 2.0,
            "discharge_days": 3.0,
            "waiting_days": 0.0,
            "canal_days": 0.0,
            "delay_days": 0.0,
            "sts_days": 0.0,
            "load_tpd": 5.0,
            "discharge_tpd": 10.0,
            "waiting_tpd": 0.0,
            "canal_tpd": 0.0,
            "delay_tpd": 0.0,
            "sts_tpd": 0.0,
            "load_eca": False,
            "discharge_eca": False,
            "waiting_eca": False,
            "canal_eca": False,
            "delay_eca": False,
            "sts_eca": False,
            "load_ets_share": 0.0,
            "discharge_ets_share": 0.0,
            "waiting_ets_share": 0.0,
            "canal_ets_share": 0.0,
            "delay_ets_share": 0.0,
            "sts_ets_share": 0.0,
        },
        "prices": {"vlsfo_usd_t": 500.0, "hsfo_usd_t": 400.0, "mgo_usd_t": 800.0},
        "ets": {"phase_in": 1.0, "eua_eur_t": 80.0, "usd_per_eur": 1.1, "include_non_co2": True},
        "fueleu": {"include": False, "reduction_pct": 2.0},
        "costs": {
            "port_load_usd": 50000.0,
            "port_discharge_usd": 50000.0,
            "canal_laden_usd": 0.0,
            "canal_ballast_usd": 0.0,
            "other_usd": 0.0,
            "sts_usd": 0.0,
        },
        "war_risk": {
            "hull_value_usd": 0.0,
            "crew_bonus_usd": 0.0,
            "payer": "owner",
            "areas": {"gulf": no_area(), "red_sea": no_area()},
        },
    }
    for path, value in changes.items():
        head, _, tail = path.partition(".")
        if tail:
            inputs[head] = dict(inputs[head], **{tail: value})
        else:
            inputs[head] = value
    return inputs


def test_sea_days_match_the_baltic_2017_td3c_note():
    # 5,897 nm with a 5% weather margin: 19.8457 days at 13.0 knots, 20.6395 at 12.5 knots.
    assert engine.sea_days(5897, 13.0, 0.05) == pytest.approx(19.8457, abs=5e-5)
    assert engine.sea_days(5897, 12.5, 0.05) == pytest.approx(20.6395, abs=5e-5)
    assert engine.sea_days(0, 13.0, 0.05) == 0.0


def test_consumption_interpolates_between_published_pairs():
    curve = [[14, 52], [13, 44], [12, 36], [11, 29]]  # BCI182 laden, GMB v8.8 page 78
    assert engine.consumption_tpd(curve, 13) == 44
    assert engine.consumption_tpd(curve, 12.5) == pytest.approx(40.0)
    assert engine.consumption_tpd(curve, 11.5) == pytest.approx(32.5)


def test_power_law_outside_the_pairs_is_continuous_and_fitted():
    curve = [[13, 57.3], [11, 39.8]]  # VLCC300 laden, GMB v8.8 page 89
    fit = engine.power_fit(curve)
    b = math.log(57.3 / 39.8) / math.log(13 / 11)
    assert fit["b"] == pytest.approx(b)
    assert fit["a"] * 13 ** fit["b"] == pytest.approx(57.3)
    assert fit["r2"] == pytest.approx(1.0)
    assert engine.consumption_tpd(curve, 14) == pytest.approx(57.3 * (14 / 13) ** b)
    assert engine.consumption_tpd(curve, 10) == pytest.approx(39.8 * (10 / 11) ** b)
    assert engine.consumption_tpd(curve, 13 + 1e-9) == pytest.approx(57.3, rel=1e-8)


def test_worldscale_conversion_both_ways():
    assert engine.ws_to_usd_t(100, 12.5) == pytest.approx(12.5)
    assert engine.ws_to_usd_t(250, 12.5) == pytest.approx(31.25)
    assert engine.usd_t_to_ws(31.25, 12.5) == pytest.approx(250)
    inputs = simple_voyage(freight_basis="ws", freight_value=200.0, flat_rate_usd_t=5.0)
    assert engine.freight_usd_t(inputs) == pytest.approx(10.0)
    inputs = simple_voyage(freight_basis="lump_sum", freight_value=1_000_000.0)
    assert engine.freight_usd_t(inputs) == pytest.approx(10.0)


def test_tce_of_a_voyage_worked_by_hand():
    # Gross 100,000 t x 10 = 1,000,000; commission 5% = 50,000.
    # Laden 2,400 nm at 10 kn = 10 days on 30 t = 300 t; ballast 2,400 nm at 12 kn = 8.3333 days on 30 t = 250 t.
    # Port 2 days x 5 t + 3 days x 10 t = 40 t. Fuel 590 t x 500 = 295,000. Ports 100,000.
    # TCE = (950,000 - 395,000) / 23.3333 days = 23,785.71.
    r = engine.evaluate(simple_voyage())
    assert r["days"]["total"] == pytest.approx(23 + 1 / 3)
    assert r["fuel_total_t"] == pytest.approx(590.0)
    assert r["costs"]["bunkers"] == pytest.approx(295000.0)
    assert r["revenue"]["commission_usd"] == pytest.approx(50000.0)
    assert r["tce_usd_day"] == pytest.approx(555000.0 / (23 + 1 / 3))


def test_eca_miles_burn_mgo():
    # 1,200 of the 2,400 laden miles in an ECA: 5 days on 30 t of MGO at 800 instead of VLSFO at 500.
    r = engine.evaluate(simple_voyage(**{"laden.eca_nm": 1200.0}))
    assert r["fuel_t"]["mgo"] == pytest.approx(150.0)
    assert r["costs"]["bunkers"] == pytest.approx(295000.0 + 150.0 * 300.0)


def test_scrubber_burns_hsfo_outside_ecas():
    r = engine.evaluate(simple_voyage(scrubber=True))
    assert r["fuel_t"]["hsfo"] == pytest.approx(590.0)
    assert r["costs"]["bunkers"] == pytest.approx(590.0 * 400.0)


def test_ets_cost_with_methane_and_nitrous_oxide():
    # Laden leg fully covered: 300 t VLSFO (HFO class) = 934.2 t CO2 plus
    # 300 x (0.00005 x 28 + 0.00018 x 265) = 14.73 t CO2e; at 80 EUR and 1.1 USD/EUR.
    r = engine.evaluate(simple_voyage(**{"laden.ets_share": 1.0}))
    covered = 300 * 3.114 + 300 * (0.00005 * 28 + 0.00018 * 265)
    assert r["emissions"]["ets_covered_t"] == pytest.approx(covered)
    assert r["costs"]["ets"] == pytest.approx(covered * 80 * 1.1)
    r = engine.evaluate(simple_voyage(**{"laden.ets_share": 0.5, "ets.include_non_co2": False, "ets.phase_in": 0.4}))
    assert r["costs"]["ets"] == pytest.approx(300 * 3.114 * 0.5 * 0.4 * 80 * 1.1)


def test_fueleu_penalty_for_heavy_fuel_oil():
    # HFO well to wake: 13.5 + (3.114 + 0.00005 x 25 + 0.00018 x 298) / 0.0405 = 91.7442 gCO2e/MJ,
    # against 91.16 x 0.98 = 89.3368. 300 t laden in scope = 12.15 million MJ.
    r = engine.evaluate(simple_voyage(**{"laden.ets_share": 1.0}))
    fe = r["fueleu"]
    intensity = 13.5 + (3.114 + 0.00005 * 25 + 0.00018 * 298) / 0.0405
    assert fe["intensity_g_mj"] == pytest.approx(intensity)
    assert fe["target_g_mj"] == pytest.approx(89.3368)
    energy = 300e6 * 0.0405
    assert fe["energy_mj"] == pytest.approx(energy)
    balance = (89.3368 - intensity) * energy
    assert fe["balance_g"] == pytest.approx(balance)
    assert fe["penalty_eur"] == pytest.approx(-balance / (intensity * 41000) * 2400)
    assert r["costs"]["fueleu"] == 0.0
    included = engine.evaluate(simple_voyage(**{"laden.ets_share": 1.0, "fueleu.include": True}))
    assert included["costs"]["fueleu"] == pytest.approx(fe["penalty_eur"] * 1.1)


def war(payer, gulf=None, red_sea=None):
    return {
        "hull_value_usd": 100e6,
        "crew_bonus_usd": 10000.0,
        "payer": payer,
        "areas": {"gulf": gulf or no_area(), "red_sea": red_sea or no_area()},
    }


def test_war_risk_premium_counts_seven_day_periods_inside_the_area():
    # The Gulf: 1,200 nm of the laden leg at 10 knots is 5 days, plus 2 days loading: 7 days, one period.
    gulf = dict(no_area(), premium_pct=0.5, entries=1, laden_nm=1200.0, port_activities=["load"])
    r = engine.evaluate(simple_voyage(war_risk=war("owner", gulf=gulf)))
    assert r["war_risk"]["areas"]["gulf"]["days"] == pytest.approx(7.0)
    assert r["war_risk"]["areas"]["gulf"]["periods"] == 1.0
    assert r["costs"]["war_risk"] == pytest.approx(0.005 * 100e6 * 1 + 10000)
    # A day of delay at the load port makes 8 days inside: two periods.
    delayed = simple_voyage(war_risk=war("owner", gulf=dict(gulf, port_activities=["load", "delay"])))
    delayed["port"] = dict(delayed["port"], delay_days=1.0)
    r = engine.evaluate(delayed)
    assert r["war_risk"]["areas"]["gulf"]["periods"] == 2.0
    assert r["costs"]["war_risk"] == pytest.approx(0.005 * 100e6 * 2 + 10000)


def test_a_red_sea_transit_on_each_leg_is_a_period_each():
    red_sea = dict(no_area(), premium_pct=0.5, entries=1, ballast_transits=1)
    r = engine.evaluate(simple_voyage(war_risk=war("owner", red_sea=red_sea)))
    assert r["war_risk"]["areas"]["red_sea"]["periods"] == 1.0
    assert r["war_risk"]["areas"]["red_sea"]["ballast_periods"] == 1.0
    assert r["war_risk"]["premium_usd"] == pytest.approx(0.005 * 100e6 * 2)


def test_the_ballast_transit_is_the_owners_whoever_pays_the_charters_premium():
    # 0.5 percent of a USD 100m hull is USD 500,000 a transit; the crew bonus goes with the charter's part.
    red_sea = dict(no_area(), premium_pct=0.5, entries=1, ballast_transits=1)
    plain = engine.evaluate(simple_voyage())
    r = engine.evaluate(simple_voyage(war_risk=war("charterer", red_sea=red_sea)))
    assert r["war_risk"]["charter_usd"] == pytest.approx(500000 + 10000)
    assert r["war_risk"]["ballast_usd"] == pytest.approx(500000)
    assert r["costs"]["war_risk"] == pytest.approx(500000)
    assert r["charterer_costs_usd"] == pytest.approx(510000)
    assert r["tce_usd_day"] == pytest.approx(plain["tce_usd_day"] - 500000 / plain["days"]["total"])
    owner = engine.evaluate(simple_voyage(war_risk=war("owner", red_sea=red_sea)))
    assert owner["costs"]["war_risk"] == pytest.approx(1010000)
    assert owner["charterer_costs_usd"] == 0.0


def test_the_charterer_pays_the_premium_and_the_owner_tce_stands():
    gulf = dict(no_area(), premium_pct=7.5, entries=1, laden_nm=300.0, ballast_nm=300.0, port_activities=["load"])
    plain = engine.evaluate(simple_voyage())
    r = engine.evaluate(simple_voyage(war_risk=war("charterer", gulf=gulf)))
    assert r["costs"]["war_risk"] == 0.0
    assert r["charterer_costs_usd"] == pytest.approx(0.075 * 100e6 + 10000)
    assert r["tce_usd_day"] == pytest.approx(plain["tce_usd_day"])


def test_breakeven_freight_reprices_to_the_target():
    inputs = simple_voyage(flat_rate_usd_t=4.0)
    for target in (0.0, 15000.0, 40000.0):
        quote = engine.freight_for_tce(inputs, target)
        priced = dict(inputs, freight_value=quote["usd_t"])
        assert engine.evaluate(priced)["tce_usd_day"] == pytest.approx(target, abs=1e-6)
        assert quote["lump_sum_usd"] == pytest.approx(quote["usd_t"] * 100000)
        assert quote["ws"] == pytest.approx(100 * quote["usd_t"] / 4.0)


def test_trip_charter_pays_the_owner_hire_less_the_ballast():
    trip = simple_voyage(contract="trip", freight_basis="hire_usd_day", freight_value=20000.0)
    no_ballast = dict(trip, ballast=dict(trip["ballast"], distance_nm=0.0))
    r = engine.evaluate(no_ballast)
    assert r["tce_usd_day"] == pytest.approx(20000.0 * 0.95)
    r = engine.evaluate(trip)
    trip_days = 10 + 5
    ballast_cost = 250 * 500
    assert r["costs"]["bunkers"] == pytest.approx(ballast_cost)
    assert r["tce_usd_day"] == pytest.approx((20000 * 0.95 * trip_days - ballast_cost) / (trip_days + 25 / 3))
    assert r["charterer_costs_usd"] == pytest.approx(300 * 500 + 40 * 500 + 100000)
    hire = engine.freight_for_tce(trip, 15000.0)["hire_usd_day"]
    assert engine.evaluate(dict(trip, freight_value=hire))["tce_usd_day"] == pytest.approx(15000.0)


def test_trip_charterer_bears_the_trip_allowances():
    trip = simple_voyage(
        contract="trip",
        freight_basis="hire_usd_day",
        freight_value=20000.0,
        **{"laden.ets_share": 1.0, "ballast.ets_share": 0.5},
    )
    r = engine.evaluate(trip)
    ballast_covered = 250 * (3.114 + 0.00005 * 28 + 0.00018 * 265) * 0.5
    assert r["costs"]["ets"] == pytest.approx(ballast_covered * 80 * 1.1)
    assert r["ets_all_usd"] > r["costs"]["ets"]


def test_optimal_speed_rises_with_freight_and_falls_with_bunkers():
    base = simple_voyage(**{"laden_curve": [[10.0, 20.0], [14.0, 50.0]], "ballast_curve": [[10.0, 15.0], [14.0, 40.0]]})
    low = engine.optimal_speed(base, 8.0, 16.0)
    high_freight = engine.optimal_speed(dict(base, freight_value=40.0), 8.0, 16.0)
    dear_fuel = engine.optimal_speed(
        dict(base, prices={"vlsfo_usd_t": 1500.0, "hsfo_usd_t": 1200.0, "mgo_usd_t": 2000.0}), 8.0, 16.0
    )
    assert high_freight["laden_kn"] > low["laden_kn"]
    assert dear_fuel["laden_kn"] < low["laden_kn"]
    grid = engine.tce_by_speed(base, [8.0 + 0.01 * k for k in range(801)])
    assert max(p["tce_usd_day"] for p in grid) == pytest.approx(low["tce_usd_day"])


def test_hedge_sizes_and_basis():
    inputs = simple_voyage()
    physical = engine.evaluate(inputs)["tce_usd_day"]
    h = engine.hedge(inputs, physical, 20000.0, 9.0)
    assert h["tc_hedge_days"] == pytest.approx(23 + 1 / 3)
    assert h["route_hedge_t"] == 100000.0
    assert h["route_ffa_tce_usd_day"] == pytest.approx(engine.evaluate(dict(inputs, freight_value=9.0))["tce_usd_day"])
    # A time charter FFA is gross hire: the net TCE is grossed up by the 5 percent commission first.
    assert h["physical_tce_gross_usd_day"] == pytest.approx(physical / 0.95)
    assert h["basis_vs_tc_ffa_usd_day"] == pytest.approx(physical / 0.95 - 20000.0)
    assert h["tc_hedge_days_net"] == pytest.approx((23 + 1 / 3) * 0.95)


def test_sensitivities_move_the_right_way():
    rows = {row["id"]: row for row in engine.sensitivities(simple_voyage(**{"laden.ets_share": 1.0}))}
    assert (
        rows["freight"]["high_tce_usd_day"] > rows["freight"]["base_tce_usd_day"] > rows["freight"]["low_tce_usd_day"]
    )
    assert rows["bunkers"]["high_tce_usd_day"] < rows["bunkers"]["low_tce_usd_day"]
    assert rows["eua"]["high_tce_usd_day"] < rows["eua"]["low_tce_usd_day"]
    assert rows["port_days"]["high_tce_usd_day"] < rows["port_days"]["base_tce_usd_day"]
