"""The Map view's figures: every route the study prices, at its latest dated week, and the routings it could take.

Each route is priced on the preset the calculator opens for it (its latest
dated rate): the engine gives the days, the distances, the voyage costs and
the freight that covers them for every route, and the TCE where the rate is in
dollars. A rate in Worldscale points has no dollar value without the licensed
flat rate, so for those tanker routes the TCE shown is the Baltic's own, which
the weekly report prints beside the rate; the engine's figure is shown beside
the Baltic's only where both exist for the same week (TD22 and TC20). The two
are different calculations: the Baltic's is after the port and canal costs it
deducts (Guide to Market Benchmarks, appendix 3), the engine's before port
charges and canal tolls, which have no public per call figure. S4A, a trip
time charter, is shown at the Baltic's hire; the owner's round trip with the
ballast back unpaid is a what-if beside it, not its figure.

The map's week is the newest date on which at least two of its routes carry a
TCE the Baltic printed: the dry rates and the tanker report come out on their
own days, so one route's rate can run ahead of the others, and the takeaway
names the highest and the lowest of the Baltic's TCEs in that week.

The alternatives follow one rule. Each list opens with the base routing on
the alternatives' own basis, and every change is taken against that base. A
war risk premium is priced by who pays it: the owner's comes off the TCE, the
charterer's is a cost of carriage beside the freight. A tanker's canal transit
takes the days a transit the guide gives TC20 (two days for its two Suez
transits). Where a toll has no public figure, the comparison is the toll at
which the two routings earn the same, not a TCE before the toll. Every
routing also carries the freight a tonne it needs on top of its base's to
earn the base's TCE, the one measure the costliest detour is picked on. The
routings and options are the ones the study already computes: the
calculator's leg routings (P7, TD22), the Suez and Cape comparison of the
Detours view for TC20, its Hormuz options for TD3C, and the Panamax trip from
Asia to Europe, a detour study rather than a Baltic route. The words for
every figure are written in pages.atlas_page.
"""

from __future__ import annotations

import copy
import itertools
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from . import analysis, baltic, cases, engine, routemap, sea_routes

#: The routes on the map, in the calculator's order.
ROUTES: tuple[str, ...] = (*baltic.STUDY_ROUTES, "TC20", "TD34")
#: The detour study drawn beside the routes: the Panamax one way from Qingdao to Rotterdam.
STUDY_ID = "QD_RTM_PMX"
#: The Hormuz rate the Detours view prices the Gulf premium at (Marsh, 22 July 2026, its low end).
GULF_RATE_ID = "hormuz_2026_07_22"
#: The Red Sea rate the Detours view prices a transit of Bab el Mandeb at (Marsh, 22 July 2026).
RED_SEA_RATE_ID = "bab_el_mandeb_2026_07"
#: The study's rate for each listed area a routing passes.
AREA_RATES: Mapping[str, str] = {"gulf": GULF_RATE_ID, "red_sea": RED_SEA_RATE_ID}
#: The route whose guide description sets a tanker's days in a canal: TC20's, two days for its two Suez transits.
CANAL_DAYS_ROUTE = "TC20"
#: Two alternatives' names closer than this on the map, in map units, are written once.
LABEL_APART = 24.0
#: Passages no choice in the study turns on: every routing of a route sails them alike, so the map does not name them.
QUIET_PASSAGES = ("Dover Strait", "Florida Strait", "Yucatan Channel", "Strait of Gibraltar")
#: Two routes sail the same water when this share of one's laden line lies within SAME_WATER_UNITS of the other's.
SAME_WATER_SHARE = 0.5
SAME_WATER_UNITS = 2.5
#: The other leg routings each route lists, the one a desk would weigh first at the top. TD22 lists only the
#: way back by Suez: the study routes its laden VLCC by Malacca rather than the shallower Sunda Strait
#: (baltic.ROUTES["TD22"].notes), so a routing laden by Sunda is not one it would weigh.
ROUTING_ORDER: Mapping[str, tuple[str, ...]] = {
    "P7": ("no_canals-no_canals", "direct-no_canals", "no_canals-direct"),
    "TD22": ("no_canals_no_sunda-no_panama",),
}
#: The barrels in a VLCC cargo, which make the shuttle's cost a barrel a cost a tonne, as on Detours (Windward,
#: republished by Hellenic Shipping News on 30 July 2026).
VLCC_BARRELS_ID = "vlcc_barrels_2026_07_30"
#: The fewest of the Baltic's TCEs a week needs for the map: its highest and its lowest are two routes.
TCES_A_WEEK = 2


class TooFewTcesError(ValueError):
    """Fewer than two of the Baltic's TCEs share a date, so the map has no highest and lowest to name that week."""


class MixedWeeksError(ValueError):
    """TD3C's figure and the Hormuz study its options are priced at, TD34's TCE among them, are of different weeks."""


def latest(preset_list: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """The preset the calculator opens for each route: its latest date, a latest preset before an anchor of that day."""
    out: dict[str, Mapping[str, Any]] = {}
    for preset in preset_list:
        code = preset["route"]
        best = out.get(code)
        rank = (preset["date"], preset["kind"] == "latest")
        if best is None or rank > (best["date"], best["kind"] == "latest"):
            out[code] = preset
    return out


def map_date(presets: Mapping[str, Mapping[str, Any]]) -> str:
    """The map's week: the newest date on which at least two of the map's routes carry a TCE the Baltic printed.

    `presets` is each route's latest preset (latest()). A dry rate or one
    tanker route's report a week ahead of the rest does not move the map's
    week, so the takeaway always has a highest and a lowest TCE to name.
    """
    counts = Counter(
        preset["date"]
        for code, preset in presets.items()
        if code in ROUTES and preset["published"] and preset["published"]["tce_usd_day"] is not None
    )
    dates = [date for date, count in counts.items() if count >= TCES_A_WEEK]
    if not dates:
        raise TooFewTcesError("no date has two of the Baltic's TCEs on the map's routes: %s" % dict(counts))
    return max(dates)


def war_area(inputs: Mapping[str, Any], load: str) -> bool:
    """True if a voyage passes a listed war risk area, or loads in the Gulf of Oman, which the crews' Warlike
    Operations Area takes in (the crew war bonus applies there, though no dated premium was found)."""
    areas = inputs["war_risk"]["areas"]
    return load in cases.GULF_OF_OMAN or any(
        areas[area]["entries"] or areas[area]["ballast_transits"] for area in AREA_RATES
    )


def priced(preset: Mapping[str, Any]) -> dict[str, Any]:
    """The inputs the engine can price: a Worldscale rate with no flat rate is set to nothing a tonne.

    The days, the distances, the voyage costs and the freight that covers them
    do not depend on the freight, so they are the voyage's own either way.
    """
    inputs = dict(preset["inputs"])
    if not preset["evaluable"]:
        inputs.update(freight_basis="usd_t", freight_value=0.0)
    return inputs


def patched(inputs: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of the inputs with dotted paths set, as a routing variant's patch sets them."""
    out = copy.deepcopy(dict(inputs))
    for path, value in patch.items():
        node = out
        keys = path.split(".")
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = copy.deepcopy(value)
    return out


def day_split(result: Mapping[str, Any]) -> dict[str, float]:
    days = result["days"]
    return {
        "total": days["total"],
        "ballast": days["ballast_sea"],
        "laden": days["laden_sea"],
        "port": days["port_total"],
    }


def gulf_premium(inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    """The charterer's Gulf premium on a voyage loading inside the Gulf, at the Detours view's rate; None outside it."""
    if not inputs["war_risk"]["areas"]["gulf"]["entries"]:
        return None
    rate = analysis._rate(GULF_RATE_ID)
    hull = inputs["war_risk"]["hull_value_usd"]
    if not hull:
        return {"premium_pct": rate["low"], "source_id": rate["id"], "hull_value_usd": None}
    gulf = engine.evaluate(analysis._with_war(dict(inputs), "gulf", rate["low"]))["war_risk"]["areas"]["gulf"]
    return {
        "premium_pct": rate["low"],
        "source_id": rate["id"],
        "hull_value_usd": hull,
        "days_inside": gulf["days"],
        "periods": gulf["periods"],
        "premium_usd": gulf["usd"],
        "per_tonne_usd": gulf["usd"] / inputs["cargo_t"],
        "per_period_usd_t": gulf["usd"] / gulf["periods"] / inputs["cargo_t"],
    }


def figures(preset: Mapping[str, Any]) -> dict[str, Any]:
    """The engine's figures for a preset, and the figure the map heads the route with.

    The headline is the Baltic's TCE where the weekly report prints one, the
    Baltic's hire on a trip time charter (S4A), and the engine's estimate
    otherwise. On a trip the engine's own figure is the owner's TCE over the
    round trip with the ballast back unpaid: a what-if, net of commission.
    """
    inputs = priced(preset)
    result = engine.evaluate(inputs)
    zero = engine.freight_for_tce(inputs, 0.0)
    published = preset["published"]
    engine_tce = result["tce_usd_day"] if preset["evaluable"] else None
    trip = inputs["contract"] == "trip"
    costs = result["costs"]
    net = 1.0 - inputs["commission_pct"] / engine.PERCENT
    if published:
        headline, tce = "baltic_tce", published["tce_usd_day"]
    elif trip:
        headline, tce = "baltic_hire", inputs["freight_value"]
    else:
        headline, tce = "engine_tce", engine_tce
    out: dict[str, Any] = {
        "headline": headline,
        "engine_tce_usd_day": engine_tce,
        "published_tce_usd_day": published["tce_usd_day"] if published else None,
        "published_qualifier": published["qualifier"] if published else None,
        "tce_usd_day": tce,
        "tce_basis": "engine" if headline == "engine_tce" else "baltic",
        "commission_pct": inputs["commission_pct"],
        "days": day_split(result),
        "laden_nm": inputs["laden"]["distance_nm"],
        "ballast_nm": inputs["ballast"]["distance_nm"],
        "eca_nm": inputs["laden"]["eca_nm"] + inputs["ballast"]["eca_nm"],
        "breakeven_usd_t": zero["usd_t"],
        "breakeven_lump_sum_usd": zero["lump_sum_usd"],
        "breakeven_hire_usd_day": zero["hire_usd_day"],
        "freight_usd_t": None if trip or not preset["evaluable"] else engine.freight_usd_t(inputs),
        "bunkers_usd": costs["bunkers"],
        "ets_usd": costs["ets"],
        "costs_usd": costs["total_usd"],
        "costs_per_day_usd": costs["total_usd"] / result["days"]["total"],
        "trip_hire_usd_day": inputs["freight_value"] if trip else None,
        "trip_hire_net_usd_day": inputs["freight_value"] * net if trip else None,
        "trip_days": result["days"]["trip"] if trip else None,
        "round_trip_gross_usd_day": engine_tce / net if trip and engine_tce is not None else None,
        "charterer_costs_usd": result["charterer_costs_usd"] if trip else None,
        "gulf_war_risk": gulf_premium(inputs),
        "war_area": war_area(inputs, preset["legs"]["laden"]["from"]),
    }
    out["eca_share"] = out["eca_nm"] / (out["laden_nm"] + out["ballast_nm"])
    return out


def picks(items: Sequence[Mapping[str, Any]], on_date: str) -> dict[str, Any]:
    """What the page's takeaway and summary name: the highest and the lowest of the Baltic's TCEs, the longest
    round voyage, and the costliest detour.

    Only routes priced on the map's own date take part in the first three, so
    a figure of an earlier week (P7's) is never set beside them, and only
    round-voyage TCEs the Baltic prints: a trip hire is not one, and the
    engine's estimates are not the Baltic's. The highest and the lowest are two
    routes even when two print the same figure.

    The costliest detour is taken over every routing alternative on one money
    measure: the extra freight the whole cargo needs, on top of its base
    routing's, to earn the base's TCE (the extra a tonne times the item's
    cargo). An alternative without that figure cannot be set on the measure:
    it is returned under "unpriced", for the page to say so.
    """
    same_day = [i for i in items if i["kind"] == "route" and i["date"] == on_date]
    tces = sorted((i for i in same_day if i["headline"] == "baltic_tce"), key=lambda i: -i["tce_usd_day"])
    if len(tces) < TCES_A_WEEK:
        raise TooFewTcesError("%d of the Baltic's TCEs on %s, two needed" % (len(tces), on_date))
    measured: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    unpriced: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for i in items:
        for alt in i["alternatives"]:
            if alt["kind"] == "routing":
                on_measure = alt["freight_change_usd_t"] is not None and i["cargo_t"]
                (measured if on_measure else unpriced).append((i, alt))
    costliest = max(measured, key=lambda pair: pair[1]["freight_change_usd_t"] * pair[0]["cargo_t"], default=None)
    return {
        "top": tces[0],
        "bottom": min(tces[1:], key=lambda i: i["tce_usd_day"]),
        "longest": max(same_day, key=lambda i: i["days"]),
        "costliest": {
            "item": costliest[0],
            "alternative": costliest[1],
            "extra_freight_usd": costliest[1]["freight_change_usd_t"] * costliest[0]["cargo_t"],
        }
        if costliest
        else None,
        "unpriced": unpriced,
    }


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------


def transits(route: baltic.Route, laden: str, ballast: str) -> int:
    """How many of a round voyage's two legs pass a canal under these routings."""
    return cases.canal_transits(
        cases.leg_record(route.load, route.discharge, laden)["passes"],
        cases.leg_record(route.discharge, route.load, ballast)["passes"],
    )


def canal_days_a_transit() -> float:
    """A tanker's days in a canal transit: TC20's description gives two days for its two Suez transits."""
    route = baltic.ROUTES[CANAL_DAYS_ROUTE]
    return (route.canal_days or 0.0) / transits(route, route.laden_routing, route.ballast_routing)


def with_premiums(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The inputs with the study's rate in every listed area the routing passes; the engine charges each premium
    to its payer, so the owner's (a ballast transit) comes off the TCE and the charterer's does not."""
    out = dict(inputs)
    for area, rate_id in AREA_RATES.items():
        listed = inputs["war_risk"]["areas"][area]
        if listed["entries"] or listed["ballast_transits"]:
            out = analysis._with_war(out, area, analysis._rate(rate_id)["low"])
    return out


def toll_crossing(
    base_tce: float, base_days: float, base_transits: int, alt_tce: float, alt_days: float, alt_transits: int
) -> float | None:
    """The toll a transit, the same on every transit, at which two routings earn the same TCE; None if never.

    Each routing's TCE falls by its transits times the toll over its days, so
    below the crossing the routing with the higher TCE before tolls stays ahead.
    """
    slope = base_transits / base_days - alt_transits / alt_days
    if slope == 0.0:
        return None
    toll = (base_tce - alt_tce) / slope
    return toll if toll > 0.0 else None


def routing_alternatives(preset: Mapping[str, Any], base: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The calculator's other leg routings for a route, priced at the preset's market, the base routing first.

    On a tanker a routing pays the study's war risk premiums by payer and a day
    in the canal a transit, as TC20's description does; a dry routing, like
    its base, has no canal time in the guide's terms. Neither has a public
    toll, so each is set against the base by the toll a transit at which the
    two earn the same; a dry routing that avoids every canal also by the days
    the base could wait at its canals, no toll paid and no fuel burnt waiting.
    Each also carries the freight a tonne it needs on top of the base's to earn
    the base's TCE, the engine's freight for that TCE on the routing's own
    inputs less the base's.
    """
    code = preset["route"]
    route = baltic.ROUTES[code]
    inputs = priced(preset)
    tanker = route.segment != "dry"
    base_days = base["days"]["total"]
    base_tce = base["engine_tce_usd_day"]
    base_freight = engine.freight_for_tce(inputs, base_tce)["usd_t"] if base_tce is not None else None
    base_transits = transits(route, preset["legs"]["laden"]["routing"], preset["legs"]["ballast"]["routing"])
    variants = {"%s-%s" % (v["laden"], v["ballast"]): v for v in preset["routings"] if not v["is_preset"]}
    out: list[dict[str, Any]] = [
        {
            "id": "base",
            "kind": "base",
            "legs": [],
            "routing": {"laden": preset["legs"]["laden"]["routing"], "ballast": preset["legs"]["ballast"]["routing"]},
            "days": base_days,
            "tce_usd_day": base_tce,
            "transits": base_transits,
            "excluded": list(preset["excluded"]),
        }
    ]
    for alt_id in ROUTING_ORDER[code]:
        variant = variants[alt_id]
        alt_inputs = patched(inputs, variant["patch"])
        excluded = [item["text"] for item in variant["excluded_items"]]
        alt_transits = transits(route, variant["laden"], variant["ballast"])
        canal_days = alt_inputs["port"]["canal_days"]
        if tanker:
            alt_inputs = with_premiums(alt_inputs)
            # A premium priced here is no longer something the TCE leaves out.
            excluded = [text for text in excluded if not text.startswith("the additional war risk premium")]
            if alt_transits and not canal_days:
                canal_days = canal_days_a_transit() * alt_transits
                alt_inputs = patched(
                    alt_inputs,
                    {
                        "port.canal_days": canal_days,
                        "port.canal_tpd": alt_inputs["port"]["waiting_tpd"],
                        "port.canal_ets_share": alt_inputs["laden"]["ets_share"],
                    },
                )
        result = engine.evaluate(alt_inputs)
        days, tce = result["days"]["total"], result["tce_usd_day"]
        needed = engine.freight_for_tce(alt_inputs, base_tce)["usd_t"] if base_freight is not None else None
        waiting = None
        if not tanker and base_transits and not alt_transits:
            # The days the base could wait at its canals, at no cost but time, and still earn this routing's TCE.
            waiting = base_tce * base_days / tce - base_days
        out.append(
            {
                "id": alt_id,
                "kind": "routing",
                "routing": {"laden": variant["laden"], "ballast": variant["ballast"]},
                "legs": [
                    sea_routes.leg_key(route.load, route.discharge, variant["laden"]),
                    sea_routes.leg_key(route.discharge, route.load, variant["ballast"]),
                ],
                "laden_nm": alt_inputs["laden"]["distance_nm"],
                "ballast_nm": alt_inputs["ballast"]["distance_nm"],
                "days": days,
                "days_change": days - base_days,
                "tce_usd_day": tce,
                "tce_change": tce - base_tce,
                "transits": alt_transits,
                "base_transits": base_transits,
                "canal_days": canal_days,
                "owner_premium_usd": result["war_risk"]["ballast_usd"],
                "red_sea_premium_pct": analysis._rate(RED_SEA_RATE_ID)["low"],
                "hull_value_usd": alt_inputs["war_risk"]["hull_value_usd"],
                "toll_crossing_usd": toll_crossing(base_tce, base_days, base_transits, tce, days, alt_transits),
                "ahead_below": "alternative" if tce > base_tce else "base",
                "waiting_days_crossing": waiting,
                "freight_change_usd_t": None if needed is None or base_freight is None else needed - base_freight,
                "war_area": war_area(alt_inputs, route.load),
                "excluded": excluded,
            }
        )
    return out


def tc20_alternatives(st: Mapping[str, Any], base: Mapping[str, Any]) -> list[dict[str, Any]]:
    """TC20 by Suez and round the Cape, as the Detours view prices them (analysis.suez_tanker), Suez first.

    Detours' Suez TCE carries the owner's Red Sea premium for the ballast
    transit, which the engine's figure at the head of the panel leaves out.
    """
    suez, cape = st["options"]
    versus = st["cape_vs_suez"]
    return [
        {
            "id": "base",
            "kind": "base",
            "legs": [],
            "days": suez["days"],
            "tce_usd_day": suez["tce_usd_day"],
            "headline_tce_usd_day": base["engine_tce_usd_day"],
            "tce_below_headline": base["engine_tce_usd_day"] - suez["tce_usd_day"],
            "owner_red_sea_usd": st["red_sea_war_risk"]["owner_usd"],
            "charterer_war_risk_usd_t": suez["charterer_war_risk_usd_t"],
            "red_sea_premium_pct": st["red_sea_war_risk"]["premium_pct"],
            "gulf_premium_pct": st["gulf_war_risk"]["premium_pct"],
            "excluded": list(suez["excluded"]),
        },
        {
            "id": "no_suez-no_suez",
            "kind": "routing",
            "routing": {"laden": "no_suez", "ballast": "no_suez"},
            "legs": ["jubail__rotterdam__no_suez", "rotterdam__jubail__no_suez"],
            "laden_nm": cape["laden_nm"],
            "ballast_nm": cape["ballast_nm"],
            "days": cape["days"],
            "days_change": versus["extra_days"],
            "tce_usd_day": cape["tce_usd_day"],
            "tce_change": cape["tce_usd_day"] - suez["tce_usd_day"],
            "suez_tce_usd_day": suez["tce_usd_day"],
            "freight_needed_usd_t": versus["freight_needed_usd_t"],
            "freight_change_usd_t": versus["extra_freight_usd_t"],
            "charterer_war_risk_usd_t": cape["charterer_war_risk_usd_t"],
            "charterer_war_risk_change_usd_t": cape["charterer_war_risk_usd_t"] - suez["charterer_war_risk_usd_t"],
            "break_even_suez_toll_usd": st["break_even_suez_toll_usd"],
            "break_even_suez_transits": st["break_even_suez_transits"],
            "excluded": list(cape["excluded"]),
        },
    ]


def td3c_alternatives(hz: Mapping[str, Any], week: str, td34_week: str) -> list[dict[str, Any]]:
    """TD3C's Hormuz options, as the Detours view prices them (analysis.hormuz) at the latest TCE level.

    Every option is a cost of carriage a tonne: the freight that earns the
    Baltic's TCE at the engine's days and costs (derived, as on Detours) and
    the charterer's Gulf premium beside it. The base, loading at Ras Tanura
    with no wait, comes first, and already carries the one seven-day period of
    premium its days inside the Gulf make; a wait's change is its cost of
    carriage less the base's, so that period is counted once. The export VLCC
    of the transfer is priced at TD3C's TCE of the week, as on Detours, with
    the shuttle beside it at its reported cost; TD34, another cargo loading
    outside the strait, at its own. No dated premium was found for a loading in
    the Gulf of Oman, so neither carries one.

    `week` and `td34_week` are the weeks of TD3C's and TD34's figures, their
    latest presets' dates. Every option is priced at the study's week, so
    TD3C's figure must be of it: a report newer than the study's, added by
    hand, stops the build rather than mix them. TD34's TCE of that week is set
    against TD3C's only where TD34's own row shows it: a week whose report
    prints no TD34 TCE, or a TD34 row of another week, leaves TD34 out rather
    than set two weeks against each other.
    """
    if hz["as_of"] != week:
        raise MixedWeeksError(
            "TD3C's figure is of the week to %s, but the Hormuz study its options are priced at (analysis.hormuz) is "
            "of the week to %s: move the last of HORMUZ_LEVELS to %s, a week whose report must print TD3C's TCE; "
            "where that report prints no TD34 TCE, TD34 is left out of TD3C's options" % (week, hz["as_of"], week)
        )
    chains = hz["chains"]
    latest_week = hz["levels"][-1]["week_ending"]
    scenarios = {s["id"]: s for s in hz["scenarios"]}
    freight = chains["td3c_freight_at_own_tce_usd_t"]
    premium = scenarios["war_low"]["charterer_war_risk_usd_t"]
    base_carriage = freight + premium

    def at_latest(levels: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        return next(level for level in levels if level["week_ending"] == latest_week)

    waits = []
    for sid in ("wait_5", "wait_10", "wait_20"):
        scenario = scenarios[sid]
        carriage_t = (
            freight + scenario["charterer_war_risk_usd_t"] + at_latest(scenario["levels"])["extra_freight_usd_t"]
        )
        waits.append(
            {
                "id": sid,
                "waiting_days": scenario["extra_days"],
                "periods": scenario["periods"],
                "charterer_usd_t": scenario["charterer_war_risk_usd_t"],
                "owner_usd_t": at_latest(scenario["levels"])["extra_freight_usd_t"],
                "carriage_usd_t": carriage_t,
                "change_usd_t": carriage_t - base_carriage,
            }
        )
    reports = {r["id"]: r for r in cases.seed("market.json")["hormuz_chain"]["reports"]}
    cargo = baltic.ROUTES["TD3C"].cargo_t or 0.0
    barrels = reports[VLCC_BARRELS_ID]["low"]
    shuttle = next(s for s in chains["shuttle"] if s["unit"] == "USD a barrel")
    transit = next(s for s in chains["shuttle"] if s["unit"] == "USD a transit")
    td34, sts = chains["td34"], chains["sts"]
    export_t = sts["freight_at_td3c_tce_usd_t"]
    carriage = [export_t + shuttle["low"] * barrels / cargo, export_t + shuttle["high"] * barrels / cargo]
    # The shortest wait after which loading at Ras Tanura costs more than the transfer at its low end.
    above = next((w for w in waits if w["carriage_usd_t"] > carriage[0]), None)
    # TD34's TCE of the study's week, where TD34's own row shows that week's: the figure its line is read against.
    td34_shown = td34["published_tce_usd_day"] is not None and td34_week == hz["as_of"]
    return [
        {
            "id": "base",
            "kind": "base",
            "legs": [],
            "days": scenarios["base"]["days"],
            "freight_usd_t": freight,
            "premium_usd_t": premium,
            "periods": scenarios["war_low"]["periods"],
            "carriage_usd_t": base_carriage,
            "premium_pct": analysis._rate(hz["war_risk_source"])["low"],
        },
        *(
            [
                {
                    "id": "td34",
                    "kind": "option",
                    "legs": ["mina_al_fahal__ningbo__direct", "ningbo__mina_al_fahal__direct"],
                    "laden_nm": td34["laden_nm"],
                    "days": td34["days"],
                    "days_change": td34["extra_days"],
                    "tce_usd_day": td34["published_tce_usd_day"],
                    # The week of TD34's TCE, which its entry is dated by.
                    "week_ending": hz["as_of"],
                    "tce_basis": "baltic",
                    "freight_needed_usd_t": td34["freight_at_own_tce_usd_t"],
                    "td3c_freight_usd_t": freight,
                    # No premium is priced off Mina Al Fahal, so its cost of carriage is its freight.
                    "carriage_usd_t": td34["freight_at_own_tce_usd_t"],
                    "change_usd_t": td34["freight_at_own_tce_usd_t"] - base_carriage,
                    "excluded": list(td34["excluded"]),
                }
            ]
            if td34_shown
            else []
        ),
        {
            "id": "transfer",
            "kind": "option",
            "legs": ["ras_tanura__fujairah__direct", "fujairah__ningbo__direct", "ningbo__fujairah__direct"],
            "laden_nm": sts["laden_nm"],
            "days": sts["days"],
            "days_change": sts["extra_days"],
            "freight_needed_usd_t": export_t,
            "freight_change_usd_t": at_latest(sts["levels"])["extra_freight_usd_t"],
            # The TCE the export VLCC is priced at: TD3C's of the latest week, as on Detours.
            "tce_usd_day": hz["levels"][-1]["tce_usd_day"],
            "shuttle_usd_bbl": [shuttle["low"], shuttle["high"]],
            "shuttle_reported": shuttle["reported"],
            "barrels": barrels,
            "barrels_reported": reports[VLCC_BARRELS_ID]["reported"],
            "shuttle_usd_t": [shuttle["low"] * barrels / cargo, shuttle["high"] * barrels / cargo],
            "carriage_usd_t": carriage,
            "change_usd_t": [carriage[0] - base_carriage, carriage[1] - base_carriage],
            "wait_above_low": {"days": above["waiting_days"], "carriage_usd_t": above["carriage_usd_t"]}
            if above
            else None,
            "transit_usd": transit["low"],
            "transit_reported": transit["reported"],
            "transit_carriage_usd_t": export_t + transit["low"] / cargo,
            "excluded": list(sts["excluded"]),
        },
        {
            "id": "waiting",
            "kind": "scenario",
            "legs": [],
            "waits": waits,
            "premium_pct": analysis._rate(hz["war_risk_source"])["low"],
            "per_period_usd_t": premium,
        },
    ]


def _passes_canal(option: Mapping[str, Any]) -> bool:
    return bool({"Suez Canal", "Panama Canal"} & set(option["passes"]))


def study_case(sd: Mapping[str, Any]) -> cases.Case:
    """The detour study's Suez voyage, built as analysis.suez_dry builds it: the week's bunker table at the hub
    nearest Qingdao, and the allowance price and dollar rate of that date. Its sources are the study's."""
    route = analysis.ASIA_EUROPE_PANAMAX
    market = cases.weekly_market(sd["as_of"], cases.bunker_hub(route.load))
    return cases.build(
        STUDY_ID,
        market,
        freight_value=0.0,
        freight_basis="usd_t",
        route=replace(route, laden_routing="direct", ballast_routing="direct"),
    )


def study(sd: Mapping[str, Any]) -> dict[str, Any]:
    """The Panamax one way from Qingdao to Rotterdam by Suez, the Cape or Panama (analysis.suez_dry).

    Each option's cost of carriage is the freight that earns the P4 hire and
    the charterer's Red Sea premium, as the Detours view sets them; a routing
    through a canal also has the toll and waiting it could pay at the Cape's
    freight, which Detours computes on the freight alone. The sources of its
    bunkers, allowances and dollar rate are those of the case it is priced on.
    """
    options = {option["name"]: option for option in sd["options"]}
    suez = options["Suez"]
    legs = {
        "Suez": "qingdao__rotterdam__direct",
        "Cape of Good Hope": "qingdao__rotterdam__no_canals",
        "Panama": "qingdao__rotterdam__no_suez",
    }

    def option(name: str, option_id: str) -> dict[str, Any]:
        o = options[name]
        canal = _passes_canal(o)
        return {
            "id": option_id,
            "kind": "routing",
            "legs": [legs[name]],
            "laden_nm": o["laden_nm"],
            "days": o["days"],
            "days_change": o["days"] - suez["days"],
            "freight_needed_usd_t": o["freight_for_target_usd_t"],
            "freight_change_usd_t": o["extra_freight_vs_suez_usd_t"],
            "carriage_usd_t": o["cost_of_carriage_usd_t"],
            "carriage_change_usd_t": o["extra_cost_of_carriage_vs_suez_usd_t"],
            "toll_and_waiting_budget_usd": o["toll_and_waiting_budget_usd"] if canal else None,
            "waiting_days_budget": o["waiting_days_budget"] if canal else None,
            "charterer_war_risk_usd_t": o["charterer_war_risk_usd_t"],
            "excluded": list(o["excluded"]),
        }

    route = analysis.ASIA_EUROPE_PANAMAX
    case = study_case(sd)
    sources = case.sources
    return {
        "id": STUDY_ID,
        "kind": "study",
        "segment": "dry",
        "route": route,
        "date": sd["as_of"],
        "target_tce_usd_day": sd["target_tce_usd_day"],
        "p4_hire_usd_day": sd["p4_hire_usd_day"],
        "p4_commission_pct": sd["p4_commission_pct"],
        "p4_trip_days": list(sd["p4_trip_days"]),
        "cargo_t": sd["cargo_t"],
        "base": option("Suez", "suez"),
        "alternatives": [option("Cape of Good Hope", "cape"), option("Panama", "panama")],
        "red_sea_premium_pct": sd["war_risk"]["premium_pct"],
        "red_sea_source_id": sd["war_risk"]["source_id"],
        "war_area": war_area(case.inputs, route.load),
        "hub": cases.route_hub(route),
        "sources": {
            "bunkers": sources["prices.vlsfo_usd_t"]["source"],
            "eua": sources["ets.eua_eur_t"]["source"],
            "fx": sources["ets.usd_per_eur"]["source"],
            "hull": sources["war_risk.hull_value_usd"]["source"],
            "speeds_chosen": sources["laden.speed_kn"]["status"] == "chosen",
        },
        "ets_usd": engine.evaluate(analysis.one_way(case)[0])["costs"]["ets"],
    }


# --------------------------------------------------------------------------
# Geometry for each item: its view, its labels
# --------------------------------------------------------------------------


def path_points(d: str) -> list[tuple[float, float]]:
    """The points of an absolute M and L path, as routemap writes them."""
    numbers = [float(n) for n in re.findall(r"-?[0-9.]+", d)]
    return list(zip(numbers[::2], numbers[1::2], strict=True))


def far_point(candidates: Sequence[str], against: Sequence[str], legs: Mapping[str, Any]) -> list[float] | None:
    """The point of some legs farthest from other legs: where an alternative's label shows it apart."""
    others = [p for key in against for p in path_points(legs[key]["d"])]
    best: tuple[float, tuple[float, float]] | None = None
    for key in candidates:
        for p in path_points(legs[key]["d"]):
            gap = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in others) if others else 0.0
            if best is None or gap > best[0]:
                best = (gap, p)
    return [round(best[1][0], routemap.PLACES), round(best[1][1], routemap.PLACES)] if best else None


def view(keys: Sequence[str], legs: Mapping[str, Any]) -> list[float]:
    return routemap.frame_box([legs[key]["box"] for key in keys])


def ordered_passes(key: str) -> list[str]:
    """A leg's passages in the order it sails them: each at the point of the line nearest its reference point."""
    passes = cases.seed("sea_routes.json")["legs"][key]["passes"]
    line = cases.lines()[key]

    def at(name: str) -> int:
        lon, lat, _ = sea_routes.REFERENCE_POINTS[name]
        return min(range(len(line)), key=lambda i: math.hypot(line[i][0] - lon, line[i][1] - lat))

    return sorted(passes, key=at)


def item_geometry(
    legs: Sequence[str], alternatives: Sequence[Mapping[str, Any]], geo: Mapping[str, Any]
) -> dict[str, Any]:
    """The view a route is framed in, the passages its lines use, and where each alternative's name sits.

    An alternative's name goes at the point of its own lines farthest from the
    route's, where it shows apart; a name that would fall within LABEL_APART
    of an earlier one is not written, since the panel names every alternative.
    """
    alt_legs = [key for alt in alternatives for key in alt["legs"]]
    keys = [*legs, *alt_legs]
    passages: list[str] = []
    for key in keys:
        for name in ordered_passes(key):
            if name not in passages and name not in routemap.UNNAMED_PASSAGES and name not in QUIET_PASSAGES:
                passages.append(name)
    placed: list[list[float]] = []
    label_at: dict[str, list[float] | None] = {}
    for alt in alternatives:
        own = [key for key in alt["legs"] if key not in legs]
        point = far_point(own, legs, geo["legs"]) if own else None
        if point and any(math.hypot(point[0] - p[0], point[1] - p[1]) < LABEL_APART for p in placed):
            point = None
        if point:
            placed.append(point)
        label_at[alt["id"]] = point
    boxes = [geo["legs"][key]["box"] for key in keys]
    return {
        "view": routemap.frame_box(boxes),
        "view_tall": routemap.frame_box(boxes, routemap.ATLAS_TALL_ASPECT),
        "passages": passages,
        "label_at": label_at,
    }


def path_lines(d: str) -> list[list[tuple[float, float]]]:
    """The pieces of an absolute M and L path, each its own list of points."""
    return [path_points("M" + piece) for piece in d.split("M") if piece]


def _along(lines: Sequence[Sequence[tuple[float, float]]], step: float) -> list[tuple[float, float]]:
    """Points every `step` map units along some lines, their ends included."""
    out = []
    for points in lines:
        for a, b in itertools.pairwise(points):
            n = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
            out.extend((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n))
        out.append(points[-1])
    return out


def _to_lines(p: tuple[float, float], lines: Sequence[Sequence[tuple[float, float]]]) -> float:
    """The distance from a point to the nearest segment of some lines."""
    best = math.inf
    for points in lines:
        for a, b in itertools.pairwise(points):
            dx, dy = b[0] - a[0], b[1] - a[1]
            span = dx * dx + dy * dy
            t = 0.0 if span == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span))
            best = min(best, math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)))
    return best


def same_water(laden: Mapping[str, str], legs: Mapping[str, Any]) -> dict[str, list[str]]:
    """For each item, the others whose laden line runs over most of its own: on the map one line hides the other."""
    lines = {item: path_lines(legs[key]["d"]) for item, key in laden.items()}
    samples = {item: _along(own, SAME_WATER_UNITS) for item, own in lines.items()}
    out: dict[str, list[str]] = {}
    for item, own in samples.items():
        out[item] = [
            other
            for other, theirs in lines.items()
            if other != item
            and sum(1 for p in own if _to_lines(p, theirs) <= SAME_WATER_UNITS) >= SAME_WATER_SHARE * len(own)
        ]
    return out


def clusters(
    items: Sequence[tuple[str, str, float | None]], ports: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """The loading areas the map labels: ports within CLUSTER_UNITS of each other, with the routes loading there.

    `items` is (id, loading port, TCE) in the list's order; a label block lists
    its routes by TCE, the highest first, a route with none last.
    """
    order: list[str] = []
    for _, port, _ in items:
        if port not in order:
            order.append(port)
    out = []
    for group in routemap.clusters(ports, order):
        members = [(item_id, tce) for item_id, port, tce in items if port in group]
        members.sort(key=lambda m: -(m[1] if m[1] is not None else -1.0))
        xs = [ports[p]["x"] for p in group]
        ys = [ports[p]["y"] for p in group]
        out.append(
            {
                "ports": group,
                "x": round(math.fsum(xs) / len(xs), routemap.PLACES),
                "y": round(math.fsum(ys) / len(ys), routemap.PLACES),
                "box": [min(xs), min(ys), max(xs), max(ys)],
                "items": [item_id for item_id, _ in members],
            }
        )
    return out
