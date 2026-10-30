#!/usr/bin/env python
"""Write data/fixtures/engine-cases.json: engine inputs and the Python engine's full output.

src/engine.js prices the calculator in the browser; tools/validate-engine.mjs
runs it on these cases with plain node and requires every output to agree with
voyage.engine to 1e-9. The cases are:

* 240 random voyages from a fixed seed, so the file is the same on every run:
  voyage and trip charters, every freight basis, two and four point speed
  curves, speeds inside and outside the published pairs (the power law), ECA
  miles, scrubbers, every ETS share and phase-in, FuelEU in and out of the TCE,
  war risk in two listed areas paid by either party, ballast transits paid by
  the owner, canal and port costs,
  zero cost lines;
* every anchor the study reproduces (the lump sum tanker weeks, the early March
  VLCC rates, the dry weeks), and every study route on the common market;
* edge cases named in their "edge" field: a zero length ballast leg, a speed
  exactly on a published pair, an ECA longer than its leg, seven days and a
  moment over seven days in a listed area.

For each case the file holds evaluate(), the freight for two target TCEs, the
sensitivities, the hedge against a time charter and a route FFA and, for every
fifth case, the best speed on the grid.

    python scripts/gen_fixtures.py           write the file
    python scripts/gen_fixtures.py --check   compare with the committed file
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voyage import anchors, baltic, cases, engine  # noqa: E402

SCHEMA_VERSION = 1
CASES = 240
SEED = 20261029
OUT = ROOT / "data" / "fixtures" / "engine-cases.json"


def _curve(rng: random.Random, points: int) -> list[list[float]]:
    top = rng.uniform(11.0, 15.5)
    step = rng.uniform(0.5, 1.5)
    speeds = [round(top - k * step, 2) for k in range(points)]
    tpd = rng.uniform(12.0, 70.0)
    curve = []
    for v in speeds:
        curve.append([v, round(tpd * (v / top) ** rng.uniform(2.2, 3.4), 3)])
    rng.shuffle(curve)
    return curve


def _port(rng: random.Random) -> dict:
    port = {}
    for activity in ("load", "discharge", "waiting", "canal", "delay", "sts"):
        port[activity + "_days"] = round(rng.choice([0.0, rng.uniform(0.25, 12.0)]), 4)
        port[activity + "_tpd"] = round(rng.choice([0.0, rng.uniform(2.0, 120.0)]), 3)
        port[activity + "_eca"] = rng.random() < 0.4
        port[activity + "_ets_share"] = rng.choice([0.0, 0.5, 1.0])
    return port


def _war_area(rng: random.Random) -> dict:
    return {
        "premium_pct": rng.choice([0.0, 0.25, 0.5, 2.5, 7.5]),
        "entries": rng.choice([0, 0, 1, 2]),
        "laden_nm": round(rng.choice([0.0, rng.uniform(50.0, 900.0)]), 1),
        "ballast_nm": round(rng.choice([0.0, rng.uniform(50.0, 900.0)]), 1),
        "port_activities": sorted(rng.sample(["load", "discharge", "waiting", "delay", "sts"], rng.randint(0, 3))),
        "ballast_transits": rng.choice([0, 0, 1, 2]),
    }


def random_case(rng: random.Random, number: int) -> dict:
    trip = number % 6 == 5
    basis = "hire_usd_day" if trip else rng.choice(["usd_t", "ws", "lump_sum"])
    cargo = round(rng.uniform(25000.0, 280000.0), 1)
    flat = round(rng.uniform(5.0, 30.0), 3) if basis == "ws" or rng.random() < 0.3 else None
    value = {
        "hire_usd_day": rng.uniform(-5000.0, 400000.0),
        "usd_t": rng.uniform(5.0, 120.0),
        "ws": rng.uniform(40.0, 1400.0),
        "lump_sum": rng.uniform(1e6, 8e7),
    }[basis]
    points = rng.choice([2, 4])
    laden_curve = _curve(rng, points)
    ballast_curve = _curve(rng, points)
    speeds = sorted(v for v, _ in laden_curve)

    def leg() -> dict:
        distance = round(
            rng.choice([0.0, rng.uniform(150.0, 16000.0)]) if number % 17 == 3 else rng.uniform(150.0, 16000.0), 1
        )
        speed = round(rng.uniform(speeds[0] - 2.0, speeds[-1] + 1.5), 3)
        return {
            "distance_nm": distance,
            "speed_kn": speed,
            "eca_nm": round(rng.uniform(0.0, distance * 0.6), 1),
            "ets_share": rng.choice([0.0, 0.5, 1.0]),
        }

    return {
        "contract": "trip" if trip else "voyage",
        "freight_basis": basis,
        "freight_value": round(value, 4),
        "flat_rate_usd_t": flat,
        "cargo_t": cargo,
        "commission_pct": rng.choice([0.0, 1.25, 2.5, 3.75, 5.0, 6.25]),
        "other_revenue_usd": round(rng.choice([0.0, rng.uniform(0.0, 500000.0)]), 2),
        "sea_margin": rng.choice([0.0, 0.05, 0.1]),
        "laden": leg(),
        "ballast": leg(),
        "laden_curve": laden_curve,
        "ballast_curve": ballast_curve,
        "mgo_at_sea_tpd": rng.choice([0.0, 0.1, 0.5]),
        "scrubber": rng.random() < 0.3,
        "scrubber_in_eca": rng.random() < 0.5,
        "vlsfo_class": rng.choice(["HFO", "LFO"]),
        "port": _port(rng),
        "prices": {
            "vlsfo_usd_t": round(rng.uniform(400.0, 1200.0), 2),
            "hsfo_usd_t": round(rng.uniform(300.0, 950.0), 2),
            "mgo_usd_t": round(rng.uniform(600.0, 1800.0), 2),
        },
        "ets": {
            "phase_in": rng.choice([0.0, 0.4, 0.7, 1.0]),
            "eua_eur_t": round(rng.uniform(50.0, 100.0), 2),
            "usd_per_eur": round(rng.uniform(1.0, 1.25), 6),
            "include_non_co2": rng.random() < 0.5,
        },
        "fueleu": {"include": rng.random() < 0.5, "reduction_pct": rng.choice([2.0, 6.0])},
        "costs": {
            "port_load_usd": round(rng.choice([0.0, rng.uniform(0.0, 600000.0)]), 2),
            "port_discharge_usd": round(rng.choice([0.0, rng.uniform(0.0, 600000.0)]), 2),
            "canal_laden_usd": round(rng.choice([0.0, rng.uniform(0.0, 900000.0)]), 2),
            "canal_ballast_usd": round(rng.choice([0.0, rng.uniform(0.0, 700000.0)]), 2),
            "other_usd": round(rng.choice([0.0, rng.uniform(0.0, 300000.0)]), 2),
            "sts_usd": round(rng.choice([0.0, rng.uniform(0.0, 300000.0)]), 2),
        },
        "war_risk": {
            "hull_value_usd": round(rng.uniform(2e7, 2e8), 0),
            "crew_bonus_usd": round(rng.choice([0.0, 50000.0]), 2),
            "payer": rng.choice(["owner", "charterer"]),
            "areas": {"gulf": _war_area(rng), "red_sea": _war_area(rng)},
        },
    }


def study_cases() -> list[tuple[str, dict]]:
    """The inputs of every reproduced anchor and of every study route on the common market."""
    out = []
    for row in anchors.tanker_weekly():
        if row["reproducible"]:
            hub = cases.route_hub(baltic.ROUTES[row["route"]])
            market = cases.weekly_market(row["week_ending"], hub)
            case = cases.build(row["route"], market, freight_value=row["rate_value"], freight_basis="lump_sum")
            out.append(("anchor %s %s" % (row["route"], row["week_ending"]), case.inputs))
        elif row.get("implied"):
            # A Worldscale week priced at the flat rate a cited pair implies, as anchors.tanker_weekly prices it.
            hub = cases.route_hub(baltic.ROUTES[row["route"]])
            market = cases.weekly_market(row["week_ending"], hub)
            case = cases.build(row["route"], market, freight_value=row["freight_usd_t"], freight_basis="usd_t")
            out.append(("anchor %s %s at the implied flat rate" % (row["route"], row["week_ending"]), case.inputs))
    for row in anchors.dry_weekly():
        hub = cases.route_hub(baltic.ROUTES[row["route"]])
        case = cases.build(row["route"], cases.weekly_market(row["date"], hub), freight_value=row["freight_usd_t"])
        out.append(("anchor %s %s" % (row["route"], row["date"]), case.inputs))
    for row in anchors.early_march():
        market = anchors.early_march_market(row["date"])
        case = cases.build("TD3C", market, freight_value=row["freight_usd_t"], freight_basis="usd_t")
        out.append(("anchor TD3C %s" % row["id"], case.inputs))
    common = cases.common_market()
    for code in baltic.STUDY_ROUTES + baltic.SUPPORT_ROUTES:
        basis = None if baltic.ROUTES[code].unit != "WS" else "usd_t"
        value = {"USD/t": 30.0, "WS": 30.0, "USD lump sum": 2.0e7, "USD/day": 25000.0}[baltic.ROUTES[code].unit]
        case = cases.build(code, common, freight_value=value, freight_basis=basis)
        out.append(("route %s on the common market" % code, case.inputs))
    return out


def edge_cases(rng: random.Random) -> list[tuple[str, dict]]:
    base = random_case(rng, 1)
    no_ballast = copy.deepcopy(base)
    no_ballast["ballast"]["distance_nm"] = 0.0
    on_pair = copy.deepcopy(base)
    on_pair["laden"]["speed_kn"] = sorted(v for v, _ in on_pair["laden_curve"])[0]
    long_eca = copy.deepcopy(base)
    long_eca["laden"]["eca_nm"] = long_eca["laden"]["distance_nm"] * 2.0
    # Seven days inside a listed area is one period; a moment more is two.
    seven = copy.deepcopy(base)
    seven["contract"], seven["freight_basis"] = "voyage", "usd_t"
    seven["war_risk"]["payer"] = "owner"
    seven["war_risk"]["areas"]["gulf"] = dict(
        premium_pct=2.5, entries=1, laden_nm=0.0, ballast_nm=0.0, port_activities=["load"], ballast_transits=0
    )
    seven["port"]["load_days"] = 7.0
    longer = copy.deepcopy(seven)
    longer["port"]["load_days"] = 7.0001
    return [
        ("zero ballast leg", no_ballast),
        ("speed on a published pair", on_pair),
        ("ECA longer than the leg", long_eca),
        ("seven days in a listed area", seven),
        ("a moment over seven days in a listed area", longer),
    ]


#: The arguments every case is called with besides its inputs, written into
#: each case so that the JavaScript makes the same calls.
TARGET_TCE_USD_DAY = 25000.0
TC_FFA_USD_DAY = 30000.0
ROUTE_FFA_FACTOR = 0.9
SPEED_BOUNDS_KN = [9.0, 15.0]


def calls(inputs: dict, number: int) -> dict:
    route_ffa = None if inputs["contract"] == "trip" else engine.freight_usd_t(inputs) * ROUTE_FFA_FACTOR
    return {
        "target_tce_usd_day": TARGET_TCE_USD_DAY,
        "tc_ffa_usd_day": TC_FFA_USD_DAY,
        "route_ffa_usd_t": route_ffa,
        "speed_bounds_kn": SPEED_BOUNDS_KN if number % 5 == 0 else None,
    }


def outputs(inputs: dict, call: dict) -> dict:
    physical = engine.evaluate(inputs)
    out = {
        "evaluate": physical,
        "breakeven_zero": engine.freight_for_tce(inputs, 0.0),
        "breakeven_target": engine.freight_for_tce(inputs, call["target_tce_usd_day"]),
        "sensitivities": engine.sensitivities(inputs),
        "hedge": engine.hedge(inputs, physical["tce_usd_day"], call["tc_ffa_usd_day"], call["route_ffa_usd_t"]),
        "power_fit": engine.power_fit(inputs["laden_curve"]),
    }
    if call["speed_bounds_kn"] is not None:
        out["optimal"] = engine.optimal_speed(inputs, *call["speed_bounds_kn"])
    return out


def row(name: str, inputs: dict, number: int, edge: str | None = None) -> dict:
    call = calls(inputs, number)
    out = {"name": name, "inputs": inputs, "calls": call, "output": outputs(inputs, call)}
    if edge:
        out["edge"] = edge
    return out


def build() -> dict:
    rng = random.Random(SEED)
    rows = [row("random %d" % number, random_case(rng, number), number) for number in range(CASES)]
    rows += [row(name, inputs, 0, edge=name) for name, inputs in edge_cases(rng)]
    rows += [row(name, inputs, number) for number, (name, inputs) in enumerate(study_cases())]
    return {"schema_version": SCHEMA_VERSION, "seed": SEED, "constants": engine.constants(), "cases": rows}


def dumps(document: dict) -> str:
    return json.dumps(document, indent=1, ensure_ascii=True, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = dumps(build())
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("%s %s" % (OUT.relative_to(ROOT), "matches" if same else "differs from a rebuild"))
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %d cases" % (OUT.relative_to(ROOT), text.count('"name"')))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
