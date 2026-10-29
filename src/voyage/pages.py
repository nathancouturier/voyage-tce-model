"""The words of every view: titles, takeaways, chart titles, source lines and section summaries.

Each sentence is built from the numbers it states, as segments (voyage.words), so a
figure in a sentence is the figure in the table under it and changes with the data.
Nothing here computes a market quantity: the numbers arrive from the engine and the
analysis through voyage.export, which calls these functions and writes the artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import baltic, cases
from .words import date_label, fig, plain, usd, usd_m, word

Segments = list[Any]

# --------------------------------------------------------------------------
# Inputs: labels and formats
# --------------------------------------------------------------------------

#: Every input a preset cites, with the words and the format a table shows it in.
#: A share is shown as a percent (scale 100); a curve or a class is shown as text.
INPUT_LABELS: dict[str, tuple[str, str | None, float]] = {
    "laden.speed_kn": ("Laden speed", "knots_2", 1.0),
    "ballast.speed_kn": ("Ballast speed", "knots_2", 1.0),
    "laden_curve": ("Laden speed and consumption", None, 1.0),
    "ballast_curve": ("Ballast speed and consumption", None, 1.0),
    "laden.distance_nm": ("Laden distance", "nm", 1.0),
    "ballast.distance_nm": ("Ballast distance", "nm", 1.0),
    "laden.eca_nm": ("Laden miles inside ECAs", "nm", 1.0),
    "ballast.eca_nm": ("Ballast miles inside ECAs", "nm", 1.0),
    "port.load_days": ("Days loading", "days_2", 1.0),
    "port.discharge_days": ("Days discharging", "days_2", 1.0),
    "port.waiting_days": ("Days waiting", "days_2", 1.0),
    "port.canal_days": ("Days in canal transit", "days_2", 1.0),
    "port.load_tpd": ("Fuel at loading", "tpd", 1.0),
    "port.discharge_tpd": ("Fuel at discharge", "tpd", 1.0),
    "port.waiting_tpd": ("Fuel while waiting", "tpd", 1.0),
    "port.canal_tpd": ("Fuel in canal transit", "tpd", 1.0),
    "freight_value": ("Freight", None, 1.0),
    "flat_rate_usd_t": ("Worldscale flat rate", "usd_t", 1.0),
    "cargo_t": ("Cargo", "t", 1.0),
    "commission_pct": ("Total commission", "percent_2", 1.0),
    "sea_margin": ("Weather margin on steaming time", "percent_0", 100.0),
    "prices.vlsfo_usd_t": ("VLSFO price", "usd_t", 1.0),
    "prices.hsfo_usd_t": ("HSFO price", "usd_t", 1.0),
    "prices.mgo_usd_t": ("MGO price", "usd_t", 1.0),
    "ets.eua_eur_t": ("EU allowance price", "eur_t", 1.0),
    "ets.usd_per_eur": ("Dollars per euro", "usd_per_eur", 1.0),
    "ets.phase_in": ("EU ETS phase in", "percent_0", 100.0),
    "vlsfo_class": ("VLSFO emission class", None, 1.0),
    "costs.port_load_usd": ("Port charges at loading", "usd", 1.0),
    "costs.port_discharge_usd": ("Port charges at discharge", "usd", 1.0),
    "costs.canal_laden_usd": ("Canal toll, laden", "usd", 1.0),
    "costs.canal_ballast_usd": ("Canal toll, ballast", "usd", 1.0),
    "war_risk.premium_pct": ("War risk premium, percent of hull value", "percent_2", 1.0),
    "war_risk.hull_value_usd": ("Hull value", "usd", 1.0),
    "war_risk.crew_bonus_usd": ("Crew war bonus", "usd", 1.0),
}

STATUS_WORDS = {"sourced": "Sourced", "derived": "Derived", "empty": "No public figure", "changed": "Your figure"}

FREIGHT_FORMATS = {"usd_t": "usd_t", "ws": "ws", "lump_sum": "usd", "hire_usd_day": "usd_day"}
FREIGHT_UNITS = {
    "usd_t": "USD a tonne",
    "ws": "Worldscale points",
    "lump_sum": "USD lump sum",
    "hire_usd_day": "USD a day",
}


def _lookup(inputs: Mapping[str, Any], path: str) -> Any:
    value: Any = inputs
    for part in path.split("."):
        value = value.get(part) if isinstance(value, Mapping) else None
    return value


def curve_words(curve: Sequence[Sequence[float]]) -> str:
    """[[13, 57.3], [11, 39.8]] as "13 knots on 57.3 t a day, 11 knots on 39.8 t a day"."""
    return ", ".join("%g knots on %g t a day" % (v, c) for v, c in curve)


def inputs_table(preset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every input a preset cites, in the order of INPUT_LABELS, with its value, format, status and source."""
    inputs = preset["inputs"]
    rows = []
    for path, (label, fmt, scale) in INPUT_LABELS.items():
        info = preset["sources"].get(path)
        if info is None:
            continue
        value = _lookup(inputs, path)
        text = None
        if path in ("laden_curve", "ballast_curve"):
            text, value = curve_words(value), None
        elif path == "vlsfo_class":
            text, value = {"HFO": "HFO, ISO 8217 RME to RMK", "LFO": "LFO, ISO 8217 RMA to RMD"}[value], None
        elif path == "freight_value":
            fmt = FREIGHT_FORMATS[inputs["freight_basis"]]
            label = "Freight, %s" % FREIGHT_UNITS[inputs["freight_basis"]]
        elif value is not None:
            value = value * scale
        rows.append(
            {
                "path": path,
                "label": label,
                "value": value if info["status"] != "empty" or value else None,
                "format": fmt,
                "text": text,
                "status": info["status"],
                "status_words": STATUS_WORDS[info["status"]],
                "source": info["source"],
            }
        )
    return rows


# --------------------------------------------------------------------------
# The bridge
# --------------------------------------------------------------------------

FAMILY = {"bunkers": "bunkers", "ports": "ports", "canals": "canals", "ets": "ets", "war_risk": "war", "other": "other"}


def _port_name(port_id: str) -> str:
    return cases.ports()[port_id]["name"]


def bridge_details(preset: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    """For each row of the bridge: the line under its name, and the words a zero row shows instead of a bar."""
    inputs = preset["inputs"]
    route = baltic.ROUTES[preset["route"]]
    legs = preset["legs"]
    hub = _port_name(legs["hub"])
    basis = inputs["freight_basis"]
    if basis == "lump_sum":
        gross: Segments = ["Lump sum fixed, ", usd_m(inputs["freight_value"], "inputs.freight_value")]
    elif basis == "usd_t":
        gross = [
            fig(inputs["freight_value"], "usd_t", "inputs.freight_value", prefix="USD "),
            " a tonne on ",
            fig(inputs["cargo_t"], "t", "inputs.cargo_t", suffix=" tonnes"),
        ]
    elif basis == "ws":
        gross = [fig(inputs["freight_value"], "ws", "inputs.freight_value", prefix="WS "), " on the flat rate entered"]
    else:
        gross = [
            "Hire of ",
            usd(inputs["freight_value"], "inputs.freight_value", "usd_day"),
            " a day for ",
            fig(result["days"]["trip"], "days", "result.days.trip", suffix=" days"),
        ]
    if result["revenue"]["other_usd"]:
        gross += [" and ", usd(result["revenue"]["other_usd"], "inputs.other_revenue_usd"), " of other revenue"]

    fuel = result["fuel_t"]
    grades = [(g, fuel[g]) for g in ("vlsfo", "hsfo", "mgo") if fuel.get(g)]
    bunkers: Segments = []
    for at, (grade, tonnes) in enumerate(grades):
        if at:
            bunkers.append(" and " if at == len(grades) - 1 else ", ")
        bunkers += [fig(tonnes, "t", "result.fuel_t.%s" % grade, suffix=" t"), " of %s" % grade.upper()]
    bunkers.append(" at %s prices" % hub)

    load, discharge = _port_name(route.load), _port_name(route.discharge)
    port_empty = preset["sources"].get("costs.port_load_usd", {}).get("status") == "empty"
    canal_passes = sorted({c for leg in ("laden", "ballast") for c in legs[leg]["passes"] if c.endswith("Canal")})
    ets_shares = (inputs["laden"]["ets_share"], inputs["ballast"]["ets_share"])
    commission = [
        fig(inputs["commission_pct"], "percent_2", "inputs.commission_pct", suffix=" percent"),
        " of gross freight and other revenue",
    ]
    ets: Segments
    if any(ets_shares):
        ets = [
            fig(result["emissions"]["ets_covered_t"], "tco2", "result.emissions.ets_covered_t", suffix=" t"),
            " of CO2e covered, at ",
            fig(inputs["ets"]["eua_eur_t"], "eur_t", "inputs.ets.eua_eur_t", prefix="EUR "),
            " an allowance and ",
            fig(inputs["ets"]["phase_in"] * 100.0, "percent_0", "inputs.ets.phase_in", suffix=" percent"),
            " phase in",
        ]
    else:
        ets = ["No EEA port on either leg"]
    war = inputs["war_risk"]
    war_detail: Segments
    if war["premium_pct"]:
        war_detail = [
            fig(war["premium_pct"], "percent_2", "inputs.war_risk.premium_pct", suffix=" percent"),
            " of a ",
            usd_m(war["hull_value_usd"], "inputs.war_risk.hull_value_usd", "usd_m_0"),
            " hull, ",
            fig(war["periods"], "count", "inputs.war_risk.periods"),
            " period" if war["periods"] == 1 else " periods",
        ]
    else:
        war_detail = ["No war risk area priced on this routing"]
    return {
        "gross": {"detail": gross},
        "commission": {"detail": commission},
        "bunkers": {"detail": bunkers},
        "ports": {
            "detail": ["%s and %s" % (load, discharge)],
            "zero": "Left out: no public per call figure" if port_empty else "None entered",
        },
        "canals": {
            "detail": ["%s" % " and ".join(canal_passes)] if canal_passes else ["No canal on this routing"],
            "zero": "Left out: no public toll for this ship" if canal_passes else "None on this routing",
        },
        "ets": {"detail": ets, "zero": "None: outside the EEA"},
        "war_risk": {"detail": war_detail, "zero": "None in the base case"},
        "other": {"detail": ["Ship to ship transfer and other costs"], "zero": "None entered"},
        "fueleu": {"detail": ["FuelEU Maritime penalty, shown only when included"], "zero": "Not in the TCE"},
        "result": {"detail": ["Freight less commission and voyage costs"]},
    }


def bridge(preset: Mapping[str, Any], result: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The bridge rows with their family, detail and zero words.

    The five cost families always; other costs and FuelEU only when not zero."""
    details = bridge_details(preset, result)
    out = []
    for row in rows:
        if row["id"] in ("other", "fueleu") and not row["value_usd"]:
            continue
        info = details[row["id"]]
        out.append(
            {
                **row,
                "family": FAMILY.get(row["id"]),
                "accent": row["id"] == "result",
                "detail": info["detail"],
                "zero": info.get("zero") if not row["value_usd"] else None,
            }
        )
    return {
        "rows": out,
        "days": result["days"]["total"],
        "tce_usd_day": result["tce_usd_day"],
        "result_line": [
            "Over ",
            fig(result["days"]["total"], "days", "result.days.total", suffix=" days"),
            " (",
            fig(result["days"]["ballast_sea"], "days", "result.days.ballast_sea"),
            " in ballast, ",
            fig(result["days"]["laden_sea"], "days", "result.days.laden_sea"),
            " laden and ",
            fig(result["days"]["port_total"], "days", "result.days.port_total"),
            " in port), the result is a TCE of ",
            fig(result["tce_usd_day"], "usd_day", "result.tce_usd_day", prefix="USD ", accent=True),
            " a day.",
        ],
    }


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


def overview(
    featured: Mapping[str, Any],
    result: Mapping[str, Any],
    zero: Mapping[str, Any],
    rows: list[dict[str, Any]],
    comparison: list[Mapping[str, Any]],
    map_key: str,
) -> dict[str, Any]:
    inputs = featured["inputs"]
    route = baltic.ROUTES[featured["route"]]
    vessel = baltic.VESSELS[route.vessel]
    published = featured["published"]
    week = featured["rate"]["date"]
    load, discharge = _port_name(route.load), _port_name(route.discharge)
    hub = _port_name(featured["legs"]["hub"])
    tce = result["tce_usd_day"]
    costs = result["costs"]
    bunker_share = costs["bunkers"] / costs["total_usd"]
    error = tce / published["tce_usd_day"] - 1.0
    bunker_source = featured["sources"]["prices.vlsfo_usd_t"]["source"]
    via = sorted({p for leg in ("laden", "ballast") for p in featured["legs"][leg]["passes"]})
    cape = "Cape of Good Hope" in via

    verdict = [
        "A VLCC fixed on TD22, %s to %s, at the Baltic's " % (load, discharge),
        usd_m(inputs["freight_value"], "inputs.freight_value"),
        " in the week to ",
        word(date_label(week), "date"),
        ", earns about ",
        fig(tce, "usd_day", "result.tce_usd_day", prefix="USD "),
        " a day over a ",
        fig(result["days"]["total"], "days", "result.days.total"),
        " day round voyage; ",
        "freight of ",
        usd(zero["usd_t"], "breakeven.usd_t", "usd_t"),
        " a tonne would only cover its voyage costs.",
    ]
    dates = [
        [
            "Freight and the Baltic's TCE: Baltic Exchange weekly tanker report, week to ",
            word(date_label(week), "date"),
            ", as republished by Hellenic Shipping News.",
        ],
        ["Bunkers: %s, priced at %s, the hub with public prices nearest %s." % (bunker_source, hub, load)],
        [
            "Ship, speeds and port days: Baltic Exchange Guide to Market Benchmarks v%s (%s), %s."
            % (baltic.GMB["version"], baltic.GMB["date"], vessel.id)
        ],
        [
            "Distances: searoute over Eurostat SeaRoute; emission control areas in force on ",
            word(date_label(week), "date"),
            ".",
        ],
    ]
    facts = [
        {
            "id": "tce",
            "label": "TCE, round voyage from %s" % discharge,
            "value": fig(tce, "usd_day", "result.tce_usd_day"),
            "unit": "USD a day",
            "as_of": week,
            "note": [
                "The Baltic published ",
                usd(published["tce_usd_day"], "published.tce_usd_day", "usd_day"),
                "; the engine reads ",
                fig(error * 100.0, "error_percent", "published.error", suffix=" percent"),
                " higher" if error > 0 else " lower",
                ", mostly the port charges it leaves out.",
            ],
        },
        {
            "id": "breakeven",
            "label": "Freight that covers voyage costs",
            "value": fig(zero["usd_t"], "usd_t", "breakeven.usd_t"),
            "unit": "USD a tonne",
            "as_of": week,
            "note": [
                "A lump sum of ",
                usd_m(zero["lump_sum_usd"], "breakeven.lump_sum_usd"),
                "; the ",
                usd_m(inputs["freight_value"], "inputs.freight_value"),
                " fixed is ",
                fig(inputs["freight_value"] / zero["lump_sum_usd"], "exponent", "breakeven.cover"),
                " times that.",
            ],
        },
        {
            "id": "bunker_share",
            "label": "Bunkers in voyage costs",
            "value": fig(bunker_share * 100.0, "percent", "result.bunker_share"),
            "unit": "percent",
            "as_of": week,
            "note": [
                "VLSFO at ",
                usd(inputs["prices"]["vlsfo_usd_t"], "inputs.prices.vlsfo_usd_t", "usd_t"),
                " and MGO at ",
                usd(inputs["prices"]["mgo_usd_t"], "inputs.prices.mgo_usd_t", "usd_t"),
                " a tonne; port charges, the other voyage cost, have no public figure.",
            ],
        },
    ]
    b = bridge(featured, result, rows)
    b["title"] = [
        "Of ",
        usd_m(result["revenue"]["gross_usd"], "result.revenue.gross_usd"),
        " of freight, ",
        usd_m(result["result_usd"], "result.result_usd"),
        " is left after commission and ",
        usd_m(costs["total_usd"], "result.costs.total_usd"),
        " of voyage costs, ",
        *(
            ["all of them bunkers."]
            if bunker_share > 1.0 - 1e-9
            else [fig(bunker_share * 100.0, "percent", "result.bunker_share", suffix=" percent"), " of them bunkers."]
        ),
    ]
    b["source"] = [
        "Engine output for TD22 in the week to ",
        word(date_label(week), "date"),
        ". Freight: Baltic Exchange via Hellenic Shipping News. Bunkers: %s. " % bunker_source,
        "A cost with no public figure is left out and named in its row.",
    ]
    b["caption"] = "The bridge from gross freight to the voyage result, in US dollars, one row per step."
    leaves = list(featured["excluded"])
    return {
        "title": "What a VLCC earns from the US Gulf to China",
        "verdict": verdict,
        "dates": dates,
        "facts": facts,
        "bridge": b,
        "leaves_out": [
            "The TCE leaves out %s, so with them it would be lower; " % "; ".join(leaves),
            "it is an estimate of what the voyage earns at these inputs, not a forecast.",
        ],
        "map": {
            "key": map_key,
            "title": [
                "TD22 sails %s, %s to %s laden and back in ballast: "
                % ("round the Cape of Good Hope" if cape else "the shortest way", load, discharge),
                fig(inputs["laden"]["distance_nm"], "nm", "inputs.laden.distance_nm", suffix=" nautical miles"),
                " each way, ",
                fig(inputs["laden"]["eca_nm"], "nm", "inputs.laden.eca_nm"),
                " of them inside the North American and US Caribbean emission control areas.",
            ],
            "legend": [
                {"kind": "laden", "text": "Laden leg, %s to %s" % (load, discharge)},
                {"kind": "ballast", "text": "Ballast leg, %s to %s, drawn beside it" % (discharge, load)},
                {"kind": "eca", "text": "Inside an emission control area: 0.10 percent sulphur fuel (MGO)"},
            ],
            "source": [
                "Lines: searoute over Eurostat SeaRoute, the lines the distances are measured on. "
                "Emission control areas: MARPOL Annex VI, in force on ",
                word(date_label(week), "date"),
                ". Land: Natural Earth 1:110m.",
            ],
        },
        "sections": [
            {
                "id": "method",
                "name": "Method",
                "summary": [
                    "The Baltic's round voyage TCE: ballast from %s, laden from %s, " % (discharge, load),
                    fig(inputs["sea_margin"] * 100.0, "percent_0", "inputs.sea_margin", suffix=" percent"),
                    " weather margin, and the engine against the Baltic in ",
                    fig(len(comparison), "count", "comparison.count"),
                    " weeks.",
                ],
            },
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["What the TCE leaves out, the ship's speeds and consumptions, and the port days."],
            },
            {
                "id": "data",
                "name": "Data",
                "summary": ["Every input with its value, its status and its source."],
            },
        ],
        "method": {
            "paragraphs": [
                [
                    "The TCE is the voyage's freight less commission and voyage costs, divided by the days of "
                    "the whole round voyage. It follows the Baltic Exchange's tanker method (Guide to Market "
                    "Benchmarks v%s, Appendix 3): the ship is delivered at the discharge port, %s, sails in "
                    "ballast to %s, loads, sails laden back and discharges. Steaming days carry a "
                    % (baltic.GMB["version"], discharge, load),
                    fig(inputs["sea_margin"] * 100.0, "percent_0", "inputs.sea_margin", suffix=" percent"),
                    " weather margin; fuel is priced at the bunker port nearest the load port; port, waiting and "
                    "canal days follow the route description.",
                ],
                [
                    "Operating and capital costs are not voyage costs: a TCE is compared with them, never net of "
                    "them. A TCE without the ballast leg is a different number; the one here includes it.",
                ],
            ],
            "formulas": [
                "TCE = (gross freight + other revenue - commission - voyage costs) / total voyage days",
                "Voyage days = ballast steaming + laden steaming (each with the weather margin) + port, waiting "
                "and canal days",
                "Freight that covers voyage costs = voyage costs / (1 - commission share), the TCE set to zero",
            ],
            "comparison_title": [
                "Against the Baltic's own TD22 TCE, the engine reads between ",
                fig(
                    min(r["error"] for r in comparison if r["bunkers"].endswith(r["week_ending"])) * 100.0,
                    "error_percent",
                    "comparison.min_error",
                    suffix=" percent",
                ),
                " and ",
                fig(
                    max(r["error"] for r in comparison if r["bunkers"].endswith(r["week_ending"])) * 100.0,
                    "error_percent",
                    "comparison.max_error",
                    suffix=" percent",
                ),
                " higher in weeks with a bunker table of the same week.",
            ],
            "comparison_note": (
                "Higher every week because the engine leaves out port charges (the Baltic uses Cory Brothers' "
                "estimates, which are not published). The week to 13 March 2026 is priced with the table of "
                "6 March, before bunker prices jumped after the closure of the Strait of Hormuz, and reads "
                "furthest above."
            ),
        },
        "assumptions": {
            "leaves_out": leaves,
            "vessel": [
                "%s: %s. " % (vessel.id, vessel.note),
                "Laden ",
                fig(inputs["laden"]["speed_kn"], "knots", "inputs.laden.speed_kn", suffix=" knots"),
                ", ballast ",
                fig(inputs["ballast"]["speed_kn"], "knots", "inputs.ballast.speed_kn", suffix=" knots"),
                ", the guide's description speeds. Consumption laden: %s; ballast: %s."
                % (curve_words(inputs["laden_curve"]), curve_words(inputs["ballast_curve"])),
            ],
            "port": [
                "Port days from the route description: ",
                fig(inputs["port"]["load_days"], "days", "inputs.port.load_days"),
                " loading, ",
                fig(inputs["port"]["discharge_days"], "days", "inputs.port.discharge_days"),
                " discharging and ",
                fig(inputs["port"]["waiting_days"], "days", "inputs.port.waiting_days"),
                " waiting, burning ",
                fig(inputs["port"]["load_tpd"], "tpd", "inputs.port.load_tpd"),
                ", ",
                fig(inputs["port"]["discharge_tpd"], "tpd", "inputs.port.discharge_tpd"),
                " and ",
                fig(inputs["port"]["waiting_tpd"], "tpd", "inputs.port.waiting_tpd"),
                " t a day.",
            ],
        },
        "data_caption": "Every input of the featured voyage, with its value, its status and its source.",
        "inputs_table": inputs_table(featured),
        "comparison": [
            {
                **r,
                "error_pct": r["error"] * 100.0,
                "bunkers_words": "Same week"
                if r["bunkers"].endswith(r["week_ending"])
                else "Week of %s, the latest table before it" % date_label(r["bunkers"].split()[-1]),
            }
            for r in comparison
        ],
        "plain_verdict": plain(verdict),
    }


# --------------------------------------------------------------------------
# Calculator
# --------------------------------------------------------------------------


def calculator_words() -> dict[str, Any]:
    """The calculator's fixed words. A template's {name} is filled by the page with a figure it computes
    from the artifact's inputs; no figure is written here."""
    return {
        "title": "Price a voyage",
        "lead": [
            "Choose a route and a dated market. Every field starts from its source or says why it is empty, "
            "and every change prices the voyage again with the same engine as the rest of the study."
        ],
        "words": {
            "route_label": "Route",
            "gross": "Gross freight and other revenue",
            "commission": "Commission",
            "result": "Voyage result",
            "none": "None on this voyage",
            "none_ets": "None: no EEA port",
            "market_label": "Market",
            "verdict": "At these inputs the voyage earns {tce} a day over {days} days.",
            "verdict_trip": "At this hire the owner earns {tce} a day over {days} days, the ballast leg back to the "
            "delivery area included; over the {trip_days} days of the trip alone the hire nets {trip_tce} a day after "
            "commission.",
            "verdict_negative": "At these inputs the voyage loses {tce} a day over {days} days.",
            "published": "The Baltic published {published} for this week; the engine reads {error} percent "
            "{direction}.",
            "no_freight": "Enter a freight rate under Market to price the voyage.",
            "ws_missing": "The rate is in Worldscale points, and a Worldscale rate needs the route's flat rate in "
            "USD a "
            "tonne. Flat rates are licensed by the Worldscale Association and no public source states this "
            "route's for the year: enter it under Market, or switch the freight to USD a tonne or a lump sum.",
            "leaves_out": "The TCE leaves out {items}, so with them it would be lower.",
            "leaves_out_none": "Every voyage cost of this voyage has a figure.",
            "estimate": "A TCE is an estimate of what a voyage earns at stated inputs, not a forecast.",
            "breakeven_heading": "Freight that earns a TCE of",
            "breakeven_target_label": "Target TCE",
            "breakeven_target_unit": "USD a day; zero gives the freight that only covers voyage costs",
            "breakeven_usd_t": "USD a tonne",
            "breakeven_ws": "Worldscale points",
            "breakeven_ws_missing": "needs a flat rate",
            "breakeven_lump": "Lump sum, USD",
            "breakeven_hire": "Hire, USD a day",
            "bridge_title": "Where the freight goes: {gross} of freight, {result} left after commission and {costs} "
            "of voyage costs.",
            "bridge_caption": "The bridge from gross freight to the voyage result, in US dollars, one row per step.",
            "tornado_title": "{first} moves the TCE most: {range} a day between its two cases.",
            "tornado_axis": "TCE, USD a day",
            "tornado_lower": "Input lower",
            "tornado_higher": "Input higher",
            "tornado_desc": "Each bar runs from the TCE with the input lower to the TCE with it higher; the base TCE "
            "is the vertical rule.",
            "speed_title": "The TCE is highest at {best} knots laden at these inputs; the voyage is priced at "
            "{current}.",
            "speed_title_bound": "The TCE still rises at {best} knots, the top of the range the published "
            "consumptions support; the voyage is priced at {current}.",
            "speed_axis_x": "Laden speed, knots (ballast keeps its gap)",
            "speed_axis_y": "TCE, USD a day",
            "speed_desc": "The TCE at each laden speed from one knot below the slowest published consumption to one "
            "knot above the fastest. Between published pairs consumption is interpolated; outside them it follows "
            "the power law fitted to the pairs.",
            "speed_title_low": "The TCE is highest at {best} knots, the slowest speed searched; the voyage is priced "
            "at {current}.",
            "speed_trip_note": "On a trip the hire is paid by the day and the charterer buys the laden fuel, so a "
            "faster ship shortens the paid days and the owner's TCE falls with speed.",
            "speed_best": "Best, {best} kn",
            "speed_current": "Priced, {current} kn",
            "source": "Engine output at the inputs above. Preset: {preset}; bunkers and carbon: {market}.",
            "result_line": "Over {days} days ({ballast} in ballast, {laden} laden and {port} in port and waiting), "
            "the result is a TCE of {tce} a day.",
            "million": "USD {value} million",
            "routing": "Routing",
            "routing_note": "A routing sets the leg's distance and its miles inside ECAs; canal days and tolls stay "
            "as entered.",
            "ets_year": "EU ETS year",
            "ets_year_note": "40 percent of 2024 emissions, 70 percent of 2025 and 100 percent from 2026, with methane "
            "and nitrous oxide from 2026 (Directive 2003/87/EC, Articles 3gb and 3ga).",
            "freight_basis": "Freight basis",
            "vlsfo_class": "VLSFO emission class",
            "scrubber": "Scrubber fitted: burns HSFO outside ECAs",
            "scrubber_in_eca": "Scrubber also used inside ECAs, where local rules allow",
            "fueleu": "Include the FuelEU Maritime penalty in the TCE",
            "curves": "Published speeds and consumptions",
            "curve_fit": "Outside the published pairs consumption follows c = a v^b fitted to them: laden b {laden}, "
            "ballast b {ballast}.",
            "war_rates": "Dated war risk premiums",
            "war_use": "Use {value} percent",
            "reset": "Reset",
            "empty_placeholder": "No public figure",
            "not_cited": "A scenario input: the base case uses the value shown.",
            "changed": "Your figure.",
            "invalid": "Enter a number.",
            "data_caption": "Every input of the voyage as it now stands, with its status and its source.",
            "method": [
                "The calculator runs src/engine.js, the browser copy of the Python engine, checked against it to "
                "within one part in a billion on every committed test case. The TCE is gross freight and other "
                "revenue less commission and voyage costs, divided by the days of the whole round voyage, ballast "
                "leg included. On a trip charter the owner's TCE is the hire over the trip less commission, less "
                "the costs the owner bears (the ballast leg's bunkers and allowances), over the trip and the "
                "ballast leg.",
                "Steaming days are distance over speed times 24 hours, plus the weather margin. Fuel at sea follows "
                "the ship's published speed and consumption pairs, interpolated between them and extended outside "
                "them by a power law fitted to them; inside an emission control area the ship burns MGO, outside "
                "VLSFO, or HSFO behind a scrubber. The sensitivities change one input at a time and keep the "
                "others.",
            ],
        },
        "sections": [
            {
                "id": "method",
                "name": "Method",
                "summary": ["How the calculator prices a voyage and its sensitivities."],
            },
            {
                "id": "speed",
                "name": "Speed across markets",
                "summary": [
                    "The best speed at low, middle and high freight and bunker prices, and the textbook result tested."
                ],
            },
            {"id": "data", "name": "Data", "summary": ["Every input of the voyage as it now stands, with its source."]},
        ],
    }


# --------------------------------------------------------------------------
# Speed across markets (the calculator's section)
# --------------------------------------------------------------------------

LEVEL_WORDS = {"low": "Low", "mid": "Middle", "high": "High"}


def speed_page(speed: Mapping[str, Any]) -> dict[str, Any]:
    routes = speed["routes"]
    held = [t for t in speed["textbook"] if t["freight_pushes_speed_up"] and t["bunkers_push_speed_down"]]
    bound_share = sum(1 for r in routes for g in r["grid"] if g["at_bound"]) / sum(len(r["grid"]) for r in routes)
    out_routes = []
    for r in routes:
        route = baltic.ROUTES[r["route"]]
        fmt = "usd_t" if r["basis"] == "usd_t" else "usd_m"

        def freight_fig(value: float, field: str, fmt: str = fmt) -> dict[str, Any]:
            if fmt == "usd_t":
                return fig(value, "usd_t", field, prefix="USD ", suffix=" a tonne")
            return usd_m(value, field)

        caption = [
            "%s, %s, %s: freight from " % (route.code, route.name, r["vessel"]),
            freight_fig(r["freight"]["low"], "freight.low"),
            " to ",
            freight_fig(r["freight"]["high"], "freight.high"),
            ", the lowest and highest public rates, median ",
            freight_fig(r["freight"]["mid"], "freight.mid"),
            "; bunkers at %s; speeds searched from " % _port_name(r["hub"]),
            fig(r["search_kn"][0], "knots", "search_kn.low"),
            " to ",
            fig(r["search_kn"][1], "knots", "search_kn.high", suffix=" knots"),
            ", consumption exponent fitted to the published pairs ",
            fig(r["power_fit_laden"]["b"], "exponent", "power_fit_laden.b"),
            ".",
        ]
        grid = []
        for g in r["grid"]:
            value = g["freight_value"]
            freight_words = "%s, %s" % (
                LEVEL_WORDS[g["freight_level"]],
                ("USD %.2f a tonne" % value) if r["basis"] == "usd_t" else ("USD %.2f million" % (value / 1e6)),
            )
            grid.append(
                {
                    **{k: v for k, v in g.items() if k != "curve"},
                    "freight_words": freight_words,
                    "bunker_words": "%s, %s" % (LEVEL_WORDS[g["bunker_level"]], date_label(g["bunker_as_of"])),
                }
            )
        out_routes.append({**{k: v for k, v in r.items() if k != "grid"}, "grid": grid, "caption": caption})
    lead = [
        "On ",
        fig(len(held), "count", "textbook.held"),
        " of the ",
        fig(len(routes), "count", "textbook.routes"),
        " routes with a public freight rate in dollars, a higher rate never lowers the best speed and dearer bunkers "
        "never raise it: the textbook result holds. It holds weakly for the tankers: with only two published "
        "consumption pairs their fitted exponents are low, so faster steaming looks cheap and in ",
        fig(bound_share * 100.0, "percent_0", "textbook.bound_share", suffix=" percent"),
        " of the cases the best speed is at the top of the range searched.",
    ]
    return {
        "lead": lead,
        "bound_mark": "(top of the range)",
        "note": "The range searched runs one knot either side of the published consumption pairs, the only speeds "
        "the guide's data support. Linear interpolation between pairs puts kinks at the published speeds, so best "
        "speeds often fall exactly on one of them.",
        "routes": out_routes,
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

SEGMENT_WORDS = {"dry": "Dry bulk", "dirty": "Dirty tankers", "clean": "Clean tankers"}


def _short(code: str) -> str:
    return code.replace("_37", "").replace("_63", "")


def routes_page(market_label: str, eua: float, fx: float, rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    with_ets = [r for r in rows if r["costs_usd"]["ets"]]
    bunkers_only = [r for r in rows if r["shares"]["bunkers"] > 1.0 - 1e-9]
    ets_shares = [r["shares"]["ets"] for r in with_ets]
    hormuz = [r for r in rows if r["with_hormuz_war_risk"] and r["with_hormuz_war_risk"].get("hull_value_usd")]
    worst = max(hormuz, key=lambda r: r["with_hormuz_war_risk"]["war_risk_to_bunkers"])
    w = worst["with_hormuz_war_risk"]
    cheapest = min(rows, key=lambda r: r["per_day_usd"])
    dearest = max(rows, key=lambda r: r["per_day_usd"])
    takeaway = [
        "At %s prices bunkers are all of the sourced voyage costs on " % market_label,
        fig(len(bunkers_only), "count", "bunkers_only.count"),
        " of the ",
        fig(len(rows), "count", "rows.count"),
        " routes; on the ",
        fig(len(with_ets), "count", "with_ets.count"),
        " that touch the EEA, EU allowances add ",
        fig(min(ets_shares) * 100.0, "percent", "ets_share.min"),
        " to ",
        fig(max(ets_shares) * 100.0, "percent", "ets_share.max", suffix=" percent"),
        ". A Hormuz war risk premium at the latest dated rate, ",
        fig(w["premium_pct"], "percent", "hormuz.premium_pct", suffix=" percent"),
        " of hull value, would cost %s " % _short(worst["route"]),
        fig(w["war_risk_to_bunkers"], "exponent", "hormuz.war_risk_to_bunkers"),
        " times its fuel bill.",
    ]
    chart_title = [
        "Voyage costs run from ",
        usd(cheapest["per_day_usd"], "per_day_usd.min", "usd_day"),
        " a day on %s to " % _short(cheapest["route"]),
        usd(dearest["per_day_usd"], "per_day_usd.max", "usd_day"),
        " on %s; outside Europe they are bunkers alone." % _short(dearest["route"]),
    ]
    return {
        "title": "The route library",
        "takeaway": takeaway,
        "baltic_map": {
            "before": "Each route is defined by the Baltic Exchange (Guide to Market Benchmarks v%s, %s) and drawn on "
            % (baltic.GMB["version"], baltic.GMB["date"]),
            "link": "the Baltic routes map",
            "after": ".",
        },
        "chart": {
            "title": chart_title,
            "axis": "Voyage costs, USD a day of the round voyage",
            "desc": "One bar a route, grouped by segment, split into bunkers and EU allowances; port charges and canal "
            "tolls have no public figure and are left out of every bar.",
            "source": [
                "Engine output at the common market, %s: Ship & Bunker monthly and quarterly averages at the hub "
                "nearest each load port, EU allowances at EUR " % market_label,
                fig(eua, "eur_t", "eua_eur_t"),
                " and ",
                fig(fx, "usd_per_eur", "usd_per_eur"),
                " dollars per euro. Ships, speeds and port days: Baltic Exchange Guide to Market Benchmarks v%s."
                % baltic.GMB["version"],
            ],
            "legend": [
                {"family": "bunkers", "text": "Bunkers"},
                {"family": "ets", "text": "EU ETS allowances"},
            ],
        },
        "table_caption": "Every route: the Baltic's ship and cargo, distances by routing, the share of the miles "
        "inside emission control areas, port days and voyage costs at %s prices." % market_label,
        "hormuz": {
            "title": "The Gulf loadings with the Hormuz premium",
            "caption": "Each Gulf loading at the common market with one transit period of the latest dated Hormuz "
            "premium, on its hull value; the LR1 of TC5 has no dated public hull value.",
            "lead": [
                "At ",
                fig(w["premium_pct"], "percent", "hormuz.premium_pct", suffix=" percent"),
                " of hull value for one transit period (%s, %s), the war risk premium becomes most of "
                "the voyage costs of every Gulf loading with a dated hull value." % _latest_hormuz_rate(),
            ],
        },
        "segments": SEGMENT_WORDS,
        "sections": [
            {
                "id": "method",
                "name": "Method",
                "summary": ["How distances, miles inside ECAs, bunker hubs and the common market are set."],
            },
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["What each route's TCE leaves out, and how laytime becomes port days."],
            },
            {
                "id": "data",
                "name": "Data",
                "summary": ["Distances against NGA Pub. 151, and the downloads."],
            },
        ],
        "method": [
            "Distances are searoute 1.6.0 over Eurostat's SeaRoute network, the line the map draws. Each route has "
            "a routing for each leg (the shortest with the canals open, or Suez, Panama or both avoided) and the "
            "table lists every routing that changes the distance. The laden leg runs from the load port to the "
            "discharge port; the ballast leg back from the discharge port, the Baltic's TCE delivery point.",
            "Miles inside emission control areas are measured on the same line against polygons built from MARPOL "
            "Annex VI Appendix VII and the area regulations, with the Mediterranean ECA from 1 May 2025 and the "
            "Canadian Arctic and Norwegian Sea ECAs from 1 March 2027. Inside them a ship without a scrubber burns "
            "MGO at 0.10 percent sulphur; outside, VLSFO at 0.50 percent.",
            "Bunkers are priced at the hub nearest the load port among the four with public prices for every "
            "grade (Singapore, Fujairah, Rotterdam, Houston), the Baltic's rule for its tanker TCEs applied to every "
            "route. The common market is the latest month with dated public bunker prices and an EU allowance "
            "price: %s." % market_label,
        ],
        "assumptions": [
            "Port charges have no public per call figure for any study port (the Baltic uses Cory Brothers' "
            "estimates, which are not published), so every TCE leaves them out and reads high by their amount.",
            "Canal tolls depend on each ship's own canal tonnage, which is not published for the Baltic's standard "
            "ships; a routing through a canal leaves its toll out and says so.",
            "Dry laytime becomes calendar days by the route's terms: Saturdays and Sundays excepted terms count "
            "five working days in seven, Sundays and holidays included terms count every day, and the turn time is "
            "added. Capesize loading on the port's scale has no published rate and is left out.",
        ],
        "pub151": {
            "published_head": "Pub. 151",
            "within_head": "Within 2 percent",
            "caption": "Searoute distances against NGA Pub. 151, Distances Between Ports (11th edition, 2001), "
            "for the port pairs the routes use; a composite figure adds Pub. 151's legs through the junction point "
            "named.",
            "summary": [],
        },
        "downloads_words": "Downloads",
        "downloads": [
            {
                "file": "data/downloads/cost_structure_2026_08.csv",
                "text": "Voyage costs by route at the %s market, CSV" % market_label,
            },
            {"file": "data/downloads/sea_routes.csv", "text": "Every leg's distance and the passages it uses, CSV"},
        ],
    }


# --------------------------------------------------------------------------
# Detours
# --------------------------------------------------------------------------


def detours_page(st: Mapping[str, Any], sd: Mapping[str, Any], hz: Mapping[str, Any]) -> dict[str, Any]:
    cape = st["cape_vs_suez"]
    war = st["red_sea_war_risk"]
    dry = {o["name"]: o for o in sd["options"]}
    scen = {s["id"]: s for s in hz["scenarios"]}
    latest_level = hz["levels"][-1]
    closure = next(lvl for lvl in hz["levels"] if lvl["week_ending"] == "2026-03-06")

    def extra(sid: str, week: str) -> float:
        return next(lvl for lvl in scen[sid]["levels"] if lvl["week_ending"] == week)["extra_freight_usd_t"]

    takeaway = [
        "Round the Cape an LR2 from Jubail to Rotterdam sails ",
        fig(cape["extra_days"], "days", "cape_vs_suez.extra_days", suffix=" more days"),
        " and needs ",
        usd_m(cape["extra_freight_lump_sum_usd"], "cape_vs_suez.extra_freight_lump_sum_usd"),
        " more freight (",
        usd(cape["extra_freight_usd_t"], "cape_vs_suez.extra_freight_usd_t", "usd_t"),
        " a tonne) to earn what Suez earns with the Red Sea premium paid; a ",
        fig(
            scen["war_low"]["war_risk_usd"] / hz["hull_value_usd"] * 100.0,
            "percent",
            "hormuz.premium",
            suffix=" percent",
        ),
        " Hormuz war risk premium adds ",
        usd(extra("war_low", latest_level["week_ending"]), "hormuz.war_low.extra", "usd_t"),
        " a tonne to a VLCC from Ras Tanura.",
    ]
    chart_rows = [
        {
            "group": "LR2, Jubail to Rotterdam (TC20), against Suez",
            "label": "Cape of Good Hope instead of Suez",
            "value": cape["extra_freight_usd_t"],
            "family": "routing",
            "detail": "%s more days" % ("%.1f" % cape["extra_days"]),
        },
        {
            "group": "LR2, Jubail to Rotterdam (TC20), against Suez",
            "label": "Red Sea war risk on both transits",
            "value": war["extra_freight_usd_t"],
            "family": "war",
            "detail": "USD %s" % "{:,.0f}".format(war["cost_usd"]),
        },
        {
            "group": "Panamax, Qingdao to Rotterdam, against Suez",
            "label": "Cape of Good Hope instead of Suez",
            "value": dry["Cape of Good Hope"]["extra_freight_vs_suez_usd_t"],
            "family": "routing",
            "detail": "%s more days" % ("%.1f" % dry["Cape of Good Hope"]["extra_days_vs_suez"]),
        },
        {
            "group": "Panamax, Qingdao to Rotterdam, against Suez",
            "label": "Panama instead of Suez",
            "value": dry["Panama"]["extra_freight_vs_suez_usd_t"],
            "family": "routing",
            "detail": "%s more days" % ("%.1f" % dry["Panama"]["extra_days_vs_suez"]),
        },
    ]
    for sid, label, family in (
        ("war_low", "War risk 7.5 percent of hull value", "war"),
        ("war_high", "War risk 10 percent of hull value", "war"),
        ("wait_5", "7.5 percent and 5 days waiting to transit", "war"),
        ("wait_10", "7.5 percent and 10 days waiting", "war"),
        ("wait_20", "7.5 percent and 20 days waiting", "war"),
        ("sts", "Load by ship to ship transfer off Fujairah instead", "routing"),
        ("td34", "Load at Mina Al Fahal outside the strait (TD34)", "routing"),
    ):
        chart_rows.append(
            {
                "group": "VLCC, Ras Tanura to Ningbo (TD3C), against no premium",
                "label": label,
                "value": extra(sid, latest_level["week_ending"]),
                "family": family,
                "detail": "",
            }
        )
    return {
        "title": "Detours: what the longer or riskier way costs",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "Per tonne of cargo, the Cape costs an LR2 more than the Red Sea premium does, and the Hormuz premium "
                "and waiting outweigh every routing choice for a VLCC.",
            ],
            "axis": "Extra freight to keep the TCE, USD a tonne",
            "legend": [
                {"family": "routing", "text": "Another routing or loading point: its days and fuel"},
                {"family": "war", "text": "A war risk premium, with waiting where stated"},
            ],
            "desc": "Each bar is the freight a tonne of cargo must rise by for the voyage to earn what it earns "
            "without the detour or the premium; a negative bar is a saving. Waiting is priced at the TCE of the "
            "latest week, which waiting days forgo.",
            "rows": chart_rows,
            "source": [
                "Engine output, week to ",
                word(date_label(st["as_of"]), "as_of"),
                ": TC20 at the Baltic's lump sum, the Panamax at the freight that earns the P4 trip rate, TD3C at the "
                "Baltic's TCE of the week (",
                usd(latest_level["tce_usd_day"], "hormuz.latest_tce", "usd_day"),
                " a day). War risk: Marsh and Platts, July 2026. Suez and Panama tolls have no public figure for "
                "these ships and are left out.",
            ],
        },
        "suez_tanker": {
            "lead": [
                "Before any toll Suez earns ",
                usd(st["options"][1]["tce_usd_day"], "suez.tce", "usd_day"),
                " a day with the Red Sea premium (",
                fig(st["war_risk"]["premium_pct"], "percent", "suez.war_risk.premium_pct", suffix=" percent"),
                " of a ",
                usd_m(_hull("LR2-115"), "suez.hull_value_usd", "usd_m_0"),
                " hull on each of ",
                fig(st["war_risk"]["periods"], "count", "suez.war_risk.periods"),
                " transits) and the Cape ",
                usd(st["options"][2]["tce_usd_day"], "cape.tce", "usd_day"),
                ". Suez stays the better voyage until its toll passes ",
                usd_m(st["break_even_suez_toll_usd"], "break_even_suez_toll_usd"),
                "; the Suez Canal Authority puts the toll of a one million barrel crude tanker at about USD 500,000.",
            ],
        },
        "suez_dry": {
            "lead": [
                "To earn the P4 trip rate of ",
                usd(sd["target_tce_usd_day"], "target_tce_usd_day", "usd_day"),
                " a day, a Panamax with 66,000 t from Qingdao to Rotterdam needs ",
                usd(dry["Suez"]["freight_for_target_usd_t"], "suez.freight", "usd_t"),
                " a tonne by Suez (with the Red Sea premium), ",
                usd(dry["Panama"]["freight_for_target_usd_t"], "panama.freight", "usd_t"),
                " by Panama and ",
                usd(dry["Cape of Good Hope"]["freight_for_target_usd_t"], "cape.freight", "usd_t"),
                " round the Cape. At the Cape's freight, Suez can spend ",
                usd(dry["Suez"]["toll_and_waiting_budget_usd"], "suez.budget"),
                " on tolls and waiting, ",
                fig(dry["Suez"]["waiting_days_budget"], "days", "suez.waiting_days", suffix=" days"),
                " of P4 hire, and Panama ",
                usd(dry["Panama"]["toll_and_waiting_budget_usd"], "panama.budget"),
                " (",
                fig(dry["Panama"]["waiting_days_budget"], "days", "panama.waiting_days", suffix=" days"),
                "). %s: on its own that wait makes the Cape the better voyage." % _panama_wait(),
            ],
        },
        "hormuz": {
            "lead": [
                "A ",
                fig(
                    scen["war_low"]["war_risk_usd"] / hz["hull_value_usd"] * 100.0,
                    "percent",
                    "hormuz.premium",
                    suffix=" percent",
                ),
                " premium on a ",
                usd_m(hz["hull_value_usd"], "hormuz.hull_value_usd", "usd_m_0"),
                " VLCC is ",
                usd_m(scen["war_low"]["war_risk_usd"], "hormuz.war_low.cost"),
                " for one transit, ",
                usd(extra("war_low", latest_level["week_ending"]), "hormuz.war_low.extra", "usd_t"),
                " a tonne of cargo whatever the market. Waiting to transit costs the TCE it forgoes: 10 days add ",
                usd(
                    extra("wait_10", closure["week_ending"]) - extra("war_low", closure["week_ending"]),
                    "hormuz.wait_10.closure",
                    "usd_t",
                ),
                " a tonne at the closure week's TCE and ",
                usd(
                    extra("wait_10", latest_level["week_ending"]) - extra("war_low", latest_level["week_ending"]),
                    "hormuz.wait_10.latest",
                    "usd_t",
                ),
                " at the latest. The Baltic's TD34, loading outside the strait, was assessed at ",
                usd(hz["td34_vs_td3c_published"]["td34_tce_usd_day"], "td34.tce", "usd_day"),
                " a day against TD3C's ",
                usd(hz["td34_vs_td3c_published"]["td3c_tce_usd_day"], "td3c.tce", "usd_day"),
                " in the week to ",
                word(date_label(hz["as_of"]), "hormuz.as_of"),
                ".",
            ],
            "levels_words": {lvl["week_ending"]: lvl["label"] for lvl in hz["levels"]},
        },
        "sections": [
            {
                "id": "suez",
                "name": "Suez or the Cape, LR2",
                "summary": ["TC20 from Jubail to Rotterdam: days, distance, TCE and the toll Suez can bear."],
            },
            {
                "id": "dry",
                "name": "Asia to Europe, Panamax",
                "summary": ["Suez, Panama or the Cape for a Panamax: the freight each needs and what it can spend."],
            },
            {
                "id": "hormuz",
                "name": "Hormuz, VLCC",
                "summary": ["War risk, waiting, a transfer off Fujairah and TD34, at three dated TCE levels."],
            },
            {"id": "method", "name": "Method", "summary": ["How a detour is priced, and the dated events."]},
            {"id": "data", "name": "Data", "summary": ["The scenarios as a download."]},
        ],
        "method": [
            "A detour is priced with the same engine at the same week's bunkers: the extra days and tonne miles "
            "against the base routing, and the freight at which the detour earns the base routing's TCE. For a "
            "premium the extra freight is the premium over the cargo net of commission; for waiting it is also the "
            "TCE the waiting days forgo, so it depends on the market's level.",
            "War risk premiums are a percentage of hull value per transit period of seven days, from dated insurer "
            "and broker reports; hull values are Xclusiv Shipbrokers' five year old values of 7 September 2026. The "
            "Suez and Panama tolls, the ship to ship transfer's cost, the shuttle through the strait and the crew's "
            "war bonus have no public figure for these ships and are left out, and each panel says which.",
        ],
        "events_heading": "Dated events behind the scenarios",
    }


# --------------------------------------------------------------------------
# Carbon
# --------------------------------------------------------------------------


def carbon_page(c: Mapping[str, Any]) -> dict[str, Any]:
    rows = {r["route"]: r for r in c["rows"]}
    intra, into = rows["TC23"], rows["TD20"]

    def year(row: Mapping[str, Any], y: int) -> Mapping[str, Any]:
        return next(v for v in row["years"] if v["year"] == y)

    takeaway = [
        "In 2026, with every tonne covered, an MR between two EEA ports pays ",
        usd(year(intra, 2026)["cost_usd"], "TC23.2026.cost_usd"),
        " of allowances, ",
        fig(year(intra, 2026)["share_of_voyage_costs"] * 100.0, "percent", "TC23.2026.share", suffix=" percent"),
        " of its voyage costs; a Suezmax from West Africa to Rotterdam pays ",
        usd(year(into, 2026)["cost_usd"], "TD20.2026.cost_usd"),
        " for half its emissions, and a VLCC from the Gulf to China nothing. In 2024 the same voyages paid ",
        fig(year(intra, 2024)["phase_in"] * 100.0, "percent_0", "phase_in.2024", suffix=" percent"),
        " of their emissions' allowances, on carbon dioxide alone.",
    ]
    tc = c["time_charter"]
    return {
        "title": "Carbon: what the EU ETS adds to a voyage",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "Per day of the voyage the 2026 allowances take ",
                usd(year(intra, 2026)["per_day_usd"], "TC23.2026.per_day_usd", "usd_day"),
                " from the intra-EEA MR's TCE and ",
                usd(year(into, 2026)["per_day_usd"], "TD20.2026.per_day_usd", "usd_day"),
                " from the inbound Suezmax's.",
            ],
            "axis": "EU ETS cost, USD a day of the voyage",
            "none": "None: no EEA port",
            "desc": "Three voyages by three years of the phase in: the cost of the allowances surrendered for the "
            "voyage's covered emissions, over its days. The voyage outside the EEA has none in any year.",
            "source": [
                "Engine output at EUR ",
                fig(c["eua_eur_t"], "eur_t", "eua_eur_t"),
                " an allowance (%s) and " % c["eua_source"],
                fig(c["usd_per_eur"], "usd_per_eur", "usd_per_eur"),
                " dollars per euro (Federal Reserve H.10, %s average); bunkers at the %s common market."
                % (c["market"], c["market"]),
            ],
        },
        "kinds": {
            "TC23": "MR, Amsterdam to Le Havre (TC23): between two EEA ports, 100 percent",
            "TD20": "Suezmax, Bonny to Rotterdam (TD20): into the EEA, 50 percent",
            "TD3C": "VLCC, Ras Tanura to Ningbo (TD3C): outside the EEA",
        },
        "time_charter": {
            "title": "On a time charter the charterer surrenders the allowances",
            "lead": [
                "Under BIMCO's ETS Allowances Clause for time charter parties (2022) the party that provides and pays "
                "for the fuel provides the allowances: on the S4A trip the charterer bears ",
                usd(tc["trip_ets_usd"], "time_charter.trip_ets_usd"),
                " for the trip, and the owner ",
                usd(tc["owner_ets_usd"], "time_charter.owner_ets_usd"),
                " for the ballast leg out of the EEA after redelivery.",
            ],
        },
        "sections": [
            {
                "id": "method",
                "name": "Method",
                "summary": [
                    "Coverage, the phase in, the emission factors and the warming potentials, with their texts."
                ],
            },
            {
                "id": "fueleu",
                "name": "FuelEU Maritime",
                "summary": ["The penalty one voyage's energy would carry, shown and kept out of the TCE."],
            },
            {"id": "data", "name": "Data", "summary": ["The ETS costs and the monthly allowance price as downloads."]},
        ],
        "fueleu": [
            "FuelEU Maritime (Regulation (EU) 2023/1805) has applied since 1 January 2025. It sets a limit on the "
            "greenhouse gas intensity of the energy a ship uses over a year, 89.34 grams of CO2 equivalent per "
            "megajoule from 2025 (2 percent under the 91.16 reference), and a penalty of EUR 2,400 per tonne of "
            "VLSFO equivalent energy in deficit. It is settled per ship and year, with banking, borrowing and "
            "pooling, so a single voyage has no penalty of its own: the figures below are the penalty the voyage's "
            "energy would carry if the ship burnt the same fuel all year, shown beside the TCE and kept out of it.",
        ],
        "method": [
            "Emissions are the fuel burnt by grade times the factors of the MRV Regulation (EU) 2015/757 as amended: "
            "3.114 t of CO2 per t of HFO, 3.151 for LFO and 3.206 for MGO, with VLSFO an ISO 8217 residual grade "
            "(HFO). From 2026 methane and nitrous oxide count, at 0.00005 and 0.00018 g per g of fuel times warming "
            "potentials of 28 and 265.",
            "Covered emissions follow Article 3ga of the ETS Directive: 100 percent of a voyage between two EEA ports "
            "and of the time at berth in them, 50 percent of a voyage into or out of the EEA. Allowances are "
            "surrendered for 40 percent of 2024 emissions, 70 percent of 2025 and 100 percent from 2026 "
            "(Article 3gb).",
        ],
    }


# --------------------------------------------------------------------------
# Paper
# --------------------------------------------------------------------------


def paper_page(p: Mapping[str, Any]) -> dict[str, Any]:
    rows = p["capesize"]
    wk27 = {r["route"]: r for r in rows if r["date"] == "2026-07-03"}
    c3, c5 = wk27["C3"], wk27["C5"]
    fixture = p["c5_fixture"]
    takeaway = [
        "In the week to 3 July 2026 a C3 cargo at ",
        usd(c3["freight_usd_t"], "C3.freight_usd_t", "usd_t"),
        " a tonne earned ",
        usd(c3["physical_tce_usd_day"], "C3.physical_tce_usd_day", "usd_day"),
        " a day, ",
        usd(abs(c3["basis_usd_day"]), "C3.basis_usd_day", "usd_day"),
        " %s the July Capesize 5TC FFA; a C5 cargo earned " % ("below" if c3["basis_usd_day"] < 0 else "above"),
        usd(c5["basis_usd_day"], "C5.basis_usd_day", "usd_day"),
        " a day above it. Hedging the C3 voyage takes ",
        fig(c3["hedge_days"], "days", "C3.hedge_days", suffix=" days"),
        " of 5TC, or ",
        fig(baltic.ROUTES["C3"].cargo_t, "t", "C3.cargo_t", suffix=" tonnes"),
        " of C3 FFA.",
    ]
    return {
        "hedge_columns": [
            {"text": "Route and week", "short": "route"},
            {"text": "Freight, USD a tonne", "short": "freight"},
            {"text": "Physical TCE, USD a day", "short": "physical TCE"},
            {"text": "FFA month", "short": "FFA month", "words": True},
            {"text": "Capesize 5TC FFA, USD a day", "short": "FFA"},
            {"text": "Basis, USD a day", "short": "basis"},
            {"text": "Freight that earns the FFA, USD a tonne", "short": "freight for the FFA"},
            {"text": "Spot 5TC, USD a day", "short": "spot"},
            {"text": "Timing basis, USD a day", "short": "timing basis"},
            {"text": "Hedge, days of 5TC", "short": "hedge"},
        ],
        "title": "Paper: the physical fixture against the FFA",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "The voyage TCEs sit near or above the 5TC FFA for their month, and the FFA above the spot 5TC: "
                "the market priced the coming months above the week's spot.",
            ],
            "axis": "USD a day",
            "desc": "For each anchor week and route, the physical voyage TCE (ink dot), the 5TC FFA for the voyage "
            "month (ringed dot) and the spot 5TC average (muted dot); the rule between the first two is the basis.",
            "legend": [
                {"kind": "ink", "text": "Physical voyage TCE"},
                {"kind": "ring", "text": "5TC FFA for the month"},
                {"kind": "muted", "text": "Spot Capesize 5TC average"},
            ],
            "source": [
                "Engine output for C3 and C5 at Banchero Costa's route assessments and the week's bunkers; FFA: "
                "Banchero Costa, Dry bulk FFA assessments, %s; spot 5TC: Signal Group and Banchero Costa. The July "
                "spot figure does not state its vessel basis (180,000 or 182,000 dwt)."
                % " and ".join(date_label(c["assessed"]) for c in p["curves"])
            ],
        },
        "fixture": {
            "lead": [
                "A C5 fixture reported on 22 October 2026 at ",
                usd(fixture["fixture_usd_t"], "c5_fixture.fixture_usd_t", "usd_t"),
                " a tonne for %s, against the C5 index of " % fixture["laycan"],
                usd(fixture["index_usd_t"], "c5_fixture.index_usd_t", "usd_t"),
                ", earns ",
                usd(fixture["basis_usd_day"], "c5_fixture.basis_usd_day", "usd_day"),
                " a day more than a cargo at the index: the basis between a fixture and the index it would be hedged "
                "with.",
            ],
        },
        "td3c": {
            "lead": [
                "Tanker FFAs settle in dollars a tonne on the monthly average of the route's assessments, and no "
                "public TD3C FFA quote in dollars a tonne was found. Drewry's %s conversion of the TD3C "
                "FFA into a TCE put the second quarter at about " % p["td3c"]["published"],
                usd(p["td3c"]["ffa_tce_q2_usd_day"], "td3c.ffa_tce_q2_usd_day", "usd_day"),
                " a day; the Baltic's physical TD3C TCE in that quarter was ",
                usd(p["td3c"]["physical_q2"][0]["tce_usd_day"], "td3c.physical_q2.0", "usd_day"),
                " in the week to %s and " % date_label(p["td3c"]["physical_q2"][0]["week_ending"]),
                usd(p["td3c"]["physical_q2"][1]["tce_usd_day"], "td3c.physical_q2.1", "usd_day"),
                " in the week to %s: paper sold before the closure of Hormuz missed most of the move."
                % date_label(p["td3c"]["physical_q2"][1]["week_ending"]),
            ],
        },
        "sections": [
            {
                "id": "hedge",
                "name": "Hedge and basis",
                "summary": ["Hedge sizes, the basis and the freight that would earn the FFA, week by week."],
            },
            {
                "id": "tankers",
                "name": "Tankers",
                "summary": ["TD3C paper against physical in the second quarter of 2026."],
            },
            {
                "id": "method",
                "name": "Method",
                "summary": ["How each FFA settles, from the exchanges' contract texts."],
            },
            {"id": "data", "name": "Data", "summary": ["The FFA curves as assessed, by segment and month."]},
        ],
        "method": [
            "A time charter FFA such as the Capesize 5TC settles on the arithmetic average of the Baltic's daily 5TC "
            "assessments in the contract month, in dollars a day; a voyage route FFA such as C3 or C5 on the "
            "average of the route's daily assessments, in dollars a tonne (EEX contract specifications, release "
            "047a, July 2026). Tanker FFAs on ICE settle on the average of the route's assessments over the month, "
            "in dollars a tonne.",
            "A voyage is hedged with time charter FFA days equal to its days, or with route FFA tonnes equal to its "
            "cargo. The basis is the physical TCE less the FFA's; the timing basis is the FFA for the voyage month "
            "less the spot average of the fixture's week. The physical TCEs leave out port charges, so they read "
            "high against a time charter index.",
        ],
    }


# --------------------------------------------------------------------------
# Method and data
# --------------------------------------------------------------------------


def method_page(validation: Mapping[str, Any], route_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_day = {r["route"]: r["excluded_block_per_day_usd"] for r in route_rows}
    tanker = validation["tanker"]
    reproducible = [r for r in tanker if r["reproducible"]]
    same_week = [r for r in reproducible if r["bunkers"].endswith(r["week_ending"])]
    ws = [r for r in tanker if not r["reproducible"] and r["rate_basis"] == "ws"]
    distances = validation["distances"]["checks"]
    within = [c for c in distances if c["within_tolerance"]]
    outlier = max(reproducible, key=lambda r: r["error"])
    usual = [r for r in reproducible if r is not outlier]
    takeaway = [
        "With bunker prices of the same week the engine reproduces the Baltic's TCE for TD22 and TC20 within ",
        fig(min(r["error"] for r in same_week) * 100.0, "error_percent", "validation.min_error"),
        " to ",
        fig(max(r["error"] for r in same_week) * 100.0, "error_percent", "validation.max_error", suffix=" percent"),
        ", always above it by about the port charges it leaves out; ",
        fig(len(ws), "count", "validation.ws_count"),
        " Worldscale anchors cannot be reproduced without a licensed flat rate, and ",
        fig(len(within), "count", "distances.within"),
        " of ",
        fig(len(distances), "count", "distances.count"),
        " distances fall within 2 percent of NGA Pub. 151.",
    ]
    return {
        "title": "Method and data",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "The engine reads above the Baltic's TCE every week, by ",
                fig(min(r["error"] for r in usual) * 100.0, "error_percent", "chart.min_error"),
                " to ",
                fig(max(r["error"] for r in usual) * 100.0, "error_percent", "chart.max_error", suffix=" percent"),
                ", except the week to ",
                word(date_label(outlier["week_ending"]), "chart.outlier.week_ending"),
                " (",
                fig(outlier["error"] * 100.0, "error_percent", "chart.outlier.error", suffix=" percent"),
                "), priced with the bunker table of the week before prices jumped after the closure of Hormuz.",
            ],
            "axis": "Engine above the Baltic, percent",
            "desc": "One dot a week for TD22 and TC20, the two tanker routes whose Baltic rate is a lump sum and so "
            "converts to dollars without a licensed flat rate. A ringed dot is priced with a bunker table up to a "
            "week older than the fixture.",
            "legend": [
                {"kind": "ink", "text": "Bunker table of the same week"},
                {"kind": "ring", "text": "Bunker table up to a week older"},
            ],
            "source": [
                "Baltic Exchange weekly tanker reports as republished by Hellenic Shipping News; bunkers: Star Asia "
                "Shipbroking and Banchero Costa weekly tables; engine output."
            ],
        },
        "sections": [
            {
                "id": "conventions",
                "name": "Conventions",
                "summary": ["Every market convention the engine applies, with the text it is read from."],
            },
            {
                "id": "formulas",
                "name": "Formulas",
                "summary": ["The TCE, the days, the fuel, the carbon and the freight that earns a target."],
            },
            {
                "id": "validation",
                "name": "Validation",
                "summary": ["Every published figure the engine was checked against, reproduced or not, and why."],
            },
            {
                "id": "sources",
                "name": "Sources",
                "summary": ["Every source with its as of date, its retrieval and its licence."],
            },
            {
                "id": "limitations",
                "name": "Limitations",
                "summary": ["What the study cannot do, and the hosts this environment could not reach."],
            },
            {"id": "downloads", "name": "Downloads", "summary": ["The CSV files and the research note."]},
        ],
        "formulas": [
            "TCE = (gross freight + other revenue - commission - voyage costs) / voyage days",
            "Gross freight = USD a tonne x cargo, or the lump sum, or WS / 100 x flat rate x cargo; on a trip, hire x "
            "trip days",
            "Commission = commission share x (gross freight + other revenue)",
            "Voyage costs = bunkers + port charges + canal tolls + EU allowances + war risk premium + other costs",
            "Steaming days = distance x (1 + weather margin) / (24 x speed)",
            "Voyage days = ballast and laden steaming days + loading, discharging, waiting, canal, delay and transfer "
            "days",
            "Fuel at sea = steaming days x consumption at the speed, by zone: MGO inside an ECA, VLSFO outside (HSFO "
            "behind a scrubber)",
            "Consumption = linear between published pairs; outside them c = a v^b, fitted by least squares on the "
            "logs of the pairs",
            "EU allowances = (CO2 + 28 CH4 + 265 N2O from 2026) x coverage share x phase in x EUA price x USD per EUR",
            "War risk = premium x hull value x periods + crew bonus",
            "Freight for a target TCE = (target x voyage days + voyage costs) / (1 - commission share) - other revenue",
            "Best speed = the laden speed on a 0.01 knot grid that maximises the TCE, the ballast leg keeping its gap",
        ],
        "limitations_heading": "What the study cannot do",
        "blocked_heading": "Hosts this environment could not reach, and what each would have added",
        "early_march_caption": "Early March 2026: the Middle East Gulf to China VLCC rates reported in dollars a "
        "tonne, "
        "priced as TD3C. Platts printed USD 62.07 on 2 March; the USD 89 a tonne reported on 3 March names no primary "
        "assessment and is not Platts', whose year to date rise to USD 62.07 was 461 percent. The Baltic's TD3C TCE "
        "was USD 209,550 a day in the week to 27 February and USD 485,959 in the week to 6 March.",
        "baltic_2017_head": "Baltic, 2017",
        "baltic_2017_caption": "The Baltic's own worked TD3C TCE calculation (July 2017), the one fully worked public "
        "example found: its days and fuel reproduced line by line. It prints no prices, so no dollar figure can be "
        "checked against it.",
        "baltic_2017_labels": {
            "laden_days": "Laden days",
            "ballast_days": "Ballast days",
            "total_days": "Total days",
            "laden_fuel_t": "Fuel laden, t",
            "ballast_fuel_t": "Fuel in ballast, t",
            "waiting_fuel_t": "Fuel waiting, t",
            "load_fuel_t": "Fuel loading, t",
            "discharge_fuel_t": "Fuel discharging, t",
        },
        "limitations": [
            "Port charges have no public per call figure: every TCE leaves them out and reads high by their amount, "
            "USD {:,.0f} a day on C3 and USD {:,.0f} a day on C5 for each USD 100,000 of charges.".format(
                per_day["C3"], per_day["C5"]
            ),
            "Worldscale flat rates are licensed and none is public for 2025 or 2026, so a rate in Worldscale points "
            "cannot be priced without the visitor's own flat rate, and those anchors are not reproduced.",
            "Suez and Panama tolls depend on each ship's own canal tonnage and are left out; the detours report the "
            "toll each routing could bear instead.",
            "Bunker prices are dated public averages or weekly broker tables at four hubs, not the price a ship "
            "actually paid; the week of the closure of Hormuz shows how fast they moved.",
            "FFA levels are dated public assessments, two dry curves; no public tanker FFA quote in dollars a tonne "
            "was found.",
            "The Baltic's tanker speeds and consumptions come as two pairs, so the fitted exponent is low and the "
            "best speed often sits at the top of the range searched.",
            "A TCE is an estimate of what a voyage earns at stated inputs, not a forecast, and it is compared with "
            "operating and capital costs, never net of them.",
        ],
        "blocked": [
            "pancanal.com and micanaldepanama.com: the Panama Canal tariff and its toll calculator, which would have "
            "given dated Panama tolls by vessel class.",
            "worldscale.co.uk: the flat rate schedule, which is licensed in any case; a public statement of a 2026 "
            "flat rate would have made the Worldscale anchors reproducible.",
            "dehst.de: the German auction reports, read instead from the copy the sibling study jkm-ttf-arbitrage "
            "publishes.",
            "ecfr.gov, nauticalcharts.noaa.gov and marinecadastre.gov: the North American ECA coordinates in US "
            "regulation, read instead from MARPOL Annex VI Appendix VII.",
            "web.archive.org, tradewindsnews.com, reuters.com, gcaptain.com, freightinvestorservices.com and sgx.com: "
            "trade press and exchange pages with more dated freight, bunker and FFA quotes.",
            "balticexchange.com pages behind a script challenge: the circulars and weekly roundups, read instead as "
            "republished; the Guide to Market Benchmarks itself was read as a PDF.",
        ],
        "downloads": [
            {
                "file": "data/downloads/anchors_tanker.csv",
                "text": "Tanker anchors: every published rate and TCE, reproduced or not",
            },
            {
                "file": "data/downloads/anchors_dry.csv",
                "text": "Dry anchors: route rates and the engine's TCE against the time charter averages",
            },
            {
                "file": "data/downloads/cost_structure_2026_08.csv",
                "text": "Voyage costs by route at the August 2026 market",
            },
            {"file": "data/downloads/detours_hormuz.csv", "text": "The Hormuz scenarios at three dated TCE levels"},
            {"file": "data/downloads/carbon_ets.csv", "text": "EU ETS cost by voyage and year"},
            {"file": "data/downloads/eua_monthly.csv", "text": "EU allowance price, monthly"},
            {"file": "data/downloads/sea_routes.csv", "text": "Every leg's distance and the passages it uses"},
            {"file": "Voyage-Economics-TCE-Research-Note.pdf", "text": "The research note (PDF)"},
        ],
    }


def _hull(vessel_id: str) -> float:
    return float(cases.seed("market.json")["hull_values_usd"]["values"][vessel_id]["value"])


def _panama_wait() -> str:
    fact = next(f for f in cases.seed("canals.json")["panama"]["facts"] if f["id"] == "waits_2026_04")
    return fact["text"]


def _latest_hormuz_rate() -> tuple[str, str]:
    rates = [r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"].startswith("hormuz")]
    latest = max(rates, key=lambda r: r["as_of"])
    return latest["reported"].split(" to ")[0].split(",")[0].split(" (")[0], date_label(latest["as_of"])
