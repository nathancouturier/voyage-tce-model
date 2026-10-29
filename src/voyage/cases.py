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
* Prices: the bunker hub nearest the load port (voyage.ports.BUNKER_HUBS),
  unless the route names another with its reason (C3: Singapore).
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
from .words import date_label

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
    # Eastbound Pacific lines run past 180 degrees; the zones are stored within -180 to 180.
    lons = [geo.wrap_lon(c[0]) for c in coordinates]
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


def route_hub(route: baltic.Route) -> str:
    """The hub a route's bunkers are priced at: the hub nearest its load port, unless the route names another."""
    return route.bunker_hub or bunker_hub(route.load)


#: The port activities a voyage loading inside the Gulf spends there: loading,
#: the Baltic's waiting days and any delay, all at the load port.
GULF_ACTIVITIES = ("load", "waiting", "delay")
#: Load ports in the Gulf of Oman, outside the Strait of Hormuz.
GULF_OF_OMAN = ("mina_al_fahal", "fujairah")


@cache
def in_gulf(port_id: str) -> bool:
    """A port inside the Strait of Hormuz: its route to Singapore passes the strait."""
    if port_id == "singapore":
        return False
    return "Strait of Hormuz" in leg_record(port_id, "singapore", "direct")["passes"]


@cache
def miles_inside_gulf(origin: str, destination: str, routing: str) -> float:
    """A leg's miles on the Gulf side of the Strait of Hormuz: between its Gulf end and the strait.

    The strait is the reference point the passage test uses; the line is cut
    where it comes nearest to it.
    """
    coordinates = lines()[sea_routes.leg_key(origin, destination, routing)]
    lon, lat, _ = sea_routes.REFERENCE_POINTS["Strait of Hormuz"]
    run = nearest_run = 0.0
    nearest = None
    for _, end, length in geo.densify(coordinates, 2.0):
        run += length
        gap = geo.haversine_nm(end, (lon, lat))
        if nearest is None or gap < nearest:
            nearest, nearest_run = gap, run
    return nearest_run if in_gulf(origin) else run - nearest_run


def speed_source(vessel: baltic.Vessel, route: baltic.Route, leg: str) -> tuple[str, str]:
    """The status and the words for the speed a case prices a leg at."""
    pairs = vessel.laden if leg == "laden" else vessel.ballast
    speeds = sorted({v for v, _ in pairs}, reverse=True)
    listed = (
        "%s and %g" % (", ".join("%g" % v for v in speeds[:-1]), speeds[-1]) if len(speeds) > 1 else "%g" % speeds[0]
    )
    where = "GMB v8.8 page %d" % vessel.page if vessel.page else "the superseded vessel's record"
    if vessel.segment != "dry":
        return (
            "sourced",
            "%s, %s: the %s speed its description names, at which the Baltic prices its TCE (Appendix 3, "
            "page 98); its 11 knot pairs are the guide's Eco speeds" % (where, vessel.id, leg),
        )
    return (
        "chosen",
        "the fastest of the %s speeds %s gives for %s (%s knots), since the %s terms name no speed"
        % (leg, where, vessel.id, listed, route.code),
    )


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
    #: hub -> the day its bunker row was first printed, when a weekly table reprints an earlier one
    bunkers_first_printed: Mapping[str, str] = field(default_factory=dict)


@cache
def first_printed() -> dict[tuple[str, str], str]:
    """(table date, hub) -> the date the same publisher first printed that row, through unchanged reprints.

    A broker that carries its bunker table over from an earlier week prints the
    same three prices again: the row is that earlier week's prices.
    """
    out: dict[tuple[str, str], str] = {}
    last: dict[tuple[str, str], tuple[list[float], str]] = {}
    for week in sorted(seed("market.json")["weekly_bunkers_usd_t"]["weeks"], key=lambda w: w["date"]):
        publisher = week["source"].split(" weekly")[0]
        for hub, row in week["prices"].items():
            previous = last.get((publisher, hub))
            first = previous[1] if previous and previous[0] == list(row) else week["date"]
            out[(week["date"], hub)] = first
            last[(publisher, hub)] = (list(row), first)
    return out


def _eua(month: str) -> tuple[float, str, str]:
    """The EU allowance price of the latest month on or before `month` that has one: price, words, month."""
    from .sources import ec_eua

    rows = ec_eua.read_cache()
    available = sorted(m for m in rows if m <= month)
    if not available:
        raise ValueError("no EUA price on or before %s" % month)
    used = available[-1]
    row = rows[used]
    return float(row["eua_eur_t"]), "%s, monthly average for %s" % (row["source"], date_label(used)), used


def _fx(date: str) -> tuple[float, str]:
    """The mean of the H.10 rates of the date's month published up to the date.

    A day after the date is never read, so a later release cannot move a dated
    voyage; a date before its month's first published rate takes the latest
    month before it.
    """
    from .sources import frb_h10

    days = [(d, v) for d, v in frb_h10.read_cache() if v is not None and d <= date]
    if not days:
        raise ValueError("no H.10 euro rate published on or before %s" % date)
    month = days[-1][0][:7]
    values = [v for d, v in days if d.startswith(month)]
    if date[:7] == month and date < month_end(month):
        words = "mean of the %d published days from 1 to %s" % (len(values), date_label(date))
    else:
        words = "mean of the %d published days of %s" % (len(values), date_label(month))
    return sum(values) / len(values), "Federal Reserve H.10, " + words


def month_before(month: str) -> str:
    """The month before a month (YYYY-MM)."""
    year, number = (int(part) for part in month.split("-"))
    return "%04d-12" % (year - 1) if number == 1 else "%04d-%02d" % (year, number - 1)


def month_end(month: str) -> str:
    """The last calendar day of a month (YYYY-MM), as YYYY-MM-DD."""
    import calendar

    year, number = (int(part) for part in month.split("-"))
    return "%s-%02d" % (month, calendar.monthrange(year, number)[1])


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
    eua_value, eua_source, eua_month = _eua(spec["eua"]["month"])
    fx_value, fx_source = _fx(month_end(spec["usd_per_eur"]["month"]))
    return Market(
        "common",
        spec["label"],
        month_end(spec["month"]),
        bunkers,
        eua_month,
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
    first = {h: first_printed()[(best["date"], h)] for h in best["prices"]}

    def words(h: str) -> str:
        text = "%s, %s" % (best["source"], date_label(best["date"]))
        if first[h] != best["date"]:
            text += ", reprinting the row first printed on %s" % date_label(first[h])
        return text

    bunkers = {
        h: {grade: (float(values[i]), words(h)) for i, grade in enumerate(GRADES)}
        for h, values in best["prices"].items()
    }
    month = date[:7]
    # The allowance price of a month is known after it ends: a dated voyage takes the latest month before its own.
    eua_value, eua_source, eua_month = _eua(month_before(month))
    fx_value, fx_source = _fx(date)
    return Market(
        "week_" + best["date"],
        "week of %s" % best["date"],
        date,
        bunkers,
        eua_month,
        eua_value,
        eua_source,
        fx_value,
        fx_source,
        first,
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
            eua_value, eua_source, eua_month = _eua(month_before(month))
            fx_value, fx_source = _fx(date)
            return Market(
                "quarter_" + quarter,
                "%s average" % quarter,
                date,
                bunkers,
                eua_month,
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

    hub = route_hub(route)
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
    canal_names = []
    for name in canal_legs:
        canal = "Suez" if "Suez Canal" in (laden_info if name == "laden" else ballast_info)["passes"] else "Panama"
        canal_names.append(canal)
        src("costs.canal_%s_usd" % name, "empty", seed("canals.json")[canal.lower()]["why_empty"])
        excluded.append("the %s Canal toll on the %s leg (no public toll for this ship)" % (canal, name))
    if route.segment == "dry" and canal_names:
        where = " and ".join("the %s Canal" % c for c in sorted(set(canal_names)))
        src("port.canal_days", "empty", "the guide's %s terms set no time at %s" % (route.code, where))
        excluded.append(
            "time at %s, the transit and any wait (no canal days in the guide's %s terms)" % (where, route.code)
        )

    hormuz = [
        name
        for name, info in (("laden", laden_info), ("ballast", ballast_info))
        if "Strait of Hormuz" in info["passes"]
    ]
    gulf_area = {
        "premium_pct": 0.0,
        "entries": 1 if hormuz else 0,
        "laden_nm": round(miles_inside_gulf(route.load, route.discharge, laden_routing), 1)
        if "laden" in hormuz
        else 0.0,
        "ballast_nm": round(miles_inside_gulf(ballast_from, route.load, ballast_routing), 1)
        if "ballast" in hormuz
        else 0.0,
        "port_activities": list(GULF_ACTIVITIES) if hormuz and in_gulf(route.load) else [],
    }
    red_sea = [
        name for name, info in (("laden", laden_info), ("ballast", ballast_info)) if "Bab el Mandeb" in info["passes"]
    ]
    red_sea_area = {
        "premium_pct": 0.0,
        "entries": len(red_sea),
        "laden_nm": 0.0,
        "ballast_nm": 0.0,
        "port_activities": [],
    }

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
            "hull_value_usd": float(hull.get("value") or 0.0),
            "crew_bonus_usd": 0.0,
            "payer": "charterer",
            "areas": {"gulf": gulf_area, "red_sea": red_sea_area},
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
    src("laden.speed_kn", *speed_source(vessel, route, "laden"))
    src("ballast.speed_kn", *speed_source(vessel, route, "ballast"))
    src(
        "laden.distance_nm",
        "derived",
        "searoute %s over Eurostat SeaRoute, %s"
        % (sea_routes.SEAROUTE_VERSION, sea_routes.ROUTING_LABELS[laden_routing]),
    )
    src(
        "ballast.distance_nm",
        "derived",
        "searoute %s over Eurostat SeaRoute, %s"
        % (sea_routes.SEAROUTE_VERSION, sea_routes.ROUTING_LABELS[ballast_routing]),
    )
    src(
        "laden.eca_nm",
        "derived",
        "the laden line inside the emission control areas in force on %s" % date_label(on_date),
    )
    src(
        "ballast.eca_nm",
        "derived",
        "the ballast line inside the emission control areas in force on %s" % date_label(on_date),
    )
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
    baltic_leaves_out = (
        "the Baltic leaves it out of its own TCE too (GMB v8.8 Appendix 3, page 98; the %s TCE description names no "
        "war risk cost)" % route.code
    )
    if hormuz:
        src(
            "war_risk.areas.gulf.premium_pct",
            "left_out",
            "%s: the voyage enters the Gulf through the Strait of Hormuz, a listed area where an additional premium "
            "applies, usually for the charterer's account (Platts, 8 December 2025); dated rates below"
            % baltic_leaves_out,
        )
        excluded.append(
            "the additional war risk premium in the Gulf (usually the charterer's; the Baltic's TCE leaves it out)"
        )
    elif route.load in GULF_OF_OMAN:
        src(
            "war_risk.areas.gulf.premium_pct",
            "derived",
            "the voyage loads at %s, outside the Strait of Hormuz, and does not enter the Gulf; the Gulf of Oman "
            "has been an IBF Warlike Operations Area for crews since 6 March 2026, and no dated premium for it "
            "was found" % ports()[route.load]["name"],
        )
    else:
        src("war_risk.areas.gulf.premium_pct", "derived", "the routing does not enter the Gulf")
    if red_sea:
        src(
            "war_risk.areas.red_sea.premium_pct",
            "left_out",
            "%s: the voyage passes Bab el Mandeb %s, into a listed area where an additional premium applies, "
            "usually for the charterer's account (Platts, 8 December 2025); dated rates below"
            % (baltic_leaves_out, "on both legs" if len(red_sea) == 2 else "on the %s leg" % red_sea[0]),
        )
        excluded.append(
            "the additional war risk premium for the Red Sea passage (usually the charterer's; the Baltic's TCE "
            "leaves it out)"
        )
    else:
        src("war_risk.areas.red_sea.premium_pct", "derived", "the routing does not pass Bab el Mandeb")
    src(
        "war_risk.payer",
        "sourced",
        "on a trip time charter the charterer pays the trip's costs, war risk included"
        if route.contract == "trip"
        else "usually the charterer's in spot voyage charters (Platts, 8 December 2025), reimbursed to the owner "
        "at cost under VOYWAR 2013 (Gard, 21 March 2026)",
    )

    if route.segment == "dry" and route.contract == "voyage" and route.load_rate_tpd is None:
        notes.append("Loading time follows the port's scale; the TCE leaves it out and is higher than with it.")
    if route.bunker_hub:
        notes.append("Bunkers priced at %s: %s." % (ports()[hub]["name"], route.bunker_hub_why))
    else:
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
