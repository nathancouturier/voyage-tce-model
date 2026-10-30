"""The Map view's figures: which routes its takeaway names, what each route is headed by, and the one rule its
alternatives follow (the base first, every change against it, premiums by payer, a toll budget where no toll is
public)."""

import json
import math
from pathlib import Path

import pytest

from voyage import analysis, atlas, baltic, engine, export

ROOT = Path(__file__).resolve().parents[1]
ATLAS = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
ITEMS = {item["id"]: item for item in ATLAS["items"]}


@pytest.fixture(scope="module")
def latest() -> dict:
    return atlas.latest(export.presets())


def item(item_id: str, date: str, headline: str, tce: float | None, days: float, kind: str = "route") -> dict:
    return {"id": item_id, "kind": kind, "date": date, "headline": headline, "tce_usd_day": tce, "days": days}


# --------------------------------------------------------------------------
# The takeaway's picks
# --------------------------------------------------------------------------


def test_picks_take_only_the_maps_week_and_the_baltics_round_trip_tces() -> None:
    items = [
        item("A", "2026-10-23", "baltic_tce", 500.0, 40.0),
        item("B", "2026-10-23", "baltic_tce", 100.0, 30.0),
        item("OLD", "2026-09-11", "engine_tce", 900.0, 90.0),
        item("STALE", "2026-09-11", "baltic_tce", 1000.0, 20.0),
        item("HIRE", "2026-10-23", "baltic_hire", 50.0, 25.0),
        item("EST", "2026-10-23", "engine_tce", 2000.0, 35.0),
        item("STUDY", "2026-10-23", "study", None, 100.0, kind="study"),
    ]
    chosen = atlas.picks(items, "2026-10-23")
    assert chosen["top"]["id"] == "A"
    assert chosen["bottom"]["id"] == "B"
    # The longest round voyage of the week, never an older rate's nor the one way study.
    assert chosen["longest"]["id"] == "A"


def test_the_served_takeaway_names_same_week_figures_only() -> None:
    chosen = atlas.picks(ATLAS["items"], ATLAS["as_of"])
    assert chosen["top"]["id"] == "TD3C"
    assert chosen["bottom"]["id"] == "TC2_37"
    for pick in chosen.values():
        assert pick["date"] == ATLAS["as_of"]
        assert pick["id"] != "P7"
    fields = {s.get("field") for s in ATLAS["page"]["takeaway"] if isinstance(s, dict)}
    assert {"takeaway.top", "takeaway.bottom"} <= fields
    figures = {s["field"]: s["value"] for s in ATLAS["page"]["takeaway"] if isinstance(s, dict) and "value" in s}
    assert figures["takeaway.top"] == ITEMS["TD3C"]["tce_usd_day"]
    assert figures["takeaway.bottom"] == ITEMS["TC2_37"]["tce_usd_day"]


# --------------------------------------------------------------------------
# What heads each route
# --------------------------------------------------------------------------


def test_s4a_is_headed_by_the_baltics_hire_and_the_round_trip_is_a_what_if(latest: dict) -> None:
    f = atlas.figures(latest["S4A_63"])
    assert f["headline"] == "baltic_hire"
    assert f["tce_usd_day"] == latest["S4A_63"]["inputs"]["freight_value"]
    net = 1.0 - f["commission_pct"] / engine.PERCENT
    assert math.isclose(f["trip_hire_net_usd_day"], f["tce_usd_day"] * net)
    assert math.isclose(f["round_trip_gross_usd_day"] * net, f["engine_tce_usd_day"])
    served = ITEMS["S4A_63"]
    assert served["row"]["last"] is True
    assert served["basis"] == "baltic"
    assert [fact["id"] for fact in served["facts"]][:2] == ["tce", "round_trip"]


def test_the_map_figures_carry_no_currency_and_an_older_rate_carries_its_date() -> None:
    for entry in ATLAS["items"]:
        for segment in entry["figure"] or []:
            if isinstance(segment, dict):
                assert "USD" not in segment.get("prefix", "")
    p7 = [s for s in ITEMS["P7"]["figure"] if isinstance(s, dict) and "text" in s]
    assert p7 and p7[0]["text"] == "11 Sep"


def test_no_worldscale_route_shows_a_derived_dollar_freight_beside_its_points() -> None:
    for entry in ATLAS["items"]:
        if entry["kind"] != "route":
            continue
        fields = {
            s.get("field") for fact in entry["facts"] for s in fact["value"] + fact["note"] if isinstance(s, dict)
        }
        assert "freight_at_published_usd_t" not in fields


def test_the_detour_study_is_not_counted_as_a_route() -> None:
    routes = [entry for entry in ATLAS["items"] if entry["kind"] == "route"]
    counts = {f["id"]: f["announce"][0]["value"] for f in ATLAS["page"]["filters"]}
    assert counts["all"] == len(routes) == 14
    assert counts["dry"] == sum(1 for entry in routes if entry["segment"] == "dry") == 4
    assert set(ATLAS["page"]["list"]["study_head"]) == {"route", "tce", "days"}


# --------------------------------------------------------------------------
# The alternatives' rule
# --------------------------------------------------------------------------


def test_every_alternatives_list_opens_with_its_base() -> None:
    for entry in ATLAS["items"]:
        if entry["alternatives"]:
            assert entry["alternatives"][0]["kind"] == "base"
            assert entry["alternatives"][0]["legs"] == []
            assert all(alt["kind"] != "base" for alt in entry["alternatives"][1:])


def test_toll_crossing() -> None:
    # The base earns more before tolls and pays two; the alternative pays none.
    toll = atlas.toll_crossing(30.0, 10.0, 2, 20.0, 15.0, 0)
    assert toll is not None and math.isclose(30.0 - 2 * toll / 10.0, 20.0)
    # The alternative earns more before its one toll: it stays ahead until the toll eats the difference.
    toll = atlas.toll_crossing(20.0, 10.0, 0, 25.0, 12.0, 1)
    assert toll is not None and math.isclose(25.0 - toll / 12.0, 20.0)
    # Ahead before tolls and paying fewer of them: never caught.
    assert atlas.toll_crossing(30.0, 10.0, 0, 20.0, 10.0, 1) is None
    assert atlas.toll_crossing(30.0, 10.0, 1, 20.0, 10.0, 1) is None


def test_td22_lists_only_the_way_back_by_suez_priced_with_the_owners_premium_and_a_canal_day(latest: dict) -> None:
    preset = latest["TD22"]
    base = atlas.figures(preset)
    alternatives = atlas.routing_alternatives(preset, base)
    assert [alt["id"] for alt in alternatives] == ["base", "no_canals_no_sunda-no_panama"]
    suez = alternatives[1]
    hull = preset["inputs"]["war_risk"]["hull_value_usd"]
    rate = analysis._rate(atlas.RED_SEA_RATE_ID)["low"]
    assert math.isclose(suez["owner_premium_usd"], rate / engine.PERCENT * hull)
    assert suez["canal_days"] == atlas.canal_days_a_transit() == 1.0
    assert math.isclose(suez["days_change"], suez["days"] - base["days"]["total"])
    assert math.isclose(suez["tce_change"], suez["tce_usd_day"] - base["engine_tce_usd_day"])
    # The toll at which the way back by Suez earns no more than the base.
    assert suez["ahead_below"] == "alternative"
    assert math.isclose(suez["toll_crossing_usd"], (suez["tce_usd_day"] - base["engine_tce_usd_day"]) * suez["days"])
    assert not any(text.startswith("the additional war risk premium") for text in suez["excluded"])


def test_p7_round_the_cape_is_set_against_panamas_tolls_and_waits(latest: dict) -> None:
    preset = latest["P7"]
    base = atlas.figures(preset)
    alternatives = {alt["id"]: alt for alt in atlas.routing_alternatives(preset, base)}
    cape = alternatives["no_canals-no_canals"]
    assert cape["transits"] == 0 and cape["base_transits"] == 2
    days, tce = base["days"]["total"], base["engine_tce_usd_day"]
    assert math.isclose(tce - cape["toll_crossing_usd"] * 2 / days, cape["tce_usd_day"])
    assert math.isclose(tce * days / (days + cape["waiting_days_crossing"]), cape["tce_usd_day"])
    for alt_id in ("direct-no_canals", "no_canals-direct"):
        mixed = alternatives[alt_id]
        toll = mixed["toll_crossing_usd"]
        assert mixed["transits"] == 1 and mixed["waiting_days_crossing"] is None
        assert math.isclose(tce - 2 * toll / days, mixed["tce_usd_day"] - toll / mixed["days"])


def test_tc20_changes_are_taken_against_suez_with_the_owners_premium(latest: dict) -> None:
    st = analysis.suez_tanker()
    base = atlas.figures(latest["TC20"])
    first, cape = atlas.tc20_alternatives(st, base)
    suez = st["options"][0]
    assert first["kind"] == "base" and first["tce_usd_day"] == suez["tce_usd_day"]
    assert math.isclose(first["tce_below_headline"], base["engine_tce_usd_day"] - suez["tce_usd_day"])
    # The gap is the owner's Red Sea premium for the ballast transit, spread over the voyage.
    assert math.isclose(first["tce_below_headline"], first["owner_red_sea_usd"] / suez["days"], rel_tol=1e-6)
    assert math.isclose(cape["tce_change"], cape["tce_usd_day"] - suez["tce_usd_day"])


def test_td3c_options_are_costs_of_carriage_against_loading_at_ras_tanura() -> None:
    hz = analysis.hormuz()
    first, td34, transfer, waiting = atlas.td3c_alternatives(hz)
    assert first["kind"] == "base"
    assert math.isclose(first["carriage_usd_t"], first["freight_usd_t"] + first["premium_usd_t"])
    low, high = transfer["carriage_usd_t"]
    assert low < high
    assert math.isclose(transfer["shuttle_budget_usd_t"], first["carriage_usd_t"] - transfer["freight_needed_usd_t"])
    cargo = baltic.ROUTES["TD3C"].cargo_t
    assert math.isclose(transfer["shuttle_usd_t"][0], transfer["shuttle_usd_bbl"][0] * transfer["barrels"] / cargo)
    for wait in waiting["waits"]:
        assert math.isclose(wait["carriage_usd_t"], first["freight_usd_t"] + wait["total_usd_t"])
    # The shortest wait after which the transfer's low end is the cheaper way.
    above = transfer["wait_above_low"]
    assert above["carriage_usd_t"] > low
    shorter = [w for w in waiting["waits"] if w["waiting_days"] < above["days"]]
    assert all(w["carriage_usd_t"] <= low for w in shorter)
    assert td34["td3c_freight_usd_t"] == first["freight_usd_t"]
