"""The pre-registered analysis of the study brief, section 5, computed from the seeds and the engine.

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

import statistics
from dataclasses import replace
from typing import Any

from . import anchors, baltic, cases, engine

# --------------------------------------------------------------------------
# 1. Cost structure
# --------------------------------------------------------------------------

#: The cost families of the study brief, in the order the site shows them.
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
        total = sum(costs.values())
        war = None
        if "Strait of Hormuz" in case.legs["laden"]["passes"]:
            marsh = _rate("hormuz_2026_07_22")
            hull = case.inputs["war_risk"]["hull_value_usd"]
            if hull:
                priced = dict(
                    case.inputs, war_risk=dict(case.inputs["war_risk"], premium_pct=marsh["low"], periods=1.0)
                )
                w = _voyage_view(dataclasses_replace_inputs(case, priced))
                war_costs = {family: w["costs"][family] for family in FAMILIES}
                war_total = sum(war_costs.values())
                war = {
                    "premium_pct": marsh["low"],
                    "hull_value_usd": hull,
                    "costs_usd": war_costs,
                    "total_usd": war_total,
                    "shares": {family: value / war_total for family, value in war_costs.items()},
                    "war_risk_to_bunkers": war_costs["war_risk"] / war_costs["bunkers"],
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
        hub = cases.bunker_hub(route.load)
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
                        "at_bound": best["laden_kn"] <= lo or best["laden_kn"] >= hi - engine.SPEED_STEP_KN / 2,
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
        by = {(g["freight_level"], g["bunker_level"]): g["optimal_laden_kn"] for g in row["grid"]}
        checks.append(
            {
                "route": row["route"],
                "freight_pushes_speed_up": by[("high", "mid")] >= by[("mid", "mid")] >= by[("low", "mid")],
                "bunkers_push_speed_down": by[("mid", "high")] <= by[("mid", "mid")] <= by[("mid", "low")],
            }
        )
    return {"margin_kn": SPEED_MARGIN_KN, "step_kn": engine.SPEED_STEP_KN, "routes": out, "textbook": checks}


# --------------------------------------------------------------------------
# 3. Detours
# --------------------------------------------------------------------------


def _rate(seed_id: str) -> dict[str, Any]:
    return next(r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"] == seed_id)


def _with_war(inputs: dict[str, Any], premium_pct: float, periods: float) -> dict[str, Any]:
    return dict(inputs, war_risk=dict(inputs["war_risk"], premium_pct=premium_pct, periods=periods))


def _option(name: str, case: cases.Case, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or case.inputs
    r = engine.evaluate(inputs)
    return {
        "name": name,
        "laden_nm": inputs["laden"]["distance_nm"],
        "ballast_nm": inputs["ballast"]["distance_nm"],
        "days": r["days"]["total"],
        "tce_usd_day": r["tce_usd_day"],
        "costs_usd": r["costs"]["total_usd"],
        "war_risk_usd": r["costs"]["war_risk"],
        "result_usd": r["result_usd"],
        "excluded": case.excluded,
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
    """TC20 (Jubail to Rotterdam, LR2) at the latest week: Suez with Red Sea war risk against the Cape."""
    report = cases.seed("anchors.json")["tanker_weekly"]["reports"][-1]
    entry = next(e for e in report["entries"] if e["route"] == "TC20")
    market = cases.weekly_market(report["week_ending"], cases.bunker_hub(baltic.ROUTES["TC20"].load))
    suez_case = cases.build("TC20", market, freight_value=entry["rate_value"], freight_basis="lump_sum")
    red_sea = _rate("bab_el_mandeb_2026_07")
    suez_war = _with_war(suez_case.inputs, red_sea["low"], 2.0)
    cape_route = replace(baltic.ROUTES["TC20"], laden_routing="no_suez", ballast_routing="no_suez", canal_days=None)
    cape_case = cases.build(
        "TC20", market, freight_value=entry["rate_value"], freight_basis="lump_sum", route=cape_route
    )
    suez = _option("Suez, Red Sea war risk on both transits", suez_case, suez_war)
    suez_plain = _option("Suez, no war risk", suez_case)
    cape = _option("Cape of Good Hope", cape_case)
    # The largest toll at which Suez still earns the Cape's TCE: the Suez result less the Cape TCE over Suez days.
    break_even_toll = suez["result_usd"] - cape["tce_usd_day"] * suez["days"]
    cargo = baltic.ROUTES["TC20"].cargo_t or 0.0
    # The freight that keeps the Suez TCE once the Red Sea premium is paid.
    war_needed = engine.freight_for_tce(suez_war, suez_plain["tce_usd_day"])["usd_t"]
    return {
        "route": "TC20",
        "as_of": report["week_ending"],
        "rate_usd": entry["rate_value"],
        "cargo_t": cargo,
        "options": [_strip(o) for o in (suez_plain, suez, cape)],
        "cape_vs_suez": _stand_still(cape, suez, cargo),
        "red_sea_war_risk": {
            "cost_usd": suez["war_risk_usd"],
            "freight_needed_usd_t": war_needed,
            "extra_freight_usd_t": war_needed - entry["rate_value"] / cargo,
        },
        "break_even_suez_toll_usd": break_even_toll,
        "war_risk": {"premium_pct": red_sea["low"], "periods": 2, "source_id": red_sea["id"]},
        "toll_reference": "Suez Canal Authority: about USD 500,000 for a ship carrying one million barrels of crude",
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


def suez_dry() -> dict[str, Any]:
    """A Panamax from Qingdao to Rotterdam: Suez, the Cape and Panama, against the P4 trip rate.

    Each routing's freight is the one that earns the P4 trip rate (Far East to
    Skaw-Gibraltar) as a TCE; the Cape needs no toll, so at the Cape's freight
    each canal routing earns more, and the difference over its days is the most
    it can spend on tolls and waiting before the Cape is the better voyage.
    """
    week = next(w for w in cases.seed("anchors.json")["dry_weekly"]["weeks"] if w["date"] == "2026-10-23")
    target = week["values"]["P4_82_usd_day"]
    market = cases.weekly_market("2026-10-23", cases.bunker_hub("qingdao"))
    red_sea = _rate("bab_el_mandeb_2026_07")
    options = []
    for name, routing in (("Suez", "direct"), ("Cape of Good Hope", "no_canals"), ("Panama", "no_suez")):
        route = replace(ASIA_EUROPE_PANAMAX, laden_routing=routing, ballast_routing=routing)
        case = cases.build("QD_RTM_PMX", market, freight_value=0.0, freight_basis="usd_t", route=route)
        inputs = case.inputs
        if routing == "direct":
            inputs = _with_war(inputs, red_sea["low"], 2.0)
        option = _option(name, case, inputs)
        option["freight_for_target_usd_t"] = engine.freight_for_tce(inputs, target)["usd_t"]
        options.append(option)
    cape = options[1]
    cape_freight = cape["freight_for_target_usd_t"]
    cargo = ASIA_EUROPE_PANAMAX.cargo_t or 0.0
    rows = []
    for option in options:
        at_cape_freight = engine.evaluate(dict(option["inputs"], freight_value=cape_freight))
        budget = at_cape_freight["result_usd"] - target * at_cape_freight["days"]["total"]
        daily_cost = target + option["inputs"]["port"]["waiting_tpd"] * option["inputs"]["prices"]["vlsfo_usd_t"]
        rows.append(
            dict(
                _strip(option),
                extra_days_vs_suez=option["days"] - options[0]["days"],
                extra_tonne_miles_vs_suez=cargo * (option["laden_nm"] - options[0]["laden_nm"]),
                extra_freight_vs_suez_usd_t=option["freight_for_target_usd_t"] - options[0]["freight_for_target_usd_t"],
                toll_and_waiting_budget_usd=budget,
                waiting_days_budget=budget / daily_cost if daily_cost else None,
            )
        )
    return {
        "as_of": "2026-10-23",
        "target_tce_usd_day": target,
        "target": "P4_82, Far East to Skaw-Gibraltar Panamax trip, 23 October 2026 (Banchero Costa)",
        "cargo_t": cargo,
        "war_risk": {"premium_pct": red_sea["low"], "periods": 2, "source_id": red_sea["id"]},
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


def hormuz() -> dict[str, Any]:
    """TD3C priced through the Hormuz scenarios at the latest weekly bunker table."""
    market = cases.weekly_market("2026-10-23", "fujairah")
    base_case = cases.build("TD3C", market, freight_value=0.0, freight_basis="usd_t")
    hull = base_case.inputs["war_risk"]["hull_value_usd"]
    marsh = _rate("hormuz_2026_07_22")
    scenarios = [("base", "No war risk, no waiting", base_case, base_case.inputs)]
    for premium, label in ((marsh["low"], "low"), (marsh["high"], "high")):
        scenarios.append(
            (
                "war_%s" % label,
                "War risk %.1f%% of hull value, one transit period" % premium,
                base_case,
                _with_war(base_case.inputs, premium, 1.0),
            )
        )
    for wait in WAIT_DAYS:
        waiting = _with_war(base_case.inputs, marsh["low"], 1.0)
        waiting = dict(waiting, port=dict(waiting["port"], delay_days=wait))
        scenarios.append(
            (
                "wait_%d" % wait,
                "War risk %.1f%% and %d days waiting to transit" % (marsh["low"], wait),
                base_case,
                waiting,
            )
        )
    sts_route = replace(baltic.ROUTES["TD3C"], code="TD3C_STS", load="fujairah")
    sts_case = cases.build("TD3C", market, freight_value=0.0, freight_basis="usd_t", route=sts_route)
    scenarios.append(
        ("sts", "Loading by ship to ship transfer off Fujairah, no Hormuz transit", sts_case, sts_case.inputs)
    )
    td34 = cases.build("TD34", market, freight_value=0.0, freight_basis="usd_t")
    scenarios.append(("td34", "TD34, loading at Mina Al Fahal outside the strait", td34, td34.inputs))

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
            per_level.append(
                {
                    "week_ending": level["week_ending"],
                    "freight_needed_usd_t": needed["usd_t"],
                    "extra_freight_usd_t": needed["usd_t"] - base_at["usd_t"],
                }
            )
        rows.append(
            {
                "id": key,
                "label": label,
                "days": option["days"],
                "extra_days": option["days"] - base_option["days"],
                "laden_nm": option["laden_nm"],
                "tonne_miles": cargo * option["laden_nm"],
                "extra_tonne_miles": cargo * (option["laden_nm"] - base_option["laden_nm"]),
                "war_risk_usd": option["war_risk_usd"],
                "voyage_costs_usd": option["costs_usd"],
                "excluded": option["excluded"],
                "levels": per_level,
            }
        )
    return {
        "as_of": "2026-10-23",
        "hull_value_usd": hull,
        "war_risk_source": marsh["id"],
        "levels": levels,
        "scenarios": rows,
        "td34_vs_td3c_published": {
            "td3c_tce_usd_day": next(e for e in report["2026-10-23"]["entries"] if e["route"] == "TD3C")["tce_usd_day"],
            "td34_tce_usd_day": next(e for e in report["2026-10-23"]["entries"] if e["route"] == "TD34")["tce_usd_day"],
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


def _curve_point(curve_id: str, segment: str, period: str) -> dict[str, Any]:
    curve = next(c for c in cases.seed("ffa.json")["curves"] if c["id"] == curve_id)
    point = next(p for p in curve["segments"][segment]["points"] if p["period"] == period)
    return {"assessed": curve["assessed"], "period": period, "usd_day": point["usd_day"], "source": curve["source"]}


def paper() -> dict[str, Any]:
    rows = []
    dry = {(r["date"], r["route"]): r for r in anchors.dry_weekly()}
    plan = (
        ("2026-07-03", "C3", "wk27_2026", "2026-07"),
        ("2026-07-03", "C5", "wk27_2026", "2026-07"),
        ("2026-10-23", "C3", "wk43_2026", "2026-11"),
        ("2026-10-23", "C5", "wk43_2026", "2026-11"),
    )
    for date, route, curve, month in plan:
        anchor = dry[(date, route)]
        ffa = _curve_point(curve, "capesize", month)
        hub = cases.bunker_hub(baltic.ROUTES[route].load)
        case = cases.build(route, cases.weekly_market(date, hub), freight_value=anchor["freight_usd_t"])
        physical = anchor["engine_tce_usd_day"]
        h = engine.hedge(case.inputs, physical, ffa["usd_day"], None)
        equivalent = engine.freight_for_tce(case.inputs, ffa["usd_day"])["usd_t"]
        rows.append(
            {
                "date": date,
                "route": route,
                "freight_usd_t": anchor["freight_usd_t"],
                "physical_tce_usd_day": physical,
                "ffa": ffa,
                "hedge_days": h["tc_hedge_days"],
                "basis_usd_day": h["basis_vs_tc_ffa_usd_day"],
                "freight_matching_ffa_usd_t": equivalent,
                "spot_index_usd_day": anchor["benchmark_usd_day"],
                "timing_basis_usd_day": ffa["usd_day"] - anchor["benchmark_usd_day"],
                "excluded": anchor["excluded"],
            }
        )
    fixture = cases.seed("ffa.json")["physical_fixtures"][0]
    hub = cases.bunker_hub(baltic.ROUTES["C5"].load)
    market = cases.weekly_market("2026-10-23", hub)
    fixed = engine.evaluate(cases.build("C5", market, freight_value=fixture["freight_usd_t"]).inputs)["tce_usd_day"]
    index = engine.evaluate(cases.build("C5", market, freight_value=fixture["index_same_week"]["C5_usd_t"]).inputs)[
        "tce_usd_day"
    ]
    fixture_row = {
        "date": fixture["date"],
        "laycan": fixture["laycan"],
        "fixture_usd_t": fixture["freight_usd_t"],
        "index_usd_t": fixture["index_same_week"]["C5_usd_t"],
        "fixture_tce_usd_day": fixed,
        "index_tce_usd_day": index,
        "basis_usd_t": fixture["freight_usd_t"] - fixture["index_same_week"]["C5_usd_t"],
        "basis_usd_day": fixed - index,
        "cargo_t": baltic.ROUTES["C5"].cargo_t,
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
    td3c = {
        "ffa_tce_q2_usd_day": tanker["values"]["2026-Q2_tce_usd_day"],
        "published": tanker["published"],
        "physical_q2": q2,
        "basis_usd_day": [p["tce_usd_day"] - tanker["values"]["2026-Q2_tce_usd_day"] for p in q2],
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
