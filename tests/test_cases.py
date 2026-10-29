"""Voyages built from the seeds: legs, emission control areas, EU ETS shares, bunker hubs, phase-in."""

import pytest

from voyage import baltic, cases, eca, engine


def test_ets_phase_in_boundaries():
    assert cases.phase_in(2023) == 0.0
    assert cases.phase_in(2024) == 0.40
    assert cases.phase_in(2025) == 0.70
    assert cases.phase_in(2026) == 1.0
    assert cases.phase_in(2031) == 1.0


def test_ets_shares_by_voyage_type():
    assert cases.ets_share("amsterdam", "le_havre") == 1.0  # between EEA ports
    assert cases.ets_share("rotterdam", "new_york") == 0.5  # out of the EEA
    assert cases.ets_share("houston", "rotterdam") == 0.5  # into the EEA
    assert cases.ets_share("ras_tanura", "ningbo") == 0.0  # outside


def test_mediterranean_eca_applies_from_1_may_2025():
    med = {z.id for z in eca.in_force(cases.zones(), "2025-05-01")}
    before = {z.id for z in eca.in_force(cases.zones(), "2025-04-30")}
    assert "mediterranean" in med
    assert "mediterranean" not in before
    after = dict(cases.eca_miles("jubail", "rotterdam", "direct", "2025-05-01"))
    earlier = dict(cases.eca_miles("jubail", "rotterdam", "direct", "2025-04-30"))
    assert after["mediterranean"] > 1500
    assert "mediterranean" not in earlier
    assert after["north_sea"] == pytest.approx(earlier["north_sea"])


def test_ports_inside_the_right_areas():
    assert cases.port_in_eca("rotterdam", "2026-08-31") == "north_sea"
    assert cases.port_in_eca("houston", "2026-08-31") == "na_atlantic_gulf"
    assert cases.port_in_eca("new_york", "2026-08-31") == "na_atlantic_gulf"
    assert cases.port_in_eca("ras_tanura", "2026-08-31") is None
    assert cases.port_in_eca("ningbo", "2026-08-31") is None


def test_eca_miles_of_study_legs():
    miles = dict(cases.eca_miles("rotterdam", "new_york", "direct", "2026-08-31"))
    assert set(miles) == {"north_sea", "na_atlantic_gulf"}
    assert miles["na_atlantic_gulf"] == pytest.approx(1231.8, abs=5)
    assert cases.eca_miles("ras_tanura", "ningbo", "direct", "2026-08-31") == ()
    # Amsterdam to Le Havre lies wholly in the North Sea ECA, from IJmuiden by the canal.
    leg = cases.leg_record("amsterdam", "le_havre", "direct")
    assert dict(cases.eca_miles("amsterdam", "le_havre", "direct", "2026-08-31"))["north_sea"] == pytest.approx(
        leg["distance_nm"], abs=3
    )


def test_bunker_hub_is_the_nearest_with_prices():
    assert cases.bunker_hub("ras_tanura") == "fujairah"
    assert cases.bunker_hub("galveston") == "houston"
    assert cases.bunker_hub("port_hedland") == "singapore"
    assert cases.bunker_hub("tubarao") == "rotterdam"
    assert cases.bunker_hub("bonny") == "rotterdam"


def test_c3_names_its_hub_because_the_nearest_is_off_the_voyage():
    c3 = baltic.ROUTES["C3"]
    assert cases.route_hub(c3) == "singapore" and c3.bunker_hub_why
    assert all(
        cases.route_hub(baltic.ROUTES[code]) == cases.bunker_hub(baltic.ROUTES[code].load)
        for code in baltic.STUDY_ROUTES
        if code != "C3"
    )


def test_common_market_is_august_2026():
    m = cases.common_market()
    assert m.eua_month == "2026-08"
    assert m.eua_eur_t == pytest.approx(82.31)
    assert m.bunkers["singapore"]["vlsfo"][0] == 822.0
    assert m.bunkers["singapore"]["hsfo"][0] == 629.0
    assert m.usd_per_eur == pytest.approx(1.1593619, rel=1e-6)


def test_every_study_route_builds_and_prices():
    m = cases.common_market()
    for code in baltic.STUDY_ROUTES + baltic.SUPPORT_ROUTES:
        route = baltic.ROUTES[code]
        value = {"usd_t": 20.0, "ws": 100.0, "lump_sum": 5e6, "hire_usd_day": 20000.0}
        case = cases.build(code, m, freight_value=None)
        basis = case.inputs["freight_basis"]
        if basis == "ws":
            case = cases.build(code, m, freight_value=20.0, freight_basis="usd_t")
        else:
            case = cases.build(code, m, freight_value=value[basis])
        r = engine.evaluate(case.inputs)
        assert r["days"]["total"] > 0
        assert r["costs"]["bunkers"] > 0
        assert case.inputs["commission_pct"] == route.commission_pct
        assert "port charges" in " ".join(case.excluded)


def test_tanker_cases_follow_the_baltic_tce_description():
    case = cases.build("TD3C", cases.common_market(), freight_value=20.0, freight_basis="usd_t")
    port = case.inputs["port"]
    assert (port["load_days"], port["discharge_days"], port["waiting_days"]) == (2, 2, 2)
    assert (port["load_tpd"], port["discharge_tpd"], port["waiting_tpd"]) == (20, 110, 10)
    assert case.inputs["laden"]["speed_kn"] == 13 and case.inputs["ballast"]["speed_kn"] == 12
    assert case.inputs["commission_pct"] == 3.75
    assert case.legs["hub"] == "fujairah"


def test_dry_laytime_in_calendar_days():
    m = cases.common_market()
    p7 = cases.build("P7", m, freight_value=70.0).inputs["port"]
    assert p7["load_days"] == pytest.approx(66000 / 10000 * 7 / 5 + 1)
    assert p7["discharge_days"] == pytest.approx(66000 / 8000 * 7 / 5 + 1)
    c3 = cases.build("C3", m, freight_value=30.0)
    assert c3.inputs["port"]["discharge_days"] == pytest.approx(170000 / 30000 + 1)
    assert c3.inputs["port"]["load_days"] == pytest.approx(0.25)
    assert any("loading time" in text for text in c3.excluded)


def test_capesize_vessel_is_the_bci182_from_2_january_2026_and_refused_before():
    priced = cases.build("C5", cases.weekly_market("2026-07-03", "singapore"), freight_value=10.0)
    assert priced.legs["vessel"] == "BCI182"
    assert baltic.vessel_for(baltic.ROUTES["C5"], "2026-01-02").id == "BCI182"
    # The BCI180 is not defined: v8.8 no longer prints its consumptions.
    with pytest.raises(ValueError):
        baltic.vessel_for(baltic.ROUTES["C5"], "2025-12-24")
