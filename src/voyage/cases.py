"""Voyages as the engine prices them: every input of a Baltic route on a dated market, with its source.

build(route, market) returns the engine's input (a plain dict, the shape
voyage.engine and src/engine.js read) and, beside it, where every value comes
from: "sourced" (a dated public document, cited), "derived" (computed from
sourced values by a stated rule), or "empty" (no public source; the value is
left out and the result says so). Nothing is filled with an assumption: an
empty cost counts as zero and the case lists it among what its TCE leaves out.

The rules, each recorded in docs/methodology.md:

* Legs: the laden leg from the load port to the discharge port and the ballast
  leg from the discharge port (the Baltic's TCE delivery port) back to the load
  port, on the routings of voyage.baltic, with searoute distances and the miles
  inside each emission control area in force on the voyage date.
* Days: the 5 percent weather margin on steaming time; port, waiting and canal
  days from the Baltic's TCE route description for tankers; for dry routes the
  laytime of the route description converted to calendar days (Saturdays and
  Sundays excepted terms count five working days a week; turn time added).
* Fuel: non-scrubber ships burn VLSFO outside emission control areas and MGO
  inside them, in ports inside them and at berth in EU ports.
* Prices: the bunker hub nearest the load port (voyage.ports.BUNKER_HUBS).
* Carbon: EU ETS shares by leg and port, the year's phase-in, the month's EUA
  price and dollar rate.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache, lru_cache
from typing import Any

from . import baltic, eca, geo, jsonio, sea_routes
from .ports import BUNKER_HUBS
from .sources import base

SEA_MARGIN = baltic.TANKER_SEA_MARGIN
GRADES = ("vlsfo", "hsfo", "mgo")
#: SSHEX laytime counts five working days in seven.
WORKING_DAYS_PER_WEEK = 5.0
DAYS_PER_WEEK = 7.0
HOURS_PER_DAY = 24.0
#: The study's choice of FuelEU's reduction for 2025 to 2029, Article 4(2).
FUELEU_REDUCTION_2025_PCT = 2.0
#: Article 3gb of the ETS Directive: the share of verified emissions surrendered.
ETS_PHASE_IN = {2024: 0.40, 2025: 0.70}
ETS_FULL_FROM = 2026


# --------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------


@cache
def seed(name: str) -> dict[str, Any]:
    return jsonio.read(base.SEED / name)


@lru_cache(maxsize=1)
def lines() -> dict[str, list[list[float]]]:
    payload = json.loads(gzip.decompress((base.SEED / "sea_routes.geojson.gz").read_bytes()))
    return {feature["id"]: feature["geometry"]["coordinates"] for feature in payload["features"]}


@lru_cache(maxsize=1)
def ports() -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in seed("sea_routes.json")["ports"]}


@lru_cache(maxsize=1)
def zones() -> tuple[eca.Zone, ...]:
    out = []
    for z in seed("eca.json")["zones"]:
        rings = tuple([(float(lon), float(lat)) for lon, lat in ring] for ring in z["rings"])
        out.append(eca.Zone(z["id"], z["name"], z["in_force_from"], z["source"], z["construction"], rings))
    return tuple(out)


def leg_record(origin: str, destination: str, routing: str) -> dict[str, Any]:
    return seed("sea_routes.json")["legs"][sea_routes.leg_key(origin, destination, routing)]


@cache
def eca_miles(origin: str, destination: str, routing: str, on_date: str) -> tuple[tuple[str, float], ...]:
    """Miles of a leg inside each emission control area in force on a date, by zone."""
    coordinates = lines()[sea_routes.leg_key(origin, destination, routing)]
    active = eca.in_force(zones(), on_date)
    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]
    box = (min(lons), min(lats), max(lons), max(lats))
    near = []
    for zone in active:
        zl = [p[0] for p in zone.rings[0]]
        zt = [p[1] for p in zone.rings[0]]
        if max(zl) >= box[0] and min(zl) <= box[2] and max(zt) >= box[1] and min(zt) <= box[3]:
            near.append(zone)
    found = eca.miles_in(coordinates, near)
    return tuple(sorted((k, round(v, 1)) for k, v in found.items()))


def port_in_eca(port_id: str, on_date: str) -> str | None:
    """The emission control area a port lies in on a date, or None."""
    p = ports()[port_id]
    for zone in eca.in_force(zones(), on_date):
        if geo.point_in_polygon((p["lon"], p["lat"]), zone.rings):
            return zone.id
    return None


def ets_share(origin: str, destination: str) -> float:
    """EU ETS coverage of a voyage between two ports of call: 1 between EEA ports, 0.5 into or out of one."""
    a, b = ports()[origin]["eea"], ports()[destination]["eea"]
    if a and b:
        return 1.0
    if a or b:
        return 0.5
    return 0.0


@cache
def bunker_hub(load_port: str) -> str:
    """The bunker hub nearest a load port by sea, on the shortest routing."""
    if load_port in BUNKER_HUBS:
        return load_port
    distances = {hub: leg_record(load_port, hub, "direct")["distance_nm"] for hub in BUNKER_HUBS}
    return min(distances, key=distances.__getitem__)


# --------------------------------------------------------------------------
# Markets
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Market:
    """A dated market: the bunker prices, allowance price and dollar rate a case is priced at."""

    id: str
    label: str
    date: str
    #: hub -> {grade: (price, source text)}
    bunkers: Mapping[str, Mapping[str, tuple[float, str]]]
    eua_month: str
    eua_eur_t: float
    eua_source: str
    usd_per_eur: float
    fx_source: str


def _eua(month: str) -> tuple[float, str]:
    from .sources import ec_eua

    rows = ec_eua.read_cache()
    available = sorted(m for m in rows if m <= month)
    if not available:
        raise ValueError("no EUA price on or before %s" % month)
    row = rows[available[-1]]
    return float(row["eua_eur_t"]), "%s, %s monthly average (%s)" % (row["source"], available[-1], row["report"])


def _fx(month: str) -> tuple[float, str]:
    from .sources import frb_h10

    days = frb_h10.read_cache()
    months = sorted({d[:7] for d, v in days if v is not None and d[:7] <= month})
    chosen = months[-1]
    value, count = frb_h10.monthly_mean(chosen)
    return value, "Federal Reserve H.10, mean of %d published days of %s" % (count, chosen)


@cache
def common_market() -> Market:
    """The study's common dated market, August 2026."""
    spec = seed("market.json")["common_market"]
    bunkers = {
        hub: {
            grade: (float(v["value"]), "Ship & Bunker, %s, %s" % (hub.title(), v["period"]))
            for grade, v in grades.items()
        }
        for hub, grades in spec["bunkers_usd_t"].items()
    }
    eua_value, eua_source = _eua(spec["eua"]["month"])
    fx_value, fx_source = _fx(spec["usd_per_eur"]["month"])
    return Market(
        "common",
        spec["label"],
        spec["month"] + "-31",
        bunkers,
        spec["eua"]["month"],
        eua_value,
        eua_source,
        fx_value,
        fx_source,
    )


@cache
def weekly_market(date: str, hub: str | None = None, max_lag_days: int = 7) -> Market:
    """The latest brokers' bunker table dated on, or at most max_lag_days before, a date.

    With a hub, only a table that prices that hub qualifies.
    """
    from datetime import date as _date

    target = _date.fromisoformat(date)
    best = None
    for week in seed("market.json")["weekly_bunkers_usd_t"]["weeks"]:
        d = _date.fromisoformat(week["date"])
        lag = (target - d).days
        if hub is not None and hub not in week["prices"]:
            continue
        if 0 <= lag <= max_lag_days and (best is None or d > _date.fromisoformat(best["date"])):
            best = week
    if best is None:
        raise ValueError("no weekly bunker table within %d days before %s" % (max_lag_days, date))
    bunkers = {
        h: {grade: (float(values[i]), "%s, %s" % (best["source"], best["date"])) for i, grade in enumerate(GRADES)}
        for h, values in best["prices"].items()
    }
    month = date[:7]
    eua_value, eua_source = _eua(month)
    fx_value, fx_source = _fx(month)
    return Market(
        "week_" + best["date"],
        "week of %s" % best["date"],
        date,
        bunkers,
        month,
        eua_value,
        eua_source,
        fx_value,
        fx_source,
    )


@cache
def quarter_market(quarter: str, date: str) -> Market:
    """Ship & Bunker's quarterly averages for a quarter (YYYY-Qn), for an anchor date without a weekly table."""
    for q in seed("market.json")["quarterly_bunkers_usd_t"]["quarters"]:
        if q["quarter"] == quarter:
            bunkers = {
                hub: {grade: (float(spec["values"][i]), "%s" % q["source"]) for i, grade in enumerate(GRADES)}
                for hub, spec in q["prices"].items()
            }
            month = date[:7]
            eua_value, eua_source = _eua(month)
            fx_value, fx_source = _fx(month)
            return Market(
                "quarter_" + quarter,
                "%s average" % quarter,
                date,
                bunkers,
                month,
                eua_value,
                eua_source,
                fx_value,
                fx_source,
            )
    raise ValueError("no quarterly bunker table for %s" % quarter)


def phase_in(year: int) -> float:
    return 1.0 if year >= ETS_FULL_FROM else ETS_PHASE_IN.get(year, 0.0)


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


@dataclass
class Case:
    id: str
    route: str
    title: str
    inputs: dict[str, Any]
    sources: dict[str, dict[str, str]] = field(default_factory=dict)
    excluded: list[str] = field(default_factory=list)
    legs: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "route": self.route,
            "title": self.title,
            "inputs": self.inputs,
            "sources": self.sources,
            "excluded": self.excluded,
            "legs": self.legs,
            "notes": self.notes,
        }


def _days_sshex(cargo_t: float, rate_tpd: float, turn_h: float) -> float:
    return cargo_t / rate_tpd * DAYS_PER_WEEK / WORKING_DAYS_PER_WEEK + turn_h / HOURS_PER_DAY


def _days_shinc(cargo_t: float, rate_tpd: float, turn_h: float) -> float:
    return cargo_t / rate_tpd + turn_h / HOURS_PER_DAY


def _leg(origin: str, destination: str, routing: str, speed_kn: float, on_date: str) -> tuple[dict[str, Any], dict]:
    record = leg_record(origin, destination, routing)
    miles = dict(eca_miles(origin, destination, routing, on_date))
    leg = {
        "distance_nm": record["distance_nm"],
        "speed_kn": speed_kn,
        "eca_nm": round(sum(miles.values()), 1),
        "ets_share": ets_share(origin, destination),
    }
    info = {
        "from": origin,
        "to": destination,
        "routing": routing,
        "eca_by_zone_nm": miles,
        "passes": record["passes"],
        "key": sea_routes.leg_key(origin, destination, routing),
    }
    return leg, info


def build(
    route_code: str,
    market: Market,
    *,
    freight_value: float | None = None,
    freight_basis: str | None = None,
    freight_source: str = "",
    laden_routing: str | None = None,
    ballast_routing: str | None = None,
    ballast_from: str | None = None,
    case_id: str | None = None,
    route: baltic.Route | None = None,
) -> Case:
    """The engine input for a Baltic route on a market, with every value's source.

    route replaces the Baltic definition of route_code, for a voyage the guide
    does not define (the analyses' detour and transfer variants).
    """
    route = route or baltic.ROUTES[route_code]
    vessel = baltic.vessel_for(route, market.date)
    on_date = market.date
    year = int(on_date[:4])
    laden_routing = laden_routing or route.laden_routing
    ballast_routing = ballast_routing or route.ballast_routing
    ballast_from = ballast_from or route.discharge
    gmb = "GMB v8.8 page %d" % route.page

    laden, laden_info = _leg(route.load, route.discharge, laden_routing, vessel.reference_laden_kn, on_date)
    ballast, ballast_info = _leg(ballast_from, route.load, ballast_routing, vessel.reference_ballast_kn, on_date)

    hub = bunker_hub(route.load)
    prices = {grade + "_usd_t": market.bunkers[hub][grade][0] for grade in GRADES}

    sources: dict[str, dict[str, str]] = {}
    excluded: list[str] = []
    notes: list[str] = []

    def src(path: str, status: str, text: str) -> None:
        sources[path] = {"status": status, "source": text}

    port: dict[str, Any] = {}
    load_port_eca = port_in_eca(route.load, on_date)
    discharge_port_eca = port_in_eca(route.discharge, on_date)
    load_mgo = load_port_eca is not None or ports()[route.load]["eea"]
    discharge_mgo = discharge_port_eca is not None or ports()[route.discharge]["eea"]
    load_share = 1.0 if ports()[route.load]["eea"] else 0.0
    discharge_share = 1.0 if ports()[route.discharge]["eea"] else 0.0

    if route.segment == "dry":
        if route.contract == "trip":
            low, high = route.trip_days or (0.0, 0.0)
            trip_days = (low + high) / 2.0
            sea = laden["distance_nm"] * (1 + SEA_MARGIN) / (laden["speed_kn"] * HOURS_PER_DAY)
            each = max(0.0, (trip_days - sea) / 2.0)
            load_days = discharge_days = each
            src(
                "port.load_days",
                "derived",
                "half the remainder of the %s duration of %g to %g days (midpoint %g) "
                "after the laden passage" % (gmb, low, high, trip_days),
            )
            src("port.discharge_days", "derived", sources["port.load_days"]["source"])
        else:
            if route.load_rate_tpd:
                load_days = _days_sshex(route.cargo_t or 0.0, route.load_rate_tpd, route.load_turn_h or 0.0)
                src(
                    "port.load_days",
                    "derived",
                    "%s: %s t at %s t a day %s, five working days a week, plus %g hours "
                    "turn time"
                    % (
                        gmb,
                        f"{route.cargo_t:,.0f}",
                        f"{route.load_rate_tpd:,.0f}",
                        route.load_terms,
                        route.load_turn_h or 0.0,
                    ),
                )
            elif route.load_terms == "port scale":
                load_days = (route.load_turn_h or 0.0) / HOURS_PER_DAY
                src(
                    "port.load_days",
                    "derived",
                    "%s: %g hours turn time only; the loading time itself follows the "
                    "port's scale, which is not published" % (gmb, route.load_turn_h or 0.0),
                )
                excluded.append(
                    "loading time at %s (the Baltic's terms load at the port's scale, which is not "
                    "published)" % ports()[route.load]["name"]
                )
            else:
                load_days = (route.load_turn_h or 0.0) / HOURS_PER_DAY
                src("port.load_days", "empty", "no loading terms for this voyage")
                excluded.append("loading time at %s (no terms for this voyage)" % ports()[route.load]["name"])
            if route.discharge_rate_tpd is None:
                discharge_days = (route.discharge_turn_h or 0.0) / HOURS_PER_DAY
                src("port.discharge_days", "empty", "no discharge terms for this voyage")
                excluded.append("discharging time at %s (no terms for this voyage)" % ports()[route.discharge]["name"])
            else:
                if route.discharge_terms == "SHINC":
                    discharge_days = _days_shinc(
                        route.cargo_t or 0.0, route.discharge_rate_tpd, route.discharge_turn_h or 0.0
                    )
                    terms = "Sundays and holidays included"
                else:
                    discharge_days = _days_sshex(
                        route.cargo_t or 0.0, route.discharge_rate_tpd, route.discharge_turn_h or 0.0
                    )
                    terms = "five working days a week"
                src(
                    "port.discharge_days",
                    "derived",
                    "%s: %s t at %s t a day, %s, plus %g hours turn time"
                    % (
                        gmb,
                        f"{route.cargo_t:,.0f}",
                        f"{route.discharge_rate_tpd:,.0f}",
                        terms,
                        route.discharge_turn_h or 0.0,
                    ),
                )
        port.update(load_days=load_days, discharge_days=discharge_days, waiting_days=0.0, canal_days=0.0)
        src("port.waiting_days", "empty", "no waiting time in the Baltic's dry route terms")
        load_tpd = discharge_tpd = waiting_tpd = 0.0
        src("port.load_tpd", "empty", "the guide prints no port consumption for bulk carriers")
        src("port.discharge_tpd", "empty", "the guide prints no port consumption for bulk carriers")
        excluded.append("fuel burnt in port (the Baltic prints no port consumption for bulk carriers)")
    else:
        port.update(
            load_days=route.load_days or 0.0,
            discharge_days=route.discharge_days or 0.0,
            waiting_days=route.waiting_days or 0.0,
            canal_days=route.canal_days or 0.0,
        )
        for name in ("load_days", "discharge_days", "waiting_days", "canal_days"):
            src(
                "port." + name,
                "sourced",
                "GMB v8.8 page %d, %s TCE description" % (route.tce_page or route.page, route.code),
            )
        load_tpd = vessel.port_load_tpd or 0.0
        discharge_tpd = vessel.port_discharge_tpd or 0.0
        waiting_tpd = vessel.port_waiting_tpd or 0.0
        for name in ("load_tpd", "discharge_tpd", "waiting_tpd"):
            src("port." + name, "sourced", "GMB v8.8 page %d, %s vessel description" % (vessel.page, vessel.id))

    canal_share = laden["ets_share"] if route.canal_days else 0.0
    port.update(
        delay_days=0.0,
        sts_days=0.0,
        load_tpd=load_tpd,
        discharge_tpd=discharge_tpd,
        waiting_tpd=waiting_tpd,
        canal_tpd=0.0,
        delay_tpd=waiting_tpd,
        sts_tpd=load_tpd,
        load_eca=load_mgo,
        discharge_eca=discharge_mgo,
        waiting_eca=load_mgo,
        canal_eca=False,
        delay_eca=False,
        sts_eca=False,
        load_ets_share=load_share,
        discharge_ets_share=discharge_share,
        waiting_ets_share=load_share,
        canal_ets_share=canal_share,
        delay_ets_share=0.0,
        sts_ets_share=0.0,
    )
    if route.canal_days:
        port["canal_tpd"] = waiting_tpd
        src(
            "port.canal_tpd",
            "derived",
            "canal transit priced at the waiting consumption, the guide's slow steaming figure in port",
        )

    ets = {
        "phase_in": phase_in(year),
        "eua_eur_t": market.eua_eur_t,
        "usd_per_eur": market.usd_per_eur,
        "include_non_co2": year >= ETS_FULL_FROM,
    }
    src(
        "ets.phase_in",
        "sourced",
        "Directive 2003/87/EC Article 3gb: %d%% of %d emissions" % (round(ets["phase_in"] * 100), year),
    )
    src("ets.eua_eur_t", "sourced", market.eua_source)
    src("ets.usd_per_eur", "sourced", market.fx_source)

    hull = seed("market.json")["hull_values_usd"]["values"].get(vessel.id, {})
    costs = {
        "port_load_usd": 0.0,
        "port_discharge_usd": 0.0,
        "canal_laden_usd": 0.0,
        "canal_ballast_usd": 0.0,
        "other_usd": 0.0,
        "sts_usd": 0.0,
    }
    src(
        "costs.port_load_usd",
        "empty",
        "no public per call figure; the Baltic uses Cory Brothers' estimates, which are not published",
    )
    src("costs.port_discharge_usd", "empty", sources["costs.port_load_usd"]["source"])
    excluded.append(
        "port charges at %s and %s (no public per call figure)"
        % (ports()[route.load]["name"], ports()[route.discharge]["name"])
    )
    canal_legs = [
        name
        for name, info in (("laden", laden_info), ("ballast", ballast_info))
        if {"Suez Canal", "Panama Canal"} & set(info["passes"])
    ]
    for name in canal_legs:
        canal = "Suez" if "Suez Canal" in (laden_info if name == "laden" else ballast_info)["passes"] else "Panama"
        src("costs.canal_%s_usd" % name, "empty", seed("canals.json")[canal.lower()]["why_empty"])
        excluded.append("the %s Canal toll on the %s leg (no public toll for this ship)" % (canal, name))

    if route.contract == "trip":
        basis = "hire_usd_day"
    else:
        basis = freight_basis or {"USD/t": "usd_t", "WS": "ws", "USD lump sum": "lump_sum"}[route.unit]
    inputs = {
        "contract": route.contract,
        "freight_basis": basis,
        "freight_value": freight_value,
        "flat_rate_usd_t": None,
        "cargo_t": route.cargo_t or 0.0,
        "commission_pct": route.commission_pct,
        "other_revenue_usd": 0.0,
        "sea_margin": SEA_MARGIN,
        "laden": laden,
        "ballast": ballast,
        "laden_curve": [list(p) for p in vessel.laden],
        "ballast_curve": [list(p) for p in vessel.ballast],
        "mgo_at_sea_tpd": vessel.mgo_at_sea_tpd,
        "scrubber": False,
        "scrubber_in_eca": False,
        "vlsfo_class": "HFO",
        "port": port,
        "prices": prices,
        "ets": ets,
        "fueleu": {"include": False, "reduction_pct": FUELEU_REDUCTION_2025_PCT},
        "costs": costs,
        "war_risk": {
            "premium_pct": 0.0,
            "hull_value_usd": float(hull.get("value") or 0.0),
            "periods": 1.0,
            "crew_bonus_usd": 0.0,
        },
    }
    src("freight_value", "sourced" if freight_value is not None else "empty", freight_source or "enter a rate")
    src(
        "flat_rate_usd_t",
        "empty",
        "Worldscale flat rates are licensed by the Worldscale Association and no dated "
        "public source states this route's flat rate for the year",
    )
    src("cargo_t", "sourced", "%s route description" % gmb)
    src("commission_pct", "sourced", "%s route description" % gmb)
    src("sea_margin", "sourced", "GMB v8.8 Appendix 3, page 99: 5% weather allowance on steaming time")
    src("laden_curve", "sourced", "GMB v8.8 page %d, %s" % (vessel.page, vessel.id) if vessel.page else vessel.note)
    src("ballast_curve", "sourced", sources["laden_curve"]["source"])
    src("laden.speed_kn", "sourced", "the guide's description speed, %s" % vessel.id)
    src("ballast.speed_kn", "sourced", "the guide's description speed, %s" % vessel.id)
    src(
        "laden.distance_nm",
        "derived",
        "searoute %s over Eurostat SeaRoute, %s routing" % (sea_routes.SEAROUTE_VERSION, laden_routing),
    )
    src(
        "ballast.distance_nm",
        "derived",
        "searoute %s over Eurostat SeaRoute, %s routing" % (sea_routes.SEAROUTE_VERSION, ballast_routing),
    )
    src("laden.eca_nm", "derived", "the laden line inside the ECA polygons in force on %s" % on_date)
    src("ballast.eca_nm", "derived", "the ballast line inside the ECA polygons in force on %s" % on_date)
    for grade in GRADES:
        src("prices.%s_usd_t" % grade, "sourced", market.bunkers[hub][grade][1])
    src("vlsfo_class", "sourced", "IMO MEPC.391(81): VLSFO is an ISO 8217 residual grade (RME, RMG, RMK)")
    src(
        "war_risk.hull_value_usd",
        "sourced" if hull.get("value") else "empty",
        "Xclusiv Shipbrokers, 7 September 2026, %s" % hull.get("row", "")
        if hull.get("value")
        else hull.get("why_empty", "no hull value"),
    )
    src("war_risk.crew_bonus_usd", "empty", seed("market.json")["war_risk"]["crew_bonus"]["why_empty"])
    src("war_risk.premium_pct", "sourced", "no war risk area on this routing in the base case")

    if route.segment == "dry" and route.contract == "voyage" and route.load_rate_tpd is None:
        notes.append("Loading time follows the port's scale; the TCE leaves it out and is higher than with it.")
    notes.append(
        "Bunkers priced at %s, the hub with public prices nearest %s."
        % (ports()[hub]["name"], ports()[route.load]["name"])
    )

    case = Case(
        case_id or "%s_%s" % (route_code, market.id),
        route_code,
        "%s, %s" % (route.code, route.name),
        inputs,
        sources,
        excluded,
        {
            "laden": laden_info,
            "ballast": ballast_info,
            "hub": hub,
            "market": market.label,
            "date": on_date,
            "vessel": vessel.id,
        },
        notes,
    )
    return case
