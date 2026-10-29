"""The validation anchors: public rates with a published TCE, reproduced by the engine or explained.

No input is tuned to an anchor. Each result carries the engine's TCE, the
published one, the error, and what the engine leaves out that the publisher
includes. An anchor whose rate is in Worldscale points is not reproducible:
the year's flat rate is licensed and no public source states it, and the
study does not back one out of the published TCE.
"""

from __future__ import annotations

from typing import Any

from . import baltic, cases, engine

LUMP_SUM_ROUTES = ("TD22", "TC20")


def _tce(route: str, market: cases.Market, value: float, basis: str | None = None, **overrides: Any) -> dict[str, Any]:
    case = cases.build(route, market, freight_value=value, freight_basis=basis)
    inputs = case.inputs
    for path, new in overrides.items():
        head, _, tail = path.partition(".")
        if tail:
            inputs[head] = dict(inputs[head], **{tail: new})
        else:
            inputs[head] = new
    result = engine.evaluate(inputs)
    return {"case": case, "result": result, "tce_usd_day": result["tce_usd_day"]}


def tanker_weekly() -> list[dict[str, Any]]:
    """Every tanker rate and TCE pair of the Baltic weekly reports, reproduced where the rate allows."""
    out = []
    for report in cases.seed("anchors.json")["tanker_weekly"]["reports"]:
        for entry in report["entries"]:
            route = entry["route"]
            row = {
                "week_ending": report["week_ending"],
                "published": report["published"],
                "route": route,
                "rate_basis": entry["rate_basis"],
                "rate_value": entry["rate_value"],
                "published_tce_usd_day": entry["tce_usd_day"],
                "tce_qualifier": entry["tce_qualifier"],
                "raw_key": entry["raw_key"],
                "reproducible": False,
                "engine_tce_usd_day": None,
                "error": None,
                "reason": "",
                "bunkers": "",
            }
            if entry["tce_usd_day"] is None:
                row["reason"] = "a rate only: the report gives no TCE for this route that week"
            elif entry["rate_basis"] == "ws":
                row["reason"] = (
                    "Worldscale rate: the %s flat rate is licensed and no public source states it"
                    % report["week_ending"][:4]
                )
            elif route in LUMP_SUM_ROUTES:
                hub = cases.bunker_hub(baltic.ROUTES[route].load)
                try:
                    market = cases.weekly_market(report["week_ending"], hub)
                except ValueError:
                    row["reason"] = "no public bunker table within a week before the assessment"
                else:
                    computed = _tce(route, market, entry["rate_value"], "lump_sum")
                    row.update(
                        reproducible=True,
                        engine_tce_usd_day=computed["tce_usd_day"],
                        error=computed["tce_usd_day"] / entry["tce_usd_day"] - 1.0,
                        bunkers=market.label,
                        excluded=computed["case"].excluded,
                    )
            out.append(row)
    return out


def early_march() -> list[dict[str, Any]]:
    """TD3C priced at the early March 2026 rates, against the TCEs reported the same week."""
    items = {item["id"]: item for item in cases.seed("anchors.json")["early_march_2026"]["items"]}
    hub = cases.bunker_hub(baltic.ROUTES["TD3C"].load)
    week = cases.weekly_market("2026-03-02", hub)
    december = cases.quarter_market("2025-Q4", "2025-12-12")
    hull = cases.seed("market.json")["hull_values_usd"]["march_2026_vlcc"]["value"]
    premium = next(r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"] == "hormuz_2026_03_early")[
        "low"
    ]
    rows = []
    for item_id, market in (
        ("platts_pg_china_2025_12_12", december),
        ("platts_pg_china_2026_03_02", week),
        ("oilprice_gulf_china_2026_03_03", week),
    ):
        item = items[item_id]
        base_case = _tce("TD3C", market, item["freight_usd_t"], "usd_t")
        row = {
            "id": item_id,
            "date": item["date"],
            "freight_usd_t": item["freight_usd_t"],
            "source": item["source"],
            "primary": item["primary"],
            "bunkers": market.label,
            "engine_tce_usd_day": base_case["tce_usd_day"],
            "days": base_case["result"]["days"]["total"],
        }
        if item["date"] >= "2026-03-01":
            war = _tce(
                "TD3C",
                market,
                item["freight_usd_t"],
                "usd_t",
                **{"war_risk.premium_pct": premium, "war_risk.hull_value_usd": float(hull), "war_risk.periods": 1.0},
            )
            row["engine_tce_with_war_risk_usd_day"] = war["tce_usd_day"]
            row["war_risk_usd"] = war["result"]["costs"]["war_risk"]
        rows.append(row)
    return rows


def dry_weekly() -> list[dict[str, Any]]:
    """The Capesize, Panamax and Supramax rates of the anchor weeks, as TCEs beside the time charter averages."""
    weeks = cases.seed("anchors.json")["dry_weekly"]["weeks"]
    rows = []
    plan = (
        ("2026-07-03", "dry_bancosta_weekly_2026_wk27_pdf", ("C3", "C5"), "C5TC_usd_day"),
        ("2026-10-23", "dry_bancosta_weekly_2026_wk43_pdf", ("C3", "C5"), "C5TC_182_usd_day"),
        ("2026-09-11", "dry_hsn_panamax_in_focus_2026_html", ("P7",), "P5TC_usd_day"),
    )
    for date, key, routes, benchmark in plan:
        week = next(w for w in weeks if w["date"] == date and w["raw_key"] == key)
        for route in routes:
            hub = cases.bunker_hub(baltic.ROUTES[route].load)
            market = cases.weekly_market(date, hub)
            rate = week["values"]["%s_usd_t" % route]
            computed = _tce(route, market, rate, "usd_t")
            rows.append(
                {
                    "date": date,
                    "route": route,
                    "freight_usd_t": rate,
                    "engine_tce_usd_day": computed["tce_usd_day"],
                    "benchmark": benchmark,
                    "benchmark_usd_day": week["values"][benchmark],
                    "gap_usd_day": computed["tce_usd_day"] - week["values"][benchmark],
                    "bunkers": market.label,
                    "excluded": computed["case"].excluded,
                    "days": computed["result"]["days"]["total"],
                    "ballast_days": computed["result"]["days"]["ballast_sea"],
                    "source": week["source"],
                }
            )
    return rows


def baltic_2017() -> dict[str, Any]:
    """The Baltic's July 2017 TD3C calculation: days and fuel, reproduced from its own inputs."""
    spec = cases.seed("anchors.json")["baltic_td3c_2017"]
    i = spec["inputs"]
    laden_days = engine.sea_days(i["distance_nm"], i["laden_kn"], i["sea_margin"])
    ballast_days = engine.sea_days(i["distance_nm"], i["ballast_kn"], i["sea_margin"])
    total = laden_days + ballast_days + i["load_days"] + i["discharge_days"] + i["waiting_days"]
    computed = {
        "laden_days": laden_days,
        "ballast_days": ballast_days,
        "total_days": total,
        "laden_fuel_t": laden_days * i["laden_tpd"],
        "ballast_fuel_t": ballast_days * i["ballast_tpd"],
        "waiting_fuel_t": i["waiting_days"] * i["waiting_tpd"],
        "load_fuel_t": i["load_days"] * i["load_tpd"],
        "discharge_fuel_t": i["discharge_days"] * i["discharge_tpd"],
    }
    return {"computed": computed, "published": spec["published"]}


def distances() -> dict[str, Any]:
    checks = cases.seed("sea_routes.json")["pub151_checks"]
    within = [c for c in checks["checks"] if c["within_tolerance"]]
    return {"tolerance": checks["tolerance"], "checks": checks["checks"], "within": len(within)}
