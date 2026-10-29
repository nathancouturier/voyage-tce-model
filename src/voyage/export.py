"""Write the site's artifacts: data/*.json, data/downloads/*.csv and data/manifest.json.

Every number the page shows is written here, from the seeds, the caches and the
engine, and nowhere else (tools/check-literals.mjs keeps numbers out of src/).
Each artifact names itself, carries schema_version 1 and declares the decimals
of every format it uses, so the page formats nothing by guess. The files are
the same bytes on every run (scripts/export.py --check in the gate): floats are
rounded to 6 places, keys keep their order, the text is ASCII with LF endings.

Sentences travel as segments: a string, or {"value", "format", "field"} for a
figure, so the page sets each figure in its own span and a test can walk it back
to its field.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from . import analysis, anchors, baltic, cases, engine, jsonio, pages, routemap, sea_routes
from .sources import base, ec_eua, frb_h10
from .words import DECIMALS, date_label, market_words

SCHEMA_VERSION = 1
DATA = base.DATA
DOWNLOADS = DATA / "downloads"
FLOAT_PLACES = 6

FEATURED = {"route": "TD22", "week_ending": "2026-10-23"}
SHOCK_LABELS = {
    "freight": "Freight 10 percent lower or higher",
    "bunkers": "Bunker prices 10 percent lower or higher",
    "speed": "Laden and ballast speed 1 knot slower or faster",
    "port_days": "One day less or more waiting",
    "eua": "EU allowance price 20 percent lower or higher",
}
COST_LABELS = {
    "bunkers": "Bunkers",
    "ports": "Port charges",
    "canals": "Canal tolls",
    "ets": "EU ETS allowances",
    "war_risk": "War risk premium",
    "other": "Other and ship to ship",
    "fueleu": "FuelEU Maritime",
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def clean(value: Any) -> Any:
    """Floats rounded to FLOAT_PLACES, -0.0 written as 0.0, tuples as lists; NaN refused."""
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("a non finite number reached an artifact")
        rounded = round(value, FLOAT_PLACES)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    raise TypeError("cannot write %r to an artifact" % type(value))


#: The factors a page multiplies a value by to show it in another unit: a share as a percent, dollars as millions.
SCALE = {"percent": 100.0, "million": 1e6}


def header(name: str, **extra: Any) -> dict[str, Any]:
    return {
        "artifact": name,
        "schema_version": SCHEMA_VERSION,
        "conventions": {"decimals": DECIMALS, "scale": SCALE},
        **extra,
    }


def raw_source(raw_key: str) -> dict[str, Any]:
    entry = base.raw_entry(raw_key)
    return {"url": entry["url"], "retrieved": entry["retrieved_at"][:10], "publisher": entry["publisher"]}


# --------------------------------------------------------------------------
# Presets: every voyage the site prices, built once
# --------------------------------------------------------------------------


def _latest_rates() -> dict[str, dict[str, Any]]:
    """The latest public rate of every route, with its date and source."""
    out: dict[str, dict[str, Any]] = {}
    for report in cases.seed("anchors.json")["tanker_weekly"]["reports"]:
        for entry in report["entries"]:
            out[entry["route"]] = {
                "date": report["week_ending"],
                "basis": "lump_sum" if entry["rate_basis"] == "lump_sum_usd" else "ws",
                "value": entry["rate_value"],
                "source": report["source"],
                "raw_key": entry["raw_key"],
                "published_tce_usd_day": entry["tce_usd_day"],
                "tce_qualifier": entry["tce_qualifier"],
            }
    for week in cases.seed("anchors.json")["dry_weekly"]["weeks"]:
        for key, value in week["values"].items():
            route = key.rsplit("_", 2)[0] if key.endswith("_usd_t") else None
            if route in ("C3", "C5", "P7") and (route not in out or week["date"] >= out[route]["date"]):
                out[route] = {
                    "date": week["date"],
                    "basis": "usd_t",
                    "value": value,
                    "source": week["source"],
                    "raw_key": week["raw_key"],
                    "published_tce_usd_day": None,
                    "tce_qualifier": "",
                }
            if key == "S4A_usd_day" and ("S4A_63" not in out or week["date"] >= out["S4A_63"]["date"]):
                out["S4A_63"] = {
                    "date": week["date"],
                    "basis": "hire_usd_day",
                    "value": value,
                    "source": week["source"],
                    "raw_key": week["raw_key"],
                    "published_tce_usd_day": None,
                    "tce_qualifier": "",
                }
    return out


def _market_for(route: baltic.Route, date: str) -> cases.Market:
    hub = cases.route_hub(route)
    try:
        return cases.weekly_market(date, hub)
    except ValueError:
        return cases.common_market()


def _preset(
    preset_id: str,
    label: str,
    kind: str,
    case: cases.Case,
    rate: Mapping[str, Any] | None,
    market: cases.Market,
    published: Mapping[str, Any] | None = None,
    market_label: str | None = None,
) -> dict[str, Any]:
    inputs = case.inputs
    evaluable = not (inputs["freight_basis"] == "ws" and not inputs.get("flat_rate_usd_t"))
    return {
        "id": preset_id,
        "label": label,
        "market_label": market_label or label,
        "kind": kind,
        "route": case.route,
        "title": case.title,
        "date": market.date,
        "market": market.label,
        "market_words": market_words(market.label),
        "eua_words": market.eua_source,
        "fx_words": market.fx_source,
        "inputs": inputs,
        "sources": case.sources,
        "excluded": case.excluded,
        "notes": case.notes,
        "legs": case.legs,
        "rate": dict(rate) if rate else None,
        "published": dict(published) if published else None,
        "evaluable": evaluable,
    }


def presets() -> list[dict[str, Any]]:
    out = []
    latest = _latest_rates()
    anchored = {(row["route"], row["week_ending"]) for row in anchors.tanker_weekly() if row["reproducible"]}
    for code in (*baltic.STUDY_ROUTES, "TC20", "TD34"):
        route = baltic.ROUTES[code]
        rate = latest.get(code)
        if rate is None or (code, rate["date"]) in anchored:
            continue
        market = _market_for(route, rate["date"])
        case = cases.build(
            code,
            market,
            freight_value=rate["value"],
            freight_basis=rate["basis"],
            freight_source="%s; rate %s %s"
            % (rate["source"], "for the week to" if route.segment != "dry" else "of", date_label(rate["date"])),
        )
        published = None
        if rate["published_tce_usd_day"] is not None:
            published = {
                "tce_usd_day": rate["published_tce_usd_day"],
                "qualifier": rate["tce_qualifier"],
                "source": rate["source"],
            }
        out.append(
            _preset(
                "latest-%s" % code.lower(),
                "%s, %s" % (code.replace("_37", "").replace("_63", ""), date_label(rate["date"])),
                "latest",
                case,
                rate,
                market,
                published,
                ("Week to %s" if route.segment != "dry" else "%s") % date_label(rate["date"]),
            )
        )
    for row in anchors.tanker_weekly():
        if not row["reproducible"]:
            continue
        route = baltic.ROUTES[row["route"]]
        market = cases.weekly_market(row["week_ending"], cases.route_hub(route))
        case = cases.build(
            row["route"],
            market,
            freight_value=row["rate_value"],
            freight_basis="lump_sum",
            freight_source="Baltic Exchange weekly tanker report, week ending %s" % date_label(row["week_ending"]),
        )
        out.append(
            _preset(
                "anchor-%s-%s" % (row["route"].lower(), row["week_ending"]),
                "%s, week to %s" % (row["route"], date_label(row["week_ending"])),
                "anchor",
                case,
                {"date": row["week_ending"], "basis": "lump_sum", "value": row["rate_value"]},
                market,
                {
                    "tce_usd_day": row["published_tce_usd_day"],
                    "qualifier": row["tce_qualifier"],
                    "source": "Baltic Exchange, as republished by Hellenic Shipping News",
                },
                "Week to %s" % date_label(row["week_ending"]),
            )
        )
    for item in anchors.early_march():
        market = anchors.early_march_market(item["date"])
        case = cases.build(
            "TD3C", market, freight_value=item["freight_usd_t"], freight_basis="usd_t", freight_source=item["source"]
        )
        out.append(
            _preset(
                "anchor-td3c-%s" % item["id"].replace("_", "-"),
                "TD3C at %s a tonne, %s" % (("USD %.2f" % item["freight_usd_t"]), date_label(item["date"])),
                "anchor",
                case,
                {"date": item["date"], "basis": "usd_t", "value": item["freight_usd_t"]},
                market,
                None,
                "%s, USD %.2f a tonne, %s"
                % (item["source"].split(",")[0].split(" ")[0], item["freight_usd_t"], date_label(item["date"])),
            )
        )
    return out


# --------------------------------------------------------------------------
# Bridges, breakevens and the leaves out sentence
# --------------------------------------------------------------------------


def bridge_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Gross freight down to the result, the days and the TCE, row by row with the running total."""
    rows = []
    running = result["revenue"]["gross_usd"] + result["revenue"]["other_usd"]
    rows.append(
        {
            "id": "gross",
            "label": "Gross freight and other revenue",
            "kind": "total",
            "value_usd": running,
            "from_usd": 0.0,
            "to_usd": running,
        }
    )
    commission = result["revenue"]["commission_usd"]
    rows.append(
        {
            "id": "commission",
            "label": "Commission",
            "kind": "deduction",
            "value_usd": -commission,
            "from_usd": running,
            "to_usd": running - commission,
        }
    )
    running -= commission
    for family in ("bunkers", "ports", "canals", "ets", "war_risk", "other", "fueleu"):
        value = result["costs"][family]
        rows.append(
            {
                "id": family,
                "label": COST_LABELS[family],
                "kind": "cost",
                "value_usd": -value,
                "from_usd": running,
                "to_usd": running - value,
            }
        )
        running -= value
    rows.append(
        {
            "id": "result",
            "label": "Voyage result",
            "kind": "total",
            "value_usd": result["result_usd"],
            "from_usd": 0.0,
            "to_usd": result["result_usd"],
        }
    )
    return rows


def leaves_out(case: cases.Case) -> list[str]:
    return list(case.excluded)


# --------------------------------------------------------------------------
# Map
# --------------------------------------------------------------------------


def map_voyages(preset_list: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    voyages: dict[str, dict[str, Any]] = {}
    for preset in preset_list:
        legs = preset["legs"]
        route = baltic.ROUTES[preset["route"]]
        key = "%s|%s|%s" % (preset["route"], legs["laden"]["routing"], legs["ballast"]["routing"])
        if key not in voyages:
            voyages[key] = routemap.voyage_map(
                route, legs["laden"]["routing"], legs["ballast"]["routing"], preset["date"]
            )
    for code, laden, ballast in (
        ("P7", "no_canals", "no_canals"),
        ("TC20", "no_suez", "no_suez"),
        ("TD22", "no_canals", "no_panama"),
    ):
        key = "%s|%s|%s" % (code, laden, ballast)
        if key not in voyages:
            voyages[key] = routemap.voyage_map(baltic.ROUTES[code], laden, ballast, "2026-10-23")
    return voyages


# --------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------


def overview(preset_list: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    featured = next(p for p in preset_list if p["id"] == "anchor-td22-%s" % FEATURED["week_ending"])
    inputs = featured["inputs"]
    result = engine.evaluate(inputs)
    zero = engine.freight_for_tce(inputs, 0.0)
    comparison = [
        {
            "week_ending": r["week_ending"],
            "rate_usd": r["rate_value"],
            "published_tce_usd_day": r["published_tce_usd_day"],
            "qualifier": r["tce_qualifier"],
            "engine_tce_usd_day": r["engine_tce_usd_day"],
            "error": r["error"],
            "bunkers": r["bunkers"],
            "bunkers_first_printed": r["bunkers_first_printed"],
            "bunker_age_days": r["bunker_age_days"],
            "post_closure": r["week_ending"] in anchors.POST_CLOSURE_WEEKS,
        }
        for r in anchors.tanker_weekly()
        if r["route"] == "TD22" and r["reproducible"]
    ]
    map_key = "%s|%s|%s" % (
        featured["route"],
        featured["legs"]["laden"]["routing"],
        featured["legs"]["ballast"]["routing"],
    )
    page = pages.overview(featured, result, zero, bridge_rows(result), comparison, map_key)
    return header("overview", featured=featured["id"], route=featured["route"], **page)


def leaves_out_from(preset: Mapping[str, Any]) -> list[str]:
    return list(preset["excluded"])


FIELD_SPECS = [
    # step, path, label, unit, format, scale (the field shows the input times this)
    ("ship", "laden.speed_kn", "Laden speed", "knots", "knots", 1.0),
    ("ship", "ballast.speed_kn", "Ballast speed", "knots", "knots", 1.0),
    ("ship", "mgo_at_sea_tpd", "MGO burnt at sea beside fuel oil", "t a day", "tpd", 1.0),
    ("route", "laden.distance_nm", "Laden distance", "nautical miles", "nm", 1.0),
    ("route", "laden.eca_nm", "Laden miles inside ECAs", "nautical miles", "nm", 1.0),
    ("route", "ballast.distance_nm", "Ballast distance", "nautical miles", "nm", 1.0),
    ("route", "ballast.eca_nm", "Ballast miles inside ECAs", "nautical miles", "nm", 1.0),
    ("route", "port.load_days", "Days loading", "days", "days_2", 1.0),
    ("route", "port.discharge_days", "Days discharging", "days", "days_2", 1.0),
    ("route", "port.waiting_days", "Days waiting", "days", "days_2", 1.0),
    ("route", "port.canal_days", "Days in canal transit", "days", "days_2", 1.0),
    ("market", "freight_value", "Freight", "", "usd_t", 1.0),
    ("market", "flat_rate_usd_t", "Worldscale flat rate", "USD a tonne", "usd_t", 1.0),
    ("market", "cargo_t", "Cargo", "tonnes", "t", 1.0),
    ("market", "prices.vlsfo_usd_t", "VLSFO price", "USD a tonne", "usd_t", 1.0),
    ("market", "prices.mgo_usd_t", "MGO price", "USD a tonne", "usd_t", 1.0),
    ("market", "prices.hsfo_usd_t", "HSFO price", "USD a tonne", "usd_t", 1.0),
    ("market", "ets.eua_eur_t", "EU allowance price", "EUR a tonne", "eur_t", 1.0),
    ("market", "ets.usd_per_eur", "Dollars per euro", "USD", "usd_per_eur", 1.0),
    ("costs", "costs.port_load_usd", "Port charges at loading", "USD", "usd", 1.0),
    ("costs", "costs.port_discharge_usd", "Port charges at discharge", "USD", "usd", 1.0),
    ("costs", "costs.canal_laden_usd", "Canal toll, laden", "USD", "usd", 1.0),
    ("costs", "costs.canal_ballast_usd", "Canal toll, ballast", "USD", "usd", 1.0),
    (
        "costs",
        "war_risk.areas.gulf.premium_pct",
        "War risk premium, the Gulf",
        "percent of hull value a period",
        "percent_2",
        1.0,
    ),
    (
        "costs",
        "war_risk.areas.red_sea.premium_pct",
        "War risk premium, Red Sea and Gulf of Aden",
        "percent of hull value a period",
        "percent_2",
        1.0,
    ),
    ("costs", "war_risk.hull_value_usd", "Hull value", "USD", "usd", 1.0),
    ("costs", "war_risk.crew_bonus_usd", "Crew war bonus", "USD", "usd", 1.0),
    ("costs", "costs.sts_usd", "Ship to ship transfer cost", "USD", "usd", 1.0),
    ("costs", "costs.other_usd", "Other voyage costs", "USD", "usd", 1.0),
    ("advanced", "sea_margin", "Weather margin on steaming time", "percent", "percent", 100.0),
    ("advanced", "commission_pct", "Total commission", "percent of freight", "percent_2", 1.0),
    ("advanced", "other_revenue_usd", "Other revenue: ballast bonus, demurrage", "USD", "usd", 1.0),
    ("advanced", "port.delay_days", "Days waiting to transit a risk area", "days", "days_2", 1.0),
    ("advanced", "port.delay_tpd", "Fuel while waiting to transit", "t a day", "tpd", 1.0),
    ("advanced", "port.sts_days", "Days of ship to ship transfer", "days", "days_2", 1.0),
    ("advanced", "port.sts_tpd", "Fuel during the transfer", "t a day", "tpd", 1.0),
    ("advanced", "port.load_tpd", "Fuel at loading", "t a day", "tpd", 1.0),
    ("advanced", "port.discharge_tpd", "Fuel at discharge", "t a day", "tpd", 1.0),
    ("advanced", "port.waiting_tpd", "Fuel while waiting", "t a day", "tpd", 1.0),
    ("advanced", "port.canal_tpd", "Fuel in canal transit", "t a day", "tpd", 1.0),
]

STEPS = [
    {"id": "ship", "label": "Ship", "summary": "The Baltic's ship, its speeds and consumptions, a scrubber"},
    {"id": "route", "label": "Route", "summary": "Routing of each leg, distances, miles inside ECAs, port days"},
    {"id": "market", "label": "Market", "summary": "Freight, Worldscale flat rate, bunker prices, carbon price"},
    {"id": "costs", "label": "Costs", "summary": "Port charges, canal tolls, war risk premium, other costs"},
    {"id": "advanced", "label": "Advanced", "summary": "Weather margin, commission, waiting, transfers, fuel in port"},
]

#: Which inputs fill an item of a preset's "leaves out" list: once the visitor has
#: entered every one of them, the item no longer applies.
EXCLUDED_FIELDS = (
    ("port charges", ("costs.port_load_usd", "costs.port_discharge_usd")),
    ("loading time", ("port.load_days",)),
    ("discharging time", ("port.discharge_days",)),
    ("fuel burnt in port", ("port.load_tpd", "port.discharge_tpd")),
    ("toll on the laden leg", ("costs.canal_laden_usd",)),
    ("toll on the ballast leg", ("costs.canal_ballast_usd",)),
    ("canal days", ("port.canal_days",)),
    ("war risk premium in the Gulf", ("war_risk.areas.gulf.premium_pct",)),
    ("war risk premium for the Red Sea", ("war_risk.areas.red_sea.premium_pct",)),
)


def excluded_items(preset: Mapping[str, Any]) -> list[dict[str, Any]]:
    out = []
    for text in preset["excluded"]:
        paths = next((list(p) for key, p in EXCLUDED_FIELDS if key in text), [])
        if not paths:
            raise ValueError("an excluded item names no input: %s" % text)
        out.append({"text": text, "paths": paths})
    return out


def calculator(preset_list: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    vessels = {}
    for vid, v in baltic.VESSELS.items():
        record = asdict(v)
        record["laden"] = [list(p) for p in v.laden]
        record["ballast"] = [list(p) for p in v.ballast]
        record["power_fit_laden"] = engine.power_fit(v.laden)
        record["power_fit_ballast"] = engine.power_fit(v.ballast)
        vessels[vid] = record
    routes = {}
    for code, r in baltic.ROUTES.items():
        if code not in baltic.STUDY_ROUTES + baltic.SUPPORT_ROUTES:
            continue
        routes[code] = {
            "code": code,
            "name": r.name,
            "segment": r.segment,
            "contract": r.contract,
            "unit": r.unit,
            "vessel": r.vessel,
            "load": r.load,
            "discharge": r.discharge,
            "cargo_t": r.cargo_t,
            "commission_pct": r.commission_pct,
            "page": r.page,
            "tce_page": r.tce_page,
            "tce_basis": r.tce_basis,
            "description": r.description,
            "laden_routing": r.laden_routing,
            "ballast_routing": r.ballast_routing,
        }
    alternatives = {}
    for preset in preset_list:
        if preset["kind"] != "latest":
            continue
        code = preset["route"]
        route = baltic.ROUTES[code]
        options = []
        for routing in sea_routes.ROUTINGS:
            laden = cases.leg_record(route.load, route.discharge, routing)
            ballast = cases.leg_record(route.discharge, route.load, routing)
            if any(
                o["laden_nm"] == laden["distance_nm"] and o["ballast_nm"] == ballast["distance_nm"] for o in options
            ):
                continue
            options.append(
                {
                    "routing": routing,
                    "label": sea_routes.ROUTING_LABELS[routing],
                    "laden_nm": laden["distance_nm"],
                    "laden_eca_nm": round(
                        sum(v for _, v in cases.eca_miles(route.load, route.discharge, routing, preset["date"])), 1
                    ),
                    "ballast_nm": ballast["distance_nm"],
                    "ballast_eca_nm": round(
                        sum(v for _, v in cases.eca_miles(route.discharge, route.load, routing, preset["date"])), 1
                    ),
                    "passes_laden": laden["passes"],
                    "passes_ballast": ballast["passes"],
                }
            )
        alternatives[code] = options
    fields = [
        {"step": s, "path": p, "label": label, "unit": unit, "format": fmt, "scale": scale}
        for s, p, label, unit, fmt, scale in FIELD_SPECS
    ]
    return header(
        "calculator",
        default_preset="anchor-td22-%s" % FEATURED["week_ending"],
        steps=STEPS,
        fields=fields,
        freight_bases=[
            {"id": "usd_t", "label": "USD a tonne", "format": "usd_t"},
            {"id": "ws", "label": "Worldscale points", "format": "ws"},
            {"id": "lump_sum", "label": "Lump sum, USD", "format": "usd"},
            {"id": "hire_usd_day", "label": "Hire, USD a day", "format": "usd_day"},
        ],
        ets_years=[
            {"year": y, "phase_in": cases.phase_in(y), "include_non_co2": y >= cases.ETS_FULL_FROM}
            for y in analysis.PHASE_IN_YEARS
        ],
        vlsfo_classes=[
            {"id": "HFO", "label": "HFO (ISO 8217 RME to RMK), the study's default"},
            {"id": "LFO", "label": "LFO (ISO 8217 RMA to RMD)"},
        ],
        shocks=[{"id": s, "label": SHOCK_LABELS[s]} for s, _, _ in engine.SHOCKS],
        speed_chart={"margin_kn": analysis.SPEED_MARGIN_KN, "step_kn": analysis.SPEED_CHART_STEP_KN},
        target_tce={"value": 0.0, "label": "Breakeven: the freight that covers the voyage costs priced"},
        presets=[{**p, "excluded_items": excluded_items(p)} for p in preset_list],
        route_order=[
            {"code": code, "label": code.replace("_37", "").replace("_63", ""), "segment": baltic.ROUTES[code].segment}
            for code in (*baltic.STUDY_ROUTES, "TC20", "TD34")
            if any(p["route"] == code for p in preset_list)
        ],
        input_labels={
            path: {"label": label, "format": fmt, "scale": scale}
            for path, (label, fmt, scale) in pages.INPUT_LABELS.items()
        },
        status_words=pages.STATUS_WORDS,
        payer_words=pages.PAYER_WORDS,
        war_area_names=pages.WAR_AREA_NAMES,
        **pages.calculator_words(),
        vessels=vessels,
        routes=routes,
        alternatives=alternatives,
        cost_labels=COST_LABELS,
        war_risk_rates=cases.seed("market.json")["war_risk"]["rates_pct"],
        hull_values=cases.seed("market.json")["hull_values_usd"],
    )


def routes_artifact() -> dict[str, Any]:
    cs = analysis.cost_structure()
    rows = []
    doc = cases.seed("sea_routes.json")
    market = cases.common_market()
    for row in cs["rows"]:
        route = baltic.ROUTES[row["route"]]
        port = cases.build(row["route"], market, freight_value=0.0, freight_basis="usd_t").inputs["port"]
        by_routing = []
        for routing in sea_routes.ROUTINGS:
            laden = cases.leg_record(route.load, route.discharge, routing)
            if any(b["laden_nm"] == laden["distance_nm"] for b in by_routing):
                continue
            by_routing.append(
                {
                    "routing": routing,
                    "label": sea_routes.ROUTING_LABELS[routing],
                    "laden_nm": laden["distance_nm"],
                    "passes": laden["passes"],
                }
            )
        rows.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "route",
                        "name",
                        "segment",
                        "contract",
                        "days",
                        "total_usd",
                        "per_day_usd",
                        "costs_usd",
                        "shares",
                        "excluded",
                        "excluded_block_per_day_usd",
                        "hub",
                        "laden_nm",
                        "ballast_nm",
                        "eca_nm",
                        "with_hormuz_war_risk",
                        "bunkers_by_grade_usd",
                        "fuel_t",
                    )
                },
                "vessel": route.vessel,
                "cargo_t": route.cargo_t,
                "commission_pct": route.commission_pct,
                "load": cases.ports()[route.load]["name"],
                "discharge": cases.ports()[route.discharge]["name"],
                "page": route.page,
                "by_routing": by_routing,
                "eca_share": row["eca_nm"] / (row["laden_nm"] + row["ballast_nm"]),
                "port_days": {k: port[k] for k in ("load_days", "discharge_days", "waiting_days", "canal_days")},
                "vessel_label": baltic.VESSELS[route.vessel].label,
                "hub_name": cases.ports()[row["hub"]]["name"],
                "label": row["route"].replace("_37", "").replace("_63", ""),
            }
        )
    page = pages.routes_page(cs["market"], cs["eua_eur_t"], cs["usd_per_eur"], rows)
    return header(
        "routes",
        market=cs["market"],
        eua_eur_t=cs["eua_eur_t"],
        usd_per_eur=cs["usd_per_eur"],
        rows=rows,
        pub151=doc["pub151_checks"],
        baltic_map_url="https://nathancouturier.github.io/baltic-freight-routes/",
        gmb={"version": baltic.GMB["version"], "date": baltic.GMB["date"], "url": baltic.GMB["url"]},
        page=page,
    )


def detours_artifact() -> dict[str, Any]:
    st, sd, hz = analysis.suez_tanker(), analysis.suez_dry(), analysis.hormuz()
    return header(
        "detours",
        suez_tanker=st,
        suez_dry=sd,
        hormuz=hz,
        events=cases.seed("events.json")["events"],
        canals=cases.seed("canals.json"),
        page=pages.detours_page(st, sd, hz),
    )


def carbon_artifact() -> dict[str, Any]:
    c = analysis.carbon()
    return header(
        "carbon",
        **c,
        page=pages.carbon_page(c),
        convention_links={
            i["id"]: base.raw_entry(i["raw_key"])["url"] for i in cases.seed("conventions.json")["items"]
        },
        conventions_rows=[
            i
            for i in cases.seed("conventions.json")["items"]
            if i["id"]
            in (
                "ets_scope",
                "ets_phase_in",
                "emission_factors",
                "gwp_ets",
                "bimco_etsa",
                "fueleu",
                "gwp_fueleu",
                "vlsfo_grade",
            )
        ],
    )


def paper_artifact() -> dict[str, Any]:
    p = analysis.paper()
    ffa = cases.seed("ffa.json")
    data = {**p, "curves": ffa["curves"], "settlement": ffa["settlement"]}
    return header("paper", **data, page=pages.paper_page(data))


def speed_artifact() -> dict[str, Any]:
    data = analysis.speed()
    page = pages.speed_page(data)
    return header(
        "speed",
        margin_kn=data["margin_kn"],
        step_kn=data["step_kn"],
        textbook=data["textbook"],
        **page,
    )


def method_artifact() -> dict[str, Any]:
    tanker = anchors.tanker_weekly()
    validation = {
        "tanker": tanker,
        "early_march": anchors.early_march(),
        "dry": anchors.dry_weekly(),
        "baltic_2017": anchors.baltic_2017(),
        "distances": cases.seed("sea_routes.json")["pub151_checks"],
    }

    def with_url(item: Mapping[str, Any]) -> dict[str, Any]:
        return {**item, "url": base.raw_entry(item["raw_key"])["url"]} if item.get("raw_key") else dict(item)

    validation["tanker"] = [
        {
            **with_url(row),
            "route_label": row["route"].replace("_37", "").replace("_63", ""),
            "bunkers_words": pages.bunker_age_words(row).lower() if row["bunkers"] else "",
        }
        for row in validation["tanker"]
    ]
    validation["early_march"] = [
        {**row, "bunkers_words": market_words(row["bunkers"])} for row in validation["early_march"]
    ]
    return header(
        "method",
        convention_items=[with_url(i) for i in cases.seed("conventions.json")["items"]],
        validation=validation,
        market=cases.seed("market.json"),
        events=cases.seed("events.json")["events"],
        page=pages.method_page(validation, analysis.cost_structure()["rows"]),
    )


def manifest_artifact() -> dict[str, Any]:
    eua = ec_eua.read_cache()
    fx = [d for d, v in frb_h10.read_cache() if v is not None]
    raw = base.raw_manifest()["files"]
    series = [
        {
            "id": "gmb",
            "what": "Baltic Exchange route and vessel definitions, Guide to Market Benchmarks v8.8",
            "as_of": "2026-09",
            "source": raw_source("baltic_gmb"),
            "licence": "Baltic copyright, cited with pages",
        },
        {
            "id": "ports",
            "what": "Port positions, NGA World Port Index (Pub. 150)",
            "as_of": None,
            "as_of_words": "Not dated: the agency's service carries no edition date",
            "source": raw_source("nga_wpi_ports"),
            "licence": "US Government work, public domain",
        },
        {
            "id": "distances",
            "what": "Sea routes, searoute 1.6.0 over Eurostat SeaRoute, checked against NGA Pub. 151",
            "as_of": None,
            "as_of_words": "searoute 1.6.0's network; Pub. 151, 11th edition, 2001",
            "source": {
                "url": "https://github.com/genthalili/searoute-py",
                "retrieved": "2026-10-29",
                "publisher": "searoute (Apache 2.0), Eurostat SeaRoute (EUPL 1.2)",
            },
            "licence": "Apache 2.0 and EUPL 1.2",
        },
        {
            "id": "eca",
            "what": "Emission control areas, MARPOL Annex VI Appendix VII and the area regulations",
            "as_of": "2024-10-04",
            "source": raw_source("imo_mepc_328_76"),
            "licence": "IMO documents, cited",
        },
        {
            "id": "eua",
            "what": "EU allowance price, monthly: European Commission auction reports, then DEHSt",
            "as_of": max(eua),
            "source": raw_source("jkm_dehst_eua_monthly"),
            "licence": "CC BY 4.0 (Commission), CC BY-NC-ND 4.0 (DEHSt)",
        },
        {
            "id": "fx",
            "what": "US dollars per euro, Federal Reserve H.10",
            "as_of": fx[-1],
            "source": raw_source("frb_h10_package"),
            "licence": "US Government work, public domain",
        },
        {
            "id": "bunkers",
            "what": "Bunker prices, weekly: Star Asia Shipbroking and Banchero Costa tables",
            "as_of": "2026-10-23",
            "source": raw_source("bunkers_starasia_market_report_week43_2026_pdf"),
            "licence": "Copyright of the publishers; figures cited",
        },
        {
            "id": "bunkers_sb",
            "what": "Bunker prices, monthly and quarterly averages: Ship & Bunker",
            "as_of": "2026-09-30",
            "source": raw_source("bunkers_sb_prices_rotterdam_20261028_redacted_html"),
            "licence": "Copyright of the publisher; figures cited",
        },
        {
            "id": "tanker_rates",
            "what": "Tanker rates and TCEs, Baltic Exchange weekly reports via Hellenic Shipping News",
            "as_of": "2026-10-23",
            "source": raw_source("tanker_hsn_baltic_tanker_report_pub2026_10_26_html"),
            "licence": "Copyright; figures cited",
        },
        {
            "id": "dry_rates",
            "what": "Dry rates and time charter averages, Signal Group and Banchero Costa",
            "as_of": "2026-10-23",
            "source": raw_source("dry_bancosta_weekly_2026_wk43_pdf"),
            "licence": "Copyright; figures cited",
        },
        {
            "id": "ffa",
            "what": "Dry FFA assessments, Banchero Costa",
            "as_of": "2026-10-25",
            "source": raw_source("dry_bancosta_weekly_2026_wk43_pdf"),
            "licence": "Copyright; figures cited",
        },
        {
            "id": "war_risk",
            "what": "War risk premiums, Platts and Marsh via Hellenic Shipping News",
            "as_of": "2026-07-22",
            "source": raw_source("risk_hsn_2026_07_24_marsh_middle_east_insurance_costs_rise_html"),
            "licence": "Copyright; figures cited",
        },
        {
            "id": "hull_values",
            "what": "Hull values, Xclusiv Shipbrokers weekly",
            "as_of": "2026-09-07",
            "source": raw_source("dry_xclusiv_weekly_2026_09_07_pdf"),
            "licence": "Copyright; figures cited",
        },
        {
            "id": "canals",
            "what": "Suez Canal Authority surcharges",
            "as_of": "2026-07-15",
            "source": raw_source("canals_sca_api_articles_pc16_2026_crude_tankers_xml"),
            "licence": "Cited",
        },
    ]
    return header(
        "manifest",
        caption="Every source the study reads: the date of its latest figure, when it was retrieved, its publisher "
        "and its licence. Licensed documents are cited with their figures and never redistributed.",
        series=series,
        raw_files=len(raw),
        raw_committed=sum(1 for e in raw.values() if e["committed"]),
        footer={
            "sources": "Data: Baltic Exchange route definitions and weekly reports as republished, Ship & Bunker, "
            "Star Asia and Banchero Costa bunker and FFA tables, the European Commission and DEHSt auction "
            "reports, the Federal Reserve, NGA, Eurostat SeaRoute, the IMO and EUR-Lex, each cited where it is used.",
            "updated_words": "Data last updated",
            "updated": pages.retrieval_days()[-1],
            "latest_words": "latest market input dated",
            "latest_input": max(
                s["as_of"] for s in series if s["id"] in ("bunkers", "tanker_rates", "dry_rates", "ffa", "eua", "fx")
            ),
            "method_words": "Every source with its date and licence",
        },
    )


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------


def csv_text(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_value(row.get(k)) for k in columns})
    return out.getvalue()


def _csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return "%.6f" % value if abs(value) < 1e15 else repr(value)
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return "" if value is None else value


def downloads() -> dict[str, str]:
    tanker = anchors.tanker_weekly()
    files = {
        "anchors_tanker.csv": csv_text(
            tanker,
            [
                "week_ending",
                "route",
                "rate_basis",
                "rate_value",
                "published_tce_usd_day",
                "tce_qualifier",
                "reproducible",
                "engine_tce_usd_day",
                "error",
                "bunkers",
                "bunkers_first_printed",
                "reason",
            ],
        ),
        "anchors_dry.csv": csv_text(
            anchors.dry_weekly(),
            [
                "date",
                "route",
                "freight_usd_t",
                "engine_tce_usd_day",
                "engine_tce_gross_usd_day",
                "benchmark",
                "benchmark_usd_day",
                "benchmark_basis",
                "benchmark_182_usd_day",
                "gap_usd_day",
                "bunkers",
                "hub",
                "days",
                "ballast_days",
            ],
        ),
    }
    cs = analysis.cost_structure()
    files["cost_structure_2026_08.csv"] = csv_text(
        [
            {
                "route": r["route"],
                "days": r["days"],
                **{"%s_usd" % k: v for k, v in r["costs_usd"].items()},
                "total_usd": r["total_usd"],
                "hub": r["hub"],
                "excluded": r["excluded"],
            }
            for r in cs["rows"]
        ],
        [
            "route",
            "days",
            "bunkers_usd",
            "ports_usd",
            "canals_usd",
            "ets_usd",
            "war_risk_usd",
            "total_usd",
            "hub",
            "excluded",
        ],
    )
    hz = analysis.hormuz()
    files["detours_hormuz.csv"] = csv_text(
        [
            {
                "scenario": s["id"],
                "label": s["label"],
                "days": s["days"],
                "extra_days": s["extra_days"],
                "days_inside_gulf": s["days_inside_gulf"],
                "periods": s["periods"],
                "laden_nm": s["laden_nm"],
                "charterer_war_risk_usd": s["war_risk_usd"],
                "charterer_war_risk_usd_t": s["charterer_war_risk_usd_t"],
                **{
                    "owner_extra_freight_usd_t_at_%s" % lvl["week_ending"]: lvl["extra_freight_usd_t"]
                    for lvl in s["levels"]
                },
            }
            for s in hz["scenarios"]
        ],
        [
            "scenario",
            "label",
            "days",
            "extra_days",
            "days_inside_gulf",
            "periods",
            "laden_nm",
            "charterer_war_risk_usd",
            "charterer_war_risk_usd_t",
        ]
        + ["owner_extra_freight_usd_t_at_%s" % lvl["week_ending"] for lvl in hz["levels"]],
    )
    carbon = analysis.carbon()
    files["carbon_ets.csv"] = csv_text(
        [{"route": r["route"], "kind": r["kind"], **y} for r in carbon["rows"] for y in r["years"]],
        [
            "route",
            "kind",
            "year",
            "phase_in",
            "covered_t",
            "allowances_t",
            "cost_usd",
            "per_day_usd",
            "per_tonne_cargo_usd",
            "share_of_voyage_costs",
        ],
    )
    files["eua_monthly.csv"] = (base.CACHE / "eua_monthly.csv").read_text(encoding="utf-8")
    legs = []
    for key, leg in cases.seed("sea_routes.json")["legs"].items():
        if leg["from"] in cases.ports() and leg["to"] in cases.ports():
            legs.append(
                {
                    "leg": key,
                    "from": leg["from"],
                    "to": leg["to"],
                    "routing": leg["routing"],
                    "distance_nm": leg["distance_nm"],
                    "passes": leg["passes"],
                }
            )
    files["sea_routes.csv"] = csv_text(legs, ["leg", "from", "to", "routing", "distance_nm", "passes"])
    return files


# --------------------------------------------------------------------------
# Everything
# --------------------------------------------------------------------------


def build() -> dict[str, str]:
    """Every artifact as the text it is written with, keyed by its path under data/."""
    preset_list = presets()
    documents = {
        "engine.json": header("engine", constants=engine.constants()),
        "overview.json": overview(preset_list),
        "calculator.json": calculator(preset_list),
        "routes.json": routes_artifact(),
        "detours.json": detours_artifact(),
        "carbon.json": carbon_artifact(),
        "paper.json": paper_artifact(),
        "speed.json": speed_artifact(),
        "method.json": method_artifact(),
        "map.json": header("map", **routemap.document(map_voyages(preset_list))),
        "manifest.json": manifest_artifact(),
    }
    out = {name: jsonio.dumps(clean(doc)) for name, doc in documents.items()}
    for name, text in downloads().items():
        out["downloads/" + name] = text
    return out


def write(files: Mapping[str, str]) -> list[str]:
    changed = []
    for name, text in files.items():
        path = DATA / name
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(name)
    return changed


def check(files: Mapping[str, str]) -> list[str]:
    """The artifacts that differ from a rebuild."""
    out = []
    for name, text in files.items():
        path = DATA / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            out.append(name)
    return out
