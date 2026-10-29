"""The validation anchors: public rates with a published TCE, reproduced by the engine or explained.

No input is tuned to an anchor. Each result carries the engine's TCE, the
published one, the error, and what the engine leaves out that the publisher
includes. An anchor whose rate is in Worldscale points is not reproducible:
the year's flat rate is licensed and no public source states it, and the
study does not back one out of the published TCE.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any

from . import baltic, cases, engine

LUMP_SUM_ROUTES = ("TD22", "TC20")


def with_inputs(inputs: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """A copy of engine inputs with values replaced at dotted paths ("war_risk.areas.gulf.premium_pct")."""
    out = dict(inputs)
    for path, new in overrides.items():
        keys = path.split(".")
        node = out
        for key in keys[:-1]:
            node[key] = dict(node[key])
            node = node[key]
        node[keys[-1]] = new
    return out


def _tce(route: str, market: cases.Market, value: float, basis: str | None = None, **overrides: Any) -> dict[str, Any]:
    case = cases.build(route, market, freight_value=value, freight_basis=basis)
    inputs = with_inputs(case.inputs, **overrides)
    result = engine.evaluate(inputs)
    return {"case": case, "result": result, "tce_usd_day": result["tce_usd_day"]}


#: The two weeks after the Strait of Hormuz closed on 2 March 2026, when the engine reads far above the
#: Baltic with bunker tables of the same week; why is not established, and they are named, not hidden.
POST_CLOSURE_WEEKS = ("2026-03-13", "2026-03-20")


def lump_sum_summary() -> dict[str, Any]:
    """The lump sum anchors grouped by how fresh their bunker table was, and how the gap moves with freight.

    Fresh: a row first printed in the anchor's own week. A week old: printed in
    the seven days before. Stale: an older row a broker reprinted. The two
    weeks after the closure of Hormuz are set apart, named.
    """
    rows = [r for r in tanker_weekly() if r["reproducible"]]
    exception = [r for r in rows if r["week_ending"] in POST_CLOSURE_WEEKS]
    rest = [r for r in rows if r["week_ending"] not in POST_CLOSURE_WEEKS]
    fresh = [r for r in rest if r["bunker_freshness"] == "fresh"]
    week_old = [r for r in rest if r["bunker_freshness"] == "week_old"]
    stale = [r for r in rest if r["bunker_freshness"] == "older"]
    usual = fresh + week_old
    td22 = [r for r in usual if r["route"] == "TD22"]
    low = min(td22, key=lambda r: r["rate_value"])
    high = max(td22, key=lambda r: r["rate_value"])

    def gap(r: dict[str, Any]) -> float:
        return r["engine_tce_usd_day"] - r["published_tce_usd_day"]

    def span(group: list[dict[str, Any]]) -> list[float]:
        return [min(r["error"] for r in group), max(r["error"] for r in group)]

    return {
        "rows": rows,
        "fresh": fresh,
        "week_old": week_old,
        "stale": stale,
        "exception": exception,
        "fresh_error": span(fresh),
        "usual_error": span(usual),
        "routes": sorted({r["route"] for r in rows}),
        "weeks": len({r["week_ending"] for r in rows}),
        "gap_low": {"row": low, "gap_usd_day": gap(low)},
        "gap_high": {"row": high, "gap_usd_day": gap(high)},
    }


def broker_cross_check() -> dict[str, Any]:
    """TD22 on the cross-check date priced at another broker's Houston prices, against the table the study uses."""
    from dataclasses import replace

    spec = cases.seed("market.json")["broker_cross_check"]
    date = spec["date"]
    row = next(r for r in tanker_weekly() if r["route"] == "TD22" and r["week_ending"] == date)
    market = cases.weekly_market(date, "houston")
    other = dict(market.bunkers)
    other["houston"] = {
        grade: (float(spec["prices"]["houston"][i]), spec["source"]) for i, grade in enumerate(cases.GRADES)
    }
    priced = _tce("TD22", replace(market, bunkers=other), row["rate_value"], "lump_sum")
    return {
        "date": date,
        "source": spec["source"],
        "vlsfo_study_usd_t": market.bunkers["houston"]["vlsfo"][0],
        "vlsfo_other_usd_t": spec["prices"]["houston"][0],
        "error_study": row["error"],
        "error_other": priced["tce_usd_day"] / row["published_tce_usd_day"] - 1.0,
    }


def early_march_market(date: str) -> cases.Market:
    """The market of an early March anchor: the weekly table of up to seven days before, else the quarter's averages."""
    hub = cases.route_hub(baltic.ROUTES["TD3C"])
    try:
        return cases.weekly_market(date, hub)
    except ValueError:
        return cases.quarter_market("%s-Q%d" % (date[:4], (int(date[5:7]) - 1) // 3 + 1), date)


#: Bunker prices up to this many days older than the assessment still count as the week before's.
WEEK_DAYS = 7


def _freshness(age_days: int) -> str:
    """How old a row's bunker prices were: first printed that week, up to a week before, or older."""
    if age_days == 0:
        return "fresh"
    return "week_old" if age_days <= WEEK_DAYS else "older"


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
                hub = cases.route_hub(baltic.ROUTES[route])
                try:
                    market = cases.weekly_market(report["week_ending"], hub)
                except ValueError:
                    row["reason"] = "no bunker table retrieved from within a week before the assessment"
                else:
                    computed = _tce(route, market, entry["rate_value"], "lump_sum")
                    first = market.bunkers_first_printed[hub]
                    row.update(
                        reproducible=True,
                        engine_tce_usd_day=computed["tce_usd_day"],
                        error=computed["tce_usd_day"] / entry["tce_usd_day"] - 1.0,
                        bunkers=market.label,
                        bunkers_first_printed=first,
                        bunker_age_days=(_date.fromisoformat(report["week_ending"]) - _date.fromisoformat(first)).days,
                        bunker_freshness=_freshness(
                            (_date.fromisoformat(report["week_ending"]) - _date.fromisoformat(first)).days
                        ),
                        excluded=computed["case"].excluded,
                    )
            out.append(row)
    return out


def early_march() -> list[dict[str, Any]]:
    """TD3C priced at the early March 2026 rates, against the TCEs reported the same week."""
    items = {item["id"]: item for item in cases.seed("anchors.json")["early_march_2026"]["items"]}
    hull = cases.seed("market.json")["hull_values_usd"]["march_2026_vlcc"]["value"]
    premium = next(r for r in cases.seed("market.json")["war_risk"]["rates_pct"] if r["id"] == "hormuz_2026_03_early")[
        "low"
    ]
    rows = []
    for item_id in ("platts_pg_china_2025_12_12", "platts_pg_china_2026_03_02", "oilprice_gulf_china_2026_03_03"):
        item = items[item_id]
        market = early_march_market(item["date"])
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
            # A scenario, not the Baltic's basis: the premium in the owner's costs, as if the freight carried it.
            war = _tce(
                "TD3C",
                market,
                item["freight_usd_t"],
                "usd_t",
                **{
                    "war_risk.areas.gulf.premium_pct": premium,
                    "war_risk.hull_value_usd": float(hull),
                    "war_risk.payer": "owner",
                },
            )
            row["engine_tce_with_war_risk_usd_day"] = war["tce_usd_day"]
            row["war_risk_usd"] = war["result"]["costs"]["war_risk"]
            row["war_risk_periods"] = war["result"]["war_risk"]["areas"]["gulf"]["periods"]
            row["war_risk_days_inside"] = war["result"]["war_risk"]["areas"]["gulf"]["days"]
        rows.append(row)
    return rows


def capesize_basis_2026_07_03() -> dict[str, Any]:
    """Which ship the C5TC average of 3 July 2026 is for: the BCI and BDI printed the same day decide it.

    The BCI is the 182,000 t basket times 0.11026 and the BDI weighs the C5TC,
    P5TC and S11TC (GMB v8.8 page 76); with the printed average as the 180,000 t
    basis the 182,000 t basket is 3,503 higher (page 77).
    """
    weeks = cases.seed("anchors.json")["dry_weekly"]["weeks"]
    signal = next(w for w in weeks if w["raw_key"] == "dry_hsn_p1140060_wk27_2026_html")["values"]
    banchero = next(w for w in weeks if w["raw_key"] == "dry_bancosta_weekly_2026_wk27_pdf")["values"]
    printed = signal["C5TC_usd_day"]

    def indices(basket_182: float) -> tuple[float, float]:
        bci = round(basket_182) * baltic.BCI_FACTOR
        weights = baltic.BDI_WEIGHTS
        bdi = (
            round(
                basket_182 * weights["C5TC"]
                + banchero["P5TC_usd_day"] * weights["P5TC"]
                + banchero["S11TC_usd_day"] * weights["S11TC"]
            )
            * baltic.BDI_FACTOR
        )
        return bci, bdi

    as_180 = indices(printed + baltic.C5TC_180_DIFFERENTIAL)
    as_182 = indices(printed)
    return {
        "printed_usd_day": printed,
        "basket_182_if_180_usd_day": printed + baltic.C5TC_180_DIFFERENTIAL,
        "bci_published": signal["BCI"],
        "bdi_published": signal["BDI"],
        "bci_if_180": as_180[0],
        "bdi_if_180": as_180[1],
        "bci_if_182": as_182[0],
        "bdi_if_182": as_182[1],
        "basis": "180" if round(as_180[0]) == signal["BCI"] and round(as_180[1]) == signal["BDI"] else "182",
    }


def dry_weekly() -> list[dict[str, Any]]:
    """The Capesize and Panamax rates of the anchor weeks, as TCEs beside the time charter averages.

    The averages are gross daily hire and the TCEs net of the 5 percent
    commission, so each TCE is also grossed up by its commission (GMB v8.8
    section 7.4.3) and the gap is taken on that one basis, against the average
    for the ship the study prices (the 182,000 t Capesize).
    """
    weeks = cases.seed("anchors.json")["dry_weekly"]["weeks"]
    basis_0703 = capesize_basis_2026_07_03()
    rows = []
    plan = (
        ("2026-07-03", "dry_bancosta_weekly_2026_wk27_pdf", ("C3", "C5"), "C5TC_usd_day"),
        ("2026-10-23", "dry_bancosta_weekly_2026_wk43_pdf", ("C3", "C5"), "C5TC_182_usd_day"),
        ("2026-09-11", "dry_hsn_panamax_in_focus_2026_html", ("P7",), "P5TC_usd_day"),
    )
    for date, key, routes, benchmark in plan:
        week = next(w for w in weeks if w["date"] == date and w["raw_key"] == key)
        printed = week["values"][benchmark]
        if benchmark == "C5TC_usd_day":
            basis = basis_0703["basis"]
            like_for_like = printed + (baltic.C5TC_180_DIFFERENTIAL if basis == "180" else 0.0)
        else:
            basis = "182" if benchmark == "C5TC_182_usd_day" else ""
            like_for_like = printed
        for route in routes:
            hub = cases.route_hub(baltic.ROUTES[route])
            market = cases.weekly_market(date, hub)
            rate = week["values"]["%s_usd_t" % route]
            computed = _tce(route, market, rate, "usd_t")
            keep = 1.0 - computed["case"].inputs["commission_pct"] / engine.PERCENT
            gross = computed["tce_usd_day"] / keep
            rows.append(
                {
                    "date": date,
                    "route": route,
                    "freight_usd_t": rate,
                    "engine_tce_usd_day": computed["tce_usd_day"],
                    "engine_tce_gross_usd_day": gross,
                    "benchmark": benchmark,
                    "benchmark_usd_day": printed,
                    "benchmark_basis": basis,
                    "benchmark_182_usd_day": like_for_like,
                    "gap_usd_day": gross - like_for_like,
                    "bunkers": market.label,
                    "hub": hub,
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
