"""The study's five pre-registered analyses, computed from the seeds and the engine.

1. Cost structure at the common dated market (August 2026): each route's
   voyage costs by family, the share of each, and what the sourced costs
   leave out.
2. Speed: TCE against laden speed for the segments with public freight in US
   dollars, at the low, middle and high freight and bunker levels observed in
   2026, and the speed that maximises the TCE.
3. Detours: Suez against the Cape for an Asia to Europe tanker (TC20) and dry
   voyage (a Panamax, Qingdao to Rotterdam), and Hormuz scenarios for a Middle
   East Gulf VLCC loading (war risk, waiting, a ship to ship transfer in the
   Gulf of Oman, the Baltic's own Gulf of Oman route TD34): extra days, extra
   tonne miles and the freight that keeps the TCE unchanged.
4. Carbon: EU ETS cost of an intra-EEA, an into-EEA and a non-EEA voyage under
   the 2024, 2025 and 2026 phase-in, at a dated allowance price, and its time
   charter allocation.
5. Physical against paper: the physical TCE of each anchor week with a public
   FFA quote against the FFA, the hedge size and the basis.

Nothing here is tuned; every figure comes from a seed through the engine.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import replace
from itertools import pairwise
from typing import Any

from . import anchors, baltic, cases, engine, geo, sea_routes

# --------------------------------------------------------------------------
# 1. Cost structure
# --------------------------------------------------------------------------

#: The cost families of a voyage, in the order the site shows them.
FAMILIES = ("bunkers", "ports", "canals", "ets", "war_risk")
#: The block of excluded cost the result is restated per day for.
EXCLUDED_BLOCK_USD = 100_000.0


def dataclasses_replace_inputs(case: cases.Case, inputs: dict[str, Any]) -> cases.Case:
    """The same case with other inputs."""
    return replace(case, inputs=inputs)


def _voyage_view(case: cases.Case) -> dict[str, Any]:
    """A case priced as a voyage with no freight: its full voyage costs, whoever pays them."""
    inputs = dict(case.inputs, contract="voyage", freight_basis="usd_t", freight_value=0.0)
    return engine.evaluate(inputs)


def cost_structure() -> dict[str, Any]:
    market = cases.common_market()
    rows = []
    for code in baltic.STUDY_ROUTES:
        case = cases.build(code, market, freight_value=0.0, freight_basis="usd_t")
        r = _voyage_view(case)
        costs = {family: r["costs"][family] for family in FAMILIES}
        total = math.fsum(costs.values())
        war = None
        if case.inputs["war_risk"]["areas"]["gulf"]["entries"]:
            marsh = _rate("hormuz_2026_07_22")
            hull = case.inputs["war_risk"]["hull_value_usd"]
            if hull:
                w = engine.evaluate(_with_war(case.inputs, "gulf", marsh["low"]))["war_risk"]
                gulf = w["areas"]["gulf"]
                war = {
                    "premium_pct": marsh["low"],
                    "hull_value_usd": hull,
                    "days_inside": gulf["days"],
                    "periods": gulf["periods"],
                    "premium_usd": gulf["usd"],
                    "premium_to_bunkers": gulf["usd"] / costs["bunkers"],
                    "per_tonne_usd": gulf["usd"] / case.inputs["cargo_t"],
                }
            else:
                war = {
                    "premium_pct": marsh["low"],
                    "hull_value_usd": None,
                    "why_empty": "no dated public hull value for this ship",
                }
        rows.append(
            {
                "route": code,
                "name": baltic.ROUTES[code].name,
                "segment": baltic.ROUTES[code].segment,
                "contract": baltic.ROUTES[code].contract,
                "days": r["days"]["total"],
                "costs_usd": costs,
                "total_usd": total,
                "shares": {family: (value / total if total else 0.0) for family, value in costs.items()},
                "bunkers_by_grade_usd": r["bunkers_by_grade_usd"],
                "bunkers_by_activity_usd": r["bunkers_by_activity_usd"],
                "fuel_t": r["fuel_t"],
                "ets_covered_t": r["emissions"]["ets_covered_t"],
                "per_day_usd": total / r["days"]["total"],
                "excluded": case.excluded,
                "excluded_block_per_day_usd": EXCLUDED_BLOCK_USD / r["days"]["total"],
                "hub": case.legs["hub"],
                "laden_nm": case.inputs["laden"]["distance_nm"],
                "ballast_nm": case.inputs["ballast"]["distance_nm"],
                "eca_nm": case.inputs["laden"]["eca_nm"] + case.inputs["ballast"]["eca_nm"],
                "with_hormuz_war_risk": war,
            }
        )
    return {"market": market.label, "eua_eur_t": market.eua_eur_t, "usd_per_eur": market.usd_per_eur, "rows": rows}


# --------------------------------------------------------------------------
# 2. Speed
# --------------------------------------------------------------------------

#: The segments with public freight in US dollars, by the route that carries it.
SPEED_ROUTES = ("C5", "C3", "TD22", "TC20")
#: The search reaches one knot beyond the vessel's published pairs at each end:
#: beyond that the fitted power law says nothing the guide supports.
SPEED_MARGIN_KN = 1.0
SPEED_CHART_STEP_KN = 0.25


def observed_rates(route: str) -> list[float]:
    """Every public rate of a route in the anchors, in its own unit (USD/t or lump sum)."""
    seed = cases.seed("anchors.json")
    out: list[float] = []
    if route in ("TD22", "TC20"):
        for report in seed["tanker_weekly"]["reports"]:
            out += [e["rate_value"] for e in report["entries"] if e["route"] == route]
    else:
        for week in seed["dry_weekly"]["weeks"]:
            value = week["values"].get("%s_usd_t" % route)
            if value is not None and value not in out:
                out.append(value)
    return sorted(out)


def bunker_levels(hub: str) -> dict[str, tuple[cases.Market, str]]:
    """The lowest and highest weekly VLSFO table of 2026 at a hub, and the common market between them."""
    weeks = [w for w in cases.seed("market.json")["weekly_bunkers_usd_t"]["weeks"] if hub in w["prices"]]
    low = min(weeks, key=lambda w: w["prices"][hub][0])
    high = max(weeks, key=lambda w: w["prices"][hub][0])
    return {
        "low": (cases.weekly_market(low["date"], hub), low["date"]),
        "mid": (cases.common_market(), "2026-08"),
        "high": (cases.weekly_market(high["date"], hub), high["date"]),
    }


def speed() -> dict[str, Any]:
    out = []
    for code in SPEED_ROUTES:
        route = baltic.ROUTES[code]
        published = [v for v, _ in baltic.VESSELS[route.vessel].laden]
        lo, hi = min(published) - SPEED_MARGIN_KN, max(published) + SPEED_MARGIN_KN
        chart = [lo + k * SPEED_CHART_STEP_KN for k in range(round((hi - lo) / SPEED_CHART_STEP_KN) + 1)]
        rates = observed_rates(code)
        freight = {"low": rates[0], "mid": statistics.median(rates), "high": rates[-1]}
        basis = "lump_sum" if code in ("TD22", "TC20") else "usd_t"
        hub = cases.route_hub(route)
        grid = []
        for f_level, f_value in freight.items():
            for b_level, (market, as_of) in bunker_levels(hub).items():
                case = cases.build(code, market, freight_value=f_value, freight_basis=basis)
                best = engine.optimal_speed(case.inputs, lo, hi)
                at_reference = engine.evaluate(case.inputs)["tce_usd_day"]
                grid.append(
                    {
                        "freight_level": f_level,
                        "freight_value": f_value,
                        "bunker_level": b_level,
                        "bunker_as_of": as_of,
                        "vlsfo_usd_t": case.inputs["prices"]["vlsfo_usd_t"],
                        "optimal_laden_kn": best["laden_kn"],
                        "at_top": best["laden_kn"] >= hi - engine.SPEED_STEP_KN / 2,
                        "at_bottom": best["laden_kn"] <= lo + engine.SPEED_STEP_KN / 2,
                        "optimal_tce_usd_day": best["tce_usd_day"],
                        "reference_laden_kn": case.inputs["laden"]["speed_kn"],
                        "reference_tce_usd_day": at_reference,
                        "curve": [
                            {"laden_kn": p["laden_kn"], "tce_usd_day": p["tce_usd_day"]}
                            for p in engine.tce_by_speed(case.inputs, chart)
                        ],
                    }
                )
        fit = engine.power_fit(case.inputs["laden_curve"])
        out.append(
            {
                "route": code,
                "vessel": case.legs["vessel"],
                "basis": basis,
                "rates_observed": rates,
                "freight": freight,
                "hub": hub,
                "search_kn": [lo, hi],
                "published_kn": sorted(published),
                "power_fit_laden": fit,
                "power_fit_ballast": engine.power_fit(case.inputs["ballast_curve"]),
                "grid": grid,
            }
        )
    checks = []
    for row in out:
        by = {(g["freight_level"], g["bunker_level"]): g for g in row["grid"]}
        # Freight: along each bunker level, low to high freight; bunkers: along
        # each freight level, low to high bunkers, the speed taken the other way.
        freight = [[by[(f, b)] for f in LEVELS] for b in LEVELS]
        bunkers = [[by[(f, b)] for b in reversed(LEVELS)] for f in LEVELS]
        checks.append(
            {
                "route": row["route"],
                "freight_pushes_speed_up": textbook_test(freight),
                "bunkers_push_speed_down": textbook_test(bunkers),
            }
        )
    return {"margin_kn": SPEED_MARGIN_KN, "step_kn": engine.SPEED_STEP_KN, "routes": out, "textbook": checks}


#: The levels of the speed grid, low to high.
LEVELS = ("low", "mid", "high")


def textbook_test(lines: list[list[dict[str, Any]]]) -> str:
    """Whether the best speed rises along every line of grid cells, as the textbook says.

    "holds": it never falls and rises somewhere; "contradicted": it falls
    somewhere; "not_tested": it never moves and every cell sits at an end of
    the speeds searched, where it could not move; "no_move": it never moves
    although it could.
    """
    speeds = [[cell["optimal_laden_kn"] for cell in line] for line in lines]
    if any(b < a for line in speeds for a, b in pairwise(line)):
        return "contradicted"
    if any(b > a for line in speeds for a, b in pairwise(line)):
        return "holds"
    if all(cell["at_top"] or cell["at_bottom"] for line in lines for cell in line):
        return "not_tested"
    return "no_move"


# --------------------------------------------------------------------------
# 3. Detours
# --------------------------------------------------------------------------


def _rate(seed_id: str) -> dict[str, Any]:
    return next(r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"] == seed_id)


def _with_war(inputs: dict[str, Any], area: str, premium_pct: float, **area_changes: Any) -> dict[str, Any]:
    """The inputs with a premium in one listed area (and any other change to that area)."""
    areas = dict(inputs["war_risk"]["areas"])
    areas[area] = dict(areas[area], premium_pct=premium_pct, **area_changes)
    return dict(inputs, war_risk=dict(inputs["war_risk"], areas=areas))


#: Tonne miles are shown in billions.
BILLION = 1.0e9

#: The words a case's leaves-out list uses for each listed area's premium.
_PREMIUM_WORDS = {
    "gulf": "the additional war risk premium in the Gulf",
    "red_sea": "the additional war risk premium for the Red Sea passage",
}


def _option(
    name: str, case: cases.Case, inputs: dict[str, Any] | None = None, excluded: list[str] | None = None
) -> dict[str, Any]:
    """One routing or scenario: days, TCE, and the premium each party pays.

    A premium priced here is no longer something the TCE leaves out, so its
    item leaves the list; the columns say who pays it.
    """
    inputs = inputs or case.inputs
    r = engine.evaluate(inputs)
    cargo = inputs["cargo_t"]
    war = r["war_risk"]
    charterer = inputs["war_risk"]["payer"] == "charterer"
    charter_usd = war["charter_usd"] if charterer else 0.0
    priced = [words for area, words in _PREMIUM_WORDS.items() if inputs["war_risk"]["areas"][area]["premium_pct"] > 0]
    left_out = excluded if excluded is not None else case.excluded
    return {
        "name": name,
        "laden_nm": inputs["laden"]["distance_nm"],
        "ballast_nm": inputs["ballast"]["distance_nm"],
        "days": r["days"]["total"],
        "tce_usd_day": r["tce_usd_day"],
        "costs_usd": r["costs"]["total_usd"],
        "war_risk_usd": war["total_usd"],
        "war_risk_periods": {area: info["periods"] for area, info in war["areas"].items()},
        "war_risk_ballast_periods": {area: info["ballast_periods"] for area, info in war["areas"].items()},
        "war_risk_days_inside": {area: info["days"] for area, info in war["areas"].items()},
        "war_risk_payer": inputs["war_risk"]["payer"],
        "charterer_war_risk_usd": charter_usd,
        "owner_war_risk_usd": r["costs"]["war_risk"],
        "charterer_war_risk_usd_t": charter_usd / cargo if cargo else 0.0,
        "result_usd": r["result_usd"],
        "excluded": [item for item in left_out if not any(item.startswith(words) for words in priced)],
        "inputs": inputs,
        "passes": case.legs["laden"]["passes"],
    }


def _stand_still(option: dict[str, Any], base: dict[str, Any], cargo_t: float) -> dict[str, Any]:
    """Extra days and tonne miles against the base, and the freight that keeps the base TCE."""
    needed = engine.freight_for_tce(option["inputs"], base["tce_usd_day"])
    base_freight = engine.freight_for_tce(base["inputs"], base["tce_usd_day"])
    return {
        "extra_days": option["days"] - base["days"],
        "extra_tonne_miles": cargo_t * (option["laden_nm"] - base["laden_nm"]),
        "freight_needed_usd_t": needed["usd_t"],
        "extra_freight_usd_t": needed["usd_t"] - base_freight["usd_t"],
        "extra_freight_lump_sum_usd": needed["lump_sum_usd"] - base_freight["lump_sum_usd"],
    }


def suez_tanker() -> dict[str, Any]:
    """TC20 (Jubail to Rotterdam, LR2) at the latest week: Suez against the Cape, with the war risk premiums.

    Both routings load inside the Gulf, so both pay the Gulf premium; Suez also
    pays the Red Sea premium on each transit. On the usual spot terms the
    charterer pays the Gulf's and the laden transit's, which move the cost of
    carriage, not the owner's TCE; the ballast transit, the approach to the
    next loading, is the owner's and comes off its TCE by Suez.
    """
    report = cases.seed("anchors.json")["tanker_weekly"]["reports"][-1]
    entry = next(e for e in report["entries"] if e["route"] == "TC20")
    market = cases.weekly_market(report["week_ending"], cases.route_hub(baltic.ROUTES["TC20"]))
    suez_case = cases.build("TC20", market, freight_value=entry["rate_value"], freight_basis="lump_sum")
    red_sea = _rate("bab_el_mandeb_2026_07")
    gulf = _rate("hormuz_2026_07_22")
    cape_route = replace(baltic.ROUTES["TC20"], laden_routing="no_suez", ballast_routing="no_suez", canal_days=None)
    cape_case = cases.build(
        "TC20", market, freight_value=entry["rate_value"], freight_basis="lump_sum", route=cape_route
    )
    suez_war = _with_war(_with_war(suez_case.inputs, "red_sea", red_sea["low"]), "gulf", gulf["low"])
    cape_war = _with_war(cape_case.inputs, "gulf", gulf["low"])
    suez = _option("Suez", suez_case, suez_war)
    cape = _option("Cape of Good Hope", cape_case, cape_war)
    # The largest toll at which Suez still earns the Cape's TCE: the Suez result less the Cape TCE over Suez days.
    break_even_toll = suez["result_usd"] - cape["tce_usd_day"] * suez["days"]
    cargo = baltic.ROUTES["TC20"].cargo_t or 0.0
    red_sea_war = engine.evaluate(suez_war)["war_risk"]["areas"]["red_sea"]
    red_sea_area = suez_war["war_risk"]["areas"]["red_sea"]
    return {
        "route": "TC20",
        "as_of": report["week_ending"],
        "rate_usd": entry["rate_value"],
        "cargo_t": cargo,
        "options": [
            dict(_strip(o), extra_tonne_miles_bn=cargo * (o["laden_nm"] - suez["laden_nm"]) / BILLION)
            for o in (suez, cape)
        ],
        "cape_vs_suez": _stand_still(cape, suez, cargo),
        "red_sea_war_risk": {
            "premium_pct": red_sea["low"],
            "source_id": red_sea["id"],
            "transits": red_sea_area["entries"] + red_sea_area["ballast_transits"],
            "laden_transits": red_sea_area["entries"],
            "ballast_transits": red_sea_area["ballast_transits"],
            "cost_usd": red_sea_war["usd"] + red_sea_war["ballast_usd"],
            "charterer_usd": red_sea_war["usd"],
            "owner_usd": red_sea_war["ballast_usd"],
            "per_tonne_usd": red_sea_war["usd"] / cargo,
            "per_transit_usd": red_sea["low"] / engine.PERCENT * suez_war["war_risk"]["hull_value_usd"],
        },
        "gulf_war_risk": {"premium_pct": gulf["low"], "source_id": gulf["id"]},
        "break_even_suez_toll_usd": break_even_toll,
        "break_even_suez_transits": sum(
            1 for leg in ("laden", "ballast") if "Suez Canal" in suez_case.legs[leg]["passes"]
        ),
        "toll_reference": "Suez Canal Authority: about USD 500,000 a transit for a ship carrying one million "
        "barrels of crude",
    }


#: The Panamax Asia to Europe voyage of the dry detour: not a Baltic route; the
#: cargo is the Baltic Panamax voyage routes' 66,000 t, and no laytime is
#: assumed, so the freight levels exclude port time while their differences do not.
ASIA_EUROPE_PANAMAX = baltic.Route(
    "QD_RTM_PMX",
    "Qingdao to Rotterdam (Panamax)",
    "dry",
    "",
    "voyage",
    "USD/t",
    "BPI82",
    "qingdao",
    "rotterdam",
    80,
    "A Baltic Panamax (BPI82) with 66,000 t, the cargo of the Baltic's Panamax voyage routes, Qingdao to Rotterdam",
    cargo_t=66000,
    commission_pct=5.0,
)


def one_way(case: cases.Case) -> tuple[dict[str, Any], list[str]]:
    """A case's inputs with no ballast leg, and what it leaves out without the ballast leg's items."""
    inputs = dict(case.inputs, ballast=dict(case.inputs["ballast"], distance_nm=0.0, eca_nm=0.0))
    laden = case.legs["laden"]["passes"]
    areas = dict(inputs["war_risk"]["areas"])
    areas["gulf"] = dict(
        areas["gulf"], ballast_nm=0.0, entries=1 if "Strait of Hormuz" in laden else 0, ballast_transits=0
    )
    areas["red_sea"] = dict(
        areas["red_sea"], ballast_nm=0.0, entries=1 if "Bab el Mandeb" in laden else 0, ballast_transits=0
    )
    inputs["war_risk"] = dict(inputs["war_risk"], areas=areas)
    return inputs, [e for e in case.excluded if "ballast leg" not in e]


def suez_dry() -> dict[str, Any]:
    """A Panamax from Qingdao to Rotterdam, one way like the P4 trip: Suez, the Cape and Panama.

    P4_82 pays hire for a 55 to 70 day trip from delivery in the Far East to
    redelivery in the Skaw-Gibraltar range (GMB v8.8 page 80). Each routing's
    freight is the one at which the voyage, delivered at Qingdao and
    redelivered at Rotterdam with no ballast leg, earns as a TCE net of its own
    5 percent commission the P4 hire net of P4's 5 percent. The Cape needs no
    toll, so at the Cape's freight each canal routing earns more, and the
    difference over its days is the most it can spend on tolls and waiting
    before the Cape is the better voyage. The Red Sea premium of the Suez
    transit is the charterer's, beside the freight.
    """
    week = next(w for w in cases.seed("anchors.json")["dry_weekly"]["weeks"] if w["date"] == "2026-10-23")
    p4 = baltic.ROUTES["P4_82"]
    hire = week["values"]["P4_82_usd_day"]
    target = hire * (1.0 - p4.commission_pct / engine.PERCENT)
    market = cases.weekly_market("2026-10-23", cases.bunker_hub("qingdao"))
    red_sea = _rate("bab_el_mandeb_2026_07")
    options = []
    for name, routing in (("Suez", "direct"), ("Cape of Good Hope", "no_canals"), ("Panama", "no_suez")):
        route = replace(ASIA_EUROPE_PANAMAX, laden_routing=routing, ballast_routing=routing)
        case = cases.build("QD_RTM_PMX", market, freight_value=0.0, freight_basis="usd_t", route=route)
        inputs, excluded = one_way(case)
        if inputs["war_risk"]["areas"]["red_sea"]["entries"]:
            inputs = _with_war(inputs, "red_sea", red_sea["low"])
        option = _option(name, case, inputs, excluded)
        option["freight_for_target_usd_t"] = engine.freight_for_tce(inputs, target)["usd_t"]
        option["cost_of_carriage_usd_t"] = option["freight_for_target_usd_t"] + option["charterer_war_risk_usd_t"]
        options.append(option)
    cape = options[1]
    cape_freight = cape["freight_for_target_usd_t"]
    cargo = ASIA_EUROPE_PANAMAX.cargo_t or 0.0
    rows = []
    for option in options:
        at_cape_freight = engine.evaluate(dict(option["inputs"], freight_value=cape_freight))
        budget = at_cape_freight["result_usd"] - target * at_cape_freight["days"]["total"]
        # A bulk carrier's waiting fuel has no published figure, so a waiting day is priced at the hire alone.
        rows.append(
            dict(
                _strip(option),
                extra_days_vs_suez=option["days"] - options[0]["days"],
                extra_tonne_miles_vs_suez=cargo * (option["laden_nm"] - options[0]["laden_nm"]),
                extra_tonne_miles_bn=cargo * (option["laden_nm"] - options[0]["laden_nm"]) / BILLION,
                extra_freight_vs_suez_usd_t=option["freight_for_target_usd_t"] - options[0]["freight_for_target_usd_t"],
                extra_cost_of_carriage_vs_suez_usd_t=option["cost_of_carriage_usd_t"]
                - options[0]["cost_of_carriage_usd_t"],
                toll_and_waiting_budget_usd=budget,
                waiting_days_budget=budget / target if target else None,
            )
        )
    return {
        "as_of": "2026-10-23",
        "p4_hire_usd_day": hire,
        "p4_commission_pct": p4.commission_pct,
        "p4_trip_days": list(p4.trip_days or ()),
        "p4_page": p4.page,
        "target_tce_usd_day": target,
        "target": "P4_82, 23 October 2026 (Banchero Costa): delivery Hong Kong-South Korea, a 55 to 70 day trip, "
        "redelivery Skaw-Gibraltar, hire before 5 percent total commission (Guide to Market Benchmarks v8.8, page 80)",
        "basis": "one way: delivery Qingdao, redelivery Rotterdam, no ballast leg, no port time",
        "cargo_t": cargo,
        "war_risk": {"premium_pct": red_sea["low"], "transits": 1, "source_id": red_sea["id"], "payer": "charterer"},
        "options": rows,
    }


def _strip(option: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in option.items() if k != "inputs"}


#: The TCE levels the Hormuz scenarios keep unchanged: the Baltic's TD3C TCE
#: before the war, in the week of the closure and in the latest week.
HORMUZ_LEVELS = (
    ("2025-12-12", "before the war"),
    ("2026-03-06", "the week of the closure"),
    ("2026-10-23", "the latest week"),
)
WAIT_DAYS = (5.0, 10.0, 20.0)
#: The shuttle that carries a cargo through the strait to a transfer off
#: Fujairah, as reported (the market's figures, not the study's).
SHUTTLE_REPORTS = ("shuttle_usd_bbl_2026_09_21", "shuttle_usd_transit_2026_10_12")


#: A sensitivity on the listed area's edge: the Gulf of Oman to 58 degrees east.
GULF_OF_OMAN_EDGE_LON = 58.0


def _days_inside_to(case: cases.Case, edge_lon: float) -> float:
    """A Gulf loading's days west of a meridian: both legs' miles there at their speeds, and the load port's days."""
    inputs = case.inputs
    total = 0.0
    for leg, outward in (("laden", True), ("ballast", False)):
        info = case.legs[leg]
        coordinates = cases.lines()[sea_routes.leg_key(info["from"], info["to"], info["routing"])]
        points = coordinates if outward else list(reversed(coordinates))
        run = 0.0
        for _, end, length in geo.densify(points, 2.0):
            if end[0] >= edge_lon:
                break
            run += length
        total += engine.sea_days(run, inputs[leg]["speed_kn"], inputs["sea_margin"])
    port = inputs["port"]
    return total + math.fsum(port[a + "_days"] for a in inputs["war_risk"]["areas"]["gulf"]["port_activities"])


def hormuz() -> dict[str, Any]:
    """TD3C priced through the Hormuz scenarios at the latest weekly bunker table.

    The premium is the charterer's on the usual spot terms: it is shown at cost
    per tonne of cargo and does not move the owner's TCE. Waiting inside the
    Gulf costs the owner days (the freight that keeps the TCE rises) and the
    charterer further seven day periods of premium. Loading off Fujairah after
    a transfer, and TD34 from Mina Al Fahal, are a different cargo chain: the
    export ship's voyage is priced, the shuttle and the transfer are not.
    """
    market = cases.weekly_market("2026-10-23", "fujairah")
    base_case = cases.build("TD3C", market, freight_value=0.0, freight_basis="usd_t")
    hull = base_case.inputs["war_risk"]["hull_value_usd"]
    marsh = _rate("hormuz_2026_07_22")
    scenarios = [("base", "No war risk, no waiting", base_case, base_case.inputs)]
    for premium, label in ((marsh["low"], "low"), (marsh["high"], "high")):
        scenarios.append(
            (
                "war_%s" % label,
                "War risk %g percent of hull value" % premium,
                base_case,
                _with_war(base_case.inputs, "gulf", premium),
            )
        )
    for wait in WAIT_DAYS:
        waiting = _with_war(base_case.inputs, "gulf", marsh["low"])
        waiting = dict(waiting, port=dict(waiting["port"], delay_days=wait))
        scenarios.append(
            (
                "wait_%d" % wait,
                "War risk %g percent and %d days waiting inside the Gulf" % (marsh["low"], wait),
                base_case,
                waiting,
            )
        )

    report = {r["week_ending"]: r for r in cases.seed("anchors.json")["tanker_weekly"]["reports"]}
    levels = []
    for week, label in HORMUZ_LEVELS:
        entry = next(e for e in report[week]["entries"] if e["route"] == "TD3C")
        levels.append({"week_ending": week, "label": label, "tce_usd_day": entry["tce_usd_day"]})
    cargo = baltic.ROUTES["TD3C"].cargo_t or 0.0
    base_option = _option("base", base_case)
    rows = []
    for key, label, case, inputs in scenarios:
        option = _option(label, case, inputs)
        per_level = []
        for level in levels:
            base_at = engine.freight_for_tce(base_option["inputs"], level["tce_usd_day"])
            needed = engine.freight_for_tce(inputs, level["tce_usd_day"])
            owner = needed["usd_t"] - base_at["usd_t"]
            per_level.append(
                {
                    "week_ending": level["week_ending"],
                    "freight_needed_usd_t": needed["usd_t"],
                    "extra_freight_usd_t": owner,
                    "extra_cost_of_carriage_usd_t": owner + option["charterer_war_risk_usd_t"],
                }
            )
        rows.append(
            {
                "id": key,
                "label": label,
                "days": option["days"],
                "extra_days": option["days"] - base_option["days"],
                "days_inside_gulf": option["war_risk_days_inside"]["gulf"],
                "periods": option["war_risk_periods"]["gulf"],
                "laden_nm": option["laden_nm"],
                "tonne_miles": cargo * option["laden_nm"],
                "extra_tonne_miles": cargo * (option["laden_nm"] - base_option["laden_nm"]),
                "extra_tonne_miles_bn": cargo * (option["laden_nm"] - base_option["laden_nm"]) / BILLION,
                "war_risk_usd": option["war_risk_usd"],
                "charterer_war_risk_usd": option["charterer_war_risk_usd"],
                "charterer_war_risk_usd_t": option["charterer_war_risk_usd_t"],
                "voyage_costs_usd": option["costs_usd"],
                "excluded": option["excluded"],
                "levels": per_level,
            }
        )

    # The transfer chain and TD34: the export voyage only, beside the market's figures.
    latest = levels[-1]["tce_usd_day"]
    sts_route = replace(baltic.ROUTES["TD3C"], code="TD3C_STS", load="fujairah")
    sts_case = cases.build("TD3C", market, freight_value=0.0, freight_basis="usd_t", route=sts_route)
    td34 = cases.build("TD34", market, freight_value=0.0, freight_basis="usd_t")
    published = {e["route"]: e["tce_usd_day"] for e in report["2026-10-23"]["entries"] if e["tce_usd_day"]}
    base_latest = engine.freight_for_tce(base_case.inputs, latest)["usd_t"]

    def chain(label: str, case: cases.Case) -> dict[str, Any]:
        """An export voyage that loads outside the strait, set against TD3C as the scenarios are."""
        voyage_days = engine.days(case.inputs)["total"]
        laden_nm = case.inputs["laden"]["distance_nm"]
        return {
            "label": label,
            "days": voyage_days,
            "extra_days": voyage_days - base_option["days"],
            "laden_nm": laden_nm,
            "tonne_miles": cargo * laden_nm,
            "extra_tonne_miles": cargo * (laden_nm - base_option["laden_nm"]),
            "extra_tonne_miles_bn": cargo * (laden_nm - base_option["laden_nm"]) / BILLION,
            "freight_at_td3c_tce_usd_t": engine.freight_for_tce(case.inputs, latest)["usd_t"],
            "levels": [
                {
                    "week_ending": level["week_ending"],
                    "extra_freight_usd_t": engine.freight_for_tce(case.inputs, level["tce_usd_day"])["usd_t"]
                    - engine.freight_for_tce(base_option["inputs"], level["tce_usd_day"])["usd_t"],
                }
                for level in levels
            ],
            "excluded": case.excluded,
        }

    chains = {
        "sts": chain("Export VLCC from Fujairah after a transfer", sts_case),
        "td34": dict(
            chain("TD34, a cargo loading at Mina Al Fahal", td34),
            freight_at_own_tce_usd_t=engine.freight_for_tce(td34.inputs, published["TD34"])["usd_t"],
            published_tce_usd_day=published["TD34"],
        ),
        "td3c_freight_at_own_tce_usd_t": base_latest,
        "shuttle": [
            next(r for r in cases.seed("market.json")["hormuz_chain"]["reports"] if r["id"] == rid)
            for rid in SHUTTLE_REPORTS
        ],
    }
    return {
        "as_of": "2026-10-23",
        "hull_value_usd": hull,
        "war_risk_source": marsh["id"],
        "levels": levels,
        "scenarios": rows,
        "chains": chains,
        "days_inside_to_58e": _days_inside_to(base_case, GULF_OF_OMAN_EDGE_LON),
        "td34_vs_td3c_published": {
            "td3c_tce_usd_day": published["TD3C"],
            "td34_tce_usd_day": published["TD34"],
        },
    }


# --------------------------------------------------------------------------
# 4. Carbon
# --------------------------------------------------------------------------

CARBON_VOYAGES = (("TC23", "between two EEA ports"), ("TD20", "into the EEA"), ("TD3C", "outside the EEA"))
PHASE_IN_YEARS = (2024, 2025, 2026)


def carbon() -> dict[str, Any]:
    market = cases.common_market()
    rows = []
    for code, kind in CARBON_VOYAGES:
        case = cases.build(code, market, freight_value=0.0, freight_basis="usd_t")
        by_year = []
        for year in PHASE_IN_YEARS:
            ets = dict(case.inputs["ets"], phase_in=cases.phase_in(year), include_non_co2=year >= cases.ETS_FULL_FROM)
            r = engine.evaluate(dict(case.inputs, ets=ets))
            cargo = case.inputs["cargo_t"]
            by_year.append(
                {
                    "year": year,
                    "phase_in": ets["phase_in"],
                    "covered_t": r["emissions"]["ets_covered_t"],
                    "allowances_t": r["emissions"]["ets_covered_t"] * ets["phase_in"],
                    "cost_usd": r["costs"]["ets"],
                    "per_day_usd": r["costs"]["ets"] / r["days"]["total"],
                    "per_tonne_cargo_usd": r["costs"]["ets"] / cargo if cargo else None,
                    "share_of_voyage_costs": r["costs"]["ets"] / r["costs"]["total_usd"],
                }
            )
        r = engine.evaluate(case.inputs)
        rows.append(
            {
                "route": code,
                "kind": kind,
                "co2_t": r["emissions"]["co2_t"],
                "co2e_t": r["emissions"]["co2e_t"],
                "laden_share": case.inputs["laden"]["ets_share"],
                "ballast_share": case.inputs["ballast"]["ets_share"],
                "fueleu": r["fueleu"],
                "years": by_year,
            }
        )
    trip = cases.build("S4A_63", market, freight_value=0.0)
    r = engine.evaluate(trip.inputs)
    allocation = {
        "route": "S4A_63",
        "owner_ets_usd": r["costs"]["ets"],
        "trip_ets_usd": r["ets_all_usd"] - r["costs"]["ets"],
        "rule": "BIMCO ETS Allowances Clause 2022: the charterer provides the allowances for the ship's emissions "
        "during the charter; the owner's are the ballast leg's",
    }
    return {
        "market": market.label,
        "eua_eur_t": market.eua_eur_t,
        "eua_source": market.eua_source,
        "usd_per_eur": market.usd_per_eur,
        "rows": rows,
        "time_charter": allocation,
    }


# --------------------------------------------------------------------------
# 5. Physical against paper
# --------------------------------------------------------------------------


def _trading_day_between(after: str, until: str) -> bool:
    """Whether a weekday falls after one date and on or before another."""
    from datetime import date, timedelta

    day = date.fromisoformat(after) + timedelta(days=1)
    last = date.fromisoformat(until)
    while day <= last:
        if day.weekday() < 5:
            return True
        day += timedelta(days=1)
    return False


def curve_for(curve_id: str, physical_date: str) -> dict[str, Any]:
    """The FFA curve a physical date is set against: the latest column a desk could have traded on that date.

    A report prints each curve at its assessment date beside the previous one.
    The assessed column counts when no trading day lies between the physical
    date and it (a curve dated the weekend after a Friday); otherwise the
    previous column, when it is on or before the physical date.
    """
    curve = next(c for c in cases.seed("ffa.json")["curves"] if c["id"] == curve_id)
    if curve["assessed"] <= physical_date or not _trading_day_between(physical_date, curve["assessed"]):
        column, dated = "usd_day", curve["assessed"]
    elif curve["previous"] <= physical_date:
        column, dated = "previous_usd_day", curve["previous"]
    else:
        raise ValueError("curve %s has no column on or before %s" % (curve_id, physical_date))
    return {"curve": curve, "column": column, "dated": dated}


def printings(dated: str) -> list[dict[str, Any]]:
    """Every column of the seed's curves dated on a day: a report prints a curve at its date, and the next
    report prints it again beside its own, not always with the same values."""
    out = []
    for curve in cases.seed("ffa.json")["curves"]:
        if curve["assessed"] == dated:
            out.append({"curve": curve, "column": "usd_day", "dated": dated})
        if curve["previous"] == dated:
            out.append({"curve": curve, "column": "previous_usd_day", "dated": dated})
    return out


def ffa_strip(
    curve_id: str, segment: str, physical_date: str, total_days: float, chosen: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The FFA over a voyage's days: each day from the physical date, ballast leg first, at its month's FFA.

    The column is the latest a desk could have traded on the physical date,
    unless one is given. Raises when a month the voyage reaches has no FFA on
    the curve: no month is filled in.
    """
    from datetime import date, timedelta

    chosen = chosen or curve_for(curve_id, physical_date)
    points = {p["period"]: p[chosen["column"]] for p in chosen["curve"]["segments"][segment]["points"]}
    weights: dict[str, float] = {}
    cursor = date.fromisoformat(physical_date)
    remaining = total_days
    while remaining > 0:
        next_month = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
        span = min(float((next_month - cursor).days), remaining)
        month = "%04d-%02d" % (cursor.year, cursor.month)
        weights[month] = weights.get(month, 0.0) + span
        remaining -= span
        cursor = next_month
    missing = [m for m in weights if m not in points]
    if missing:
        raise ValueError("curve %s has no FFA for %s" % (curve_id, ", ".join(missing)))
    value = math.fsum(points[m] * w for m, w in weights.items()) / total_days
    return {
        "curve": chosen["curve"]["id"],
        "column": chosen["column"],
        "printed": chosen["curve"]["assessed"],
        "dated": chosen["dated"],
        "assessed": chosen["curve"]["assessed"],
        "source": chosen["curve"]["source"],
        "usd_day": value,
        "months": [{"month": m, "days": w, "usd_day": points[m]} for m, w in weights.items()],
    }


def paper() -> dict[str, Any]:
    rows = []
    dry = {(r["date"], r["route"]): r for r in anchors.dry_weekly()}
    plan = (
        ("2026-07-03", "C3", "wk27_2026"),
        ("2026-07-03", "C5", "wk27_2026"),
        ("2026-10-23", "C3", "wk43_2026"),
        ("2026-10-23", "C5", "wk43_2026"),
    )
    for date, route, curve in plan:
        anchor = dry[(date, route)]
        code = baltic.ROUTES[route]
        hub = cases.route_hub(code)
        case = cases.build(route, cases.weekly_market(date, hub), freight_value=anchor["freight_usd_t"])
        physical = anchor["engine_tce_usd_day"]
        days = engine.days(case.inputs)["total"]
        strip = ffa_strip(curve, "capesize", date, days)
        h = engine.hedge(case.inputs, physical, strip["usd_day"], None)
        keep = 1.0 - case.inputs["commission_pct"] / engine.PERCENT
        equivalent = engine.freight_for_tce(case.inputs, strip["usd_day"] * keep)["usd_t"]
        # The same date's curve as every report printed it: the basis on each print.
        prints = []
        for chosen in printings(strip["dated"]):
            other = ffa_strip(chosen["curve"]["id"], "capesize", date, days, chosen)
            prints.append(
                {
                    "curve": other["curve"],
                    "printed": other["printed"],
                    "column": other["column"],
                    "usd_day": other["usd_day"],
                    "basis_usd_day": h["physical_tce_gross_usd_day"] - other["usd_day"],
                    "used": (other["curve"], other["column"]) == (strip["curve"], strip["column"]),
                }
            )
        # Without the weather margin the guide leaves to dry panellists (7.4.2): the sensitivity the page states.
        bare = engine.evaluate(dict(case.inputs, sea_margin=0.0))["tce_usd_day"]
        row = {
            "date": date,
            "route": route,
            "hub": hub,
            "freight_usd_t": anchor["freight_usd_t"],
            "physical_tce_usd_day": physical,
            "physical_tce_gross_usd_day": h["physical_tce_gross_usd_day"],
            "commission_pct": case.inputs["commission_pct"],
            "ffa": strip,
            "hedge_days": h["tc_hedge_days"],
            "hedge_days_net": h["tc_hedge_days_net"],
            "basis_usd_day": h["basis_vs_tc_ffa_usd_day"],
            "printings": prints,
            "basis_range_usd_day": [min(x["basis_usd_day"] for x in prints), max(x["basis_usd_day"] for x in prints)],
            "no_margin_tce_gross_usd_day": bare / keep,
            "no_margin_basis_usd_day": bare / keep - strip["usd_day"],
            "freight_matching_ffa_usd_t": equivalent,
            "spot_index_usd_day": anchor["benchmark_usd_day"],
            "spot_basis": anchor["benchmark_basis"],
            "spot_182_usd_day": anchor["benchmark_182_usd_day"],
            "timing_basis_usd_day": strip["usd_day"] - anchor["benchmark_182_usd_day"],
            "excluded": anchor["excluded"],
            "inputs": case.inputs,
        }
        if code.bunker_hub:
            # The hub the general rule would give, for the sensitivity the page states.
            rule_hub = cases.bunker_hub(code.load)
            at_rule = cases.build(
                route,
                cases.weekly_market(date, rule_hub),
                freight_value=anchor["freight_usd_t"],
                route=replace(code, bunker_hub="", bunker_hub_why=""),
            )
            rule_tce = engine.evaluate(at_rule.inputs)["tce_usd_day"]
            row["rule_hub"] = rule_hub
            row["rule_hub_tce_usd_day"] = rule_tce
            row["rule_hub_basis_usd_day"] = rule_tce / keep - strip["usd_day"]
        rows.append(row)
    fixture = cases.seed("ffa.json")["physical_fixtures"][0]
    hub = cases.route_hub(baltic.ROUTES["C5"])
    market = cases.weekly_market("2026-10-23", hub)

    def c5_tce(usd_t: float) -> float:
        return engine.evaluate(cases.build("C5", market, freight_value=usd_t).inputs)["tce_usd_day"]

    # The report gives the route on the fixture's own day only in its narrative; its table of Baltic
    # indices and its narrative differ at the next day's close, so the basis is given on both series.
    on_day = fixture["route_on_day"]["usd_t"]
    table_next = fixture["index_same_week"]["C5_usd_t"]
    narrative_next = fixture["narrative_next_day"]["usd_t"]
    gap = table_next - narrative_next
    fixed = c5_tce(fixture["freight_usd_t"])
    fixture_row = {
        "date": fixture["date"],
        "laycan": fixture["laycan"],
        "fixture_usd_t": fixture["freight_usd_t"],
        "fixture_tce_usd_day": fixed,
        "route_on_day_usd_t": on_day,
        "route_on_day_tce_usd_day": c5_tce(on_day),
        "next_day": fixture["index_same_week"]["date"],
        "index_next_day_usd_t": table_next,
        "index_next_day_tce_usd_day": c5_tce(table_next),
        "narrative_next_day_usd_t": narrative_next,
        "series_gap_usd_t": gap,
        "basis_usd_t": fixture["freight_usd_t"] - on_day,
        "basis_usd_day": fixed - c5_tce(on_day),
        "basis_table_series_usd_t": fixture["freight_usd_t"] - (on_day + gap),
        "basis_table_series_usd_day": fixed - c5_tce(on_day + gap),
        "cargo_t": baltic.ROUTES["C5"].cargo_t,
        "tce_market": market.label,
    }
    tanker = cases.seed("ffa.json")["tanker_ffa_tce"][0]
    reports = {r["week_ending"]: r for r in cases.seed("anchors.json")["tanker_weekly"]["reports"]}
    q2 = [
        {
            "week_ending": week,
            "tce_usd_day": next(e for e in reports[week]["entries"] if e["route"] == "TD3C")["tce_usd_day"],
        }
        for week in ("2026-04-17", "2026-06-26")
    ]
    # A February projection set beside later outcomes, not a basis: no same-day tanker FFA in dollars was found.
    td3c = {
        "ffa_tce_q2_usd_day": tanker["values"]["2026-Q2_tce_usd_day"],
        "published": tanker["published"],
        "physical_q2": q2,
    }
    return {
        "capesize": rows,
        "c5_fixture": fixture_row,
        "td3c": td3c,
        "c5tc_180_differential_usd_day": baltic.C5TC_180_DIFFERENTIAL,
    }


def run() -> dict[str, Any]:
    return {
        "cost_structure": cost_structure(),
        "speed": speed(),
        "detours": {"suez_tanker": suez_tanker(), "suez_dry": suez_dry(), "hormuz": hormuz()},
        "carbon": carbon(),
        "paper": paper(),
    }
