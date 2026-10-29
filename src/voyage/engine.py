"""The voyage estimate: days, fuel, emissions, costs, time charter equivalent, breakevens.

Every function here is pure arithmetic on a plain, JSON shaped input, so that
src/engine.js can repeat it line for line and tools/validate-engine.mjs can
hold the two to 1e-9. No market price, tariff or assumption lives here: those
are inputs, and voyage.cases fills them from the cited seeds.

Units: distances in nautical miles, speeds in knots, time in days, fuel in
tonnes and tonnes per day, prices in USD per tonne, money in USD unless a key
says EUR, emissions in tonnes.

The TCE, as the Baltic Exchange's Guide to Market Benchmarks (v8.8, Appendix
3, page 98) defines it:

    TCE = (gross freight + other revenue - commissions - voyage costs) / total voyage days

Voyage costs are bunkers at sea and in port, port charges, canal tolls, EU ETS
allowances, war risk additional premiums and any other voyage specific cost;
operating and capital costs are not voyage costs. Days are the ballast leg,
the laden leg, port days, canal transit and waiting days, with the sea margin
(the Baltic's weather allowance) applied to steaming time only:

    sea days = distance x (1 + margin) / (speed x 24)

On a trip time charter the owner earns hire for the days from delivery to
redelivery and the charterer pays the trip's bunkers, ports, canals and, under
the BIMCO ETS Allowances Clause for Time Charter Parties 2022, its emission
allowances; the owner pays only the ballast leg that positions the ship.

An additional war risk premium is a percentage of hull value for each period
of up to seven days in a listed area, charged on entering it. On a voyage
charter the charter's premium goes to whichever party the input names as its
payer: usually the charterer, which leaves it out of the owner's TCE, as the
Baltic's TCE descriptions name no such premium. A passage through a listed
area on the ballast leg, the approach to the next loading, is the owner's.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

HOURS_PER_DAY = 24.0
PERCENT = 100.0

#: Emission factors, tonnes per tonne of fuel, by MARPOL fuel class: EU MRV
#: Regulation (EU) 2015/757 Annex I as replaced by Delegated Regulation (EU)
#: 2023/2776 (page 6): HFO is ISO 8217 RME to RMK, LFO RMA to RMD, MGO DMX to DMB.
CO2_FACTOR = {"HFO": 3.114, "LFO": 3.151, "MGO": 3.206}
CH4_FACTOR = {"HFO": 0.00005, "LFO": 0.00005, "MGO": 0.00005}
N2O_FACTOR = {"HFO": 0.00018, "LFO": 0.00018, "MGO": 0.00018}
#: Global warming potentials over 100 years for the EU ETS and MRV: the Annex
#: of Delegated Regulation (EU) 2020/1044 (OJ L 230, page 6).
GWP_CH4 = 28.0
GWP_N2O = 265.0

#: FuelEU Maritime, Regulation (EU) 2023/1805: Annex II lower calorific values
#: (MJ per gram) and well to tank factors (gCO2e per MJ); Annex I takes its GWPs
#: from Directive (EU) 2018/2001 Annex V Part C point 4 (CH4 25, N2O 298).
FUELEU_LCV_MJ_G = {"HFO": 0.0405, "LFO": 0.041, "MGO": 0.0427}
FUELEU_WTT_G_MJ = {"HFO": 13.5, "LFO": 13.2, "MGO": 14.4}
FUELEU_GWP_CH4 = 25.0
FUELEU_GWP_N2O = 298.0
#: Article 4(2): the reference value and the 2 percent cut that applies from 2025.
FUELEU_REFERENCE_G_MJ = 91.16
#: Annex IV Part B: the penalty per tonne of VLSFO equivalent and the energy of one.
FUELEU_PENALTY_EUR_PER_T = 2400.0
FUELEU_MJ_PER_T_VLSFO = 41000.0
GRAMS_PER_TONNE = 1.0e6

#: An additional war risk premium covers a period of up to seven days in a
#: listed area (Platts, 1 April 2026: "per seven-day period").
WAR_RISK_PERIOD_DAYS = 7.0
#: The listed areas the study can price: the Gulf, inside the Strait of Hormuz,
#: and the southern Red Sea and Gulf of Aden, entered at Bab el Mandeb.
WAR_RISK_AREAS = ("gulf", "red_sea")


def _total(values: Iterable[float]) -> float:
    """Left to right addition, as src/engine.js adds: the built-in sum compensates
    rounding from Python 3.12, which would part the two by an ulp."""
    total = 0.0
    for value in values:
        total += value
    return total


# --------------------------------------------------------------------------
# Speed and consumption
# --------------------------------------------------------------------------


def _sorted_curve(curve: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    return sorted((float(v), float(c)) for v, c in curve)


def power_fit(curve: Sequence[Sequence[float]]) -> dict[str, float]:
    """Least squares fit of ln(consumption) on ln(speed): consumption = a x speed ** b.

    Returns a, b and the coefficient of determination r2 of the log fit (1
    when there are two pairs, which the fit passes through exactly).
    """
    pairs = _sorted_curve(curve)
    n = len(pairs)
    xs = [math.log(v) for v, _ in pairs]
    ys = [math.log(c) for _, c in pairs]
    mean_x = _total(xs) / n
    mean_y = _total(ys) / n
    sxx = _total((x - mean_x) ** 2 for x in xs)
    sxy = _total((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    b = sxy / sxx
    log_a = mean_y - b * mean_x
    ss_tot = _total((y - mean_y) ** 2 for y in ys)
    ss_res = _total((y - (log_a + b * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return {"a": math.exp(log_a), "b": b, "r2": r2}


def consumption_tpd(curve: Sequence[Sequence[float]], speed_kn: float) -> float:
    """Fuel per day at a speed: linear between published pairs; outside them the
    fitted power law's exponent, anchored at the nearest published pair so the
    curve stays continuous."""
    pairs = _sorted_curve(curve)
    lo_v, lo_c = pairs[0]
    hi_v, hi_c = pairs[-1]
    if speed_kn < lo_v or speed_kn > hi_v:
        b = power_fit(pairs)["b"]
        anchor_v, anchor_c = (lo_v, lo_c) if speed_kn < lo_v else (hi_v, hi_c)
        return anchor_c * (speed_kn / anchor_v) ** b
    for (v0, c0), (v1, c1) in itertools.pairwise(pairs):
        if v0 <= speed_kn <= v1:
            if v1 == v0:
                return c0
            return c0 + (c1 - c0) * (speed_kn - v0) / (v1 - v0)
    return hi_c


def sea_days(distance_nm: float, speed_kn: float, margin: float) -> float:
    """Steaming days with the weather allowance on the distance: d (1 + m) / (24 v)."""
    if distance_nm <= 0:
        return 0.0
    return distance_nm * (1.0 + margin) / (speed_kn * HOURS_PER_DAY)


# --------------------------------------------------------------------------
# Worldscale and freight
# --------------------------------------------------------------------------


def ws_to_usd_t(ws_points: float, flat_rate_usd_t: float) -> float:
    """Worldscale points to USD per tonne: WS / 100 x the route's flat rate."""
    return ws_points / PERCENT * flat_rate_usd_t


def usd_t_to_ws(usd_t: float, flat_rate_usd_t: float) -> float:
    """USD per tonne to Worldscale points: 100 x rate / flat rate."""
    return PERCENT * usd_t / flat_rate_usd_t


def freight_usd_t(inputs: Mapping[str, Any]) -> float:
    """The freight of a voyage charter in USD per tonne, whatever basis it is quoted on."""
    basis = inputs["freight_basis"]
    value = inputs["freight_value"]
    if basis == "usd_t":
        return value
    if basis == "ws":
        return ws_to_usd_t(value, inputs["flat_rate_usd_t"])
    if basis == "lump_sum":
        return value / inputs["cargo_t"]
    raise ValueError("freight_usd_t applies to voyage charters, not %r" % basis)


# --------------------------------------------------------------------------
# The voyage
# --------------------------------------------------------------------------


def _grade(in_eca: bool, scrubber: bool, scrubber_in_eca: bool) -> str:
    """The fuel a main engine burns: MGO in an ECA unless a scrubber may run there,
    VLSFO outside, HSFO behind a scrubber."""
    if in_eca:
        return "hsfo" if (scrubber and scrubber_in_eca) else "mgo"
    return "hsfo" if scrubber else "vlsfo"


def _class_of(grade: str, vlsfo_class: str) -> str:
    """The MARPOL fuel class of a grade for the emission factors."""
    if grade == "hsfo":
        return "HFO"
    if grade == "mgo":
        return "MGO"
    return vlsfo_class


def days(inputs: Mapping[str, Any]) -> dict[str, float]:
    """Every day of the voyage by activity, and their total."""
    margin = inputs["sea_margin"]
    laden = inputs["laden"]
    ballast = inputs["ballast"]
    port = inputs["port"]
    out = {
        "ballast_sea": sea_days(ballast["distance_nm"], ballast["speed_kn"], margin),
        "laden_sea": sea_days(laden["distance_nm"], laden["speed_kn"], margin),
        "load": port["load_days"],
        "discharge": port["discharge_days"],
        "waiting": port["waiting_days"],
        "canal": port["canal_days"],
        "delay": port["delay_days"],
        "sts": port["sts_days"],
    }
    out["port_total"] = out["load"] + out["discharge"] + out["waiting"] + out["canal"] + out["delay"] + out["sts"]
    out["sea_total"] = out["ballast_sea"] + out["laden_sea"]
    out["total"] = out["sea_total"] + out["port_total"]
    # The trip of a time charter runs from delivery at the load area to redelivery
    # after discharge: everything except the ballast leg.
    out["trip"] = out["total"] - out["ballast_sea"]
    return out


def _leg_fuel(
    leg: Mapping[str, Any], curve: Sequence[Sequence[float]], margin: float, inputs: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Fuel on one leg, split by the ECA miles: [{grade, tonnes, days, ets_share}]."""
    speed = leg["speed_kn"]
    tpd = consumption_tpd(curve, speed)
    eca_nm = min(leg["eca_nm"], leg["distance_nm"])
    open_nm = leg["distance_nm"] - eca_nm
    out = []
    for nm, in_eca in ((open_nm, False), (eca_nm, True)):
        d = sea_days(nm, speed, margin)
        if d <= 0:
            continue
        grade = _grade(in_eca, inputs["scrubber"], inputs["scrubber_in_eca"])
        out.append({"grade": grade, "tonnes": tpd * d, "days": d, "ets_share": leg["ets_share"]})
        if inputs["mgo_at_sea_tpd"] > 0:
            out.append(
                {"grade": "mgo", "tonnes": inputs["mgo_at_sea_tpd"] * d, "days": d, "ets_share": leg["ets_share"]}
            )
    return out


def fuel(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Fuel burnt by activity and grade, in tonnes, with each lot's ETS coverage share."""
    margin = inputs["sea_margin"]
    port = inputs["port"]
    lots: dict[str, list[dict[str, Any]]] = {
        "ballast": _leg_fuel(inputs["ballast"], inputs["ballast_curve"], margin, inputs),
        "laden": _leg_fuel(inputs["laden"], inputs["laden_curve"], margin, inputs),
    }
    for activity in ("load", "discharge", "waiting", "canal", "delay", "sts"):
        d = port[activity + "_days"]
        tpd = port[activity + "_tpd"]
        if d <= 0 or tpd <= 0:
            lots[activity] = []
            continue
        grade = _grade(port[activity + "_eca"], inputs["scrubber"], inputs["scrubber_in_eca"])
        lots[activity] = [{"grade": grade, "tonnes": tpd * d, "days": d, "ets_share": port[activity + "_ets_share"]}]
    tonnes = {"vlsfo": 0.0, "hsfo": 0.0, "mgo": 0.0}
    for lot_list in lots.values():
        for lot in lot_list:
            tonnes[lot["grade"]] += lot["tonnes"]
    return {"lots": lots, "tonnes": tonnes, "total_t": tonnes["vlsfo"] + tonnes["hsfo"] + tonnes["mgo"]}


_PRICE_KEY = {"vlsfo": "vlsfo_usd_t", "hsfo": "hsfo_usd_t", "mgo": "mgo_usd_t"}


def _lot_cost(lot: Mapping[str, Any], prices: Mapping[str, float]) -> float:
    return lot["tonnes"] * prices[_PRICE_KEY[lot["grade"]]]


def emissions(fuel_result: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, float]:
    """CO2 and CO2 equivalent, emitted and covered by the EU ETS, in tonnes.

    Covered emissions apply each lot's coverage share (1 between two EEA ports
    and in an EEA port, 0.5 into or out of the EEA, 0 elsewhere); methane and
    nitrous oxide are added at their GWPs when include_non_co2 is set, which the
    ETS does from 2026.
    """
    ets = inputs["ets"]
    vlsfo_class = inputs["vlsfo_class"]
    co2 = co2e = covered = 0.0
    for lot_list in fuel_result["lots"].values():
        for lot in lot_list:
            klass = _class_of(lot["grade"], vlsfo_class)
            lot_co2 = lot["tonnes"] * CO2_FACTOR[klass]
            lot_other = lot["tonnes"] * (CH4_FACTOR[klass] * GWP_CH4 + N2O_FACTOR[klass] * GWP_N2O)
            co2 += lot_co2
            co2e += lot_co2 + lot_other
            counted = lot_co2 + (lot_other if ets["include_non_co2"] else 0.0)
            covered += counted * lot["ets_share"]
    return {"co2_t": co2, "co2e_t": co2e, "ets_covered_t": covered}


def ets_cost_usd(covered_t: float, ets: Mapping[str, Any]) -> float:
    """Allowances to surrender times their price: covered x phase-in x EUA x USD per EUR."""
    return covered_t * ets["phase_in"] * ets["eua_eur_t"] * ets["usd_per_eur"]


def fueleu(fuel_result: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, float]:
    """The voyage's FuelEU Maritime balance and the penalty it would add if not pooled.

    Energy in scope is each lot's energy times its coverage share (the same
    shares as the ETS: 1 within and between EU ports, 0.5 into or out of them).
    The GHG intensity is well to wake: WtT plus tank to wake CO2, CH4 and N2O
    over the lower calorific value. The compliance balance is (target -
    intensity) x energy; a deficit is priced by Annex IV Part B:
    |balance| / (intensity x 41,000) x 2,400 EUR, before any multiplier for
    consecutive years. FuelEU is assessed on a ship's whole year, with pooling,
    banking and borrowing; for one voyage this is the penalty its own fuel adds
    to that year's deficit, valid when the ship's year burns the same mix.
    """
    vlsfo_class = inputs["vlsfo_class"]
    target = FUELEU_REFERENCE_G_MJ * (1.0 - inputs["fueleu"]["reduction_pct"] / PERCENT)
    energy = 0.0
    weighted = 0.0
    for lot_list in fuel_result["lots"].values():
        for lot in lot_list:
            klass = _class_of(lot["grade"], vlsfo_class)
            mj = lot["tonnes"] * GRAMS_PER_TONNE * FUELEU_LCV_MJ_G[klass] * lot["ets_share"]
            ttw = (
                CO2_FACTOR[klass] + CH4_FACTOR[klass] * FUELEU_GWP_CH4 + N2O_FACTOR[klass] * FUELEU_GWP_N2O
            ) / FUELEU_LCV_MJ_G[klass]
            intensity = FUELEU_WTT_G_MJ[klass] + ttw
            energy += mj
            weighted += mj * intensity
    if energy == 0:
        return {
            "energy_mj": 0.0,
            "intensity_g_mj": 0.0,
            "target_g_mj": target,
            "balance_g": 0.0,
            "penalty_eur": 0.0,
            "penalty_usd": 0.0,
        }
    intensity = weighted / energy
    balance = (target - intensity) * energy
    penalty_eur = 0.0
    if balance < 0:
        penalty_eur = -balance / (intensity * FUELEU_MJ_PER_T_VLSFO) * FUELEU_PENALTY_EUR_PER_T
    return {
        "energy_mj": energy,
        "intensity_g_mj": intensity,
        "target_g_mj": target,
        "balance_g": balance,
        "penalty_eur": penalty_eur,
        "penalty_usd": penalty_eur * inputs["ets"]["usd_per_eur"],
    }


def war_risk(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The additional war risk premium by listed area: days inside, seven day periods, dollars.

    Each area carries its premium (percent of hull value a period), the miles
    each leg sails inside it, the port activities spent inside it, how many
    separate times the charter's voyage enters it, and how many times the
    ballast leg passes through it on the way back to the load port. The
    charter's periods are the days inside over seven, rounded up, and never
    fewer than its entries, since a premium is charged on entering; each
    ballast transit is one period. The charter's premium follows the payer;
    a ballast transit, the approach to the next loading, is the owner's
    (Gard, 21 March 2026). A crew war bonus is added to the charter's part.
    """
    war = inputs["war_risk"]
    margin = inputs["sea_margin"]
    port = inputs["port"]
    areas: dict[str, dict[str, float]] = {}
    charter = 0.0
    ballast = 0.0
    for name in WAR_RISK_AREAS:
        area = war["areas"][name]
        rate = area["premium_pct"] / PERCENT * war["hull_value_usd"]
        inside = 0.0
        periods = 0.0
        if area["entries"] > 0:
            inside = (
                sea_days(area["laden_nm"], inputs["laden"]["speed_kn"], margin)
                + sea_days(area["ballast_nm"], inputs["ballast"]["speed_kn"], margin)
                + _total(port[activity + "_days"] for activity in area["port_activities"])
            )
            periods = max(float(area["entries"]), float(math.ceil(inside / WAR_RISK_PERIOD_DAYS)))
        transits = float(area["ballast_transits"])
        usd = rate * periods
        transit_usd = rate * transits
        areas[name] = {
            "days": inside,
            "periods": periods,
            "usd": usd,
            "ballast_periods": transits,
            "ballast_usd": transit_usd,
        }
        charter += usd
        ballast += transit_usd
    crew = war["crew_bonus_usd"]
    return {
        "areas": areas,
        "charter_usd": charter + crew,
        "ballast_usd": ballast,
        "premium_usd": charter + ballast,
        "total_usd": charter + ballast + crew,
    }


#: The activities whose costs a trip charterer pays, and the owner the rest.
_TRIP_ACTIVITIES = ("laden", "load", "discharge", "waiting", "canal", "delay", "sts")


def evaluate(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Every line of the voyage estimate, and the TCE.

    The owner's voyage costs on a voyage charter are all of them, except the
    charter's war risk premium when its payer is the charterer. On a trip time
    charter they are the ballast leg only: its bunkers, its allowances and any
    premium for a ballast transit; the trip's costs are reported as the
    charterer's.
    """
    d = days(inputs)
    f = fuel(inputs)
    prices = inputs["prices"]
    trip = inputs["contract"] == "trip"

    bunkers_by_activity = {name: _total(_lot_cost(lot, prices) for lot in lots) for name, lots in f["lots"].items()}
    bunkers_by_grade = {"vlsfo": 0.0, "hsfo": 0.0, "mgo": 0.0}
    for lots in f["lots"].values():
        for lot in lots:
            bunkers_by_grade[lot["grade"]] += _lot_cost(lot, prices)

    em = emissions(f, inputs)
    ets_all = ets_cost_usd(em["ets_covered_t"], inputs["ets"])
    fe = fueleu(f, inputs)

    costs = inputs["costs"]
    war = war_risk(inputs)
    port_usd = costs["port_load_usd"] + costs["port_discharge_usd"]
    canal_usd = costs["canal_laden_usd"] + costs["canal_ballast_usd"]
    other_usd = costs["other_usd"] + costs["sts_usd"]
    fueleu_usd = fe["penalty_usd"] if inputs["fueleu"]["include"] else 0.0

    if trip:
        ballast_only = {"ballast": f["lots"]["ballast"]}
        ballast_fuel = {"lots": ballast_only}
        owner_bunkers = bunkers_by_activity["ballast"]
        owner_ets = ets_cost_usd(emissions(ballast_fuel, inputs)["ets_covered_t"], inputs["ets"])
        owner_fueleu = fueleu(ballast_fuel, inputs)["penalty_usd"] if inputs["fueleu"]["include"] else 0.0
        owner_canal = costs["canal_ballast_usd"]
        charterer_costs = (
            _total(bunkers_by_activity[a] for a in _TRIP_ACTIVITIES)
            + (ets_all - owner_ets)
            + port_usd
            + costs["canal_laden_usd"]
            + war["charter_usd"]
            + other_usd
            + (fueleu_usd - owner_fueleu)
        )
        lines = {
            "bunkers": owner_bunkers,
            "ports": 0.0,
            "canals": owner_canal,
            "ets": owner_ets,
            "war_risk": war["ballast_usd"],
            "other": 0.0,
            "fueleu": owner_fueleu,
        }
        gross = inputs["freight_value"] * d["trip"]
    else:
        charterer_pays_war = inputs["war_risk"]["payer"] == "charterer"
        charterer_costs = war["charter_usd"] if charterer_pays_war else 0.0
        lines = {
            "bunkers": _total(bunkers_by_activity.values()),
            "ports": port_usd,
            "canals": canal_usd,
            "ets": ets_all,
            "war_risk": war["ballast_usd"] + (0.0 if charterer_pays_war else war["charter_usd"]),
            "other": other_usd,
            "fueleu": fueleu_usd,
        }
        gross = freight_usd_t(inputs) * inputs["cargo_t"]

    other_revenue = inputs["other_revenue_usd"]
    commission = (gross + other_revenue) * inputs["commission_pct"] / PERCENT
    net_revenue = gross + other_revenue - commission
    voyage_costs = _total(lines.values())
    result = net_revenue - voyage_costs
    tce = result / d["total"]
    return {
        "days": d,
        "fuel_t": f["tonnes"],
        "fuel_total_t": f["total_t"],
        "bunkers_by_activity_usd": bunkers_by_activity,
        "bunkers_by_grade_usd": bunkers_by_grade,
        "emissions": em,
        "ets_all_usd": ets_all,
        "fueleu": fe,
        "war_risk": war,
        "revenue": {
            "gross_usd": gross,
            "other_usd": other_revenue,
            "commission_usd": commission,
            "net_usd": net_revenue,
        },
        "costs": dict(lines, total_usd=voyage_costs),
        "charterer_costs_usd": charterer_costs,
        "result_usd": result,
        "tce_usd_day": tce,
    }


# --------------------------------------------------------------------------
# Breakevens and speed
# --------------------------------------------------------------------------


def freight_for_tce(inputs: Mapping[str, Any], target_tce_usd_day: float) -> dict[str, float | None]:
    """The freight at which the voyage earns a target TCE, in the units a desk quotes.

    The TCE is linear in the freight, so the answer is closed form:
    revenue needed = (target x days + voyage costs) / (1 - commission) - other revenue.
    For a voyage charter it is given per tonne, as a lump sum and, where a flat
    rate is known, in Worldscale points; for a trip as hire per day.
    """
    r = evaluate(inputs)
    keep = 1.0 - inputs["commission_pct"] / PERCENT
    needed = (target_tce_usd_day * r["days"]["total"] + r["costs"]["total_usd"]) / keep - inputs["other_revenue_usd"]
    if inputs["contract"] == "trip":
        return {"hire_usd_day": needed / r["days"]["trip"], "usd_t": None, "lump_sum_usd": None, "ws": None}
    usd_t = needed / inputs["cargo_t"]
    flat = inputs.get("flat_rate_usd_t")
    return {
        "hire_usd_day": None,
        "usd_t": usd_t,
        "lump_sum_usd": needed,
        "ws": usd_t_to_ws(usd_t, flat) if flat else None,
    }


def with_speed(inputs: Mapping[str, Any], laden_kn: float, ballast_kn: float) -> dict[str, Any]:
    """A copy of the inputs at other laden and ballast speeds."""
    out = dict(inputs)
    out["laden"] = dict(inputs["laden"], speed_kn=laden_kn)
    out["ballast"] = dict(inputs["ballast"], speed_kn=ballast_kn)
    return out


def tce_by_speed(inputs: Mapping[str, Any], speeds: Sequence[float]) -> list[dict[str, float]]:
    """TCE at each laden speed, the ballast speed keeping its published gap to the laden one."""
    gap = inputs["ballast"]["speed_kn"] - inputs["laden"]["speed_kn"]
    out = []
    for v in speeds:
        r = evaluate(with_speed(inputs, v, v + gap))
        out.append(
            {
                "laden_kn": v,
                "ballast_kn": v + gap,
                "tce_usd_day": r["tce_usd_day"],
                "days": r["days"]["total"],
                "bunkers_usd": r["costs"]["bunkers"],
            }
        )
    return out


#: The speed search: every laden speed on this grid between the bounds.
SPEED_STEP_KN = 0.01


def optimal_speed(inputs: Mapping[str, Any], lo_kn: float, hi_kn: float) -> dict[str, float]:
    """The laden speed on a 0.01 knot grid in [lo, hi] that maximises the TCE, ballast keeping its gap.

    A plain grid, so that the browser, repeating the same arithmetic, picks the
    same speed: a finer search would let rounding in the last digit choose
    between two speeds whose TCEs differ by less than a cent a day.
    """
    gap = inputs["ballast"]["speed_kn"] - inputs["laden"]["speed_kn"]
    steps = round((hi_kn - lo_kn) / SPEED_STEP_KN)
    best_v = lo_kn
    best_t = evaluate(with_speed(inputs, lo_kn, lo_kn + gap))["tce_usd_day"]
    for k in range(1, steps + 1):
        v = lo_kn + k * SPEED_STEP_KN
        t = evaluate(with_speed(inputs, v, v + gap))["tce_usd_day"]
        if t > best_t:
            best_v, best_t = v, t
    return {"laden_kn": best_v, "ballast_kn": best_v + gap, "tce_usd_day": best_t}


#: The shocks of the sensitivity chart: (id, low factor or shift, high factor or shift).
SHOCKS: tuple[tuple[str, float, float], ...] = (
    ("freight", 0.9, 1.1),
    ("bunkers", 0.9, 1.1),
    ("speed", -1.0, 1.0),
    ("port_days", -1.0, 1.0),
    ("eua", 0.8, 1.2),
)


def shocked(inputs: Mapping[str, Any], shock: str, value: float) -> dict[str, Any]:
    """A copy of the inputs with one shock applied.

    freight, bunkers and eua scale the rate, every fuel price and the allowance
    price by a factor; speed shifts both legs by knots; port_days shifts the
    waiting days by days, never below zero.
    """
    out = dict(inputs)
    if shock == "freight":
        out["freight_value"] = inputs["freight_value"] * value
    elif shock == "bunkers":
        out["prices"] = {key: price * value for key, price in inputs["prices"].items()}
    elif shock == "speed":
        out = with_speed(inputs, inputs["laden"]["speed_kn"] + value, inputs["ballast"]["speed_kn"] + value)
    elif shock == "port_days":
        port = dict(inputs["port"])
        port["waiting_days"] = max(0.0, port["waiting_days"] + value)
        out["port"] = port
    elif shock == "eua":
        out["ets"] = dict(inputs["ets"], eua_eur_t=inputs["ets"]["eua_eur_t"] * value)
    else:
        raise ValueError("unknown shock %r" % shock)
    return out


def sensitivities(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The TCE under each shock, low and high, beside the base TCE."""
    base_tce = evaluate(inputs)["tce_usd_day"]
    out = []
    for shock, low, high in SHOCKS:
        low_tce = evaluate(shocked(inputs, shock, low))["tce_usd_day"]
        high_tce = evaluate(shocked(inputs, shock, high))["tce_usd_day"]
        out.append(
            {
                "id": shock,
                "low": low,
                "high": high,
                "low_tce_usd_day": low_tce,
                "high_tce_usd_day": high_tce,
                "base_tce_usd_day": base_tce,
            }
        )
    return out


# --------------------------------------------------------------------------
# Paper: FFAs and hedges
# --------------------------------------------------------------------------


def hedge(
    inputs: Mapping[str, Any], physical_tce_usd_day: float, tc_ffa_usd_day: float | None, route_ffa_usd_t: float | None
) -> dict[str, float | None]:
    """The paper side of a physical voyage.

    A time charter FFA (USD/day, settling on a monthly average of the Baltic
    time charter index) hedges the voyage's days: size = the voyage's total
    days. A voyage route FFA (USD/t, settling on the monthly average of the
    route assessment) hedges the cargo: size = the cargo in tonnes, and its
    level converts to a TCE with this same engine.

    A time charter index and its FFA are gross daily hire (each of its routes
    at its total commission, GMB v8.8 pages 77 and 78), while a voyage TCE is
    net of commission. The guide grosses a voyage's net TCE up by the
    commission before comparing it with time charter rates (section 7.4.3,
    pages 35 and 36), and so does the basis here: the grossed up TCE less the
    time charter FFA. Against a route FFA, converted with the same engine, both
    sides are net. The owner keeps the net share of what the index pays, so
    the voyage's days times that share hedge its net earnings exactly.
    """
    total_days = days(inputs)["total"]
    keep = 1.0 - inputs["commission_pct"] / PERCENT
    gross_tce = physical_tce_usd_day / keep
    route_tce = None
    if route_ffa_usd_t is not None:
        priced = dict(inputs, freight_basis="usd_t", freight_value=route_ffa_usd_t)
        route_tce = evaluate(priced)["tce_usd_day"]
    return {
        "tc_hedge_days": total_days,
        "tc_hedge_days_net": total_days * keep,
        "route_hedge_t": inputs["cargo_t"],
        "route_ffa_tce_usd_day": route_tce,
        "physical_tce_gross_usd_day": gross_tce,
        "basis_vs_tc_ffa_usd_day": None if tc_ffa_usd_day is None else gross_tce - tc_ffa_usd_day,
        "basis_vs_route_ffa_usd_day": None if route_tce is None else physical_tce_usd_day - route_tce,
    }


def constants() -> dict[str, Any]:
    """Every constant the engine computes with, for src/engine.js, which holds no number of its own."""
    return {
        "HOURS_PER_DAY": HOURS_PER_DAY,
        "PERCENT": PERCENT,
        "CO2_FACTOR": CO2_FACTOR,
        "CH4_FACTOR": CH4_FACTOR,
        "N2O_FACTOR": N2O_FACTOR,
        "GWP_CH4": GWP_CH4,
        "GWP_N2O": GWP_N2O,
        "FUELEU_LCV_MJ_G": FUELEU_LCV_MJ_G,
        "FUELEU_WTT_G_MJ": FUELEU_WTT_G_MJ,
        "FUELEU_GWP_CH4": FUELEU_GWP_CH4,
        "FUELEU_GWP_N2O": FUELEU_GWP_N2O,
        "FUELEU_REFERENCE_G_MJ": FUELEU_REFERENCE_G_MJ,
        "FUELEU_PENALTY_EUR_PER_T": FUELEU_PENALTY_EUR_PER_T,
        "FUELEU_MJ_PER_T_VLSFO": FUELEU_MJ_PER_T_VLSFO,
        "GRAMS_PER_TONNE": GRAMS_PER_TONNE,
        "SPEED_STEP_KN": SPEED_STEP_KN,
        "WAR_RISK_PERIOD_DAYS": WAR_RISK_PERIOD_DAYS,
        "WAR_RISK_AREAS": list(WAR_RISK_AREAS),
        "SHOCKS": [list(shock) for shock in SHOCKS],
    }
