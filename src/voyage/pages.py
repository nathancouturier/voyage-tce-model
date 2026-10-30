"""The words of every view: titles, takeaways, chart titles, source lines and section summaries.

Each sentence is built from the numbers it states, as segments (voyage.words), so a
figure in a sentence is the figure in the table under it and changes with the data.
Nothing here computes a market quantity: the numbers arrive from the engine and the
analysis through voyage.export, which calls these functions and writes the artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

from . import anchors, baltic, cases
from .words import date_label, fig, plain, rounded_parts, usd, usd_m, word

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
    "war_risk.areas.gulf.premium_pct": (
        "War risk premium in the Gulf, percent of hull value a period",
        "percent_2",
        1.0,
    ),
    "war_risk.areas.red_sea.premium_pct": (
        "War risk premium for the Red Sea, percent of hull value a period",
        "percent_2",
        1.0,
    ),
    "war_risk.hull_value_usd": ("Hull value", "usd", 1.0),
    "war_risk.crew_bonus_usd": ("Crew war bonus", "usd", 1.0),
    "war_risk.payer": ("Who pays the war risk premium", None, 1.0),
}

STATUS_WORDS = {
    "sourced": "Sourced",
    "derived": "Derived",
    "chosen": "Study's choice",
    "left_out": "Left out of the TCE",
    "empty": "No public figure",
    "scenario": "Scenario input",
    "changed": "Your figure",
}
#: The class word for each Baltic ship, as the copy names it.
VESSEL_CLASS = {
    "VLCC300": "VLCC",
    "SUEZ160": "Suezmax",
    "AFRA115": "Aframax",
    "LR2-115": "LR2",
    "LR1-75": "LR1",
    "MR50": "MR",
    "HANDC37": "Handy tanker",
    "BCI182": "Capesize",
    "BPI82": "Panamax",
    "BSI63": "Supramax",
}
PAYER_WORDS = {
    "charterer": "The charterer, as on most spot voyage charters",
    "owner": "The owner, recovered in the freight",
}
WAR_AREA_NAMES = {"gulf": "the Gulf", "red_sea": "the Red Sea and Gulf of Aden"}

FREIGHT_FORMATS = {"usd_t": "usd_t", "ws": "ws", "lump_sum": "usd", "hire_usd_day": "usd_day"}
FREIGHT_UNITS = {
    "usd_t": "USD a tonne",
    "ws": "Worldscale points",
    "lump_sum": "USD lump sum",
    "hire_usd_day": "USD a day",
}


@cache
def retrieval_days() -> tuple[str, ...]:
    """Every day a document behind the study's figures was retrieved: the seeds' documents and the two caches'."""
    from .sources import base, ec_eua, frb_h10

    keys: set[str] = {ec_eua.DEHST_KEY, frb_h10.KEY}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for name, value in node.items():
                if name == "raw_key" and isinstance(value, str):
                    keys.add(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in sorted(base.SEED.glob("*.json")):
        walk(cases.seed(path.name))
    files = base.raw_manifest()["files"]
    return tuple(sorted({files[k]["retrieved_at"][:10] for k in keys if k in files}))


def retrieval_words() -> str:
    """ "retrieved 29 October 2026", or the first and last day when the documents were read on several."""
    days = retrieval_days()
    if len(days) == 1:
        return "retrieved %s" % date_label(days[0])
    return "retrieved from %s to %s" % (date_label(days[0]), date_label(days[-1]))


def with_retrieval(segments: list[Any]) -> list[Any]:
    """A chart's source line closed by the day its documents were retrieved."""
    return [*segments, " Sources ", word(retrieval_words(), "retrieved"), "."]


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
        elif path == "war_risk.payer":
            text, value = PAYER_WORDS[value], None
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
    ets: Segments | None
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
        # A zero row's words say why it is zero; no line under its name repeats them.
        ets = None
    war = inputs["war_risk"]
    entered = [area for area, spec in war["areas"].items() if spec["entries"] or spec["ballast_transits"]]
    ballast_only = all(not war["areas"][area]["entries"] for area in entered)
    war_detail: Segments | None
    if result["war_risk"]["total_usd"]:
        war_detail = []
        for area in entered:
            info = result["war_risk"]["areas"][area]
            if war_detail:
                war_detail.append("; ")
            periods = info["periods"] + info["ballast_periods"]
            war_detail += [
                fig(war["areas"][area]["premium_pct"], "percent_2", "inputs.war_risk.%s.premium_pct" % area),
                " percent of a ",
                usd_m(war["hull_value_usd"], "inputs.war_risk.hull_value_usd", "usd_m_0"),
                " hull in %s, " % WAR_AREA_NAMES[area],
                fig(periods, "count", "result.war_risk.%s.periods" % area),
                " period" if periods == 1 else " periods",
            ]
        war_detail.append(
            ", the charter's paid by the %s, a ballast transit's by the owner"
            % ("owner" if war["payer"] == "owner" else "charterer")
            if any(war["areas"][a]["ballast_transits"] for a in entered)
            else ", paid by the %s" % ("owner" if war["payer"] == "owner" else "charterer")
        )
    elif entered:
        war_detail = ["The voyage enters %s, a listed area" % " and ".join(WAR_AREA_NAMES[a] for a in entered)]
    else:
        war_detail = None
    return {
        "gross": {"detail": gross},
        "commission": {"detail": commission},
        "bunkers": {"detail": bunkers},
        "ports": {
            "detail": ["%s and %s" % (load, discharge)],
            "zero": "Left out: no public per call figure" if port_empty else "None entered",
        },
        "canals": {
            "detail": ["%s" % " and ".join(canal_passes)] if canal_passes else None,
            "zero": "Left out: no public toll for this ship" if canal_passes else "None on this routing",
        },
        "ets": {"detail": ets, "zero": "None: no EEA port"},
        "war_risk": {
            "detail": war_detail,
            "zero": (
                "Left out, as in the Baltic's TCE: the owner's on its ballast transit"
                if ballast_only
                else "Left out: the charterer's, as in the Baltic's TCE"
            )
            if entered or result["war_risk"]["total_usd"]
            else "None on this routing",
        },
        "other": {"detail": ["Ship to ship transfer and other costs"], "zero": "None entered"},
        "fueleu": {"detail": ["FuelEU Maritime penalty, shown only when included"], "zero": "Not in the TCE"},
        "result": {"detail": ["Freight less commission and voyage costs"]},
    }


def bridge(preset: Mapping[str, Any], result: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The bridge rows with their family, detail and zero words.

    The five cost families always; other costs and FuelEU only when not zero."""
    details = bridge_details(preset, result)
    # The parts of the voyage's days, rounded so that they add up to the total shown.
    d = result["days"]
    parts = rounded_parts([d["ballast_sea"], d["laden_sea"], d["port_total"]], "days")
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
            fig(parts[0], "days", "result.days.ballast_sea"),
            " in ballast, ",
            fig(parts[1], "days", "result.days.laden_sea"),
            " laden and ",
            fig(parts[2], "days", "result.days.port_total"),
            " in port and waiting), the result is a TCE of ",
            fig(result["tce_usd_day"], "usd_day", "result.tce_usd_day", prefix="USD ", accent=True),
            " a day.",
        ],
    }


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


def bunker_age_words(row: Mapping[str, Any]) -> str:
    """How fresh a validation week's bunker prices were: the table's date and when its row was first printed."""
    table = row["bunkers"].split()[-1]
    first = row["bunkers_first_printed"]
    if table == row["week_ending"]:
        return "Same week" if first == table else "The week's table, reprinting prices of %s" % date_label(first)
    if first == table:
        return "Week of %s, the latest table before it" % date_label(table)
    return "Week of %s, reprinting prices of %s" % (date_label(table), date_label(first))


def _join_words(items: list[Any]) -> list[Any]:
    """Segments joined as 'a and b' or 'a, b and c'."""
    out: list[Any] = []
    for i, item in enumerate(items):
        if i:
            out.append(" and " if i == len(items) - 1 else ", ")
        out.append(item)
    return out


def _map_title(featured: Mapping[str, Any], load: str, discharge: str, cape: bool) -> list[Any]:
    """The overview map's title: each leg's routing where the two differ, its miles, and the miles inside the
    emission control areas."""
    inputs, legs = featured["inputs"], featured["legs"]
    way = "round the Cape of Good Hope" if cape else "the shortest way"
    zones = "the North American and US Caribbean emission control areas"
    eca = fig(inputs["laden"]["eca_nm"], "nm", "inputs.laden.eca_nm")
    if inputs["laden"]["distance_nm"] == inputs["ballast"]["distance_nm"]:
        return [
            "TD22 sails %s, %s to %s laden and back in ballast: " % (way, load, discharge),
            fig(inputs["laden"]["distance_nm"], "nm", "inputs.laden.distance_nm", suffix=" nautical miles"),
            " each way, ",
            eca,
            " of them inside %s." % zones,
        ]

    def by(leg: str, other: str) -> str:
        only = [p for p in legs[leg]["passes"] if p not in legs[other]["passes"]]
        return " by the " + " and the ".join(only) if only else ""

    return [
        "TD22 sails %s, %s to %s laden%s, " % (way, load, discharge, by("laden", "ballast")),
        fig(inputs["laden"]["distance_nm"], "nm", "inputs.laden.distance_nm", suffix=" nautical miles"),
        ", and back in ballast%s, " % by("ballast", "laden"),
        fig(inputs["ballast"]["distance_nm"], "nm", "inputs.ballast.distance_nm"),
        "; ",
        eca,
        " miles of %s lie inside %s."
        % ("each leg" if inputs["laden"]["eca_nm"] == inputs["ballast"]["eca_nm"] else "the laden leg", zones),
    ]


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
    summary = anchors.lump_sum_summary()
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
        "A VLCC on TD22, %s to %s, at the Baltic's assessed " % (load, discharge),
        usd_m(inputs["freight_value"], "inputs.freight_value"),
        " in the week to ",
        word(date_label(week), "date"),
        ", earns an estimated ",
        fig(tce, "usd_day", "result.tce_usd_day", prefix="USD "),
        " a day over a ",
        fig(result["days"]["total"], "days", "result.days.total"),
        " day round voyage; ",
        "freight of ",
        usd(zero["usd_t"], "breakeven.usd_t", "usd_t"),
        " a tonne would only cover the voyage costs priced.",
    ]
    dates = [
        [
            "Freight and the Baltic's TCE: Baltic Exchange weekly tanker report, week to ",
            word(date_label(week), "date"),
            ", as republished by Hellenic Shipping News.",
        ],
        [
            "Bunkers: %s, priced at %s, the hub with public prices nearest %s." % (bunker_source, hub, load)
            if not route.bunker_hub
            else "Bunkers: %s, priced at %s: %s." % (bunker_source, hub, route.bunker_hub_why)
        ],
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
                ". Port charges, which it leaves out, explain only part of that: across the weeks checked the gap "
                "grows with freight, which a fixed charge cannot do.",
            ],
        },
        {
            "id": "breakeven",
            "label": "Freight that covers the voyage costs priced",
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
            "label": "Bunkers in the voyage costs priced",
            "value": fig(bunker_share * 100.0, "percent", "result.bunker_share"),
            "unit": "percent",
            "as_of": week,
            "note": [
                "The bunker bill, ",
                usd_m(costs["bunkers"], "result.costs.bunkers"),
                ", is ",
                fig(
                    costs["bunkers"] / result["revenue"]["gross_usd"] * 100.0,
                    "percent",
                    "result.bunkers_of_freight",
                    suffix=" percent",
                ),
                " of the freight: VLSFO at ",
                usd(inputs["prices"]["vlsfo_usd_t"], "inputs.prices.vlsfo_usd_t", "usd_t"),
                " and MGO at ",
                usd(inputs["prices"]["mgo_usd_t"], "inputs.prices.mgo_usd_t", "usd_t"),
                " a tonne. Port charges at %s and %s, the voyage's only other cost, have no public figure and are "
                "left out, so the share is of the costs priced, not of all voyage costs." % (load, discharge),
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
        " of voyage costs priced, ",
        *(
            ["all of them bunkers; port charges, with no public figure, are left out."]
            if bunker_share > 1.0 - 1e-9
            else [fig(bunker_share * 100.0, "percent", "result.bunker_share", suffix=" percent"), " of them bunkers."]
        ),
    ]
    b["source"] = with_retrieval(
        [
            "Engine output for TD22 in the week to ",
            word(date_label(week), "date"),
            ". Freight: Baltic Exchange via Hellenic Shipping News. Bunkers: %s. " % bunker_source,
            "A cost with no public figure is left out and named in its row.",
        ]
    )
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
            "title": _map_title(featured, load, discharge, cape),
            "legend": [
                {"kind": "laden", "text": "Laden leg, %s to %s" % (load, discharge)},
                {"kind": "ballast", "text": "Ballast leg, %s to %s, drawn beside it" % (discharge, load)},
                {"kind": "eca", "text": "Inside an emission control area: 0.10 percent sulphur fuel (MGO)"},
            ],
            "source": with_retrieval(
                [
                    "Lines: searoute over Eurostat SeaRoute, the lines the distances are measured on. "
                    "Emission control areas: MARPOL Annex VI, in force on ",
                    word(date_label(week), "date"),
                    ". Land: Natural Earth 1:110m.",
                ]
            ),
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
                    "canal days follow the route description. TD22 loads in the Galveston lightering area and sails "
                    "laden round the Cape of Good Hope and through the Strait of Malacca to Ningbo, the strait the "
                    "mileage of the Baltic's own TD3C calculation implies for the same laden VLCC, rather than the "
                    "shallower Sunda Strait of the shortest network line; in ballast it comes back through the Sunda "
                    "Strait. The "
                    "Baltic measures its distances on AtoBviaC tables, which are not published.",
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
                "Freight that covers the voyage costs priced = voyage costs / (1 - commission share), the TCE set "
                "to zero",
            ],
            "comparison_title": [
                "Against the Baltic's own TD22 TCE the engine reads between ",
                fig(summary["fresh_error"][0] * 100.0, "error_percent", "comparison.min_error", suffix=" percent"),
                " and ",
                fig(summary["fresh_error"][1] * 100.0, "error_percent", "comparison.max_error", suffix=" percent"),
                " higher in the weeks priced with prices first printed that week, the two weeks after the closure "
                "of Hormuz aside, and further above in dollars as freight rises: ",
                usd(summary["gap_low"]["gap_usd_day"], "comparison.gap_low", "usd_day"),
                " a day on a ",
                usd_m(summary["gap_low"]["row"]["rate_value"], "comparison.gap_low_rate"),
                " lump sum (",
                word(date_label(summary["gap_low"]["row"]["week_ending"]), "comparison.gap_low_week"),
                "), ",
                usd(summary["gap_high"]["gap_usd_day"], "comparison.gap_high", "usd_day"),
                " on ",
                usd_m(summary["gap_high"]["row"]["rate_value"], "comparison.gap_high_rate"),
                " (",
                word(date_label(summary["gap_high"]["row"]["week_ending"]), "comparison.gap_high_week"),
                ").",
            ],
            "comparison_note": [
                "Port charges, which the engine leaves out (the Baltic takes them from Cory Brothers and says they "
                "are on its website, which this study could not read), are a fixed sum a voyage, so they explain only "
                "part of the gap; the rest grows with "
                "freight, as it would if the Baltic's voyage were longer than searoute's or carried another cost that "
                "scales with freight, and the weeks checked cannot tell which. In the weeks to ",
                *_join_words(
                    [word(date_label(r["week_ending"]), "exception.%d" % i) for i, r in enumerate(summary["exception"])]
                ),
                " the engine reads ",
                *_join_words(
                    [
                        fig(r["error"] * 100.0, "error_percent", "exception.%d.error" % i)
                        for i, r in enumerate(summary["exception"])
                    ]
                ),
                " percent above with the bunker tables of those weeks, and why is not established; the guide changed "
                "its description of the fuel price in May 2026 (version 8.4), so how the Baltic priced fuel in March "
                "is not documented. Star Asia sometimes reprints a week's bunker table unchanged, so each week above "
                "says when the prices it was priced with were first printed.",
            ],
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
            {**r, "error_pct": r["error"] * 100.0, "bunkers_words": bunker_age_words(r)} for r in comparison
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
            "none": "None on this routing",
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
            "breakeven_target_unit": "USD a day; zero gives the freight that only covers the voyage costs priced",
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
            "tornado_both": "{lower} and {higher}",
            "tornado_desc": "Each row has two bars from the base TCE, the vertical rule: an outlined one to the TCE "
            "with the input lower and a filled one to the TCE with it higher. Where both cases move the TCE the same "
            "way, the two bars share the row, the lower case above, and the two changes are written together in "
            "that order.",
            "speed_title": "The TCE is highest at {best} knots laden at these inputs; the voyage is priced at "
            "{current}.",
            "speed_title_bound": "The TCE still rises at {best} knots, the top of the range searched, a knot above "
            "the fastest published consumption, where consumption is extrapolated; the voyage is priced at "
            "{current}.",
            "speed_axis_x": "Laden speed, knots (ballast keeps its gap)",
            "speed_axis_y": "TCE, USD a day",
            "speed_desc": "The TCE at each laden speed from one knot below the slowest published speed to one "
            "knot above the fastest. Between published pairs consumption is interpolated and the line is solid; "
            "outside them it follows the power law fitted to the pairs and the line is dashed.",
            "speed_published": "Consumption from the published speed pairs",
            "speed_extrapolated": "Consumption extrapolated by the fitted power law",
            "speed_title_low": "The TCE is highest at {best} knots, the slowest speed searched; the voyage is priced "
            "at {current}.",
            "speed_trip_note": "On a trip time charter the charterer orders the speed and buys the trip's fuel, and "
            "the owner earns the same hire a day at any speed, so no speed chart is drawn for a trip.",
            "speed_best": "Best, {best} kn",
            "speed_current": "Priced, {current} kn",
            "source": "Engine output at the inputs above. Preset: {preset}; bunkers: {market}; EU allowance price: "
            "{eua}; dollars per euro: {fx}. Sources " + retrieval_words() + ".",
            "result_line": "Over {days} days ({ballast} in ballast, {laden} laden and {port} in port and waiting), "
            "the result is a TCE of {tce} a day.",
            "million": "USD {value} million",
            "routing_laden": "Routing, laden leg",
            "routing_ballast": "Routing, ballast leg",
            "routing_note": "The routings the study computes for this route. A routing sets each leg's distance, its "
            "miles inside ECAs, the canal days and the listed war risk areas it enters; tolls stay as entered.",
            "ets_year": "EU ETS year",
            "ets_year_note": "40 percent of 2024 emissions, 70 percent of 2025 and 100 percent from 2026 "
            "(Directive 2003/87/EC, Article 3gb), with methane and nitrous oxide from 2026 (Annex I).",
            "freight_basis": "Freight basis",
            "vlsfo_class": "VLSFO emission class",
            "scrubber": "Scrubber fitted: burns HSFO outside ECAs",
            "scrubber_in_eca": "Scrubber also used inside ECAs, where local rules allow",
            "fueleu": "Include the FuelEU Maritime penalty in the TCE",
            "curves": "Published speeds and consumptions",
            "curve_fit": "Outside the published pairs consumption follows c = a v^b fitted to them: laden b {laden}, "
            "ballast b {ballast}.",
            "war_rates": "Dated war risk premiums for the listed areas this voyage enters",
            "war_use": "Use {value} percent",
            "war_none": "This routing enters neither the Gulf nor the Red Sea, the listed areas the study prices, so "
            "a premium entered above does not count.",
            "war_payer": "Who pays the war risk premium",
            "war_area_line": "In {area}: {days} days inside, so {periods}, {usd} at the premium entered.",
            "war_transit_line": "Through {area} on the laden leg: {periods}, one a transit, {usd} at the premium "
            "entered.",
            "war_ballast_line": "Through {area} on the ballast leg, the approach to the next loading: {periods}, "
            "{usd}, the owner's unless a charter makes the charterer pay it (Gard, 21 March 2026), so it is in the "
            "TCE.",
            "war_period_one": "one period of up to seven days",
            "war_period_many": "{n} periods of up to seven days",
            "war_paid_charterer": "The charterer pays the charter's premium: it stays out of the owner's TCE, as in "
            "the Baltic's.",
            "war_paid_owner": "The owner pays the charter's premium, and recovers it only in the freight: it is in "
            "the TCE.",
            "war_charterer": "The charterer's: {usd}",
            "war_charterer_also": "The charterer pays a further {usd}",
            "reset": "Reset",
            "empty_placeholder": "No public figure",
            "not_cited": "A scenario input: the base case uses the value shown.",
            "changed": "Your figure.",
            "source_changed": "Your figures: {fields}.",
            "live_line": "TCE now: {tce} a day.",
            "routing_changed": "the routing",
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
                "A dated market reads no price from after its date: bunkers from the brokers' weekly table of the "
                "week, or of up to seven days before, a reprinted row dated by its first printing; the EU allowance "
                "price from the latest monthly average before the voyage's own month, since a month's average is "
                "known only once it ends; the dollar rate as the mean of the Federal Reserve's H.10 rates published "
                "in the voyage's month up to its date. The common market is a period average instead: "
                + common_market_words()
                + "; its allowance price and dollar rate are August averages.",
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
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["What this voyage leaves out, and what each field's status means."],
            },
            {"id": "data", "name": "Data", "summary": ["Every input of the voyage as it now stands, with its source."]},
        ],
        "assumptions": {
            "leaves_out_heading": "What this voyage leaves out",
            "statuses_heading": "What a field's status means",
            "statuses": [
                ["sourced", "a figure from a dated public document, cited beside the field."],
                ["derived", "computed from sourced figures by a stated rule, such as a distance or port days."],
                ["chosen", "the study's choice among published values, where the source names none, with the reason."],
                ["left_out", "a cost the Baltic's TCE leaves out too, priced at zero; a figure entered here counts."],
                ["empty", "no public figure: it counts as zero and the result names it among what it leaves out."],
                [
                    "scenario",
                    "zero in the base case: a delay, a transfer, another cost or other revenue for you to set.",
                ],
                ["changed", "a figure you entered; Reset returns the field to its source."],
            ],
        },
    }


# --------------------------------------------------------------------------
# Speed across markets (the calculator's section)
# --------------------------------------------------------------------------

LEVEL_WORDS = {"low": "Low", "mid": "Middle", "high": "High"}


def _bunker_level_words(cell: Mapping[str, Any], hub: str) -> str:
    """A bunker level's words: the weekly table's date, or the common market and the period of its hub's VLSFO."""
    if cell["bunker_level"] != "mid":
        return "%s, %s" % (LEVEL_WORDS[cell["bunker_level"]], date_label(cell["bunker_as_of"]))
    spec = cases.seed("market.json")["common_market"]
    period = spec["bunkers_usd_t"][hub]["vlsfo"]["period"]
    when = "%s average" % spec["label"] if period.startswith(spec["label"]) else "third quarter average"
    return "%s, the %s common market (%s VLSFO: %s)" % (LEVEL_WORDS["mid"], spec["label"], _port_name(hub), when)


def speed_page(speed: Mapping[str, Any]) -> dict[str, Any]:
    routes = speed["routes"]
    held = [
        t
        for t in speed["textbook"]
        if t["freight_pushes_speed_up"] == "holds" and t["bunkers_push_speed_down"] == "holds"
    ]
    tanker_cells = [g for r in routes if baltic.ROUTES[r["route"]].segment != "dry" for g in r["grid"]]
    top_share = sum(1 for g in tanker_cells if g["at_top"]) / len(tanker_cells)
    moved_at = {g["freight_level"] for g in tanker_cells if not g["at_top"]}
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
                    "bunker_words": _bunker_level_words(g, r["hub"]),
                }
            )
        out_routes.append({**{k: v for k, v in r.items() if k != "grid"}, "grid": grid, "caption": caption})
    lead = [
        "On ",
        fig(len(held), "count", "textbook.held"),
        " of the ",
        fig(len(routes), "count", "textbook.routes"),
        " routes with a public freight rate in dollars, a higher rate never lowers the best speed, dearer bunkers "
        "never raise it, and each moves it somewhere in the grid: the textbook result holds. For the tankers it "
        "shows %s: with only two published consumption pairs their fitted exponents are low, so faster steaming "
        "looks cheap and in "
        % (
            "only at the lowest public freight"
            if moved_at == {"low"}
            else "in %d of their %d cases" % (sum(1 for g in tanker_cells if not g["at_top"]), len(tanker_cells))
        ),
        fig(top_share * 100.0, "percent_0", "textbook.top_share", suffix=" percent"),
        " of their cases the best speed is at the top of the range searched.",
    ]
    return {
        "lead": lead,
        "bound_marks": {"top": "top", "bottom": "bottom"},
        "note": "The range searched runs one knot either side of the published consumption pairs; beyond them "
        "consumption follows the power law fitted to the pairs, an extrapolation. Linear interpolation between "
        "pairs puts kinks at the published speeds, so best speeds often fall exactly on one of them. In the "
        "tables, top and bottom mark a best speed at an end of the range searched.",
        "routes": out_routes,
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

SEGMENT_WORDS = {"dry": "Dry bulk", "dirty": "Dirty tankers", "clean": "Clean tankers"}


def _short(code: str) -> str:
    return code.replace("_37", "").replace("_63", "")


def common_market_words() -> str:
    """Which of the common market's bunker prices are monthly and which quarterly, as one sentence's clause."""
    spec = cases.seed("market.json")["common_market"]
    monthly: dict[str, list[str]] = {}
    quarterly: dict[str, list[str]] = {}
    for hub, grades in spec["bunkers_usd_t"].items():
        for grade, value in grades.items():
            target = monthly if value["period"].startswith(spec["label"]) else quarterly
            target.setdefault(hub.title(), []).append(grade.upper())

    def listed(groups: Mapping[str, list[str]]) -> str:
        def grades(g: list[str]) -> str:
            return g[0] if len(g) == 1 else "%s and %s" % (", ".join(g[:-1]), g[-1])

        return "; ".join("%s %s" % (hub, grades(g)) for hub, g in groups.items())

    return (
        "Ship & Bunker's %s averages where it publishes them (%s) and its third quarter averages, July to "
        "September, for the other hub prices (%s)" % (spec["label"], listed(monthly), listed(quarterly))
    )


def hub_words() -> str:
    """The bunker hub rule and its one exception, as a sentence."""
    exceptions = [r for r in baltic.ROUTES.values() if r.bunker_hub and r.code in baltic.STUDY_ROUTES]
    words = (
        "Bunkers are priced at the hub nearest the load port among the four with public prices for every grade "
        "(Singapore, Fujairah, Rotterdam, Houston), the rule the Baltic applies to its tanker TCEs (Guide to Market "
        "Benchmarks v%s, Appendix 3, page 98), applied to every route" % baltic.GMB["version"]
    )
    for r in exceptions:
        words += " except %s, priced at %s: %s" % (r.code, _port_name(r.bunker_hub), r.bunker_hub_why)
    return words + "."


def _td22_malacca_words() -> tuple[str, str, str]:
    """The Baltic's 2017 TD3C mileage, the network's TD3C leg through Malacca, and how much shorter TD22's laden
    leg would be through the Sunda Strait."""
    td22, td3c = baltic.ROUTES["TD22"], baltic.ROUTES["TD3C"]
    malacca = cases.leg_record(td22.load, td22.discharge, td22.laden_routing)["distance_nm"]
    sunda = cases.leg_record(td22.load, td22.discharge, "no_canals")["distance_nm"]
    gulf = cases.leg_record(td3c.load, td3c.discharge, td3c.laden_routing)["distance_nm"]
    mileage = cases.seed("anchors.json")["baltic_td3c_2017"]["inputs"]["distance_nm"]
    return f"{mileage:,.0f}", f"{gulf:,.0f}", f"{malacca - sunda:,.1f}"


def routes_page(market_label: str, eua: float, fx: float, rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    with_ets = [r for r in rows if r["costs_usd"]["ets"]]
    bunkers_only = [r for r in rows if r["shares"]["bunkers"] > 1.0 - 1e-9]
    ets_shares = [r["shares"]["ets"] for r in with_ets]
    hormuz = [r for r in rows if r["with_hormuz_war_risk"] and r["with_hormuz_war_risk"].get("hull_value_usd")]
    worst = max(hormuz, key=lambda r: r["with_hormuz_war_risk"]["premium_to_bunkers"])
    least = min(hormuz, key=lambda r: r["with_hormuz_war_risk"]["premium_to_bunkers"])
    w = worst["with_hormuz_war_risk"]
    cheapest = min(rows, key=lambda r: r["per_day_usd"])
    dearest = max(rows, key=lambda r: r["per_day_usd"])
    takeaway = [
        "At %s prices bunkers are all of the sourced voyage costs on " % market_label,
        fig(len(bunkers_only), "count", "bunkers_only.count"),
        " of the ",
        fig(len(rows), "count", "rows.count"),
        " routes and, on the ",
        fig(len(with_ets), "count", "with_ets.count"),
        " that touch the EEA, EU allowances are ",
        fig(min(ets_shares) * 100.0, "percent", "ets_share.min"),
        " to ",
        fig(max(ets_shares) * 100.0, "percent", "ets_share.max", suffix=" percent"),
        " of them; a Hormuz war risk premium at the low end of the latest dated range, ",
        fig(w["premium_pct"], "percent", "hormuz.premium_pct"),
        " to ",
        fig(_hormuz_high(), "percent", "hormuz.premium_pct_high", suffix=" percent"),
        " of hull value (%s, %s), would cost the charterer of a %s cargo "
        % (*_latest_hormuz_rate(), _short(worst["route"])),
        fig(w["premium_to_bunkers"], "exponent", "hormuz.premium_to_bunkers"),
        " times the voyage's fuel bill, ",
        fig(w["premium_to_bunkers"] * _hormuz_high() / w["premium_pct"], "exponent", "hormuz.premium_to_bunkers_high"),
        " times at the top of the range.",
    ]
    chart_title = [
        "Sourced voyage costs run from ",
        usd(cheapest["per_day_usd"], "per_day_usd.min", "usd_day"),
        " a day on %s to " % _short(cheapest["route"]),
        usd(dearest["per_day_usd"], "per_day_usd.max", "usd_day"),
        " on %s; on the " % _short(dearest["route"]),
        fig(len(bunkers_only), "count", "bunkers_only.count"),
        " routes that do not touch the EEA they are bunkers alone, since port charges and canal tolls have no "
        "public figure.",
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
            "axis": "Sourced voyage costs, USD a day of the round voyage",
            "note": "S4A is a trip time charter: its bar holds the charterer's trip costs and the owner's ballast leg "
            "back to the US Gulf. The library holds the study's %d routes; TC20 and TD34 are priced in the calculator "
            "and on the Detours view, and TC23, the voyage between two EEA ports, on the Carbon view." % len(rows),
            "desc": "One bar a route, grouped by segment, split into bunkers and EU allowances; port charges and canal "
            "tolls have no public figure and are left out of every bar. S4A is a trip time charter: its bar holds the "
            "charterer's trip costs and the owner's ballast leg back to the US Gulf.",
            "source": with_retrieval(
                [
                    "Engine output at the common market, %s: %s, at each route's bunker hub; EU allowances at EUR "
                    % (market_label, common_market_words()),
                    fig(eua, "eur_t", "eua_eur_t"),
                    " and ",
                    fig(fx, "usd_per_eur", "usd_per_eur"),
                    " dollars per euro. Ships, speed and consumption pairs and port days: Baltic Exchange Guide to "
                    "Market Benchmarks v%s; tankers sail at the speeds their descriptions name, bulk carriers at the "
                    "fastest pair printed, the study's choice." % baltic.GMB["version"],
                ]
            ),
            "legend": [
                {"family": "bunkers", "text": "Bunkers"},
                {"family": "ets", "text": "EU ETS allowances"},
            ],
        },
        "table_caption": "Every route: the Baltic's ship and cargo, distances by routing (the one each route is "
        "priced on marked), the share of the miles inside emission control areas, port days and sourced voyage costs "
        "at %s prices." % market_label,
        "priced_mark": "(priced)",
        "turn_time_mark": "(turn time only: loading at the port's scale has no published rate)",
        "hormuz": {
            "title": "The Gulf loadings with the Hormuz premium",
            "caption": "Each Gulf loading at the common market with the latest dated Hormuz premium for each seven "
            "days or part of them it spends inside the Gulf, on its hull value. On the usual spot terms the premium "
            "is the charterer's, so it is set beside the voyage costs, not in them; the LR1 of TC5 has no dated "
            "public hull value.",
            "lead": [
                "At ",
                fig(w["premium_pct"], "percent", "hormuz.premium_pct", suffix=" percent"),
                " of hull value a period (%s, %s), the charterer's premium for a Gulf loading is "
                % _latest_hormuz_rate(),
                fig(least["with_hormuz_war_risk"]["premium_to_bunkers"], "exponent", "hormuz.premium_to_bunkers_min"),
                " to ",
                fig(w["premium_to_bunkers"], "exponent", "hormuz.premium_to_bunkers_max"),
                " times the voyage's fuel bill.",
            ],
        },
        "segments": SEGMENT_WORDS,
        "sections": [
            {
                "id": "library",
                "name": "The routes, one by one",
                "summary": [
                    "Each route's ship, cargo, commission, distances by routing, miles inside ECAs, port days and "
                    "sourced voyage costs."
                ],
            },
            {
                "id": "hormuz",
                "name": "The Gulf loadings with the Hormuz premium",
                "summary": ["The charterer's premium for each seven days inside the Gulf, beside the voyage costs."],
            },
            {
                "id": "method",
                "name": "Method",
                "summary": ["How distances, miles inside ECAs, bunker hubs and the common market are set."],
            },
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["What each route's TCE leaves out, the speeds, and how laytime becomes port days."],
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
            "discharge port; the ballast leg back from the discharge port, the Baltic's TCE delivery point. TD22's "
            "laden VLCC goes round the Cape of Good Hope and through the Strait of Malacca, the strait the %s nm of "
            "the Baltic's own TD3C calculation (July 2017) implies for the same laden ship (the network's line "
            "through Malacca measures that leg at %s nm), not through the shallower Sunda Strait of the shortest "
            "network line (%s nm shorter), which its ballast leg takes. The Baltic measures its distances on "
            "AtoBviaC tables, which are not published." % _td22_malacca_words(),
            "Each line starts at the network's node nearest its port. Amsterdam's nearest node lies in the IJmeer, "
            "behind the lakes, so its legs are asked from IJmuiden and the 14 miles of the North Sea Canal are added "
            "(Pub. 151 page 44); the stretch from the port is added at Port Hedland (43 nm of open water) and Jubail "
            "(12 nm). Elsewhere it is left out: under 10 nm at most ports, up a river or ship channel the network "
            "does not draw at Ningbo and Houston, and about 21.5 nm a leg at Tubarao, where the node lies off the "
            "way the line runs.",
            "Miles inside emission control areas are measured on the same line against polygons built from MARPOL "
            "Annex VI Appendix VII and the area regulations, with the Mediterranean ECA from 1 May 2025. The "
            "Canadian Arctic and Norwegian Sea ECAs (0.10 percent from 1 March 2027) are listed with their dates but "
            "not drawn: no study route enters them. Inside an ECA a ship without a scrubber burns MGO at 0.10 percent "
            "sulphur; outside, VLSFO at 0.50 percent.",
            hub_words()
            + " The common market is %s: %s; the allowance price and the dollar rate are %s averages."
            % (market_label, common_market_words(), market_label),
        ],
        "assumptions": [
            "Port charges have no public per call figure for any study port (the Baltic takes them from Cory "
            "Brothers and says they are on its website, which answers scripted requests with a challenge), so every "
            "TCE leaves them out and reads high by their amount.",
            "Canal tolls depend on each ship's own canal tonnage, which is not published for the Baltic's standard "
            "ships; a routing through a canal leaves its toll out and says so. The guide's dry route terms set no "
            "time at a canal, so P7 also leaves out its transit and any wait at Panama. %s." % _panama_wait(),
            "Tankers sail at the laden and ballast speeds their descriptions name, at which the Baltic prices its "
            "TCEs. The dry routes name no speed, so the study prices bulk carriers at the fastest pair the guide "
            "prints for each ship, its own choice; the calculator shows the TCE at every speed.",
            "Dry laytime becomes calendar days by the route's terms: Saturdays and Sundays excepted terms count "
            "five working days in seven, Sundays and holidays included terms count every day, and the turn time is "
            "added. Capesize loading on the port's scale has no published rate and is left out.",
            "S4A is a trip time charter: the charterer pays the trip's bunkers, ports and allowances, and the owner's "
            "TCE counts the ballast back to the US Gulf, the guide's way of setting a time charter's ballast time "
            "against its hire (section 7.4.3).",
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
                "text": "Sourced voyage costs by route at the %s market, CSV" % market_label,
            },
            {"file": "data/downloads/sea_routes.csv", "text": "Every leg's distance and the passages it uses, CSV"},
        ],
    }


# --------------------------------------------------------------------------
# Detours
# --------------------------------------------------------------------------


def _shuttle(hz: Mapping[str, Any]) -> dict[str, Any]:
    """The reported shuttle costs per tonne of a TD3C cargo, at the reported barrels in a VLCC cargo."""
    reports = {r["id"]: r for r in cases.seed("market.json")["hormuz_chain"]["reports"]}
    cargo = baltic.ROUTES["TD3C"].cargo_t or 0.0
    barrels = reports["vlcc_barrels_2026_07_30"]["low"]
    per_bbl = reports["shuttle_usd_bbl_2026_09_21"]
    transit = reports["shuttle_usd_transit_2026_10_12"]
    return {
        "bbl_low": per_bbl["low"],
        "bbl_high": per_bbl["high"],
        "bbl_low_t": per_bbl["low"] * barrels / cargo,
        "bbl_high_t": per_bbl["high"] * barrels / cargo,
        "transit_usd": transit["low"],
        "transit_t": transit["low"] / cargo,
        "barrels": barrels,
        "round_voyage_days": reports["goo_round_voyage_2026_09_23"]["low"],
    }


def detours_page(st: Mapping[str, Any], sd: Mapping[str, Any], hz: Mapping[str, Any]) -> dict[str, Any]:
    cape = st["cape_vs_suez"]
    red = st["red_sea_war_risk"]
    dry = {o["name"]: o for o in sd["options"]}
    scen = {s["id"]: s for s in hz["scenarios"]}
    latest_level = hz["levels"][-1]
    closure = next(lvl for lvl in hz["levels"] if lvl["week_ending"] == "2026-03-06")
    chains = hz["chains"]
    shuttle = _shuttle(hz)
    marsh = next(r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"] == hz["war_risk_source"])

    def owner(sid: str, week: str) -> float:
        return next(lvl for lvl in scen[sid]["levels"] if lvl["week_ending"] == week)["extra_freight_usd_t"]

    takeaway = [
        "Round the Cape an LR2 from Jubail to Rotterdam sails ",
        fig(cape["extra_days"], "days", "cape_vs_suez.extra_days", suffix=" more days"),
        " and needs ",
        usd(cape["extra_freight_usd_t"], "cape_vs_suez.extra_freight_usd_t", "usd_t"),
        " a tonne more freight to earn what it earns by Suez before Suez tolls; for a VLCC loading in the Gulf, "
        "each further seven days inside costs the charterer another ",
        usd(scen["war_low"]["charterer_war_risk_usd_t"], "hormuz.war_low.per_tonne", "usd_t"),
        " a tonne of premium at %s percent of hull value." % ("%g" % marsh["low"]),
    ]
    group_tc20 = "LR2, Jubail to Rotterdam (TC20), against Suez"
    group_dry = "Panamax, Qingdao to Rotterdam one way, against Suez"
    group_vlcc = "VLCC, Ras Tanura to Ningbo (TD3C), against no premium and no waiting"
    chart_rows = [
        {
            "group": group_tc20,
            "label": "Cape of Good Hope instead of Suez, before Suez tolls",
            "segments": [{"value": cape["extra_freight_usd_t"], "family": "routing"}],
            "detail": "%.1f more days, %.2f billion more tonne miles"
            % (cape["extra_days"], cape["extra_tonne_miles"] / 1e9),
        },
        {
            "group": group_tc20,
            "label": "Red Sea premium on the laden transit, the charterer's",
            "segments": [{"value": red["per_tonne_usd"], "family": "war"}],
            "detail": "USD %s" % f"{red['charterer_usd']:,.0f}",
        },
        {
            "group": group_dry,
            "label": "Cape of Good Hope instead of Suez",
            "segments": [{"value": dry["Cape of Good Hope"]["extra_freight_vs_suez_usd_t"], "family": "routing"}],
            "detail": "%.1f more days" % dry["Cape of Good Hope"]["extra_days_vs_suez"],
        },
        {
            "group": group_dry,
            "label": "Panama instead of Suez",
            "segments": [{"value": dry["Panama"]["extra_freight_vs_suez_usd_t"], "family": "routing"}],
            "detail": "%.1f more days" % dry["Panama"]["extra_days_vs_suez"],
        },
        {
            "group": group_dry,
            "label": "Red Sea premium on the Suez transit, the charterer's",
            "segments": [{"value": dry["Suez"]["charterer_war_risk_usd_t"], "family": "war"}],
            "detail": "",
        },
    ]
    for sid, label in (
        ("war_low", "War risk %g percent of hull value" % marsh["low"]),
        ("war_high", "War risk %g percent of hull value" % marsh["high"]),
        ("wait_5", "%g percent and 5 days waiting inside the Gulf" % marsh["low"]),
        ("wait_10", "%g percent and 10 days waiting" % marsh["low"]),
        ("wait_20", "%g percent and 20 days waiting" % marsh["low"]),
    ):
        periods = scen[sid]["periods"]
        chart_rows.append(
            {
                "group": group_vlcc,
                "label": label,
                "segments": [
                    {"value": scen[sid]["charterer_war_risk_usd_t"], "family": "war"},
                    {"value": owner(sid, latest_level["week_ending"]), "family": "routing"},
                ],
                "detail": "%d period%s" % (periods, "" if periods == 1 else "s"),
            }
        )
    return {
        "title": "Detours: what the longer or riskier way costs",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "Per tonne of cargo, the Cape costs an LR2's owner far more freight than the Red Sea premium costs "
                "its charterer; for a VLCC loading in the Gulf, each further week inside adds a period of premium and "
                "a week of lost earnings.",
            ],
            "axis": "Extra cost of carriage, USD a tonne",
            "legend": [
                {"family": "routing", "text": "Extra freight the owner needs: more days, more fuel, or days waiting"},
                {"family": "war", "text": "War risk premium, the charterer's, at cost"},
            ],
            "desc": "Each bar is what a tonne of cargo costs more than on the base routing: the freight the owner "
            "needs to earn the base TCE (ink) and the charterer's war risk premium at cost (coloured). A premium is "
            "charged for each seven days or part of them inside a listed area; the TC20 owner's own premium, on its "
            "ballast transit of the Red Sea, is inside the Suez TCE the Cape must match; waiting is priced at the TCE "
            "of the latest week, which waiting days forgo.",
            "rows": chart_rows,
            "source": with_retrieval(
                [
                    "Engine output, week to ",
                    word(date_label(st["as_of"]), "as_of"),
                    ": TC20 at the Baltic's lump sum, the Panamax one way at the freight that earns the P4 hire net of "
                    "its commission, TD3C at the Baltic's TCE of the week (",
                    usd(latest_level["tce_usd_day"], "hormuz.latest_tce", "usd_day"),
                    " a day). War risk: Marsh, 22 July 2026, on Xclusiv Shipbrokers' hull values of 7 September 2026. "
                    "Suez and Panama tolls and the crew war bonus have no public figure for these ships and are left "
                    "out; the transfer chain and TD34 are set out under Hormuz, VLCC.",
                ]
            ),
        },
        "suez_tanker": {
            "lead": [
                "Before any toll Suez earns the owner ",
                usd(st["options"][0]["tce_usd_day"], "suez.tce", "usd_day"),
                " a day and the Cape ",
                usd(st["options"][1]["tce_usd_day"], "cape.tce", "usd_day"),
                ". The Red Sea premium is ",
                fig(red["premium_pct"], "percent", "red_sea.premium_pct", suffix=" percent"),
                " of a ",
                usd_m(_hull("LR2-115"), "suez.hull_value_usd", "usd_m_0"),
                " hull a transit, ",
                usd(red["per_transit_usd"], "red_sea.per_transit_usd"),
                ": the charterer pays it on the laden transit, as it pays the Gulf's premium on both routings "
                "(Platts, 8 December 2025), and the owner on the ballast one, its approach to the next loading, "
                "which a charterer pays only if its charter says so (Gard, 21 March 2026), so it comes off the Suez "
                "TCE. Suez stays the better voyage for the owner until its tolls for the ",
                fig(st["break_even_suez_transits"], "count", "break_even_suez_transits"),
                " transits together pass ",
                usd_m(st["break_even_suez_toll_usd"], "break_even_suez_toll_usd"),
                ", about ",
                usd_m(
                    st["break_even_suez_toll_usd"] / st["break_even_suez_transits"],
                    "break_even_suez_toll_per_transit_usd",
                ),
                " a transit; the Suez Canal Authority puts the toll of a one million barrel crude tanker at about USD "
                "500,000 a transit. A Jubail loading is Saudi linked, and from 24 July 2026 Lloyd's insurers excluded "
                "Saudi linked ships from war risk cover (Windward, 30 July 2026), so cover at the quoted rate may not "
                "be available.",
            ],
        },
        "suez_dry": {
            "lead": [
                "P4 pays a Panamax ",
                usd(sd["p4_hire_usd_day"], "p4_hire_usd_day", "usd_day"),
                " a day for a trip from the Far East to the Skaw-Gibraltar range, ",
                usd(sd["target_tce_usd_day"], "target_tce_usd_day", "usd_day"),
                " after its ",
                fig(sd["p4_commission_pct"], "percent_0", "p4_commission_pct", suffix=" percent"),
                " commission. To earn as much one way, delivered at Qingdao with 66,000 t and redelivered at "
                "Rotterdam, a voyage needs ",
                usd(dry["Suez"]["freight_for_target_usd_t"], "suez.freight", "usd_t"),
                " a tonne by Suez, ",
                usd(dry["Panama"]["freight_for_target_usd_t"], "panama.freight", "usd_t"),
                " by Panama and ",
                usd(dry["Cape of Good Hope"]["freight_for_target_usd_t"], "cape.freight", "usd_t"),
                " round the Cape, before port time, port charges and tolls; by Suez its charterer also pays the Red "
                "Sea premium, ",
                usd(dry["Suez"]["charterer_war_risk_usd_t"], "suez.premium_t", "usd_t"),
                " a tonne. At the Cape's freight, Suez can spend ",
                usd(dry["Suez"]["toll_and_waiting_budget_usd"], "suez.budget"),
                " on its toll and waiting, ",
                fig(dry["Suez"]["waiting_days_budget"], "days", "suez.waiting_days", suffix=" days"),
                " of P4 hire after commission before waiting fuel, and Panama ",
                usd(dry["Panama"]["toll_and_waiting_budget_usd"], "panama.budget"),
                " (",
                fig(dry["Panama"]["waiting_days_budget"], "days", "panama.waiting_days", suffix=" days"),
                "). %s: on its own that wait makes the Cape the better voyage." % _panama_wait(),
            ],
        },
        "hormuz": {
            "lead": [
                "A ",
                fig(marsh["low"], "percent", "hormuz.premium", suffix=" percent"),
                " premium on a ",
                usd_m(hz["hull_value_usd"], "hormuz.hull_value_usd", "usd_m_0"),
                " VLCC is ",
                usd_m(scen["war_low"]["war_risk_usd"], "hormuz.war_low.cost"),
                " for each seven days, or part of them, inside the Gulf: the ",
                fig(scen["war_low"]["days_inside_gulf"], "days", "hormuz.days_inside", suffix=" days"),
                " a TD3C voyage spends there make one period, ",
                usd(scen["war_low"]["charterer_war_risk_usd_t"], "hormuz.war_low.per_tonne", "usd_t"),
                " a tonne for the charterer whatever the market. Each further seven days of waiting adds a period of "
                "premium and costs the owner the TCE it forgoes: 10 days of waiting make ",
                fig(scen["wait_10"]["periods"], "count", "hormuz.wait_10.periods", suffix=" periods"),
                ", adding ",
                usd(
                    scen["wait_10"]["charterer_war_risk_usd_t"] - scen["war_low"]["charterer_war_risk_usd_t"],
                    "hormuz.wait_10.premium_t",
                    "usd_t",
                ),
                " a tonne to the first period's ",
                usd(scen["war_low"]["charterer_war_risk_usd_t"], "hormuz.war_low.per_tonne_again", "usd_t"),
                ", and ",
                usd(owner("wait_10", latest_level["week_ending"]), "hormuz.wait_10.latest", "usd_t"),
                " of freight at the latest week's TCE (",
                usd(owner("wait_10", closure["week_ending"]), "hormuz.wait_10.closure", "usd_t"),
                " at the closure week's).",
            ],
            "chain": [
                "Loading off Fujairah splits the voyage in two. A shuttle carries the cargo through the strait, "
                "reported at USD %g to %g a barrel (The Wall Street Journal via ChosunBiz, 21 September 2026), about "
                % (shuttle["bbl_low"], shuttle["bbl_high"]),
                usd(shuttle["bbl_low_t"], "shuttle.bbl_low_t", "usd_t"),
                " to ",
                usd(shuttle["bbl_high_t"], "shuttle.bbl_high_t", "usd_t"),
                " a tonne at %s million barrels a cargo, and at " % ("%g" % (shuttle["barrels"] / 1e6)),
                usd_m(shuttle["transit_usd"], "shuttle.transit_usd", "usd_m_0"),
                " a transit (Windward, 12 October 2026), ",
                usd(shuttle["transit_t"], "shuttle.transit_t", "usd_t"),
                " a tonne; the transfer's own cost and days have no public figure. The export VLCC then sails ",
                fig(abs(chains["sts"]["extra_days"]), "days", "chains.sts.days_saved", suffix=" fewer days"),
                " than from Ras Tanura, worth ",
                usd(
                    chains["td3c_freight_at_own_tce_usd_t"] - chains["sts"]["freight_at_td3c_tce_usd_t"],
                    "chains.sts.saving_t",
                    "usd_t",
                ),
                " a tonne at TD3C's TCE. TD34 loads outside the strait: the Baltic assessed it at ",
                usd(chains["td34"]["published_tce_usd_day"], "td34.tce", "usd_day"),
                " a day against TD3C's ",
                usd(hz["td34_vs_td3c_published"]["td3c_tce_usd_day"], "td3c.tce", "usd_day"),
                " in the week to ",
                word(date_label(hz["as_of"]), "hormuz.as_of"),
                ", which puts its freight at ",
                usd(chains["td34"]["freight_at_own_tce_usd_t"], "td34.freight_t", "usd_t"),
                " a tonne against TD3C's ",
                usd(chains["td3c_freight_at_own_tce_usd_t"], "td3c.freight_t", "usd_t"),
                ", for a cargo already in the Gulf of Oman.",
            ],
            "shuttle_range": "%s to %s" % (f"{shuttle['bbl_low_t']:,.2f}", f"{shuttle['bbl_high_t']:,.2f}"),
            "table_caption": "TD3C, Ras Tanura to Ningbo, bunkers of the week to %s; the premium is the charterer's, "
            "and each column of the owner's extra freight keeps the Baltic's TD3C TCE of its week (%s). The last two "
            "rows load outside the strait, where no dated premium was found: the export VLCC after a transfer off "
            "Fujairah, with the shuttle through the strait the charterer pays beside it (reported at USD %g to %g a "
            "barrel), and TD34 from Mina Al Fahal; the transfer's own days and cost have no public figure."
            % (
                date_label(hz["as_of"]),
                "; ".join("USD %s a day %s" % (f"{lvl['tce_usd_day']:,.0f}", lvl["label"]) for lvl in hz["levels"]),
                shuttle["bbl_low"],
                shuttle["bbl_high"],
            ),
            "levels_words": {lvl["week_ending"]: lvl["label"] for lvl in hz["levels"]},
            "levels_short": {
                lvl["week_ending"]: {
                    "before the war": "pre-war",
                    "the week of the closure": "closure week",
                    "the latest week": "latest week",
                }[lvl["label"]]
                for lvl in hz["levels"]
            },
        },
        "sections": [
            {
                "id": "suez",
                "name": "Suez or the Cape, LR2",
                "summary": ["TC20 from Jubail to Rotterdam: days, distance, TCE, premiums and the toll Suez can bear."],
            },
            {
                "id": "dry",
                "name": "Asia to Europe, Panamax",
                "summary": [
                    "Suez, Panama or the Cape for a Panamax one way: the freight each needs and what it can spend."
                ],
            },
            {
                "id": "hormuz",
                "name": "Hormuz, VLCC",
                "summary": ["War risk and waiting at three dated TCE levels, the transfer chain and TD34."],
            },
            {
                "id": "method",
                "name": "Method",
                "summary": ["How a detour and a premium are priced, and the dated events."],
            },
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["Who pays, where the ship waits, the listed area's edge, and what each case leaves out."],
            },
            {"id": "data", "name": "Data", "summary": ["The scenarios as a download."]},
        ],
        "method": [
            "A detour is priced with the same engine at the same week's bunkers: the extra days and tonne miles "
            "against the base routing, and the freight at which the detour earns the base routing's TCE. On the usual "
            "spot terms a war risk premium is the charterer's (Platts, 8 December 2025), reimbursed to the owner at "
            "cost under VOYWAR 2013 (Gard, 21 March 2026), and the Baltic's TCE descriptions name none: it is shown "
            "at cost per tonne of cargo beside the owner's freight. A passage on the ballast leg, the approach to the "
            "next loading, is the owner's unless a charter says otherwise (Gard), so it comes off the owner's TCE. "
            "Waiting is priced as days the owner loses at the week's TCE, so it moves the freight the owner needs and "
            "depends on the market's level; waiting at a load port after notice of readiness would count as laytime "
            "and then demurrage, which the charterer pays at the charter's rate and the study does not price.",
            "An additional premium is a percentage of hull value charged on entering a listed area, for up to seven "
            "days there (Platts, 1 April 2026); each further seven days inside, or part of them, is another period, "
            "counted from the days the voyage spends in the Gulf west of the Strait of Hormuz, the load port's days "
            "and any waiting there included. Each Red Sea passage is one period.",
        ],
        "assumptions": [
            "The ship waits at its load port, inside the Gulf, so its waiting days count toward the premium's "
            "periods; a ship that waits outside before entering would pay one period.",
            "The listed area is taken to end at the Strait of Hormuz, so the count is a lower bound. The Joint War "
            "Committee widened its Persian Gulf and Arabian Sea listed areas in 2026 and cover periods have shortened "
            "since February (Platts, 5 October 2026); the boundary text was not found. To 58 degrees east a TD3C "
            "voyage would spend about %s days inside and pay two periods with no waiting, and a Gulf of Oman loading "
            "(the Fujairah transfer, TD34 at Mina Al Fahal) may pay a premium for which no dated rate was found."
            % ("%.1f" % hz["days_inside_to_58e"]),
            "Hull values are Xclusiv Shipbrokers' five year old values of 7 September 2026; the LR1 and the Handy "
            "tanker have none. The premium rates are the latest dated ones found: Marsh, 22 July 2026, for the Gulf "
            "and for Bab el Mandeb.",
            "The Panamax runs one way like the P4 trip, delivered at Qingdao and redelivered at Rotterdam, with no "
            "ballast leg and no port time; P4's own 55 to 70 days run from delivery and include port time and any "
            "positioning to the loading port after delivery, so its freights are floors.",
            "Left out everywhere: port charges, the Suez and Panama tolls, time at a canal on the dry routings, and "
            "the crew war bonus; on the transfer chain the transfer's own cost and days, and the shuttle, which is "
            "set beside the export voyage, not in it.",
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

    intra_class = VESSEL_CLASS[baltic.ROUTES["TC23"].vessel]
    takeaway = [
        "In 2026, with every tonne covered, a %s between two EEA ports pays " % intra_class,
        usd(year(intra, 2026)["cost_usd"], "TC23.2026.cost_usd"),
        " of allowances, ",
        fig(year(intra, 2026)["share_of_voyage_costs"] * 100.0, "percent", "TC23.2026.share", suffix=" percent"),
        " of its sourced voyage costs, a Suezmax from West Africa to Rotterdam ",
        usd(year(into, 2026)["cost_usd"], "TD20.2026.cost_usd"),
        " for half its emissions at sea and all of them at Rotterdam, and a VLCC from the Gulf to China nothing; in "
        "2024 the same voyages paid ",
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
                " from the intra-EEA %s's TCE and " % intra_class,
                usd(year(into, 2026)["per_day_usd"], "TD20.2026.per_day_usd", "usd_day"),
                " from the inbound Suezmax's.",
            ],
            "axis": "EU ETS cost, USD a day of the voyage",
            "none": "None: no EEA port",
            "desc": "Three voyages by three years of the phase in: the cost of the allowances surrendered for the "
            "voyage's covered emissions, over its days. The voyage outside the EEA has none in any year.",
            "source": with_retrieval(
                [
                    "Engine output at EUR ",
                    fig(c["eua_eur_t"], "eur_t", "eua_eur_t"),
                    " an allowance (%s) and " % c["eua_source"],
                    fig(c["usd_per_eur"], "usd_per_eur", "usd_per_eur"),
                    " dollars per euro (Federal Reserve H.10, %s average); bunkers at the %s common market."
                    % (c["market"], c["market"]),
                ]
            ),
        },
        "kinds": {
            "TC23": "%s, Amsterdam to Le Havre (TC23): between two EEA ports, 100 percent" % intra_class.capitalize(),
            "TD20": "Suezmax, Bonny to Rotterdam (TD20): into the EEA, 50 percent",
            "TD3C": "VLCC, Ras Tanura to Ningbo (TD3C): outside the EEA",
        },
        "time_charter": {
            "title": "On a time charter the charterer provides and pays for the allowances",
            "lead": [
                "Under BIMCO's ETS Allowances Clause for time charter parties (2022) the charterer provides and pays "
                "for the allowances for the ship's emissions during the charter and transfers them to the owner, who "
                "as the shipping company surrenders them (Directive 2003/87/EC, Article 3gc): on the S4A trip the "
                "charterer bears ",
                usd(tc["trip_ets_usd"], "time_charter.trip_ets_usd"),
                " for the trip, and the owner ",
                usd(tc["owner_ets_usd"], "time_charter.owner_ets_usd"),
                " for the ballast leg out of the EEA after redelivery.",
            ],
            "party_head": "Party",
            "legs_head": "What it bears",
            "charterer": "Charterer",
            "charterer_legs": "The trip, US Gulf to the Skaw-Passero range, half its emissions at sea into the EEA "
            "and all of them in port",
            "owner": "Owner",
            "owner_legs": "The ballast leg back to the US Gulf after redelivery, half its emissions at sea out of the "
            "EEA",
            "table_caption": "S4A, 2026: allowances surrendered for 100 percent of covered emissions, methane and "
            "nitrous oxide included, at EUR {eua} a tonne and {fx} dollars per euro.",
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
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["The allowance price and dollar rate, the fuel and its class, the warming potentials."],
            },
            {"id": "data", "name": "Data", "summary": ["The ETS costs and the monthly allowance price as downloads."]},
        ],
        "assumptions": [
            [
                "Allowances at EUR ",
                fig(c["eua_eur_t"], "eur_t", "eua_eur_t"),
                " a tonne (%s) and " % c["eua_source"],
                fig(c["usd_per_eur"], "usd_per_eur", "usd_per_eur"),
                " dollars per euro (Federal Reserve H.10, %s average), held for every year so that only the phase "
                "in moves the cost." % c["market"],
            ],
            [
                "Fuel at the %s common market, each voyage on its Baltic ship's speeds and consumptions: MGO inside "
                "emission control areas and at berth in EU ports, VLSFO elsewhere. VLSFO is classed by its ISO 8217 "
                "grade (IMO resolution MEPC.391(81)): HFO for RME, RMG and RMK, the default here since most VLSFO is "
                "tested against RMG 380, and LFO (3.151 t of CO2 a tonne) for RMA, RMB and RMD." % c["market"]
            ],
            [
                "Methane and nitrous oxide at the warming potentials of the ETS and MRV, 28 and 265 (Delegated "
                "Regulation (EU) 2020/1044); FuelEU uses the Renewable Energy Directive's 25 and 298."
            ],
            [
                "A voyage's share of its sourced voyage costs leaves out the port charges at its ports, which have no "
                "public figure, so with them the share would be lower."
            ],
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
            "3.114 t of CO2 per t of HFO, 3.151 for LFO and 3.206 for MGO, with VLSFO classed by its ISO 8217 grade "
            "(HFO by default, LFO for RMA to RMD). From 2026 methane and nitrous oxide count, at 0.00005 and 0.00018 g "
            "per g of fuel times warming "
            "potentials of 28 and 265.",
            "Covered emissions follow Article 3ga of the ETS Directive: 100 percent of a voyage between two EEA ports "
            "and of the emissions within a port of call in the EEA, 50 percent of a voyage into or out of the EEA. "
            "Allowances are surrendered for 40 percent of 2024 emissions, 70 percent of 2025 and 100 percent from "
            "2026 (Article 3gb); methane and nitrous oxide count from 2026 (Annex I).",
        ],
    }


# --------------------------------------------------------------------------
# Paper
# --------------------------------------------------------------------------


def _months_words(months: Sequence[Mapping[str, Any]]) -> str:
    """'July 29.0 days at 36,232, August 31.0 at 36,828' from a strip's month weights and FFAs."""
    return ", ".join(
        "%s %.1f%s at %s"
        % (date_label(m["month"]).split()[0], m["days"], " days" if i == 0 else "", f"{m['usd_day']:,.0f}")
        for i, m in enumerate(months)
    )


def _basis_range(low: float, high: float, field: str) -> Segments:
    """'between USD 419 and 4,060 above', a basis given on two prints of a curve."""
    if low >= 0 or high < 0:
        return [
            "between ",
            usd(abs(low if low >= 0 else high), field + ".0", "usd_day"),
            " and ",
            fig(abs(high if low >= 0 else low), "usd_day", field + ".1"),
            " %s" % ("above" if low >= 0 else "below"),
        ]
    return [
        "between ",
        usd(abs(low), field + ".0", "usd_day"),
        " below and ",
        fig(high, "usd_day", field + ".1"),
        " above",
    ]


def paper_page(p: Mapping[str, Any]) -> dict[str, Any]:
    rows = p["capesize"]
    by = {(r["date"], r["route"]): r for r in rows}
    c3, c5 = by[("2026-07-03", "C3")], by[("2026-07-03", "C5")]
    c3_oct = by[("2026-10-23", "C3")]
    fixture = p["c5_fixture"]
    basis = anchors.capesize_basis_2026_07_03()
    keep = 1.0 - c3["commission_pct"] / 100.0

    def side(value: float) -> str:
        return "below" if value < 0 else "above"

    takeaway = [
        "In the week to 3 July 2026 a C3 cargo at ",
        usd(c3["freight_usd_t"], "C3.freight_usd_t", "usd_t"),
        " a tonne earned ",
        usd(c3["physical_tce_gross_usd_day"], "C3.physical_tce_gross_usd_day", "usd_day"),
        " a day grossed up by its %g percent commission, " % c3["commission_pct"],
        *_basis_range(*c3["basis_range_usd_day"], "C3.basis_range"),
        " the 5TC FFA over its days on the two prints of the 29 June curve, and a C5 cargo ",
        *_basis_range(*c5["basis_range_usd_day"], "C5.basis_range"),
        " it.",
    ]
    curves = {c["id"]: c for c in p["curves"]}
    dated = sorted({r["ffa"]["dated"] for r in rows})
    return {
        "hedge_columns": [
            {"text": "Route and week", "short": "route"},
            {"text": "Freight, USD a tonne", "short": "freight"},
            {"text": "Net TCE, USD a day", "short": "net TCE"},
            {"text": "Gross TCE, USD a day", "short": "gross TCE"},
            {"text": "FFA months, days in each", "short": "FFA months", "words": True},
            {"text": "FFA, USD a day", "short": "FFA"},
            {"text": "Basis, USD a day", "short": "basis"},
            {"text": "Basis, other print, USD a day", "short": "other print"},
            {"text": "Freight for the FFA, USD a tonne", "short": "freight for the FFA"},
            {"text": "Spot 5TC, USD a day", "short": "spot"},
            {"text": "Timing basis, USD a day", "short": "timing basis"},
            {"text": "Hedge, 5TC (182) days", "short": "hedge"},
            {"text": "Net hedge, days", "short": "net hedge"},
        ],
        "title": "Paper: the physical fixture against the FFA",
        "takeaway": takeaway,
        "chart": {
            "title": [
                "Grossed up by their commission, the C5 voyages earn well above the 5TC FFA over their days in both "
                "weeks; C3 sat ",
                *_basis_range(*c3["basis_range_usd_day"], "C3.chart.basis_range"),
                " it in July, depending on which print of the 29 June curve is read, and ",
                usd(abs(c3_oct["basis_usd_day"]), "C3.october.basis_usd_day", "usd_day"),
                " a day %s it in October." % side(c3_oct["basis_usd_day"]),
            ],
            "axis": "USD a day",
            "desc": "For each anchor week and route, the physical voyage TCE grossed up by its commission (ink dot), "
            "the 5TC FFA over the voyage's days (ringed dot) and the spot 5TC on the fixture date for the 182,000 t "
            "ship (muted dot); the rule between the first two is the basis, its value written above it.",
            "basis_label": "Basis {basis}",
            "legend": [
                {
                    "kind": "ink",
                    "text": "Physical voyage TCE, grossed up by the %g percent commission" % c3["commission_pct"],
                },
                {"kind": "ring", "text": "5TC FFA over the voyage's days"},
                {"kind": "muted", "text": "Spot Capesize 5TC on the fixture date"},
            ],
            "source": with_retrieval(
                [
                    "Engine output for C3 and C5 at the route rates and bunker tables of the fixture dates, bunkers "
                    "at Singapore; FFA: Banchero Costa, Dry bulk FFA assessments, curves of %s; spot 5TC: Signal "
                    "Group and Banchero Costa, the July figure on the 180,000 t basis and here on the 182,000 t."
                    % " and ".join(date_label(d) for d in dated)
                ]
            ),
        },
        "fixture": {
            "lead": [
                "A C5 cargo fixed on %s at " % date_label(fixture["date"]),
                usd(fixture["fixture_usd_t"], "c5_fixture.fixture_usd_t", "usd_t"),
                " a tonne (loading %s) matched the index that day as the report's narrative gives it, "
                % fixture["laycan"],
                usd(fixture["route_on_day_usd_t"], "c5_fixture.route_on_day_usd_t", "usd_t"),
                ": no basis. The report's table runs ",
                usd(fixture["series_gap_usd_t"], "c5_fixture.series_gap_usd_t", "usd_t"),
                " above its narrative at the next close (",
                usd(fixture["index_next_day_usd_t"], "c5_fixture.index_next_day_usd_t", "usd_t"),
                " against ",
                usd(fixture["narrative_next_day_usd_t"], "c5_fixture.narrative_next_day_usd_t", "usd_t"),
                " on %s), so on the table's series the fixture sat " % date_label(fixture["next_day"]),
                usd(abs(fixture["basis_table_series_usd_t"]), "c5_fixture.basis_table_series_usd_t", "usd_t"),
                " a tonne %s the index, about " % ("under" if fixture["basis_table_series_usd_day"] < 0 else "over"),
                usd(abs(fixture["basis_table_series_usd_day"]), "c5_fixture.basis_table_series_usd_day", "usd_day"),
                " a day.",
            ],
            "table_caption": "A fixture against the index it would be hedged with, on the fixture's day and the "
            "next; TCEs at the bunker table of %s." % date_label(fixture["next_day"]),
        },
        "route_ffa": {
            "title": "A route FFA in dollars a tonne, converted by the engine",
            "lead": "No dated public C3 or C5 FFA quote in dollars a tonne was found, so the box starts empty. Type "
            "one to price an anchor voyage at it with the same engine: its TCE net of commission, grossed up, against "
            "the 5TC (182) FFA over the same days.",
            "voyage_label": "Voyage",
            "ffa_label": "Route FFA, USD a tonne",
            "empty": "Type a route FFA to convert it into a TCE.",
            "invalid": "Enter a number.",
            "result": "At {ffa} a tonne the voyage earns {net} a day net of commission, {gross} grossed up: {basis} "
            "{side} the 5TC (182) FFA of {strip} over its days.",
        },
        "td3c": {
            "lead": [
                "Tanker FFAs settle in dollars a tonne on the monthly average of the route's assessments, and no "
                "public TD3C FFA quote in dollars a tonne was found, so no tanker basis is computed. Drewry's %s "
                "conversion of the TD3C FFA into a TCE put the second quarter at about " % p["td3c"]["published"],
                usd(p["td3c"]["ffa_tce_q2_usd_day"], "td3c.ffa_tce_q2_usd_day", "usd_day"),
                " a day; the Baltic's TD3C TCE was ",
                usd(p["td3c"]["physical_q2"][0]["tce_usd_day"], "td3c.physical_q2.0", "usd_day"),
                " in the week to %s and " % date_label(p["td3c"]["physical_q2"][0]["week_ending"]),
                usd(p["td3c"]["physical_q2"][1]["tce_usd_day"], "td3c.physical_q2.1", "usd_day"),
                " in the week to %s, after the Strait of Hormuz closed on 2 March."
                % date_label(p["td3c"]["physical_q2"][1]["week_ending"]),
            ],
        },
        "sections": [
            {
                "id": "hedge",
                "name": "Hedge and basis",
                "summary": ["Hedge sizes by month, the basis and the freight that would earn the FFA, week by week."],
            },
            {
                "id": "tankers",
                "name": "Tankers",
                "summary": ["TD3C paper and physical in the second quarter of 2026."],
            },
            {
                "id": "method",
                "name": "Method",
                "summary": ["How each FFA settles, and how a voyage is set against it."],
            },
            {
                "id": "assumptions",
                "name": "Assumptions",
                "summary": ["Which curve and which spot figure each week takes, and the bunker hub."],
            },
            {"id": "data", "name": "Data", "summary": ["The FFA curves as printed, by segment and month."]},
        ],
        "method": [
            "A time charter FFA such as the Capesize 5TC settles on the arithmetic average of the Baltic's daily 5TC "
            "assessments in the contract month, in dollars a day; a voyage route FFA such as C3 or C5 on the "
            "average of the route's daily assessments, in dollars a tonne (EEX contract specifications, release "
            "047a, July 2026). The 182,000 t ship is hedged in 5TC (182) days, EEX's C5TM; EEX's CPTM settles on "
            "the 180,000 t basket, which the guide derives as the 182,000 t basket less USD %s a day (page 77), a "
            "fixed difference a CPTM hedge of this ship would carry. Tanker FFAs on ICE settle in dollars a tonne "
            "on the average of the month's assessments: the Baltic's for TD3C, TD20, TD22, TD25, TD34, TC2, TC14, "
            "TC20 and TC23, Platts' for TC5 and for the 75,000 t Arab Gulf to Japan contract, the TC1 size (ICE "
            "Futures Europe rulebook, section TTT), so a TC1 or TC5 cargo priced off the Baltic and hedged on ICE "
            "carries the difference between two assessors." % f"{baltic.C5TC_180_DIFFERENTIAL:,.0f}",
            "Time charter assessments, and the FFAs that settle on them, are gross daily hire: each 5TC route is "
            "assessed at 5 percent total commission (Guide to Market Benchmarks v%s, pages 77 and 78). A voyage TCE "
            "is net of the same commission, so it is grossed up by it before it is set against the 5TC, as the guide "
            "does with a voyage's time charter equivalent (section 7.4.3). The basis is that grossed up TCE less the "
            "FFA; the freight that earns the FFA is the one whose net TCE equals the FFA less commission; the timing "
            "basis is the FFA less the spot 5TC on the fixture date, both gross." % baltic.GMB["version"],
            "The FFA is the strip over the voyage's days: each day from the fixture date, ballast leg first, is "
            "priced at the FFA of its month on the latest curve that could be traded on the fixture date. The hedge "
            "is 5TC days equal to the voyage's days, or route FFA tonnes equal to its cargo; the owner keeps %d "
            "percent of what the index pays, so the voyage's days times that share hedge its net earnings exactly."
            % round(keep * 100),
        ],
        "assumptions": [
            [
                "The spot 5TC of 3 July 2026, USD %s, is the 180,000 t basis: the BCI of %s and the BDI of %s "
                "printed that day fit a 182,000 t basket of %s (that figure plus the guide's %s, page 77), and not "
                "%s itself, which would give a BCI of %s. The study prices the 182,000 t ship and sets it against "
                "%s."
                % (
                    f"{basis['printed_usd_day']:,.0f}",
                    f"{basis['bci_published']:,.0f}",
                    f"{basis['bdi_published']:,.0f}",
                    f"{basis['basket_182_if_180_usd_day']:,.0f}",
                    f"{baltic.C5TC_180_DIFFERENTIAL:,.0f}",
                    f"{basis['printed_usd_day']:,.0f}",
                    f"{basis['bci_if_182']:,.0f}",
                    f"{basis['basket_182_if_180_usd_day']:,.0f}",
                )
            ],
            [curves["wk26_2026"]["date_note"]],
            [curves["wk27_2026"]["date_note"]],
            [curves["wk43_2026"]["date_note"]],
            [
                "The physical TCEs carry a 5 percent weather margin on steaming time, the study's choice for dry "
                "routes: the guide sets it for its tanker TCEs (Appendix 3) and leaves a dry route's allowances to its "
                "panellists (section 7.4.2). Without it the grossed up TCEs would be ",
                usd(
                    min(r["no_margin_tce_gross_usd_day"] - r["physical_tce_gross_usd_day"] for r in rows),
                    "no_margin.gain_low",
                    "usd_day",
                ),
                " to ",
                fig(
                    max(r["no_margin_tce_gross_usd_day"] - r["physical_tce_gross_usd_day"] for r in rows),
                    "usd_day",
                    "no_margin.gain_high",
                ),
                " a day higher, and C3's basis ",
                fig(c3["no_margin_basis_usd_day"], "usd_day", "C3.no_margin_basis", signed=True),
                " in July and ",
                fig(c3_oct["no_margin_basis_usd_day"], "usd_day", "C3.october.no_margin_basis", signed=True),
                " in October.",
            ],
            [
                "C3 is priced at Singapore bunkers, about 270 nm off its ballast leg, where a ship leaving China "
                "takes orders. At Rotterdam's, the hub with public prices nearest Tubarao, it would earn ",
                usd(c3["rule_hub_tce_usd_day"] - c3["physical_tce_usd_day"], "C3.rule_hub_gain", "usd_day"),
                " a day more in the week to 3 July and ",
                usd(
                    c3_oct["rule_hub_tce_usd_day"] - c3_oct["physical_tce_usd_day"],
                    "C3.october.rule_hub_gain",
                    "usd_day",
                ),
                " more in the week to 23 October, and sit ",
                usd(c3["rule_hub_basis_usd_day"], "C3.rule_hub_basis", "usd_day"),
                " and ",
                usd(c3_oct["rule_hub_basis_usd_day"], "C3.october.rule_hub_basis", "usd_day"),
                " a day above the FFA.",
            ],
            [
                "The physical TCEs leave out port charges, loading time and fuel burnt in port, so they read high "
                "against a time charter index, whose hire carries none of them."
            ],
        ],
        "months_words": {"%s %s" % (r["route"], r["date"]): _months_words(r["ffa"]["months"]) for r in rows},
        "hedge_caption": "Each anchor week: the physical TCE net of commission and grossed up by it; the 5TC (182) FFA "
        "over the voyage's days on the print used, with its months; the basis, the grossed up TCE less the FFA, and "
        "the same on the curve's other print; the freight whose grossed up TCE equals the FFA; the spot 5TC on the "
        "fixture date, 182,000 t basis; the timing basis, the FFA less the spot; the hedge in days of 5TC (182), EEX "
        "C5TM, and the days that hedge the net earnings.",
    }


# --------------------------------------------------------------------------
# Method and data
# --------------------------------------------------------------------------


def method_page(validation: Mapping[str, Any], route_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_day = {r["route"]: r["excluded_block_per_day_usd"] for r in route_rows}
    summary = anchors.lump_sum_summary()
    implied = anchors.implied_summary()
    flats = anchors.implied_flat_rates()
    cross = anchors.broker_cross_check()
    reproducible = summary["rows"]
    stale = summary["stale"]
    dry = validation["dry"]
    july = [r for r in dry if r["benchmark_basis"] == "180"]
    takeaway = [
        "With bunker prices first printed in the same week the engine reads ",
        fig(summary["fresh_error"][0] * 100.0, "error_percent", "validation.min_error"),
        " to ",
        fig(summary["fresh_error"][1] * 100.0, "error_percent", "validation.max_error", suffix=" percent"),
        " above the Baltic's own TCE for TD22 and TC20, the two routes it can price without a licensed flat rate; "
        "the chart sets out every week, its exceptions and TD3C, and Validation every other check.",
    ]
    chart_title = [
        "The engine reads ",
        fig(summary["usual_error"][0] * 100.0, "error_percent", "chart.min_error"),
        " to ",
        fig(summary["usual_error"][1] * 100.0, "error_percent", "chart.max_error", suffix=" percent"),
        " above the Baltic's TD22 and TC20 TCEs in the weeks priced with bunker prices up to a week old, except the "
        "weeks to ",
        *_join_words(
            [word(date_label(r["week_ending"]), "chart.exception.%d" % i) for i, r in enumerate(summary["exception"])]
        ),
        " (",
        *_join_words(
            [
                fig(r["error"] * 100.0, "error_percent", "chart.exception.%d.error" % i)
                for i, r in enumerate(summary["exception"])
            ]
        ),
        " percent above)",
    ]
    for i, r in enumerate(stale):
        chart_title += [
            "; the week to ",
            word(date_label(r["week_ending"]), "chart.stale.%d" % i),
            ", priced with Houston prices first printed on ",
            word(date_label(r["bunkers_first_printed"]), "chart.stale.%d.first" % i),
            ", reads ",
            fig(abs(r["error"]) * 100.0, "error_percent", "chart.stale.%d.error" % i, suffix=" percent"),
            " below" if r["error"] < 0 else " above",
        ]
    inside = all(implied["error"][0] <= r["error"] <= implied["error"][1] for r in implied["exception"])
    chart_title += [
        "; TD3C, at the flat rate Platts' January pairs imply, reads ",
        fig(implied["error"][0] * 100.0, "error_percent", "chart.implied.min", signed=True),
        " to ",
        fig(implied["error"][1] * 100.0, "error_percent", "chart.implied.max", signed=True, suffix=" percent"),
        ", its two weeks after the closure within that range" if inside and implied["exception"] else "",
        ".",
    ]
    dry_caption = [
        "Dry route rates priced by the engine against the time charter average of the same day. The averages are "
        "gross hire and the TCEs net of the 5 percent commission, so each TCE is grossed up by the commission before "
        "the gap is taken (Guide to Market Benchmarks section 7.4.3), against the average for the 182,000 t ship the "
        "study prices",
    ]
    if july:
        r = july[0]
        dry_caption += [
            ": the ",
            word(date_label(r["date"]), "dry.july.date"),
            " average of ",
            usd(r["benchmark_usd_day"], "dry.july.printed", "usd_day"),
            " is the 180,000 t basis, so it is set against ",
            usd(r["benchmark_182_usd_day"], "dry.july.like_for_like", "usd_day"),
        ]
    dry_caption.append(
        ". The gap is what the TCEs leave out (port charges, loading time and fuel burnt in port, all of which would "
        "lower them) and one round voyage set against a basket of time charter routes; C3 is priced at Singapore, "
        "about 270 nm off its ballast leg, and the Paper view gives its sensitivity to Rotterdam's prices."
    )
    early_march_caption = (
        "Early March 2026: the Middle East Gulf to China VLCC rates reported in dollars a tonne, priced as TD3C. "
        "Platts printed USD 62.07 on 2 March; the USD 89 a tonne reported on 3 March names no primary assessment and "
        "is not Platts', whose year to date rise to USD 62.07 was 461 percent. The Baltic's TD3C TCE was USD 209,550 "
        "a day in the week to 27 February and USD 485,959 in the week to 6 March. The war risk column is a scenario, "
        "not the Baltic's basis: the early March premium of 2.5 percent of a USD 120 million hull for one seven day "
        "period inside the Gulf, in the owner's costs as if the freight carried it."
    )
    return {
        "title": "Method and data",
        "takeaway": takeaway,
        "dry_caption": dry_caption,
        "dry_benchmark_head": "For the %s t ship priced, USD a day" % f"{baltic.VESSELS['BCI182'].dwt_t:,.0f}",
        "early_march_caption": early_march_caption,
        "chart": {
            "title": chart_title,
            "axis": "Engine above the Baltic, percent",
            "desc": "One dot a week for TD22 and TC20, the two tanker routes whose Baltic rate is a lump sum and so "
            "converts to dollars without a licensed flat rate, and below them TD3C, whose Worldscale rate is priced at "
            "the flat rate Platts' January pairs imply. An ink dot is priced with bunker prices first printed that "
            "week, a ringed dot with prices printed up to a week before, a muted dot with older prices a broker "
            "reprinted.",
            "groups": {
                "lump_sum": "TD22 and TC20, lump sums in dollars",
                "implied": "TD3C at the flat rate Platts' January pairs imply, USD %.2f a tonne"
                % flats["TD3C"]["flat_usd_t"],
            },
            "legend": [
                {"kind": "ink", "text": "Bunker prices first printed that week"},
                {"kind": "ring", "text": "Printed up to a week before"},
                {"kind": "muted", "text": "Older prices, reprinted"},
            ],
            "source": with_retrieval(
                [
                    "Baltic Exchange weekly tanker reports, weeks to ",
                    word(date_label(min(r["week_ending"] for r in reproducible)), "chart.first_week"),
                    " to ",
                    word(date_label(max(r["week_ending"] for r in reproducible)), "chart.last_week"),
                    ", as republished by Hellenic Shipping News; bunkers: Star Asia Shipbroking weekly tables, a "
                    "reprinted row dated by its first printing; TD3C's flat rate implied by Platts' pairs of 2 and 13 "
                    "January 2026 (Hellenic Shipping News, 17 January 2026); engine output.",
                ]
            ),
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
                "summary": ["The series the figures rest on, with their dates, retrieval and licences."],
            },
            {
                "id": "limitations",
                "name": "Limitations",
                "summary": ["What the study cannot do, and the sources it could not reach."],
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
            "War risk = premium x hull value x periods + crew bonus, the charterer's unless the fixture puts it "
            "in the freight",
            "Periods in a listed area = days inside / 7, rounded up, at least one for each entry",
            "Freight for a target TCE = (target x voyage days + voyage costs) / (1 - commission share) - other revenue",
            "Best speed = the laden speed on a 0.01 knot grid that maximises the TCE, the ballast leg keeping its gap",
        ],
        "distances_words": "{within} of the {count} distances checked against NGA Pub. 151 fall within 2 percent; "
        "each check, its published legs and its error are set out with the routes:",
        "distances_link": "Routes, Data",
        "limitations_heading": "What the study cannot do",
        "blocked_heading": "Sites that could not be reached when the study was built, and what each would have added",
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
            "USD {:,.0f} a day on C3, USD {:,.0f} on C5 and USD {:,.0f} on TD22 for each USD 100,000 of charges. They "
            "explain only part of the gap to the Baltic's TD22 TCE, which grows with freight.".format(
                per_day["C3"], per_day["C5"], per_day["TD22"]
            ),
            "No public source states a Worldscale flat rate for a study route's ports. Platts' January 2026 pairs "
            "(w53.5 and USD 11.07 a tonne, w93 and USD 19.24) imply USD %.2f a tonne for its Persian Gulf to China "
            "route, whose ports it does not state: the study uses it to check the Baltic's TD3C TCEs of 2026 and "
            "nowhere else. Every other rate in Worldscale points needs the visitor's own flat rate, and those anchors "
            "are recorded, not priced." % flats["TD3C"]["flat_usd_t"],
            "No fully worked public voyage estimate with prices, from a textbook, a professional body or a broker, "
            "could be retrieved: the hosts that hold them refused scripted requests (below). The Baltic's own 2017 "
            "TD3C note, the one worked example found, prints days and tonnes and no prices, so it checks the "
            "engine's days and fuel and not its dollars.",
            "No dated public C3 or C5 route FFA quote in dollars a tonne was found; the Paper view converts one a "
            "visitor types into a TCE with the same engine.",
            "The 5 percent weather margin on dry routes is the study's choice: the guide sets it for its tanker TCEs "
            "and leaves a dry route's allowances to its panellists (section 7.4.2). Without it the Capesize TCEs of "
            "the Paper view would read %.0f to %.0f percent higher."
            % (min(validation["dry_margin"]) * 100.0, max(validation["dry_margin"]) * 100.0),
            "Suez and Panama tolls depend on each ship's own canal tonnage and are left out; the detours report the "
            "toll each routing could bear instead.",
            "Bunker prices are dated public averages or weekly broker tables at four hubs, not the price a ship "
            "actually paid. Two brokers can print very different prices for the same day: for %s Intermodal's Houston "
            "VLSFO, USD %s a tonne, stood %s percent above Star Asia's USD %s, and priced with it the TD22 comparison "
            "moves from %s to %s percent. Star Asia sometimes reprints a week's table unchanged, and after the closure "
            "of Hormuz prices moved faster than a weekly table can follow."
            % (
                date_label(cross["date"]),
                f"{cross['vlsfo_other_usd_t']:,.2f}",
                f"{(cross['vlsfo_other_usd_t'] / cross['vlsfo_study_usd_t'] - 1) * 100:.0f}",
                f"{cross['vlsfo_study_usd_t']:,.0f}",
                f"{cross['error_study'] * 100:.1f}",
                f"{cross['error_other'] * 100:.1f}",
            ),
            "The guide's dry route terms set no time at a canal, so P7 leaves out its Panama transit and any wait; "
            "bulk carriers sail at the fastest speed pair the guide prints, the study's choice where the route names "
            "none.",
            "Each sea route starts at the network's node nearest its port; the stretch to the port is added at Port "
            "Hedland, Jubail and Amsterdam and left out elsewhere (about 21.5 nm a leg at Tubarao).",
            "War risk premiums are the latest dated rates found, from July 2026; the listed area is taken to end at "
            "the Strait of Hormuz, which makes the count of seven day periods a lower bound, and cover for a Saudi "
            "linked ship may not be available at any rate.",
            "FFA levels are dated public assessments, two dry curves whose vessel basis and dates are partly "
            "unstated (the Paper view sets them out); no public tanker FFA quote in dollars a tonne was found.",
            "The Baltic's tanker speeds and consumptions come as two pairs, so the fitted exponent is low and the "
            "best speed often sits at the top of the range searched.",
            "A TCE is an estimate of what a voyage earns at stated inputs, not a forecast, and it is compared with "
            "operating and capital costs, never net of them.",
        ],
        "blocked": [
            "pancanal.com and micanaldepanama.com: the Panama Canal tariff and its toll calculator, which would have "
            "given dated Panama tolls by vessel class.",
            "worldscale.co.uk: the flat rate schedule, which is licensed in any case; a public statement of a 2026 "
            "flat rate for a study route would have made its Worldscale anchors reproducible.",
            "dehst.de: the German auction reports, read instead from the copy the sibling study jkm-ttf-arbitrage "
            "publishes.",
            "ecfr.gov, nauticalcharts.noaa.gov and marinecadastre.gov: the North American ECA coordinates in US "
            "regulation, read instead from MARPOL Annex VI Appendix VII.",
            "web.archive.org, archive.org, tradewindsnews.com, reuters.com, gcaptain.com and offshore-energy.biz: "
            "trade press with more dated freight, bunker and war risk quotes; splash247.com and lloydslist.com "
            "answered scripts with a refusal.",
            "freightinvestorservices.com, sgx.com and cmegroup.com: FFA curves and settlement pages, which would have "
            "given more dated FFA levels, tanker FFAs in dollars a tonne among them.",
            "ics.org.uk, eclass.unipi.gr, maritime-unipi.gr, commons.wmu.se, core.ac.uk, unctad.org, scribd.com and "
            "poten.com: examiners' reports, course handouts, theses and broker notes with worked voyage estimates, "
            "which would have given the fully worked examples, with prices, the validation lacks.",
            "msi.nga.mil's file download path for the World Port Index: read instead from the agency's JSON service "
            "of the same index.",
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
                "text": "Sourced voyage costs by route at the August 2026 market",
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


def _hormuz_high() -> float:
    """The top of the latest dated Hormuz premium range, percent of hull value."""
    rates = [r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"].startswith("hormuz")]
    return float(max(rates, key=lambda r: r["as_of"])["high"])


def _latest_hormuz_rate() -> tuple[str, str]:
    rates = [r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"].startswith("hormuz")]
    latest = max(rates, key=lambda r: r["as_of"])
    return latest["reported"].split(" to ")[0].split(",")[0].split(" (")[0], date_label(latest["as_of"])


# --------------------------------------------------------------------------
# The Map view
# --------------------------------------------------------------------------

#: The Baltic's own qualifier on a TCE it prints in words, as the figure's prefix.
QUALIFIER_WORDS = {"exact": "", "about": "about ", "just under": "just under "}
#: A passage as prose names it after "by".
PASSAGE_WORDS = {
    "Strait of Hormuz": "the Strait of Hormuz",
    "Bab el Mandeb": "Bab el Mandeb",
    "Suez Canal": "the Suez Canal",
    "Strait of Gibraltar": "the Strait of Gibraltar",
    "Dover Strait": "the Dover Strait",
    "Strait of Malacca": "the Strait of Malacca",
    "Sunda Strait": "the Sunda Strait",
    "Lombok Strait": "the Lombok Strait",
    "Cape of Good Hope": "the Cape of Good Hope",
    "Panama Canal": "the Panama Canal",
    "Yucatan Channel": "the Yucatan Channel",
    "Florida Strait": "the Florida Strait",
}
#: Each routing alternative's name on the map and in the panel, by route and leg routings.
ROUTING_NAMES = {
    ("P7", "no_canals", "no_canals"): ("Round the Cape", "Round the Cape of Good Hope both ways"),
    ("P7", "direct", "no_canals"): ("Back round the Cape", "By Panama laden, back round the Cape in ballast"),
    ("P7", "no_canals", "direct"): ("Laden round the Cape", "Round the Cape laden, back by Panama in ballast"),
    ("TD22", "no_canals", "no_canals"): ("Sunda both ways", "By the Sunda Strait both ways"),
    ("TD22", "no_canals_no_sunda", "no_panama"): ("Back by Suez", "By Malacca laden, back by Suez in ballast"),
    ("TD22", "no_canals", "no_panama"): ("Sunda, back by Suez", "By the Sunda Strait laden, back by Suez in ballast"),
    ("TC20", "no_suez", "no_suez"): ("Round the Cape", "Round the Cape of Good Hope both ways"),
}
#: The list's group headings: each names the basis of the TCE its rows show.
ATLAS_GROUPS = {
    "dry": "Dry bulk: the engine's estimate",
    "dirty": "Dirty tankers: the Baltic's TCE",
    "clean": "Clean tankers: the Baltic's TCE",
    "study": "A detour study, not a Baltic route",
}
#: What else a route could do, named in its list row.
ATLAS_ALSO = {
    "P7": "Also round the Cape, either way or both",
    "TD22": "Also back by Suez, or by the Sunda Strait",
    "TC20": "Also round the Cape",
    "TD3C": "Also TD34, a transfer off Fujairah, or a wait",
    "QD_RTM_PMX": "Also round the Cape, or by Panama",
}
#: Where else the site prices a route, as links from its panel.
ATLAS_LINKS: dict[str, list[dict[str, Any]]] = {
    "TD22": [{"text": "TD22 step by step on Overview", "view": "overview", "params": {}}],
    "TC20": [{"text": "Suez or the Cape on Detours", "view": "detours", "params": {"open": "suez"}}],
    "TD3C": [
        {"text": "The Hormuz scenarios on Detours", "view": "detours", "params": {"open": "hormuz"}},
        {"text": "TD3C against the FFA on Paper", "view": "paper", "params": {"open": "tankers"}},
    ],
    "TD20": [{"text": "Its EU allowances by year on Carbon", "view": "carbon", "params": {}}],
    "C3": [{"text": "C3 against the FFA on Paper", "view": "paper", "params": {}}],
    "C5": [{"text": "C5 against the FFA on Paper", "view": "paper", "params": {}}],
    "S4A_63": [{"text": "Who pays the allowances on a trip, on Carbon", "view": "carbon", "params": {}}],
    "QD_RTM_PMX": [{"text": "The detour study on Detours", "view": "detours", "params": {"open": "dry"}}],
    "TD34": [{"text": "TD3C, the same voyage loading inside the Gulf", "view": "map", "params": {"route": "TD3C"}}],
}


def _or_words(items: list[Any]) -> list[Any]:
    """Segments joined as 'a or b' or 'a, b or c'."""
    out: list[Any] = []
    for i, item in enumerate(items):
        if i:
            out.append(" or " if i == len(items) - 1 else ", ")
        out.append(item)
    return out


def _count_words(n: int) -> str:
    """A small count in words, as prose writes it."""
    return ("no", "one", "two", "three", "four", "five", "six")[n] if n < 7 else str(n)


def _article(ship: str) -> str:
    """'an' before a class word read with a vowel sound (an Aframax, an LR2, an MR), else 'a'."""
    return "an" if ship[:1] in "AEIOU" or ship[:2] in ("LR", "MR") else "a"


def _plain_join(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _passes_words(passes: Sequence[str]) -> str:
    return "by " + _plain_join([PASSAGE_WORDS[name] for name in passes]) if passes else "the direct way"


def _source_short(reported: str) -> str:
    """'Marsh (Marcus Baker) to Platts, 22 July 2026, ...' as 'Marsh'."""
    return reported.split(" to ")[0].split(",")[0].split(" (")[0]


def _days_split(days: Mapping[str, float], field: str) -> list[Any]:
    """'21.3 in ballast, 19.7 laden and 6.0 in port and waiting', the parts rounded to add to the total."""
    ballast, laden, port = rounded_parts([days["ballast"], days["laden"], days["port"]], "days")
    return [
        fig(ballast, "days", field + ".ballast"),
        " in ballast, ",
        fig(laden, "days", field + ".laden"),
        " laden and ",
        fig(port, "days", field + ".port"),
        " in port and waiting",
    ]


def _rate_value(rate: Mapping[str, Any], field: str) -> list[Any]:
    """The freight as the market quotes it."""
    basis, value = rate["basis"], rate["value"]
    if basis == "ws":
        return [fig(value, "ws", field, prefix="WS ")]
    if basis == "lump_sum":
        return [usd_m(value, field), " lump sum"]
    if basis == "hire_usd_day":
        return [usd(value, field, "usd_day"), " a day of hire"]
    return [usd(value, field, "usd_t"), " a tonne"]


def _tce_figure(f: Mapping[str, Any], field: str) -> dict[str, Any]:
    """The headline TCE as one figure, the Baltic's qualifier in front of it."""
    prefix = QUALIFIER_WORDS[f["published_qualifier"]] if f["tce_basis"] == "baltic" else ""
    return fig(f["tce_usd_day"], "usd_day", field, prefix=prefix + "USD ")


def _war_fact(code: str, f: Mapping[str, Any], st: Mapping[str, Any]) -> dict[str, Any] | None:
    """Who pays which war risk premium on the route, at the rates the Detours view prices."""
    market = cases.seed("market.json")
    rates = {r["id"]: r for r in market["war_risk"]["rates_pct"]}
    hulls = market["hull_values_usd"]
    hull_words = "%s, %s" % (_source_short(hulls["source"]), date_label(hulls["source"].split(" of ")[1].split(",")[0]))
    if code == "TC20":
        suez = st["options"][0]
        red = st["red_sea_war_risk"]
        gulf = rates[st["gulf_war_risk"]["source_id"]]
        return {
            "id": "war",
            "label": "War risk premiums",
            "value": [usd(suez["charterer_war_risk_usd_t"], "war.charterer_usd_t", "usd_t"), " a tonne"],
            "note": [
                "The charterer's: the Gulf at %g percent of the hull value a seven-day period and the laden Red Sea "
                "transit at %g percent (%s, %s). The owner pays "
                % (gulf["low"], red["premium_pct"], _source_short(gulf["reported"]), date_label(gulf["as_of"])),
                usd(red["owner_usd"], "war.owner_usd"),
                " for the ballast transit back, which the Baltic's TCE leaves out.",
            ],
        }
    gulf_risk = f["gulf_war_risk"]
    if gulf_risk is None:
        return None
    rate = rates[gulf_risk["source_id"]]
    if gulf_risk["hull_value_usd"] is None:
        return {
            "id": "war",
            "label": "War risk premium",
            "value": ["No public hull value"],
            "note": [
                "The Gulf premium is %g percent of the hull value for each seven days inside (%s, %s), the "
                "charterer's; no dated public hull value exists for this ship, so it is not priced."
                % (rate["low"], _source_short(rate["reported"]), date_label(rate["as_of"]))
            ],
        }
    return {
        "id": "war",
        "label": "War risk premium",
        "value": [usd(gulf_risk["per_period_usd_t"], "war.per_period_usd_t", "usd_t"), " a tonne"],
        "note": [
            "The charterer's, for each seven days inside the Gulf (",
            fig(gulf_risk["periods"], "count", "war.periods"),
            " on this voyage), at %g percent of a " % rate["low"],
            usd_m(gulf_risk["hull_value_usd"], "war.hull_value_usd", "usd_m_0"),
            " hull value (%s, %s; hull value %s)."
            % (_source_short(rate["reported"]), date_label(rate["as_of"]), hull_words),
        ],
    }


def _alternative(code: str, alt: Mapping[str, Any], base_excluded: Sequence[str], label_at: Any) -> dict[str, Any]:
    """One other way to sail a route: its name on the map, its name in the panel and its figures as a sentence."""
    field = "alternatives.%s" % alt["id"]

    def days_and_change() -> list[Any]:
        return [
            fig(alt["days"], "days", field + ".days", suffix=" days"),
            " (",
            fig(alt["days_change"], "days", field + ".days_change", signed=True),
            ")",
        ]

    if alt["kind"] == "routing" and code in ("P7", "TD22"):
        short, name = ROUTING_NAMES[(code, alt["routing"]["laden"], alt["routing"]["ballast"])]
        text: list[Any] = [
            *days_and_change(),
            "; TCE ",
            usd(alt["tce_usd_day"], field + ".tce_usd_day", "usd_day"),
            " a day (",
            fig(alt["tce_change"], "usd_day", field + ".tce_change", signed=True),
            "). To earn the TCE above it needs ",
            usd(alt["freight_needed_usd_t"], field + ".freight_needed_usd_t", "usd_t"),
            " a tonne (",
            fig(alt["freight_change_usd_t"], "usd_t", field + ".freight_change_usd_t", signed=True),
            ").",
        ]
        added = [item for item in alt["excluded"] if item not in base_excluded]
        if added:
            text.append(" It leaves out %s." % _plain_join(added))
    elif code == "TC20":
        short, name = ROUTING_NAMES[(code, "no_suez", "no_suez")]
        text = [
            *days_and_change(),
            "; TCE ",
            usd(alt["tce_usd_day"], field + ".tce_usd_day", "usd_day"),
            " a day, against ",
            usd(alt["suez_tce_usd_day"], field + ".suez_tce_usd_day", "usd_day"),
            " by Suez once the owner pays its premium for the ballast transit of the Red Sea. The Cape needs ",
            usd(alt["freight_change_usd_t"], field + ".freight_change_usd_t", "usd_t"),
            " a tonne more freight to earn as much, so Suez stays the better way until the tolls of its ",
            fig(alt["break_even_suez_transits"], "count", field + ".transits"),
            " transits pass ",
            usd_m(alt["break_even_suez_toll_usd"], field + ".break_even_suez_toll_usd"),
            ".",
        ]
    elif alt["id"] == "td34":
        short, name = "TD34", "TD34: loading at Mina Al Fahal, outside the Gulf"
        text = [
            *days_and_change(),
            "; the Baltic's TCE ",
            usd(alt["tce_usd_day"], field + ".tce_usd_day", "usd_day"),
            " a day. At its own TCE the freight is ",
            usd(alt["freight_needed_usd_t"], field + ".freight_needed_usd_t", "usd_t"),
            " a tonne, against ",
            usd(alt["td3c_freight_usd_t"], field + ".td3c_freight_usd_t", "usd_t"),
            " for TD3C at its own.",
        ]
    elif alt["id"] == "transfer":
        short, name = "Fujairah transfer", "A shuttle out of the Gulf, then an export VLCC from Fujairah"
        low, high = alt["shuttle_usd_bbl"]
        text = [
            "The export VLCC sails ",
            *days_and_change(),
            " and needs ",
            usd(alt["freight_needed_usd_t"], field + ".freight_needed_usd_t", "usd_t"),
            " a tonne to earn TD3C's TCE (",
            fig(alt["freight_change_usd_t"], "usd_t", field + ".freight_change_usd_t", signed=True),
            "). The shuttle through Hormuz is not priced: it was reported at ",
            usd(low, field + ".shuttle_low"),
            " to ",
            fig(high, "usd", field + ".shuttle_high"),
            " a barrel (%s)." % alt["shuttle_reported"],
        ]
    elif alt["id"] == "waiting":
        short, name = "", "Waiting inside the Gulf"
        waits = alt["waits"]
        text = [
            "Each seven days inside the Gulf costs the charterer another ",
            usd(alt["per_period_usd_t"], field + ".per_period_usd_t", "usd_t"),
            " a tonne at %g percent of the hull value. Waiting " % alt["premium_pct"],
            *_or_words([fig(w["waiting_days"], "count", field + ".%s.days" % w["id"]) for w in waits]),
            " days costs ",
            *_or_words(
                [
                    fig(w["total_usd_t"], "usd_t", field + ".%s.total_usd_t" % w["id"], prefix="USD " if not at else "")
                    for at, w in enumerate(waits)
                ]
            ),
            " a tonne in all: the premium and the owner's extra freight at the latest TCE.",
        ]
    else:
        raise KeyError(alt["id"])
    return {
        "id": alt["id"],
        "short": short,
        "name": name,
        "legs": list(alt["legs"]),
        "label_at": label_at,
        "text": text,
        "map_label": _alt_map_label(short, alt, field),
        "whole_label": "%s %s" % (_short(code), WHOLE_MAP_NAMES.get((code, alt["id"]), ""))
        if (code, alt["id"]) in WHOLE_MAP_NAMES
        else None,
    }


#: The one alternative a route's line carries on the whole map, by route and alternative, as words after its code.
WHOLE_MAP_NAMES = {
    ("P7", "no_canals-no_canals"): "by the Cape",
    ("TD22", "no_canals_no_sunda-no_panama"): "back by Suez",
    ("TC20", "no_suez-no_suez"): "by the Cape",
}


def _alt_map_label(short: str, alt: Mapping[str, Any], field: str) -> list[Any] | None:
    """An alternative's name on the map once its route is picked, with what it changes: days and TCE, or the freight."""
    if not short:
        return None
    out: list[Any] = [short + ": "]
    if alt.get("days_change") is not None:
        out += [fig(alt["days_change"], "days", field + ".days_change", signed=True, suffix=" days")]
    if alt.get("tce_usd_day") is not None:
        out += [", TCE ", fig(alt["tce_usd_day"], "usd_day", field + ".tce_usd_day")]
    elif alt.get("freight_change_usd_t") is not None:
        out += [
            ", ",
            fig(alt["freight_change_usd_t"], "usd_t", field + ".freight_change_usd_t", signed=True, prefix="USD "),
            " a tonne",
        ]
    return out


def _route_item(entry: Mapping[str, Any], st: Mapping[str, Any], atlas_date: str) -> dict[str, Any]:
    """One route of the map: its list row, its readout, its panel and its links, every figure a segment."""
    preset, f, alts, geometry = entry["preset"], entry["figures"], entry["alternatives"], entry["geometry"]
    code = preset["route"]
    route = baltic.ROUTES[code]
    label = _short(code)
    ports = "%s to %s" % (_port_name(route.load), _port_name(route.discharge))
    date = preset["date"]
    trip = route.contract == "trip"
    laden_passes, ballast_passes = entry["passes"]
    rate_source = preset["sources"]["freight_value"]["source"]

    if f["tce_basis"] == "baltic" and f["engine_tce_usd_day"] is not None:
        basis = "the Baltic's"
        gap = (f["engine_tce_usd_day"] - f["published_tce_usd_day"]) / f["published_tce_usd_day"]
        tce_note = [
            "The Baltic's TCE for the week to ",
            word(date_label(date), "date"),
            ". The engine prices the same voyage at ",
            usd(f["engine_tce_usd_day"], "engine_tce_usd_day", "usd_day"),
            ", ",
            fig(abs(gap) * 100.0, "error_percent", "engine_gap", suffix=" percent"),
            " higher" if gap > 0 else " lower",
            ", port charges left out of both.",
        ]
    elif f["tce_basis"] == "baltic":
        basis = "the Baltic's"
        tce_note = [
            "The Baltic's TCE for the week to ",
            word(date_label(date), "date"),
            ". The rate is in Worldscale points, which have no dollar value without the licensed flat rate, so "
            "the engine prices this route's days and costs but not its TCE.",
        ]
    elif trip:
        basis = "the engine's estimate"
        tce_note = [
            "The owner's TCE over the round trip, the ballast back to the US Gulf included: the trip pays ",
            usd(f["trip_hire_usd_day"], "trip_hire_usd_day", "usd_day"),
            " a day of hire for its ",
            fig(f["trip_days"], "days", "trip_days", suffix=" days"),
            " and nothing for the way back.",
        ]
    else:
        basis = "the engine's estimate"
        tce_note = [
            "The engine's estimate at the freight below, ",
            word(date_label(date), "date"),
            "; the Baltic publishes no TCE for this route.",
        ]

    same_way = ballast_passes == list(reversed(laden_passes)) and f["ballast_nm"] == f["laden_nm"]
    facts: list[dict[str, Any]] = [
        {"id": "tce", "label": "TCE", "value": [_tce_figure(f, "tce_usd_day"), " a day"], "note": tce_note},
        {
            "id": "days",
            "label": "Round voyage",
            "value": [fig(f["days"]["total"], "days", "days.total", suffix=" days")],
            "note": [*_days_split(f["days"], "days"), "."],
        },
        {
            "id": "distance",
            "label": "Distance",
            "value": [fig(f["laden_nm"], "nm", "laden_nm", suffix=" nautical miles laden")],
            "note": [
                _upper_first(_passes_words(laden_passes)),
                "; back in ballast ",
                *(
                    ["the same way"]
                    if same_way
                    else [
                        fig(f["ballast_nm"], "nm", "ballast_nm", suffix=" nautical miles "),
                        _passes_words(ballast_passes),
                    ]
                ),
                *(
                    [
                        "; ",
                        fig(f["eca_share"] * 100.0, "percent", "eca_share", suffix=" percent"),
                        " of the miles inside emission control areas.",
                    ]
                    if f["eca_nm"] > 0
                    else ["; no mile inside an emission control area."]
                ),
            ],
        },
        {
            "id": "freight",
            "label": "Freight",
            "value": _rate_value(preset["rate"], "rate.value"),
            "note": [_upper_first(rate_source) + "."],
        },
    ]
    if trip:
        facts.append(
            {
                "id": "breakeven",
                "label": "Hire that covers the owner's costs",
                "value": [usd(f["breakeven_hire_usd_day"], "breakeven_hire_usd_day", "usd_day"), " a day"],
                "note": ["The hire that leaves the owner nothing over the round trip, against the hire above."],
            }
        )
    else:
        note: list[Any] = []
        if f["freight_at_published_usd_t"] is not None:
            note = [
                "At the engine's days and costs the freight that earns the Baltic's TCE is ",
                usd(f["freight_at_published_usd_t"], "freight_at_published_usd_t", "usd_t"),
                " a tonne: derived, not a quoted rate.",
            ]
        elif f["freight_usd_t"] is not None:
            note = ["Against ", usd(f["freight_usd_t"], "freight_usd_t", "usd_t"), " a tonne fixed."]
        facts.append(
            {
                "id": "breakeven",
                "label": "Freight that covers the voyage costs",
                "value": [usd(f["breakeven_usd_t"], "breakeven_usd_t", "usd_t"), " a tonne"],
                "note": note,
            }
        )
    costs_note: list[Any] = ["Bunkers ", usd_m(f["bunkers_usd"], "bunkers_usd")]
    if f["ets_usd"] > 0:
        costs_note += [" and EU allowances ", usd(f["ets_usd"], "ets_usd")]
    else:
        costs_note.append(", no EU allowance: no EEA port")
    costs_note += ["; ", usd(f["costs_per_day_usd"], "costs_per_day_usd", "usd_day"), " a day of the round voyage."]
    if trip:
        costs_note += [
            " The owner's are the ballast leg's; the charterer pays the trip's, ",
            usd(f["charterer_costs_usd"], "charterer_costs_usd"),
            ".",
        ]
    facts.append(
        {
            "id": "costs",
            "label": "Owner's voyage costs priced" if trip else "Voyage costs priced",
            "value": [usd_m(f["costs_usd"], "costs_usd")],
            "note": costs_note,
        }
    )
    war = _war_fact(code, f, st)
    if war:
        facts.append(war)
    facts.append(
        {
            "id": "left_out",
            "label": "Left out",
            "value": [_upper_first(_plain_join(preset["excluded"])) + "."],
            "note": [],
        }
    )
    alternatives = [_alternative(code, alt, preset["excluded"], geometry["label_at"].get(alt["id"])) for alt in alts]
    return {
        "id": code,
        "label": label,
        "kind": "route",
        "segment": route.segment,
        "name": route.name,
        "ports": ports,
        "ship": VESSEL_CLASS[route.vessel],
        "preset": preset["id"],
        "date": date,
        "tce_usd_day": f["tce_usd_day"],
        "tce_basis": f["tce_basis"],
        "days": f["days"]["total"],
        "figure": [_tce_figure(f, "tce_usd_day")],
        "row": {
            "tce": [fig(f["tce_usd_day"], "usd_day", "tce_usd_day")],
            "qualifier": QUALIFIER_WORDS[f["published_qualifier"]].strip() if f["tce_basis"] == "baltic" else "",
            "days": [fig(f["days"]["total"], "days", "days.total")],
            "note": (
                [
                    "Trip charter: the owner's TCE with the ballast back; hire ",
                    usd(f["trip_hire_usd_day"], "trip_hire_usd_day", "usd_day"),
                    " a day",
                ]
                if trip
                else ["Rate of ", word(date_label(date), "date")]
                if date != atlas_date
                else []
            ),
            "also": ATLAS_ALSO.get(code, ""),
            "last": trip,
        },
        "readout": [
            word(label, "label"),
            ", %s, %s: " % (VESSEL_CLASS[route.vessel], ports),
            _tce_figure(f, "tce_usd_day"),
            " a day, %s; " % basis,
            fig(f["days"]["total"], "days", "days.total", suffix=" days round"),
        ],
        "basis": f["tce_basis"],
        "same_water": list(entry["same_water"]),
        "legs": {"laden": preset["legs"]["laden"]["key"], "ballast": preset["legs"]["ballast"]["key"], "beside": True},
        "view": geometry["view"],
        "view_tall": geometry["view_tall"],
        "passages": geometry["passages"],
        "heading": "%s, %s" % (label, route.name),
        "map_title": "%s, %s %s%s"
        % (
            label,
            ports,
            _passes_words(laden_passes),
            ", and %s other way%s to sail it" % (_count_words(len(alternatives)), "" if len(alternatives) == 1 else "s")
            if alternatives
            else "",
        ),
        "map_desc": "The route picked is drawn in the accent colour, its laden leg solid and its ballast leg dashed "
        "beside it"
        + (", its other routings dotted" if any(alt["legs"] for alt in alternatives) else "")
        + "; every other route is a thin muted line. Every figure is in the column beside the map.",
        "subhead": [
            VESSEL_CLASS[route.vessel],
            ", ",
            *(
                [fig(route.cargo_t, "t", "cargo_t", suffix=" tonnes"), ", "]
                if route.cargo_t
                else ["trip time charter, "]
            ),
            ports,
        ],
        "split": f["days"],
        "facts": facts,
        "table": {
            "tce": [
                _tce_figure(f, "tce_usd_day"),
                ", the Baltic's" if f["tce_basis"] == "baltic" else ", the engine's",
            ],
            "days": [fig(f["days"]["total"], "days", "days.total")],
            "laden_nm": [fig(f["laden_nm"], "nm", "laden_nm")],
            "freight": _rate_value(preset["rate"], "rate.value"),
            "breakeven": (
                [usd(f["breakeven_hire_usd_day"], "breakeven_hire_usd_day", "usd_day"), " a day of hire"]
                if trip
                else [usd(f["breakeven_usd_t"], "breakeven_usd_t", "usd_t"), " a tonne"]
            ),
            "costs": [usd(f["costs_usd"], "costs_usd")],
        },
        "alternatives": alternatives,
        "links": [
            {"text": "Price %s in the calculator" % label, "view": "calculator", "params": {"preset": preset["id"]}},
            *ATLAS_LINKS.get(code, []),
        ],
        "source": with_retrieval(
            [
                "Rate: %s. Bunkers: %s. " % (rate_source, preset["sources"]["prices.vlsfo_usd_t"]["source"]),
                "Ship, speeds and port days: Baltic Exchange Guide to Market Benchmarks v%s. " % baltic.GMB["version"],
                "Distances: searoute over Eurostat SeaRoute. Engine: this study.",
            ]
        ),
    }


def _study_item(
    s: Mapping[str, Any], geometry: Mapping[str, Any], passes: Sequence[str], same: Sequence[str]
) -> dict[str, Any]:
    """The Panamax one way from Qingdao to Rotterdam: a detour study, priced to earn the Baltic's P4 trip hire."""
    route = s["route"]
    base = s["base"]
    names = {"cape": ("Round the Cape", "Round the Cape of Good Hope"), "panama": ("By Panama", "By the Panama Canal")}
    alternatives = []
    for alt in s["alternatives"]:
        field = "alternatives.%s" % alt["id"]
        text: list[Any] = [
            fig(alt["days"], "days", field + ".days", suffix=" days"),
            " (",
            fig(alt["days_change"], "days", field + ".days_change", signed=True),
            "); it needs ",
            usd(alt["freight_needed_usd_t"], field + ".freight_needed_usd_t", "usd_t"),
            " a tonne (",
            fig(alt["freight_change_usd_t"], "usd_t", field + ".freight_change_usd_t", signed=True),
            ").",
        ]
        if alt["toll_and_waiting_budget_usd"]:
            text += [
                " At the Cape's freight it can spend ",
                usd(alt["toll_and_waiting_budget_usd"], field + ".budget"),
                " on its toll and waiting, ",
                fig(alt["waiting_days_budget"], "days", field + ".waiting_days", suffix=" days"),
                " of the hire. %s." % _panama_wait(),
            ]
        short, name = names[alt["id"]]
        alternatives.append(
            {
                "id": alt["id"],
                "short": short,
                "name": name,
                "legs": list(alt["legs"]),
                "label_at": geometry["label_at"].get(alt["id"]),
                "text": text,
                "map_label": _alt_map_label(short, alt, field),
                "whole_label": "Asia to Europe by Panama" if alt["id"] == "panama" else None,
            }
        )
    label = "Asia to Europe, Panamax"
    way = _passes_words(passes)
    map_title = "A Panamax from Qingdao to Rotterdam %s, or round the Cape, or by Panama" % way
    return {
        "id": s["id"],
        "label": label,
        "kind": "study",
        "segment": "dry",
        "name": "Panamax one way, Qingdao to Rotterdam",
        "ports": "Qingdao to Rotterdam",
        "ship": VESSEL_CLASS[route.vessel],
        "preset": None,
        "date": s["date"],
        "tce_usd_day": None,
        "tce_basis": "study",
        "days": base["days"],
        "figure": None,
        "row": {
            "tce": [fig(base["freight_needed_usd_t"], "usd_t", "freight_needed_usd_t", suffix=" a tonne")],
            "qualifier": "",
            "days": [fig(base["days"], "days", "days")],
            "note": ["One way by Suez: the freight that earns the P4 trip hire"],
            "also": ATLAS_ALSO["QD_RTM_PMX"],
            "last": False,
        },
        "readout": [
            word(label, "label"),
            ", a Panamax one way from Qingdao to Rotterdam: ",
            usd(base["freight_needed_usd_t"], "freight_needed_usd_t", "usd_t"),
            " a tonne by Suez to earn the P4 hire; ",
            fig(base["days"], "days", "days", suffix=" days"),
        ],
        "basis": "study",
        "same_water": list(same),
        "legs": {"laden": base["legs"][0], "ballast": None, "beside": False},
        "view": geometry["view"],
        "view_tall": geometry["view_tall"],
        "passages": geometry["passages"],
        "heading": "Asia to Europe, a Panamax one way",
        "map_title": map_title,
        "map_desc": "The study's route by Suez is drawn in the accent colour, the Cape and Panama routings "
        "dotted; every other route is a thin muted line. Every figure is in the column beside the map.",
        "subhead": [
            "Not a Baltic route: Qingdao to Rotterdam with ",
            fig(s["cargo_t"], "t", "cargo_t", suffix=" tonnes"),
            ", priced against the Baltic's P4 trip hire",
        ],
        "split": None,
        "facts": [
            {
                "id": "freight",
                "label": "Freight to earn the P4 hire",
                "value": [usd(base["freight_needed_usd_t"], "freight_needed_usd_t", "usd_t"), " a tonne by Suez"],
                "note": [
                    "The freight at which the trip earns what a Panamax earns on P4, ",
                    usd(s["p4_hire_usd_day"], "p4_hire_usd_day", "usd_day"),
                    " a day, or ",
                    usd(s["target_tce_usd_day"], "target_tce_usd_day", "usd_day"),
                    " after its ",
                    fig(s["p4_commission_pct"], "percent_0", "p4_commission_pct", suffix=" percent"),
                    " commission, in the week to ",
                    word(date_label(s["date"]), "date"),
                    ".",
                ],
            },
            {
                "id": "days",
                "label": "Days",
                "value": [fig(base["days"], "days", "days", suffix=" days by Suez")],
                "note": ["One way, delivered at Qingdao and redelivered at Rotterdam, with no port time."],
            },
            {
                "id": "distance",
                "label": "Distance",
                "value": [fig(base["laden_nm"], "nm", "laden_nm", suffix=" nautical miles")],
                "note": [_upper_first(_passes_words(passes)) + "."],
            },
            {
                "id": "war",
                "label": "War risk premium",
                "value": [usd(base["charterer_war_risk_usd_t"], "charterer_war_risk_usd_t", "usd_t"), " a tonne"],
                "note": [
                    "The charterer's, for the Red Sea transit at %g percent of the hull value."
                    % s["red_sea_premium_pct"]
                ],
            },
            {
                "id": "left_out",
                "label": "Left out",
                "value": [_upper_first(_plain_join(base["excluded"])) + "."],
                "note": [],
            },
        ],
        "alternatives": alternatives,
        "links": list(ATLAS_LINKS["QD_RTM_PMX"]),
        "source": with_retrieval(
            [
                "P4 hire: Banchero Costa, week to ",
                word(date_label(s["date"]), "date"),
                ". Ship: Baltic Exchange Guide to Market Benchmarks v%s. " % baltic.GMB["version"],
                "Distances: searoute over Eurostat SeaRoute. Engine: this study, as on Detours.",
            ]
        ),
    }


def atlas_page(
    entries: Sequence[Mapping[str, Any]],
    study: Mapping[str, Any],
    study_geometry: Mapping[str, Any],
    study_passes: Sequence[str],
    study_same: Sequence[str],
    st: Mapping[str, Any],
    clusters: Sequence[Mapping[str, Any]],
    view_box: Sequence[float],
    atlas_date: str,
) -> dict[str, Any]:
    """data/atlas.json: the Map view's words and every figure it shows, by route."""
    items = [_route_item(entry, st, atlas_date) for entry in entries]
    items.append(_study_item(study, study_geometry, study_passes, study_same))
    baltic_items = [i for i in items if i["tce_basis"] == "baltic"]
    top = max(baltic_items, key=lambda i: i["tce_usd_day"])
    bottom = min(baltic_items, key=lambda i: i["tce_usd_day"])
    longest = max((i for i in items if i["kind"] == "route"), key=lambda i: i["days"])
    tc20 = next(i for i in entries if i["preset"]["route"] == "TC20")["alternatives"][0]
    takeaway = [
        "In the week to ",
        word(date_label(atlas_date), "date"),
        " %s %s on %s earned " % (_article(top["ship"]), top["ship"], top["label"]),
        top["figure"][0],
        " a day by the Baltic's own figure, about ",
        fig(top["tce_usd_day"] / bottom["tce_usd_day"], "count", "takeaway.ratio", suffix=" times"),
        " %s %s on %s." % (_article(bottom["ship"]), bottom["ship"], bottom["label"]),
    ]
    other_dates = sorted({i["date"] for i in items if i["kind"] == "route" and i["date"] != atlas_date})
    late = [i["label"] for i in items if i["kind"] == "route" and i["date"] != atlas_date]
    key = [
        "Beside each loading port, each route and its TCE in USD a day, in the week to ",
        word(date_label(atlas_date), "date"),
        ": the Baltic's for tankers, the engine's estimate, in grey, for dry bulk",
        *(
            ["; %s at its latest public rate, of " % _plain_join(late), word(date_label(other_dates[-1]), "late_date")]
            if late
            else []
        ),
        ".",
    ]
    summary = [
        {
            "item": top["id"],
            "label": "Highest TCE",
            "value": [top["label"], ", ", top["figure"][0], " a day"],
            "note": ["The Baltic's, %s." % top["ports"]],
        },
        {
            "item": bottom["id"],
            "label": "Lowest of the Baltic's",
            "value": [bottom["label"], ", ", bottom["figure"][0], " a day"],
            "note": ["%s, %s." % (bottom["ship"], bottom["ports"])],
        },
        {
            "item": longest["id"],
            "label": "Longest round voyage",
            "value": [longest["label"], ", ", fig(longest["days"], "days", "summary.longest_days", suffix=" days")],
            "note": ["%s, %s." % (longest["ship"], longest["ports"])],
        },
        {
            "item": "TC20",
            "label": "Costliest detour",
            "value": [
                "TC20 round the Cape, ",
                fig(tc20["days_change"], "days", "summary.tc20_days", suffix=" more days"),
            ],
            "note": [
                "It needs ",
                usd(tc20["freight_change_usd_t"], "summary.tc20_freight", "usd_t"),
                " a tonne more freight than by Suez.",
            ],
        },
    ]
    return {
        "as_of": atlas_date,
        "view_box": list(view_box),
        "page": {
            "title": "What each route earns a day, and what the other ways cost",
            "takeaway": takeaway,
            "filters": [
                {
                    "id": key,
                    "label": name,
                    "announce": [
                        fig(
                            sum(1 for i in items if key == "all" or i["segment"] == key),
                            "count",
                            "filters.%s.count" % key,
                        ),
                        " on the map and in the list: %s." % name.lower(),
                    ],
                }
                for key, name in (
                    ("all", "Every route"),
                    ("dry", "Dry bulk"),
                    ("dirty", "Dirty tankers"),
                    ("clean", "Clean tankers"),
                )
            ],
            "filter_label": "Show",
            "groups": [{"id": key, "name": name} for key, name in ATLAS_GROUPS.items()],
            "list": {
                "caption": [
                    "Each route at its latest dated rate: the week to ",
                    word(date_label(atlas_date), "date"),
                    ", P7 at its latest public rate. Days are the round voyage.",
                ],
                "heading": "The routes",
                "unknown": "There is no route %s on this map; every route is listed below.",
                "head": {"route": "Route", "tce": "TCE, USD a day", "days": "Days"},
                "more_one": "other routing",
                "more_many": "other routings",
            },
            "panel": {
                "back": "Back to the list",
                "same": "Its line runs with ",
                "same_after": " for most of the way:",
                "split": {"ballast": "Ballast", "laden": "Laden", "port": "Port and waiting"},
                "alternatives": "Other ways to sail it",
                "links": "More on this route",
                "show": "Show on the map",
            },
            "summary": {"heading": "At a glance", "items": summary},
            "map": {
                "title": "Every route the study prices, from its loading port, with its TCE a day",
                "desc": "An equirectangular map from 110 degrees west to 155 degrees east. Each route's laden leg is "
                "a line from its loading port; the other routings the study prices are dotted. Every figure is in "
                "the list beside the map.",
                "legend": [
                    {"kind": "laden", "state": "list", "text": "A route's laden leg, from its loading port"},
                    {"kind": "alternative", "state": "list", "text": "Another routing the study prices"},
                    {"kind": "picked", "state": "route", "text": "The route picked: its laden leg"},
                    {"kind": "picked-ballast", "state": "route", "text": "Its ballast leg, dashed beside it"},
                    {
                        "kind": "eca",
                        "state": "route",
                        "text": "Inside an emission control area: 0.10 percent sulphur fuel (MGO)",
                    },
                    {"kind": "alternative-picked", "state": "route", "text": "Another routing it could take"},
                    {"kind": "other", "state": "route", "text": "Every other route"},
                    {
                        "kind": "edge",
                        "state": "both",
                        "text": "Where a line leaves the map across the Pacific, and where it comes back",
                    },
                ],
                "labels": key,
                "idle": "Point at a route, or pick one from the list, for its figures and the other ways it could "
                "sail.",
                "same": "Same water: ",
                "edge": "across the Pacific",
                "source": with_retrieval(
                    [
                        "Lines: searoute over Eurostat SeaRoute, the same lines the distances are measured on. "
                        "Emission control areas: MARPOL Annex VI, in force on ",
                        word(date_label(atlas_date), "date"),
                        ". Land: Natural Earth 1:110m. TCEs: the Baltic Exchange weekly tanker report via Hellenic "
                        "Shipping News for tankers; the engine at public rates for dry bulk.",
                    ]
                ),
            },
            "sections": [
                {
                    "id": "table",
                    "name": "Every route side by side",
                    "summary": ["Days, distance, freight, costs and the freight that covers them, one row a route."],
                },
                {
                    "id": "method",
                    "name": "How to read it",
                    "summary": ["Which TCE each route shows, and what every figure leaves out."],
                },
            ],
            "method": [
                [
                    "Every route is priced on its latest dated rate, the preset the calculator opens for it, by the "
                    "same engine and conventions as the rest of the study: the Baltic's round voyage, its ships, "
                    "speeds and port days, bunkers at the hub with public prices nearest the loading port, and a 5 "
                    "percent weather margin on steaming time."
                ],
                [
                    "Tanker rates are quoted in Worldscale points, and a point has no dollar value without the "
                    "licensed flat rate, so for the tanker routes the TCE shown is the Baltic's own, printed beside "
                    "the rate in its weekly report. Where the rate is a lump sum (TD22, TC20) the engine prices the "
                    "same voyage, and both figures are shown. The Baltic publishes no TCE for the dry voyage routes: "
                    "theirs is the engine's estimate at a public rate. S4A is a trip time charter, so its TCE is the "
                    "owner's over the round trip, the ballast back to the US Gulf included."
                ],
                [
                    "Port charges have no public per call figure and are left out of every TCE, as each panel says; "
                    "so are canal tolls where a routing uses a canal. An alternative that earns more only because it "
                    "leaves out a toll or a premium says so."
                ],
                [
                    "The lines are the ones the distances are measured on. The map is equirectangular and not to "
                    "scale, so it carries no distance bar. TC23, the intra-EEA Handy route, is priced only for its "
                    "carbon cost, on the Carbon view."
                ],
            ],
            "table": {
                "caption": [
                    "Every route at its latest dated rate, ",
                    word(date_label(atlas_date), "date"),
                    " unless the row says otherwise.",
                ],
                "columns": {
                    "route": "Route",
                    "tce": "TCE a day, and whose",
                    "days": "Round voyage, days",
                    "laden_nm": "Laden leg, nautical miles",
                    "freight": "Freight as quoted",
                    "breakeven": "Freight that covers the voyage costs",
                    "costs": "Voyage costs priced",
                },
            },
        },
        "clusters": list(clusters),
        "items": items,
    }
