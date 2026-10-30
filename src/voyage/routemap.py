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

THE LEGS. Both legs are written as they sail. A ballast leg that starts at the
discharge port follows the laden leg's water back, all the way or most of it
(TD22 parts only between the Strait of Malacca and the Sunda Strait), so it is
marked `beside` and the page draws it a few screen pixels to its side, at
whatever size it draws the map, so both legs show on a phone too. The stretches
inside an emission control area in force on the voyage date are cut out of each
leg as their own paths. The ports are given as points;
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
#: The margin round a voyage's view box, in map units, room for the ballast leg drawn beside the laden one too.
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
                pole = 90.0 if math.fsum(lat for _, lat in ring) > 0 else -90.0
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


def leg_drawing(origin: str, destination: str, routing: str, on_date: str) -> dict[str, Any]:
    """One leg: its path, its emission control area stretches and its box, in map units."""
    key = sea_routes.leg_key(origin, destination, routing)
    raw = cases.lines()[key]
    line = _shift_into_window(unwrap(raw))
    projected = [project(lon, lat) for lon, lat in line]
    drawn = simplify(projected, SIMPLIFY)
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
    laden = leg_drawing(route.load, route.discharge, laden_routing, on_date)
    ballast = leg_drawing(ballast_from, route.load, ballast_routing, on_date)
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
        "ballast": {
            "key": ballast["key"],
            "d": ballast["d"],
            "eca": ballast["eca"],
            "beside": ballast_from == route.discharge,
        },
        "ports": placed,
    }


# --------------------------------------------------------------------------
# The atlas: every leg of the study on one map of the world
# --------------------------------------------------------------------------

#: The atlas window, from 110 degrees west eastward to 155 degrees east and from
#: 64.5 north to 40.5 south. It leaves out the open Pacific, which only the
#: routes to China by Panama cross: their lines leave the map at its left edge
#: and come back at its right edge, and those two points are written down so
#: the page can mark them.
ATLAS_LON_MIN, ATLAS_LON_MAX = -110.0, 155.0
ATLAS_LAT_MAX, ATLAS_LAT_MIN = 64.5, -40.5
#: The margin round a route's lines when the page frames it, in map units.
ATLAS_MARGIN = 18.0
#: A route is never framed narrower than the window divided by this: the
#: framing keeps the coasts round a route in view, however short the route.
ATLAS_ZOOM_MAX = 3.0
#: Loading ports nearer each other than this, in map units, share one block of
#: labels: Ras Tanura and Jubail (about 2 units apart), Galveston and Houston
#: (about 1). New Orleans, 11 units from Galveston, keeps its own: its routes
#: are dry and show the engine's TCE, the Gulf's tankers the Baltic's.
CLUSTER_UNITS = 4.0
#: The shape of the map on a phone once a route is picked, width over height:
#: taller than the world's, so a route has room to be framed.
ATLAS_TALL_ASPECT = 1.6
#: Reference points the atlas never names: the Strait of Magellan lies south
#: of the window, and the IJsselmeer is a guard, not a passage.
UNNAMED_PASSAGES = ("Strait of Magellan", "IJsselmeer")


def atlas_window() -> tuple[float, float, float, float]:
    """The atlas window in map units: left, top, right, bottom."""
    left, top = project(ATLAS_LON_MIN, ATLAS_LAT_MAX)
    right, bottom = project(ATLAS_LON_MAX, ATLAS_LAT_MIN)
    return left, top, right, bottom


def clip_to_columns(points: Sequence[Point], left: float, right: float) -> list[dict[str, Any]]:
    """The pieces of a line between two vertical edges.

    Each piece is {"points", "cut_start", "cut_end"}, where a cut end is a
    point the edge made, not a point of the line: the line runs on beyond it.
    """
    pieces: list[dict[str, Any]] = []
    current: list[Point] = []
    cut_start = False

    def inside(p: Point) -> bool:
        return left <= p[0] <= right

    def close(cut_end: bool) -> None:
        nonlocal current
        if len(current) > 1:
            pieces.append({"points": current, "cut_start": cut_start, "cut_end": cut_end})
        current = []

    for a, b in itertools.pairwise(points):
        a_in, b_in = inside(a), inside(b)
        if a_in and not current:
            current = [a]
            cut_start = False
        if a_in and b_in:
            current.append(b)
            continue
        crossings = sorted(
            (edge - a[0]) / (b[0] - a[0]) for edge in (left, right) if (a[0] - edge) * (b[0] - edge) < 0.0
        )
        cuts = [(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])) for t in crossings]
        if a_in and not b_in:
            current.append(cuts[0])
            close(True)
        elif b_in and not a_in:
            current = [cuts[-1], b]
            cut_start = True
        elif not a_in and not b_in and len(cuts) > 1:
            current = [cuts[0], cuts[1]]
            cut_start = True
            close(True)
    close(False)
    return pieces


def atlas_pieces(coordinates: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
    """A line of (lon, lat) on the atlas: every whole turn of it that falls in the window, cut at its edges."""
    left, _, right, _ = atlas_window()
    line = unwrap(coordinates)
    out = []
    for turns in (-1, 0, 1):
        projected = [project(lon + 360.0 * turns, lat) for lon, lat in line]
        for piece in clip_to_columns(projected, left, right):
            drawn = simplify(piece["points"], SIMPLIFY)
            if len(drawn) > 1:
                out.append({**piece, "points": drawn})
    return out


def _rounded(point: Point) -> list[float]:
    return [round(point[0], PLACES), round(point[1], PLACES)]


def atlas_leg(origin: str, destination: str, routing: str, on_date: str) -> dict[str, Any]:
    """One leg on the atlas: its pieces, its ECA stretches, its box, its ends and the points where it leaves the map."""
    key = sea_routes.leg_key(origin, destination, routing)
    raw = cases.lines()[key]
    pieces = atlas_pieces(raw)
    if not pieces:
        raise ValueError("leg %s falls outside the atlas window" % key)
    eca = []
    for run in eca_runs(raw, on_date):
        eca.extend(path_d(piece["points"]) for piece in atlas_pieces(run))
    points = [p for piece in pieces for p in piece["points"]]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    starts = [piece["points"][0] for piece in pieces if not piece["cut_start"]]
    ends = [piece["points"][-1] for piece in pieces if not piece["cut_end"]]
    edges = [piece["points"][0] for piece in pieces if piece["cut_start"]]
    edges += [piece["points"][-1] for piece in pieces if piece["cut_end"]]
    return {
        "key": key,
        "from": origin,
        "to": destination,
        "routing": routing,
        "d": "".join(path_d(piece["points"]) for piece in pieces),
        "eca": eca,
        "box": [round(min(xs), PLACES), round(min(ys), PLACES), round(max(xs), PLACES), round(max(ys), PLACES)],
        "start": _rounded(starts[0]),
        "end": _rounded(ends[-1]),
        "edges": [_rounded(p) for p in edges],
    }


def frame_box(boxes: Sequence[Sequence[float]], aspect: float | None = None) -> list[float]:
    """The view the page takes to show some lines: their box with a margin, at a frame's shape.

    The box grows to the frame's width over height (the window's own unless
    another is given), never narrower than the window over ATLAS_ZOOM_MAX, and
    is moved to lie inside the window; one wider or taller than the window is
    the window, at that shape. A taller frame may reach the projection's own
    top and bottom, where the land still runs; lines too wide for it at its
    shape take the window's frame instead, so no frame ever cuts a line off.
    Written as [x, y, width, height].
    """
    left, top, right, bottom = atlas_window()
    width, height = right - left, bottom - top
    x0 = min(b[0] for b in boxes) - ATLAS_MARGIN
    y0 = min(b[1] for b in boxes) - ATLAS_MARGIN
    x1 = max(b[2] for b in boxes) + ATLAS_MARGIN
    y1 = max(b[3] for b in boxes) + ATLAS_MARGIN
    if aspect is not None:
        top, bottom = 0.0, (LAT_MAX - LAT_MIN) * PX_PER_DEGREE
        height = bottom - top
        if max(x1 - x0, (y1 - y0) * aspect) > height * aspect:
            return frame_box(boxes)
    else:
        aspect = width / height
    w = max(x1 - x0, (y1 - y0) * aspect, width / ATLAS_ZOOM_MAX)
    h = w / aspect
    if h > height:
        h, w = height, height * aspect
    if w >= width:
        w = width
        h = min(w / aspect, height)
        return [round(left, PLACES), round(top + (height - h) / 2.0, PLACES), round(w, PLACES), round(h, PLACES)]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    x = min(max(cx - w / 2.0, left), right - w)
    y = min(max(cy - h / 2.0, top), bottom - h)
    return [round(x, PLACES), round(y, PLACES), round(w, PLACES), round(h, PLACES)]


def atlas_document(on_date: str) -> dict[str, Any]:
    """The atlas block of data/map.json: the window, every leg the study sails, the ports and the passages."""
    left, top, right, bottom = atlas_window()
    legs = {}
    for origin, destination, routing, _, _ in sea_routes.STUDY_LEGS:
        leg = atlas_leg(origin, destination, routing, on_date)
        legs[leg.pop("key")] = leg
    records = cases.ports()
    ports: dict[str, dict[str, Any]] = {}
    for leg in legs.values():
        for port_id, point in ((leg["from"], leg["start"]), (leg["to"], leg["end"])):
            if port_id not in ports:
                ports[port_id] = {"name": records[port_id]["name"], "x": point[0], "y": point[1]}
    passages = []
    for name, (lon, lat, _) in sea_routes.REFERENCE_POINTS.items():
        if name in UNNAMED_PASSAGES:
            continue
        x, y = project(lon, lat)
        passages.append({"name": name, "x": round(x, PLACES), "y": round(y, PLACES)})
    return {
        "view_box": [round(left, PLACES), round(top, PLACES), round(right - left, PLACES), round(bottom - top, PLACES)],
        "as_of": on_date,
        "legs": legs,
        "ports": dict(sorted(ports.items())),
        "passages": passages,
    }


def clusters(ports: Mapping[str, Mapping[str, Any]], port_ids: Sequence[str]) -> list[list[str]]:
    """Ports grouped by distance, nearest first: a port joins a group when it lies within CLUSTER_UNITS of a member."""
    groups: list[list[str]] = []
    for port_id in port_ids:
        here = ports[port_id]
        for group in groups:
            if any(math.hypot(here["x"] - ports[p]["x"], here["y"] - ports[p]["y"]) < CLUSTER_UNITS for p in group):
                group.append(port_id)
                break
        else:
            groups.append([port_id])
    return groups


def document(voyages: Mapping[str, dict[str, Any]], atlas: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """data/map.json: the land once, every voyage drawn and, for the Map view, the atlas of every leg."""
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
        **({"atlas": dict(atlas)} if atlas is not None else {}),
        "sources": {
            "land": "Natural Earth 1:110m land, world-atlas 2.0.2 (vendor/world-atlas/land-110m.json)",
            "routes": "searoute 1.6.0 over Eurostat SeaRoute (data/seed/sea_routes.geojson.gz)",
            "eca": "data/seed/eca.json, the areas in force on the voyage date",
        },
    }
