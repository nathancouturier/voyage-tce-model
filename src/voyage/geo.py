"""Distances on the sphere and positions inside polygons, in nautical miles and degrees.

Lines are sequences of (longitude, latitude) pairs, as GeoJSON writes them.
Lengths follow great circles on a sphere of the IUGG mean Earth radius,
6,371.0088 km, in international nautical miles of 1,852 m. Polygons are rings
of (longitude, latitude) drawn on the plate carree plane; that is exact for
the emission control areas, whose legal boundaries are parallels, meridians
and straight joins between listed points, at the scale the study needs.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence

#: Mean Earth radius, IUGG, 6,371.0088 km, in nautical miles of 1,852 m.
EARTH_RADIUS_NM = 6371.0088 / 1.852

Point = tuple[float, float]


def haversine_nm(a: Sequence[float], b: Sequence[float]) -> float:
    """Great circle distance between two (lon, lat) points, in nautical miles."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(min(1.0, h)))


def polyline_length_nm(coordinates: Sequence[Sequence[float]]) -> float:
    """Length of a line of (lon, lat) pairs along great circles, in nautical miles."""
    return sum(haversine_nm(a, b) for a, b in itertools.pairwise(coordinates))


def interpolate(a: Sequence[float], b: Sequence[float], t: float) -> Point:
    """The point a fraction t of the way from a to b along the great circle."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = haversine_nm(a, b) / EARTH_RADIUS_NM
    if d == 0.0:
        return (float(a[0]), float(a[1]))
    s1 = math.sin((1 - t) * d) / math.sin(d)
    s2 = math.sin(t * d) / math.sin(d)
    x = s1 * math.cos(lat1) * math.cos(lon1) + s2 * math.cos(lat2) * math.cos(lon2)
    y = s1 * math.cos(lat1) * math.sin(lon1) + s2 * math.cos(lat2) * math.sin(lon2)
    z = s1 * math.sin(lat1) + s2 * math.sin(lat2)
    lat = math.atan2(z, math.hypot(x, y))
    lon = math.atan2(y, x)
    # Keep the longitude continuous with the segment's start, so a line drawn
    # past 180 degrees stays past it.
    lon_deg = math.degrees(lon)
    lon_deg += 360.0 * round((a[0] - lon_deg) / 360.0)
    return (lon_deg, math.degrees(lat))


def densify(coordinates: Sequence[Sequence[float]], step_nm: float) -> list[tuple[Point, Point, float]]:
    """The line cut into pieces no longer than step_nm: (start, end, length) for each piece."""
    pieces: list[tuple[Point, Point, float]] = []
    for a, b in itertools.pairwise(coordinates):
        length = haversine_nm(a, b)
        count = max(1, math.ceil(length / step_nm))
        previous: Point = (float(a[0]), float(a[1]))
        for k in range(1, count + 1):
            current = interpolate(a, b, k / count)
            pieces.append((previous, current, length / count))
            previous = current
    return pieces


def wrap_lon(lon: float) -> float:
    """A longitude brought into [-180, 180)."""
    return (lon + 180.0) % 360.0 - 180.0


def point_in_ring(point: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    """Even odd rule on the plate carree plane; the ring may be open or closed."""
    x, y = point[0], point[1]
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def point_in_polygon(point: Sequence[float], rings: Sequence[Sequence[Sequence[float]]]) -> bool:
    """Inside the outer ring and outside every hole. Longitude is wrapped first."""
    p = (wrap_lon(point[0]), point[1])
    if not point_in_ring(p, rings[0]):
        return False
    return not any(point_in_ring(p, hole) for hole in rings[1:])


def length_inside_nm(
    coordinates: Sequence[Sequence[float]],
    polygons: Iterable[Sequence[Sequence[Sequence[float]]]],
    step_nm: float = 2.0,
) -> float:
    """Nautical miles of a line that fall inside any of the polygons.

    The line is cut into pieces of at most step_nm and each piece counts in
    full when its midpoint is inside, so the error is at most one piece per
    boundary crossing.
    """
    shapes = list(polygons)
    total = 0.0
    for a, b, length in densify(coordinates, step_nm):
        middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if any(point_in_polygon(middle, rings) for rings in shapes):
            total += length
    return total


def nearest_distance_nm(coordinates: Sequence[Sequence[float]], reference: Sequence[float]) -> float:
    """Shortest distance from a (lon, lat) reference point to a line, on a plane tangent at the point.

    Each segment is placed on the plane from its first vertex's wrapped
    longitude plus its own change in longitude, so a line drawn past 180
    degrees gains no false segment across the plane.
    """
    lon0, lat0 = reference[0], reference[1]
    scale = 60.0 * math.cos(math.radians(lat0))
    best = math.inf
    for a, b in itertools.pairwise(coordinates):
        da = (a[0] - lon0 + 540.0) % 360.0 - 180.0
        db = da + (b[0] - a[0])
        ax, ay = da * scale, (a[1] - lat0) * 60.0
        bx, by = db * scale, (b[1] - lat0) * 60.0
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / span))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best
