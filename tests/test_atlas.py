"""The Map view's figures: which routes its takeaway names and in which week, what each route is headed by, and
the one rule its alternatives follow (the base first, every change against it as the two figures are shown,
premiums by payer, a toll budget where no toll is public), read from the served artifact where the words matter."""

import copy
import json
import math
from pathlib import Path

import pytest

from voyage import analysis, atlas, baltic, engine, export, pages, routemap
from voyage.words import DECIMALS, date_label

ROOT = Path(__file__).resolve().parents[1]
ATLAS = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
DETOURS = json.loads((ROOT / "data" / "detours.json").read_text(encoding="utf-8"))
ITEMS = {item["id"]: item for item in ATLAS["items"]}
MINUS = "\N{MINUS SIGN}"


@pytest.fixture(scope="module")
def latest() -> dict:
    return atlas.latest(export.presets())


def item(
    item_id: str,
    date: str,
    headline: str,
    tce: float | None,
    days: float,
    kind: str = "route",
    alternatives: list | None = None,
    cargo: float | None = 1000.0,
) -> dict:
    return {
        "id": item_id,
        "kind": kind,
        "date": date,
        "headline": headline,
        "tce_usd_day": tce,
        "days": days,
        "cargo_t": cargo,
        "alternatives": alternatives or [],
    }


def routing(alt_id: str, freight_change: float | None) -> dict:
    return {"id": alt_id, "kind": "routing", "freight_change_usd_t": freight_change}


def piece(segment) -> str:
    """One segment as the page sets it: the format's places, a true minus, a plus where the figure is signed."""
    if isinstance(segment, str):
        return segment
    if "text" in segment:
        return segment["text"]
    value = segment["value"]
    body = "{:,.{p}f}".format(abs(value), p=DECIMALS[segment["format"]])
    sign = ""
    if any(c in "123456789" for c in body):
        sign = MINUS if value < 0 else "+" if segment.get("signed") else ""
    return segment.get("prefix", "") + sign + body + segment.get("suffix", "")


def text(segments) -> str:
    return "".join(piece(s) for s in segments)


def figures(segments) -> dict:
    return {s["field"]: s["value"] for s in segments if isinstance(s, dict) and "value" in s}


def headline(latest: dict, entry: dict) -> str:
    """What heads a served item, as the export decides it; the artifact leaves it out (pages.EXPORT_ONLY)."""
    return atlas.figures(latest[entry["id"]])["headline"] if entry["kind"] == "route" else "study"


# --------------------------------------------------------------------------
# The map's week and the takeaway's picks
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


def test_picks_need_two_of_the_baltics_tces_in_the_maps_week_and_name_two_routes() -> None:
    one = [item("A", "2026-10-23", "baltic_tce", 500.0, 40.0), item("B", "2026-10-30", "baltic_tce", 100.0, 30.0)]
    with pytest.raises(atlas.TooFewTcesError):
        atlas.picks(one, "2026-10-23")
    level = [item("A", "2026-10-23", "baltic_tce", 300.0, 40.0), item("B", "2026-10-23", "baltic_tce", 300.0, 30.0)]
    chosen = atlas.picks(level, "2026-10-23")
    assert chosen["top"]["id"] != chosen["bottom"]["id"]


def preset(date: str, tce: float | None) -> dict:
    return {"date": date, "published": {"tce_usd_day": tce, "qualifier": "exact"} if tce is not None else None}


def test_the_maps_week_is_the_newest_with_two_of_the_baltics_tces() -> None:
    week, ahead = "2026-10-23", "2026-10-30"
    presets = {code: preset(week, 1000.0) for code in ("TD3C", "TD22", "TC1")}
    # A dry rate a week ahead of the tanker report does not move the map's week, nor does one tanker route's.
    presets["C3"] = preset(ahead, None)
    presets["S4A_63"] = preset(ahead, None)
    presets["TC2_37"] = preset(ahead, 900.0)
    assert atlas.map_date(presets) == week
    # Two tanker routes a week ahead are a week the takeaway can name.
    presets["TC14"] = preset(ahead, 800.0)
    assert atlas.map_date(presets) == ahead
    with pytest.raises(atlas.TooFewTcesError):
        atlas.map_date({"TD3C": preset(week, 1000.0), "C3": preset(week, None)})


def test_the_served_map_is_dated_by_its_week_and_names_same_week_figures_only(latest: dict) -> None:
    week = atlas.map_date(latest)
    takeaway = ATLAS["page"]["takeaway"]
    assert [s["text"] for s in takeaway if isinstance(s, dict) and s.get("field") == "date"] == [date_label(week)]
    # The highest and the lowest of the Baltic's round-trip TCEs of that week, and the longest round voyage.
    heads = {code: atlas.figures(latest[code]) for code in atlas.ROUTES}
    tces = {
        code: f["tce_usd_day"]
        for code, f in heads.items()
        if latest[code]["date"] == week and f["headline"] == "baltic_tce"
    }
    picked = {entry["label"]: entry["item"] for entry in ATLAS["page"]["summary"]["items"]}
    assert picked["Highest of the Baltic's"] == max(tces, key=tces.__getitem__) == "TD3C"
    assert picked["Lowest of the Baltic's"] == min(tces, key=tces.__getitem__) == "TC2_37"
    for code in (picked["Highest of the Baltic's"], picked["Lowest of the Baltic's"], picked["Longest round voyage"]):
        assert latest[code]["date"] == week
        assert code != "P7"
    shown = figures(takeaway)
    assert shown["takeaway.top"] == ITEMS["TD3C"]["tce_usd_day"]
    assert shown["takeaway.bottom"] == ITEMS["TC2_37"]["tce_usd_day"]


def test_the_artifact_holds_what_the_page_reads_and_leaves_the_exports_own_fields_out() -> None:
    assert "as_of" not in ATLAS and "view_box" not in ATLAS
    assert not {"more_one", "more_many"} & set(ATLAS["page"]["list"])
    for entry in ATLAS["items"]:
        assert not {*pages.EXPORT_ONLY, "name", "preset", "tce_basis"} & set(entry), entry["id"]
        assert "also" not in entry["row"], entry["id"]
        assert all("freight_change_usd_t" not in alt for alt in entry["alternatives"]), entry["id"]


def test_the_takeaway_is_short_and_the_summary_names_the_week_before_the_war() -> None:
    page = ATLAS["page"]
    assert len(text(page["takeaway"]).split()) <= 30
    hormuz = DETOURS["hormuz"]["levels"]
    before = next(level for level in hormuz if level["label"] == "before the war")
    top = next(entry for entry in page["summary"]["items"] if entry["label"] == "Highest of the Baltic's")
    note = text(top["note"])
    assert "USD {:,} a day of the week to 12 December 2025, before the war".format(before["tce_usd_day"]) in note
    # The multiple is written the same way wherever it appears.
    multiples = [
        s
        for s in [*page["takeaway"], *top["note"]]
        if isinstance(s, dict) and s.get("field", "").endswith("before_war_ratio")
    ]
    assert len(multiples) == 2
    assert {(s["format"], s["prefix"], s["suffix"]) for s in multiples} == {("count", "about ", " times")}
    for s in multiples:
        assert s["value"] == pytest.approx(ITEMS["TD3C"]["tce_usd_day"] / before["tce_usd_day"])


# --------------------------------------------------------------------------
# The costliest detour
# --------------------------------------------------------------------------


def test_the_costliest_detour_is_the_most_extra_freight_for_the_whole_cargo() -> None:
    items = [
        item("A", "2026-10-23", "baltic_tce", 500.0, 40.0, cargo=90000.0, alternatives=[routing("cape", 100.0)]),
        item("B", "2026-10-23", "baltic_tce", 100.0, 30.0, cargo=270000.0, alternatives=[routing("suez", 40.0)]),
        item("C", "2026-09-11", "engine_tce", 50.0, 80.0, cargo=66000.0, alternatives=[routing("x", None)]),
        item("D", "2026-10-23", "baltic_tce", 200.0, 30.0, alternatives=[{"id": "td34", "kind": "option"}]),
    ]
    chosen = atlas.picks(items, "2026-10-23")
    # 40 a tonne on 270,000 tonnes is more than 100 a tonne on 90,000: the measure is the whole cargo's.
    assert chosen["costliest"]["item"]["id"] == "B"
    assert chosen["costliest"]["extra_freight_usd"] == pytest.approx(40.0 * 270000.0)
    assert [(i["id"], alt["id"]) for i, alt in chosen["unpriced"]] == [("C", "x")]


def test_the_served_costliest_detour_is_the_maximum_over_every_routing(latest: dict) -> None:
    st, sd = analysis.suez_tanker(), analysis.suez_dry()
    measured = {}
    for code in ("P7", "TD22"):
        for alt in atlas.routing_alternatives(latest[code], atlas.figures(latest[code]))[1:]:
            measured[(code, alt["id"])] = alt["freight_change_usd_t"] * baltic.ROUTES[code].cargo_t
    cape = atlas.tc20_alternatives(st, atlas.figures(latest["TC20"]))[1]
    measured[("TC20", cape["id"])] = cape["freight_change_usd_t"] * baltic.ROUTES["TC20"].cargo_t
    study = atlas.study(sd)
    for alt in study["alternatives"]:
        measured[(study["id"], alt["id"])] = alt["freight_change_usd_t"] * study["cargo_t"]
    assert len(measured) == 7
    costliest = max(measured, key=measured.__getitem__)
    assert costliest == ("TC20", "no_suez-no_suez")
    # The extra freight a tonne to earn the base's TCE, as the engine prices it on the routing's own inputs.
    p7 = atlas.routing_alternatives(latest["P7"], atlas.figures(latest["P7"]))
    base_tce = p7[0]["tce_usd_day"]
    for alt in p7[1:]:
        inputs = atlas.patched(
            atlas.priced(latest["P7"]),
            next(
                v
                for v in latest["P7"]["routings"]
                if not v["is_preset"] and "%s-%s" % (v["laden"], v["ballast"]) == alt["id"]
            )["patch"],
        )
        needed = engine.freight_for_tce(inputs, base_tce)["usd_t"]
        assert math.isclose(alt["freight_change_usd_t"], needed - latest["P7"]["inputs"]["freight_value"], rel_tol=1e-9)
    detour = next(entry for entry in ATLAS["page"]["summary"]["items"] if entry["label"] == "Costliest detour")
    assert detour["item"] == "TC20"
    value, note = text(detour["value"]), text(detour["note"])
    # Led by the measure and its qualifier; the days and the figure a tonne in the note, as the panel shows them.
    assert value == "TC20 round the Cape, USD 11.61 million more freight, before Suez tolls"
    # The figure the pick is made on, the same as the Detours view's for the whole cargo.
    whole = DETOURS["suez_tanker"]["cape_vs_suez"]["extra_freight_lump_sum_usd"]
    assert figures(detour["value"])["summary.detour.freight_usd"] * 1e6 == pytest.approx(whole)
    assert whole == pytest.approx(cape["freight_change_usd_t"] * 90000.0)
    per_t = round(cape["freight_change_usd_t"], 2)
    assert note == (
        "31.5 more days, and USD %.2f a tonne more freight than by Suez both ways to earn as much, "
        "if war cover can be placed." % per_t
    )
    # The figure a tonne is not set out as a sum with the cargo, whose product would miss the whole cargo's figure.
    assert "tonnes" not in note


# --------------------------------------------------------------------------
# What heads each route, and how the list reads it
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


def test_the_baltics_qualifier_is_read_before_its_figure_and_only_s4a_keeps_a_line_under_it(latest: dict) -> None:
    for entry in ATLAS["items"]:
        figure = entry["row"]["tce"][0]
        if entry["id"] == "S4A_63":
            assert entry["row"]["qualifier"] == "trip hire, gross"
            continue
        assert entry["row"]["qualifier"] == ""
        if headline(latest, entry) == "baltic_tce":
            qualifier = latest[entry["id"]]["published"]["qualifier"]
            assert figure.get("prefix", "") == pages.QUALIFIER_WORDS[qualifier]
    assert text(ITEMS["TD25"]["row"]["tce"]) == "just under 197,000"


def test_the_map_figures_carry_no_currency_and_an_older_rate_carries_its_date() -> None:
    for entry in ATLAS["items"]:
        for segment in entry["figure"] or []:
            if isinstance(segment, dict):
                assert "USD" not in segment.get("prefix", "")
    p7 = [s for s in ITEMS["P7"]["figure"] if isinstance(s, dict) and "text" in s]
    assert p7 and p7[0]["text"] == "11 Sep"


def test_the_table_dates_an_older_rate_and_names_the_owners_costs_on_a_trip(latest: dict) -> None:
    assert text(ATLAS["page"]["table"]["caption"]).endswith("unless the row says otherwise.")
    week = atlas.map_date(latest)
    for entry in ATLAS["items"]:
        if entry["kind"] != "route":
            continue
        cell = text(entry["table"]["tce"])
        assert cell.endswith(", rate of 11 September 2026") == (latest[entry["id"]]["date"] != week), entry["id"]
    assert text(ITEMS["P7"]["table"]["tce"]) == "USD 37,999, the engine's, net, rate of 11 September 2026"
    s4a = ITEMS["S4A_63"]["table"]
    assert text(s4a["costs"]).endswith(", the owner's")
    assert text(s4a["breakeven"]).endswith(" a day of hire, covering the owner's costs")


def test_a_tanker_week_whose_report_printed_no_tce_says_the_engines_estimate_stands_in(latest: dict) -> None:
    st = analysis.suez_tanker()
    week = atlas.map_date(latest)
    no_tce = copy.deepcopy(latest["TC20"])
    no_tce["published"] = None
    f = atlas.figures(no_tce)
    assert f["headline"] == "engine_tce" and f["tce_usd_day"] == f["engine_tce_usd_day"]
    legs = [no_tce["legs"]["laden"]["key"], no_tce["legs"]["ballast"]["key"]]
    alternatives = atlas.tc20_alternatives(st, f)
    entry = {
        "preset": no_tce,
        "figures": f,
        "alternatives": alternatives,
        "geometry": atlas.item_geometry(legs, alternatives, routemap.atlas_document(week)),
        "passes": (atlas.ordered_passes(legs[0]), atlas.ordered_passes(legs[1])),
        "same_water": [],
    }
    served = pages._route_item(entry, st, week)
    note = text(served["facts"][0]["note"])
    assert "report for the week to 23 October 2026 printed no TCE for this route" in note
    assert "the engine's estimate stands in" in note
    assert "publishes no TCE" not in note
    assert text(served["row"]["note"]).startswith("No Baltic TCE printed this week")
    # The list's heading follows what the rows show.
    rows = [{**ITEMS[code], "headline": headline(latest, ITEMS[code])} for code in ("TC2_37", "TC14", "TC1", "TC5")]
    rows.append(served)
    clean = next(group for group in pages._groups(rows) if group["id"] == "clean")
    assert clean["name"] == "Clean tankers: the Baltic's TCE, and the engine's estimate for TC20"
    served_groups = {group["id"]: group["name"] for group in ATLAS["page"]["groups"]}
    assert served_groups["clean"] == "Clean tankers: the Baltic's TCE"
    assert served_groups["dry"] == "Dry bulk: the engine's estimates, and the Baltic's hire for S4A"


def unprinted(latest: dict, code: str) -> tuple[dict, dict]:
    """A route as the export serves it in a week whose report printed no TCE for it, and its figures."""
    week = atlas.map_date(latest)
    preset = copy.deepcopy(latest[code])
    preset["published"] = None
    f = atlas.figures(preset)
    alternatives = atlas.routing_alternatives(preset, f) if code in atlas.ROUTING_ORDER else []
    legs = [preset["legs"]["laden"]["key"], preset["legs"]["ballast"]["key"]]
    entry = {
        "preset": preset,
        "figures": f,
        "alternatives": alternatives,
        "geometry": atlas.item_geometry(legs, alternatives, routemap.atlas_document(week)),
        "passes": (atlas.ordered_passes(legs[0]), atlas.ordered_passes(legs[1])),
        "same_water": [],
    }
    return pages._route_item(entry, analysis.suez_tanker(), week), f


def test_a_worldscale_week_with_no_printed_tce_shows_no_figure_and_says_so(latest: dict) -> None:
    served, f = unprinted(latest, "TC2_37")
    # The engine cannot price a rate in Worldscale points, so there is no estimate to stand in.
    assert f["headline"] == "engine_tce" and f["tce_usd_day"] is None
    assert served["row"]["tce"][0]["missing"] == "no TCE printed"
    rows = [{**ITEMS[code], "headline": headline(latest, ITEMS[code])} for code in ("TC14", "TC1", "TC5", "TC20")]
    rows.append(served)
    clean = next(group for group in pages._groups(rows) if group["id"] == "clean")
    assert clean["name"] == "Clean tankers: the Baltic's TCE, and no TCE printed for TC2"
    for words in (pages.KEY_BASIS, pages.CAPTION_BASIS):
        assert "TC2: no TCE printed this week." in pages._basis_sentences(rows, words)
        assert "engine's estimate" not in pages._basis_sentences(rows, words)
    method = text(ATLAS["page"]["method"][1])
    assert (
        "the engine's estimate in its place where the rate is a lump sum, and no figure where the rate is in " in method
    )


def test_a_lump_sum_week_with_no_printed_tce_sets_the_routing_against_the_figure_shown(latest: dict) -> None:
    served, f = unprinted(latest, "TD22")
    assert f["headline"] == "engine_tce" and f["tce_usd_day"] == f["engine_tce_usd_day"]
    base = text(served["alternatives"][0]["text"])
    assert base.endswith("before port charges: the figure the other routing is set against.")
    assert "not the Baltic's" not in base and "no figure" not in base
    # The row shows the engine's figure, the base itself: the line has no other base to name.
    line = text(served["row"]["alts"][0])
    assert line == "Back by Suez: " + MINUS + "3.4 days, USD 7,270 a day higher, before Suez tolls"


def test_no_worldscale_route_shows_a_derived_dollar_freight_beside_its_points() -> None:
    for entry in ATLAS["items"]:
        if entry["kind"] != "route":
            continue
        fields = {
            s.get("field") for fact in entry["facts"] for s in fact["value"] + fact["note"] if isinstance(s, dict)
        }
        assert "freight_at_published_usd_t" not in fields


def test_the_detour_study_is_not_counted_as_a_route_and_has_a_name_without_a_comma() -> None:
    routes = [entry for entry in ATLAS["items"] if entry["kind"] == "route"]
    counts = {f["id"]: f["announce"][0]["value"] for f in ATLAS["page"]["filters"]}
    assert counts["all"] == len(routes) == 14
    assert counts["dry"] == sum(1 for entry in routes if entry["segment"] == "dry") == 4
    assert ATLAS["page"]["list"]["study_head"] == {"route": "Study", "tce": "Freight, USD a tonne", "days": "Days"}
    study = ITEMS[atlas.STUDY_ID]
    assert "," not in study["label"]
    assert text(study["readout"]).startswith(study["label"] + ", ")


# --------------------------------------------------------------------------
# The alternatives' rule
# --------------------------------------------------------------------------


def test_every_alternatives_list_opens_with_its_base() -> None:
    for entry in ATLAS["items"]:
        if entry["alternatives"]:
            assert entry["alternatives"][0]["kind"] == "base"
            assert entry["alternatives"][0]["legs"] == []
            assert all(alt["kind"] != "base" for alt in entry["alternatives"][1:])


def test_every_alternative_has_one_line_by_one_rule() -> None:
    for entry in ATLAS["items"]:
        others = [alt for alt in entry["alternatives"] if alt["kind"] != "base"]
        lines = entry["row"]["alts"]
        assert len(lines) == len(others), entry["id"]
        for alt, line in zip(others, lines, strict=True):
            words = text(line)
            # '<name>: <days> days, <an unsigned change and its word>[ than <base> (<figure>)], <qualifier>'.
            assert words.startswith(alt["short"] + ": "), words
            assert "USD +" not in words and "USD " + MINUS not in words, words
            assert any(w in words for w in (" more", " less", " higher", " lower")), words
            # The qualifier that decides the change is never dropped, however long the line.
            qualifier = pages.ALT_QUALIFIERS[(entry["id"], alt["id"])]
            assert not qualifier or words.endswith(", " + qualifier), words
            if alt["legs"]:
                # Named on the map by its days alone, which are against the route's own.
                days = [s for s in line if isinstance(s, dict) and s.get("field", "").endswith(".days_change")]
                assert alt["map_label"] == [alt["short"] + ": ", *days], entry["id"]
            else:
                assert alt["map_label"] is None
    assert ITEMS["C3"]["row"]["alts"] == []
    assert [text(line) for line in ITEMS["P7"]["row"]["alts"]] == [
        "Round the Cape: +32.9 days, USD 16,756 a day lower, before Panama tolls and waiting",
        "Back round the Cape: +16.1 days, USD 9,447 a day lower, before Panama tolls",
        "Laden round the Cape: +16.7 days, USD 9,972 a day lower, before Panama tolls",
    ]
    assert text(ITEMS["TC20"]["alternatives"][1]["map_label"]) == "Round the Cape: +31.5 days"


def test_a_line_names_its_base_where_the_row_shows_another_figure() -> None:
    # TC20 and TD22: the Baltic's TCE heads the row, and the routing is set against the engine's.
    tc20, td22 = text(ITEMS["TC20"]["row"]["alts"][0]), text(ITEMS["TD22"]["row"]["alts"][0])
    assert tc20 == "Round the Cape: +31.5 days, USD 132,196 a day lower than by Suez (342,369), before Suez tolls"
    assert td22 == (
        "Back by Suez: " + MINUS + "3.4 days, USD 7,270 a day higher than the engine's TCE (463,639), before Suez tolls"
    )
    for code in ("TC20", "TD22"):
        base = figures(ITEMS[code]["alternatives"][0]["text"])["alternatives.base.tce_usd_day"]
        assert figures(ITEMS[code]["row"]["alts"][0])["alternatives.base.tce_usd_day"] == base
        assert round(base) != round(ITEMS[code]["tce_usd_day"])
    # TD3C's row is a TCE a day: TD34, another cargo, is set against it; the transfer and the waits are costs of
    # carriage against loading at Ras Tanura, named with its figure, the transfer on the basis it is priced at.
    td34, transfer, waiting = (text(line) for line in ITEMS["TD3C"]["row"]["alts"])
    assert td34 == "TD34: " + MINUS + "4.8 days, USD 631,264 a day lower, another cargo, loading outside the strait"
    assert round(ITEMS["TD3C"]["tce_usd_day"] - ITEMS["TD34"]["tce_usd_day"]) == 631264
    assert transfer == (
        "Fujairah transfer: " + MINUS + "2.7 days, USD 60.78 to 90.41 a tonne more to carry than at Ras Tanura "
        "(285.00), the export VLCC at TD3C's TCE"
    )
    assert waiting.endswith("a tonne more to carry than with no wait (285.00)")
    assert "USD 631,264 a day lower than TD3C's" in text(ITEMS["TD3C"]["alternatives"][1]["text"])
    # The study's row is the freight that earns the P4 hire: its lines are freight too, as its panel gives them.
    cape, panama = (text(line) for line in ITEMS[atlas.STUDY_ID]["row"]["alts"])
    assert cape == "Round the Cape: +10.7 days, USD 7.07 a tonne more freight, before Suez tolls"
    assert panama == "By Panama: +8.6 days, USD 5.53 a tonne more freight, before tolls and waiting"
    assert "USD 7.07 a tonne more than by Suez" in text(ITEMS[atlas.STUDY_ID]["alternatives"][1]["text"])
    # P7's row is its base, the engine's TCE by Panama both ways: no base to name.
    assert ITEMS["P7"]["tce_usd_day"] == pytest.approx(
        figures(ITEMS["P7"]["alternatives"][0]["text"])["alternatives.base.tce_usd_day"]
    )
    assert all(" than " not in text(line) for line in ITEMS["P7"]["row"]["alts"])


def test_shown_changes_are_the_differences_of_the_figures_as_shown() -> None:
    assert pages._shown(0.125, "usd_t") == 0.13  # a half away from zero, as format.js rounds
    # A tie in the shortest decimal is a tie, as Intl.NumberFormat reads it, not the binary value just under it.
    assert pages._shown(2.675, "usd_t") == 2.68 and pages._shown(1.005, "usd_t") == 1.01
    td22 = ITEMS["TD22"]
    base, suez = td22["alternatives"]
    days = figures(suez["text"])
    shown_base = figures(base["text"])
    assert round(days["alternatives.no_canals_no_sunda-no_panama.days_change"], 1) == pytest.approx(
        round(days["alternatives.no_canals_no_sunda-no_panama.days"], 1)
        - round(shown_base["alternatives.base.days"], 1)
    )
    assert "107.7 days (" + MINUS + "3.4)" in text(suez["text"])
    for entry in ATLAS["items"]:
        for alt in entry["alternatives"]:
            for segment in alt["text"]:
                if isinstance(segment, dict) and segment.get("field", "").endswith(".days_change"):
                    shown = segment["value"]
                    assert round(shown, 1) == pytest.approx(shown, abs=1e-9), (entry["id"], alt["id"])


def test_the_map_and_detours_give_a_detour_the_same_days() -> None:
    # Both views take a detour's days from the two days they show, so the study's Cape reads the same on both.
    study = text(ITEMS[atlas.STUDY_ID]["alternatives"][1]["text"])
    rows = {row["label"]: row["detail"] for row in DETOURS["page"]["chart"]["rows"]}
    assert study.startswith("45.9 days (+10.7)")
    assert rows["Cape of Good Hope instead of Suez"] == "10.7 more days"
    assert rows["Cape of Good Hope instead of Suez, before Suez tolls"].startswith("31.5 more days")


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
    # Back by Suez enters a listed area the base does not: the crew war bonus is left out there.
    assert suez["war_area"] and not base["war_area"]
    assert pages.CREW_BONUS in text(ITEMS["TD22"]["alternatives"][1]["text"])


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
    # The Panama waits are named by the report they were read in.
    words = text(ITEMS["P7"]["alternatives"][1]["text"])
    assert "(Platts, republished by Hellenic Shipping News on 16 April 2026)" in words


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


def test_tc20_round_the_cape_carries_the_detours_toll_scale_and_war_cover() -> None:
    words = text(ITEMS["TC20"]["alternatives"][1]["text"])
    detours = text(DETOURS["page"]["suez_tanker"]["lead"])
    both = pages.suez_toll_and_cover()
    assert both in words and both in detours
    assert "If war cover can be placed, Suez stays the better way" in words
    # Each report is dated and named with the publication it was read in.
    assert "(Korea JoongAng Daily, republished by Hellenic Shipping News on 23 July 2026)" in both
    assert "(Windward, republished by Hellenic Shipping News on 30 July 2026)" in both


def test_td3c_options_are_costs_of_carriage_against_loading_at_ras_tanura() -> None:
    hz = analysis.hormuz()
    first, td34, transfer, waiting = atlas.td3c_alternatives(hz)
    assert first["kind"] == "base"
    assert math.isclose(first["carriage_usd_t"], first["freight_usd_t"] + first["premium_usd_t"])
    low, high = transfer["carriage_usd_t"]
    assert low < high
    cargo = baltic.ROUTES["TD3C"].cargo_t
    assert math.isclose(transfer["shuttle_usd_t"][0], transfer["shuttle_usd_bbl"][0] * transfer["barrels"] / cargo)
    for wait in waiting["waits"]:
        # The base already pays one period: a wait's change is its cost of carriage less the base's.
        assert math.isclose(wait["change_usd_t"], wait["carriage_usd_t"] - first["carriage_usd_t"])
        assert math.isclose(
            wait["carriage_usd_t"], first["freight_usd_t"] + wait["charterer_usd_t"] + wait["owner_usd_t"]
        )
    # The shortest wait after which the transfer's low end is the cheaper way.
    above = transfer["wait_above_low"]
    assert above["carriage_usd_t"] > low
    shorter = [w for w in waiting["waits"] if w["waiting_days"] < above["days"]]
    assert all(w["carriage_usd_t"] <= low for w in shorter)
    assert td34["td3c_freight_usd_t"] == first["freight_usd_t"]
    # No verdict on the shuttle: the export leg is priced at TD3C's TCE of the week, as on Detours.
    assert "shuttle_budget_usd_t" not in transfer
    assert transfer["tce_usd_day"] == hz["levels"][-1]["tce_usd_day"]


def test_td3c_prints_each_waits_change_as_its_carriage_less_the_bases() -> None:
    td3c = ITEMS["TD3C"]
    base, _, _, waiting = td3c["alternatives"]
    shown = {**figures(base["text"]), **figures(waiting["text"])}
    base_carriage = round(shown["alternatives.base.carriage_usd_t"], 2)
    for wait in ("wait_5", "wait_10", "wait_20"):
        change = shown["alternatives.waiting.%s.change_usd_t" % wait]
        carriage = round(shown["alternatives.waiting.%s.carriage_usd_t" % wait], 2)
        assert round(change, 2) == pytest.approx(carriage - base_carriage)
    words = text(waiting["text"])
    assert "USD 68.57, 137.15 or 230.69 a tonne more than loading with no wait" in words
    for wrong in ("112.19", "180.76", "274.31"):
        assert wrong not in json.dumps(td3c)
    assert "already pays one period" in words
    assert "one seven-day period of premium" in text(base["text"])


def test_the_transfer_states_its_basis_and_draws_no_verdict() -> None:
    words = text(ITEMS["TD3C"]["alternatives"][2]["text"])
    assert "priced at TD3C's TCE of the week as on the Detours view" in words
    # Each report by its author, the publication it was read in and its day, as the Detours view cites them.
    for report in (
        "(The Wall Street Journal via ChosunBiz, republished by Hellenic Shipping News on 21 September 2026)",
        "(Windward, republished by Hellenic Shipping News on 12 October 2026)",
    ):
        assert report in words and report in text(DETOURS["page"]["hormuz"]["chain"])
    assert "(Windward, republished by Hellenic Shipping News on 30 July 2026)" in words
    assert "any war risk premium off Fujairah, in the Gulf of Oman, has no dated rate and is left out" in words
    assert "after a wait of 5 days" in words
    served = json.dumps(ATLAS)
    assert "57.73" not in served and "shuttle_budget" not in served and "only if the shuttle" not in served
    td34_left_out = text(next(fact for fact in ITEMS["TD34"]["facts"] if fact["id"] == "left_out")["value"])
    assert "any war risk premium off Mina Al Fahal, in the Gulf of Oman (no dated rate found)" in td34_left_out


# --------------------------------------------------------------------------
# Sources, what is left out, and the words a desk reads first
# --------------------------------------------------------------------------


def test_the_study_names_the_sources_its_case_is_priced_on() -> None:
    sd = analysis.suez_dry()
    case = atlas.study_case(sd)
    inputs, _ = analysis.one_way(case)
    inputs = analysis._with_war(inputs, "red_sea", analysis._rate(atlas.RED_SEA_RATE_ID)["low"])
    # The case rebuilt here is the one the study is priced on: it needs the same freight for the P4 hire.
    suez = next(o for o in sd["options"] if o["name"] == "Suez")
    assert engine.freight_for_tce(inputs, sd["target_tce_usd_day"])["usd_t"] == pytest.approx(
        suez["freight_for_target_usd_t"]
    )
    source = text(ITEMS[atlas.STUDY_ID]["source"])
    for key in ("prices.vlsfo_usd_t", "ets.eua_eur_t", "ets.usd_per_eur"):
        assert case.sources[key]["source"] in source
    assert "at Singapore" in source
    assert "Panama waits: Platts, republished by Hellenic Shipping News on 16 April 2026." in source


def test_the_crew_war_bonus_is_left_out_on_every_route_through_a_listed_area() -> None:
    through = {"TD3C", "TC1", "TC5", "TC20", "TD34", atlas.STUDY_ID}
    for entry in ATLAS["items"]:
        left_out = text(next(fact for fact in entry["facts"] if fact["id"] == "left_out")["value"])
        assert ("the crew war bonus" in left_out) == (entry["id"] in through), entry["id"]


def test_the_tce_note_is_one_dated_line_and_the_method_carries_the_basis(latest: dict) -> None:
    for entry in ATLAS["items"]:
        if headline(latest, entry) != "baltic_tce":
            continue
        note = text(entry["facts"][0]["note"])
        assert note.startswith("The Baltic's round-trip TCE for the week to ")
        assert note.count(". ") == 0 and note.endswith(".")
    method = " ".join(text(paragraph) for paragraph in ATLAS["page"]["method"])
    assert "before port charges, fuel in port, and canal tolls and time" in method
    assert "appendix 3" in method and "before the additional war risk premium" in method
    assert "the study's choices" in method and "C3's bunkers at Singapore" in method


def test_the_words_a_desk_reads_first() -> None:
    page = ATLAS["page"]
    caption = text(page["list"]["caption"])
    assert len(caption.split()) <= 40
    assert caption.endswith(" Days: the round voyage, unless the row says otherwise.")
    # The facts after the routings are headed by what they are: a trip time charter has hire, not freight.
    assert ITEMS["S4A_63"]["more"] == "Hire and costs" and ITEMS["TD3C"]["more"] == "Freight and costs"
    assert "more" not in page["panel"]
    # On a phone the map's heading and the line under it are one line each, and promise no figure.
    assert page["map"]["title_narrow"] == "Every route, from its loading port"
    assert page["map"]["idle_narrow"] == "Pick a route in the list below."
    assert page["filters"][0]["label"] == "All"
    assert text(page["filters"][0]["announce"]).endswith(" on the map and in the list: every route.")
    # The key under the map is short sentences, every one dated or naming whose figure it is.
    sentences = text(page["map"]["labels"]).split(". ")
    assert len(sentences) >= 4 and all(len(sentence.split()) <= 20 for sentence in sentences)
    served = json.dumps(ATLAS)
    assert "a tonne fixed" not in served
    assert ITEMS["TD3C"]["map_title"].endswith(", and three other options")
    assert ITEMS["P7"]["map_title"].endswith(", and three other ways to sail it")
