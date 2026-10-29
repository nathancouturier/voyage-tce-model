#!/usr/bin/env python
"""Compute the sea routes once with searoute and commit them as a seed. Nothing else runs searoute.

    python scripts/routes.py           compute, check and write data/seed/sea_routes.*
    python scripts/routes.py --check   compute and compare with the committed seed, write nothing

Every ordered pair of study ports (voyage.ports) is computed under each routing
of voyage.sea_routes.ROUTINGS, and each check of voyage.distance_checks is
measured against its Pub. 151 figure. The distances, the passages searoute
reports and the checks go to data/seed/sea_routes.json; every line goes to
data/seed/sea_routes.geojson.gz, gzipped with no timestamp so the bytes are
reproducible. searoute is installed only where this script runs:

    python -m pip install -e ".[routes]"
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import distance_checks, geo, jsonio, ports, sea_routes  # noqa: E402

SEED = REPO_ROOT / "data" / "seed"
DOCUMENT = SEED / "sea_routes.json"
LINES = SEED / "sea_routes.geojson.gz"
PLACES = 4


def route(searoute, origin: tuple[float, float], destination: tuple[float, float], routing: str) -> dict:
    feature = searoute.searoute(
        [origin[0], origin[1]],
        [destination[0], destination[1]],
        units="naut",
        restrictions=list(sea_routes.ROUTINGS[routing]),
        return_passages=True,
    )
    coordinates = [[round(float(x), PLACES), round(float(y), PLACES)] for x, y in feature["geometry"]["coordinates"]]
    return {
        "distance_nm": round(float(feature["properties"]["length"]), 1),
        "passages": sorted(feature["properties"].get("traversed_passages") or []),
        "coordinates": coordinates,
    }


def compute() -> tuple[dict, dict]:
    import searoute  # only this script needs it

    version = getattr(searoute, "__version__", None)
    if version != sea_routes.SEAROUTE_VERSION:
        raise SystemExit(
            "searoute %s is installed; the seed is defined for %s" % (version, sea_routes.SEAROUTE_VERSION)
        )

    study = ports.load()
    legs: dict[str, dict] = {}
    features = []
    for origin in study.values():
        for destination in study.values():
            if origin.id == destination.id:
                continue
            for routing in sea_routes.ROUTINGS:
                result = route(searoute, (origin.lon, origin.lat), (destination.lon, destination.lat), routing)
                key = sea_routes.leg_key(origin.id, destination.id, routing)
                nearest = sea_routes.passes(result["coordinates"])
                legs[key] = {
                    "from": origin.id,
                    "to": destination.id,
                    "routing": routing,
                    "distance_nm": result["distance_nm"],
                    "passages_reported_by_searoute": result["passages"],
                    "passes": sea_routes.passed(nearest),
                    "vertices": len(result["coordinates"]),
                }
                features.append(
                    {
                        "type": "Feature",
                        "id": key,
                        "properties": {"distance_nm": result["distance_nm"]},
                        "geometry": {"type": "LineString", "coordinates": result["coordinates"]},
                    }
                )

    checks = []
    for check in distance_checks.CHECKS:
        a = distance_checks.POSITIONS[check.origin]
        b = distance_checks.POSITIONS[check.destination]
        result = route(searoute, (a[0], a[1]), (b[0], b[1]), check.routing)
        error = result["distance_nm"] / check.published_nm - 1.0
        checks.append(
            {
                "id": check.id,
                "from": check.origin,
                "to": check.destination,
                "from_position": a[2],
                "to_position": b[2],
                "routing": check.routing,
                "published_nm": check.published_nm,
                "parts": [{"entry": p.entry, "line": p.line, "nm": p.nm, "page": p.page} for p in check.parts],
                "adjustment_nm": check.adjustment_nm,
                "composite": check.composite,
                "searoute_nm": result["distance_nm"],
                "error": round(error, 6),
                "within_tolerance": abs(error) <= distance_checks.TOLERANCE,
                "note": check.note,
            }
        )

    document = {
        "schema_version": 1,
        "library": {
            "name": "searoute",
            "version": sea_routes.SEAROUTE_VERSION,
            "licence": "Apache License 2.0",
            "url": "https://github.com/genthalili/searoute-py",
            "network": "Eurostat SeaRoute maritime network, as bundled with the library (EUPL 1.2)",
        },
        "units": {"distance": "nautical miles"},
        "routings": {
            name: {"avoids": list(avoid), "label": sea_routes.ROUTING_LABELS[name]}
            for name, avoid in sea_routes.ROUTINGS.items()
        },
        "reference_points": {
            name: {"lon": lon, "lat": lat, "within_nm": radius}
            for name, (lon, lat, radius) in sea_routes.REFERENCE_POINTS.items()
        },
        "ports": ports.as_records(study),
        "legs": legs,
        "pub151_checks": {
            "source": "NGA Pub. 151, Distances Between Ports, 11th edition, 2001",
            "tolerance": distance_checks.TOLERANCE,
            "checks": checks,
        },
    }
    geojson = {"type": "FeatureCollection", "features": features}
    return document, geojson


def write_lines(geojson: dict) -> None:
    text = json.dumps(geojson, separators=(",", ":"), ensure_ascii=True) + "\n"
    LINES.write_bytes(gzip.compress(text.encode("ascii"), mtime=0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed seed, write nothing")
    args = parser.parse_args(argv)

    document, geojson = compute()
    lines = {f["id"]: f["geometry"]["coordinates"] for f in geojson["features"]}
    problems = sea_routes.leg_problems(document, lines)
    for check in document["pub151_checks"]["checks"]:
        print(
            "%-26s published %6d nm  searoute %8.1f nm  %+6.2f%%  %s"
            % (
                check["id"],
                check["published_nm"],
                check["searoute_nm"],
                100 * check["error"],
                "ok" if check["within_tolerance"] else "OUTSIDE 2%",
            )
        )
    for origin, destination, routing, _, _ in sea_routes.STUDY_LEGS:
        leg = document["legs"][sea_routes.leg_key(origin, destination, routing)]
        print(
            "%-44s %8.1f nm  passes %s"
            % (sea_routes.leg_key(origin, destination, routing), leg["distance_nm"], ", ".join(leg["passes"]))
        )
    if problems:
        print("\nthe computed routes fail their own checks:")
        for problem in problems:
            print("  " + problem)
        return 1
    if args.check:
        committed = jsonio.read(DOCUMENT)
        same = committed == json.loads(jsonio.dumps(document))
        print("\ncommitted seed %s the computation" % ("matches" if same else "DIFFERS FROM"))
        return 0 if same else 1
    jsonio.write(DOCUMENT, document)
    write_lines(geojson)
    print(
        "\nwrote %s and %s, %d legs, %.0f nm of line"
        % (
            DOCUMENT.relative_to(REPO_ROOT),
            LINES.relative_to(REPO_ROOT),
            len(lines),
            sum(geo.polyline_length_nm(c) for c in lines.values()),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
