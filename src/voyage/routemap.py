"""The maps of the voyages, drawn once here as SVG path strings for the page to render.

Land is Natural Earth's 1:110m land as world-atlas 2.0.2 packs it
(vendor/world-atlas/land-110m.json, the sibling studies' copy); the routes are
the very lines the distances are measured on (data/seed/sea_routes.geojson.gz),
so the map and the tables cannot disagree. The page needs no map library and
makes no request for map data.

THE PROJECTION. Equirectangular, from 245 degrees west to 155 degrees east,
more than a whole turn, because the Panama routes to China run west across the
Pacific while the others run east: East Asia is drawn at both edges and each
line is placed where it runs continuously. Latitudes from 50 south to 72 north.
Each voyage carries its own view box, the box round its lines with a margin, so
the page shows the part of the world the voyage sails.

THE LEGS. The laden leg is drawn as it sails; the ballast leg, which often
follows the same water back, is drawn a few map units to its side so both are
visible. The stretches inside an emission control area in force on the voyage
date are cut out of each leg as their own paths. The ports are given as points;
the page places their names at the size it draws them (src/map.js), where no
line runs through them and no other word lies under them.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from . import cases, eca, geo, sea_routes
from .sources import base

LAND = base.REPO_ROOT / "vendor" / "world-atlas" / "land-110m.json"

LON_MIN, LON_MAX = -245.0, 155.0
LAT_MIN, LAT_MAX = -50.0, 72.0
#: Map units per degree; the page scales the drawing to its width.
PX_PER_DEGREE = 2.4
PLACES = 1
#: The ballast leg's distance from the laden leg, and the margin round a voyage's view box, in map units.
BALLAST_OFFSET = 2.6
VIEW_MARGIN = 26.0
#: Lines are simplified to this tolerance in map units before they are written.
SIMPLIFY = 0.35
#: The step at which a leg is tested against the emission control areas, in nautical miles.
ECA_STEP_NM = 4.0

Point = tuple[float, float]


def decode_topojson(topology: Mapping[str, Any]) -> list[list[list[Point]]]:
    """The polygons of a TopoJSON land object as rings of (lon, lat).

    Arcs are delta encoded and quantized; a negative arc index ~i is arc i
    reversed; consecutive arcs of a ring share their joining point, kept once."""
    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]
    arcs = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        arcs.append(points)

    def ring(indices: Sequence[int]) -> list[Point]:
        out: list[Point] = []
        for index in indices:
            points = arcs[index] if index >= 0 else list(reversed(arcs[~index]))
            out.extend(points if not out else points[1:])
        return out

    polygons = []
    for geometry in topology["objects"]["land"]["geometries"]:
        if geometry["type"] == "Polygon":
            polygons.append([ring(r) for r in geometry["arcs"]])
        elif geometry["type"] == "MultiPolygon":
            polygons.extend([ring(r) for r in polygon] for polygon in geometry["arcs"])
    return polygons


def project(lon: float, lat: float) -> Point:
    """Map coordinates: x east from the left edge, y down from the top."""
    return (lon - LON_MIN) * PX_PER_DEGREE, (LAT_MAX - lat) * PX_PER_DEGREE


def unwrap(points: Sequence[Sequence[float]]) -> list[Point]:
    """A line or ring with its longitudes made continuous: each step taken the short way round."""
    out = [(float(points[0][0]), float(points[0][1]))]
    for lon, lat in points[1:]:
        lon += 360.0 * round((out[-1][0] - lon) / 360.0)
        out.append((lon, float(lat)))
    return out


def _fmt(value: float) -> str:
    text = "%.*f" % (PLACES, value)
    return "0.0" if text == "-0.0" else text


def path_d(points: Sequence[Point], close: bool = False) -> str:
    """An SVG path from map points, repeated points dropped."""
    parts = []
    last = None
    for index, (x, y) in enumerate(points):
        text = "%s %s" % (_fmt(x), _fmt(y))
        if text == last:
            continue
        parts.append(("M" if index == 0 else "L") + text)
        last = text
    return "".join(parts) + ("Z" if close else "")


def land_path() -> str:
    """Every land ring in the window, drawn at each whole turn where it falls in the window."""
    topology = json.loads(LAND.read_text(encoding="utf-8"))
    out = []
    for polygon in decode_topojson(topology):
        for ring in polygon:
            ring = unwrap(ring)
            if abs(ring[-1][0] - ring[0][0]) > 180.0:
                pole = 90.0 if sum(lat for _, lat in ring) > 0 else -90.0
                ring += [(ring[-1][0], pole), (ring[0][0], pole)]
            lats = [lat for _, lat in ring]
            if max(lats) < LAT_MIN or min(lats) > LAT_MAX:
                continue
            for turns in (-2, -1, 0, 1):
                lons = [lon + 360.0 * turns for lon, _ in ring]
                if max(lons) < LON_MIN or min(lons) > LON_MAX:
                    continue
                points = [project(lon + 360.0 * turns, lat) for lon, lat in ring]
                out.append(path_d(simplify(points, SIMPLIFY), close=True))
    return "".join(out)


def simplify(points: Sequence[Point], tolerance: float) -> list[Point]:
    """Ramer, Douglas and Peucker, iterative, keeping both ends."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = points[first]
        bx, by = points[last]
        dx, dy = bx - ax, by - ay
        span = math.hypot(dx, dy)
        best, index = -1.0, -1
        for k in range(first + 1, last):
            px, py = points[k]
            if span == 0.0:
                distance = math.hypot(px - ax, py - ay)
            else:
                distance = abs(dy * px - dx * py + bx * ay - by * ax) / span
            if distance > best:
                best, index = distance, k
        if best > tolerance and index > 0:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [p for p, k in zip(points, keep, strict=True) if k]


def _shift_into_window(line: list[Point]) -> list[Point]:
    """The unwrapped line moved by whole turns so most of it lies in the window."""
    best, best_turns = -1.0, 0
    for turns in (-1, 0, 1):
        inside = sum(1 for lon, _ in line if LON_MIN <= lon + 360.0 * turns <= LON_MAX)
        if inside > best:
            best, best_turns = inside, turns
    return [(lon + 360.0 * best_turns, lat) for lon, lat in line]


def offset(points: Sequence[Point], distance: float) -> list[Point]:
    """The line moved sideways by a distance in map units, to its left as drawn."""
    if len(points) < 2:
        return list(points)
    normals = []
    for (ax, ay), (bx, by) in itertools.pairwise(points):
        length = math.hypot(bx - ax, by - ay) or 1.0
        normals.append((-(by - ay) / length, (bx - ax) / length))
    out = []
    for index, (x, y) in enumerate(points):
        if index == 0:
            nx, ny = normals[0]
        elif index == len(points) - 1:
            nx, ny = normals[-1]
        else:
            ax, ay = normals[index - 1]
            bx, by = normals[index]
            nx, ny = ax + bx, ay + by
            length = math.hypot(nx, ny) or 1.0
            nx, ny = nx / length, ny / length
        out.append((x + nx * distance, y + ny * distance))
    return out


def eca_runs(coordinates: Sequence[Sequence[float]], on_date: str) -> list[list[Point]]:
    """The stretches of a line inside an emission control area in force on a date, as lon, lat runs."""
    zones = eca.in_force(cases.zones(), on_date)
    runs: list[list[Point]] = []
    current: list[Point] = []
    for a, b, _ in geo.densify(coordinates, ECA_STEP_NM):
        middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        inside = any(geo.point_in_polygon(middle, zone.rings) for zone in zones)
        if inside:
            if not current:
                current.append(a)
            current.append(b)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def leg_drawing(origin: str, destination: str, routing: str, on_date: str, side: float) -> dict[str, Any]:
    """One leg: its path, its emission control area stretches and its box, in map units."""
    key = sea_routes.leg_key(origin, destination, routing)
    raw = cases.lines()[key]
    line = _shift_into_window(unwrap(raw))
    projected = [project(lon, lat) for lon, lat in line]
    drawn = offset(projected, side) if side else projected
    drawn = simplify(drawn, SIMPLIFY)
    runs = []
    for run in eca_runs(raw, on_date):
        unwrapped = unwrap(run)
        # Place the run on the same turn as the leg: the copy whose start is nearest the leg's own points.
        best = None
        for t in (-1, 0, 1):
            candidate = [(lon + 360.0 * t, lat) for lon, lat in unwrapped]
            distance = min(abs(candidate[0][0] - lon) + abs(candidate[0][1] - lat) for lon, lat in line)
            if best is None or distance < best[0]:
                best = (distance, candidate)
        points = [project(lon, lat) for lon, lat in best[1]]
        if side:
            points = offset(points, side)
        runs.append(path_d(simplify(points, SIMPLIFY)))
    xs = [p[0] for p in drawn]
    ys = [p[1] for p in drawn]
    return {
        "key": key,
        "d": path_d(drawn),
        "eca": runs,
        "box": (min(xs), min(ys), max(xs), max(ys)),
        "start": drawn[0],
        "end": drawn[-1],
    }


def voyage_map(
    route: Any,
    laden_routing: str,
    ballast_routing: str,
    on_date: str,
    ballast_from: str | None = None,
) -> dict[str, Any]:
    """The drawing of one voyage: both legs, their ECA stretches, the ports and the view box."""
    ballast_from = ballast_from or route.discharge
    laden = leg_drawing(route.load, route.discharge, laden_routing, on_date, 0.0)
    same_water = ballast_from == route.discharge and ballast_routing == laden_routing
    ballast = leg_drawing(ballast_from, route.load, ballast_routing, on_date, BALLAST_OFFSET if same_water else 0.0)
    xs = [laden["box"][0], laden["box"][2], ballast["box"][0], ballast["box"][2]]
    ys = [laden["box"][1], laden["box"][3], ballast["box"][1], ballast["box"][3]]
    view = (min(xs) - VIEW_MARGIN, min(ys) - VIEW_MARGIN, max(xs) + VIEW_MARGIN, max(ys) + VIEW_MARGIN)
    records = cases.ports()
    ports = [
        {
            "id": route.load,
            "name": records[route.load]["name"],
            "x": laden["start"][0],
            "y": laden["start"][1],
            "role": "load",
        },
        {
            "id": route.discharge,
            "name": records[route.discharge]["name"],
            "x": laden["end"][0],
            "y": laden["end"][1],
            "role": "discharge",
        },
    ]
    if ballast_from not in (route.load, route.discharge):
        ports.append(
            {
                "id": ballast_from,
                "name": records[ballast_from]["name"],
                "x": ballast["start"][0],
                "y": ballast["start"][1],
                "role": "open",
            }
        )
    placed = [{**port, "x": round(port["x"], PLACES), "y": round(port["y"], PLACES)} for port in ports]
    return {
        "view_box": [
            round(view[0], PLACES),
            round(view[1], PLACES),
            round(view[2] - view[0], PLACES),
            round(view[3] - view[1], PLACES),
        ],
        "laden": {"key": laden["key"], "d": laden["d"], "eca": laden["eca"]},
        "ballast": {"key": ballast["key"], "d": ballast["d"], "eca": ballast["eca"]},
        "ports": placed,
    }


def document(voyages: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """data/map.json: the land once, and every voyage drawn."""
    return {
        "projection": {
            "name": "equirectangular",
            "lon_min": LON_MIN,
            "lon_max": LON_MAX,
            "lat_min": LAT_MIN,
            "lat_max": LAT_MAX,
            "units_per_degree": PX_PER_DEGREE,
        },
        "size": [
            round((LON_MAX - LON_MIN) * PX_PER_DEGREE, PLACES),
            round((LAT_MAX - LAT_MIN) * PX_PER_DEGREE, PLACES),
        ],
        "land": land_path(),
        "voyages": dict(voyages),
        "sources": {
            "land": "Natural Earth 1:110m land, world-atlas 2.0.2 (vendor/world-atlas/land-110m.json)",
            "routes": "searoute 1.6.0 over Eurostat SeaRoute (data/seed/sea_routes.geojson.gz)",
            "eca": "data/seed/eca.json, the areas in force on the voyage date",
        },
    }
