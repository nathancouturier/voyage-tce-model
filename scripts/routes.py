#!/usr/bin/env python
"""Compute the sea routes once with searoute and commit them as a seed. Nothing else runs searoute.

    python scripts/routes.py           compute, check and write data/seed/sea_routes.*
    python scripts/routes.py --check   compute and compare with the committed seed, write nothing

Every ordered pair of study ports (voyage.ports) is computed under each routing
of voyage.sea_routes.ROUTINGS, and each check of voyage.distance_checks is
measured against its Pub. 151 figure. A port behind land is asked from its
sea gate, and the stretch from a port far from the network is added to the
line (voyage.sea_routes.SEA_GATES and PORT_ENDS). The distances, the passages searoute
reports and the checks go to data/seed/sea_routes.json; every line goes to
data/seed/sea_routes.geojson.gz, gzipped with no timestamp so the bytes are
reproducible. searoute is installed only where this script runs:

    python -m pip install -e ".[routes]"
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import distance_checks, geo, jsonio, ports, sea_routes  # noqa: E402

SEED = REPO_ROOT / "data" / "seed"
DOCUMENT = SEED / "sea_routes.json"
LINES = SEED / "sea_routes.geojson.gz"
PLACES = 4


def ends(position: tuple[float, float], port_id: str | None) -> tuple[tuple[float, float], tuple[float, float] | None]:
    """Where searoute is asked to start or stop for a position, and the point added to the line there.

    A port with a sea gate is asked from the gate and its own position is added
    to the line; a port in PORT_ENDS is asked from itself and its position is
    added (searoute's line starts at the network node nearest it); any other
    position is asked as it is and nothing is added.
    """
    gate = sea_routes.SEA_GATES.get(port_id) if port_id else None
    if gate is not None:
        return (gate[0], gate[1]), position
    if port_id in sea_routes.PORT_ENDS:
        return position, position
    return position, None


def route(
    searoute,
    origin: tuple[float, float],
    destination: tuple[float, float],
    routing: str,
    origin_port: str | None = None,
    destination_port: str | None = None,
) -> dict:
    ask_from, add_from = ends(origin, origin_port)
    ask_to, add_to = ends(destination, destination_port)
    feature = searoute.searoute(
        [ask_from[0], ask_from[1]],
        [ask_to[0], ask_to[1]],
        units="naut",
        restrictions=list(sea_routes.restrictions(routing)),
        return_passages=True,
    )
    coordinates = [[round(float(x), PLACES), round(float(y), PLACES)] for x, y in feature["geometry"]["coordinates"]]
    distance = float(feature["properties"]["length"])
    # The stretch from a port to the network is a straight segment; searoute's
    # line may run past 180 degrees, so the added point follows its longitude.
    if add_from is not None:
        point = [round(_near(add_from[0], coordinates[0][0]), PLACES), round(add_from[1], PLACES)]
        distance += geo.haversine_nm(point, coordinates[0])
        coordinates.insert(0, point)
    if add_to is not None:
        point = [round(_near(add_to[0], coordinates[-1][0]), PLACES), round(add_to[1], PLACES)]
        distance += geo.haversine_nm(coordinates[-1], point)
        coordinates.append(point)
    return {
        "distance_nm": round(distance, 1),
        "passages": sorted(feature["properties"].get("traversed_passages") or []),
        "coordinates": coordinates,
    }


def _near(lon: float, reference: float) -> float:
    """The longitude, moved by whole turns to lie within half a turn of a reference."""
    return lon + 360.0 * round((reference - lon) / 360.0)


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
    asked = [
        (origin, destination, routing)
        for origin in study.values()
        for destination in study.values()
        if origin.id != destination.id
        for routing in sea_routes.ROUTINGS
    ] + [(study[o], study[d], routing) for o, d, routing in sea_routes.SPECIAL_LEGS]
    for origin, destination, routing in asked:
        result = route(
            searoute,
            (origin.lon, origin.lat),
            (destination.lon, destination.lat),
            routing,
            origin.id,
            destination.id,
        )
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
        result = route(
            searoute,
            (a[0], a[1]),
            (b[0], b[1]),
            check.routing,
            distance_checks.STUDY_PORTS.get(check.origin),
            distance_checks.STUDY_PORTS.get(check.destination),
        )
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
            for name, avoid in {**sea_routes.ROUTINGS, **sea_routes.SPECIAL_ROUTINGS}.items()
        },
        "special_legs": [list(leg) for leg in sea_routes.SPECIAL_LEGS],
        "reference_points": {
            name: {"lon": lon, "lat": lat, "within_nm": radius}
            for name, (lon, lat, radius) in sea_routes.REFERENCE_POINTS.items()
        },
        "sea_gates": {
            port: {"lon": round(lon, PLACES), "lat": round(lat, PLACES), "source": why}
            for port, (lon, lat, why) in sea_routes.SEA_GATES.items()
        },
        "port_ends": dict(sea_routes.PORT_ENDS),
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
            math.fsum(geo.polyline_length_nm(c) for c in lines.values()),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
