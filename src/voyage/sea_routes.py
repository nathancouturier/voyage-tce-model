"""The sea routes: how each is asked of searoute, and the checks its committed geometry must pass.

The routes are computed once with searoute (Apache License 2.0) over the
maritime network it bundles, Eurostat's SeaRoute network (European Union Public
Licence 1.2), by scripts/routes.py, and committed to data/seed/sea_routes.json
(distances, passages, checks) and data/seed/sea_routes.geojson.gz (lines).
Nothing computes a route at build time and the site never loads the library.

Every ordered pair of study ports is computed under four routings, so the
calculator can ballast from any of them:

* direct      the shortest route the network offers, canals included;
* no_suez     the Suez Canal and Bab el Mandeb closed: Asia to Europe goes
              round the Cape of Good Hope;
* no_panama   the Panama Canal closed;
* no_canals   both closed, for ships no canal takes (a laden VLCC).

One further routing is computed only for the legs listed in SPECIAL_LEGS:
no_canals_no_sunda also closes the Sunda Strait, for a laden VLCC from the
Cape of Good Hope to China, which takes the Strait of Malacca: the mileage of
the Baltic's own TD3C calculation for the same ship and cargo (5,897 nm, July
2017) fits the network's line through Malacca, not through Sunda.

The checks work from the committed geometry alone, independently of the
library: each line's great circle length within 0.5 percent of the length
searoute reported, and each study leg passing the straits it should and
avoiding those it should not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import geo

SEAROUTE_VERSION = "1.6.0"

#: routing name -> passages searoute is told to avoid (its names). The
#: Northwest Passage is closed in every routing, as searoute closes it by default.
ROUTINGS: Mapping[str, tuple[str, ...]] = {
    "direct": ("northwest",),
    "no_suez": ("northwest", "suez", "babalmandab"),
    "no_panama": ("northwest", "panama"),
    "no_canals": ("northwest", "suez", "babalmandab", "panama"),
}

#: Routings computed only for the legs in SPECIAL_LEGS, not for every pair.
SPECIAL_ROUTINGS: Mapping[str, tuple[str, ...]] = {
    "no_canals_no_sunda": ("northwest", "suez", "babalmandab", "panama", "sunda"),
}

#: The legs a special routing is computed for: TD22's laden leg, Galveston to
#: Ningbo round the Cape. The shortest network line runs through the Sunda
#: Strait; the mileage the Baltic gives a laden VLCC300 with 270,000 t on TD3C
#: (5,897 nm, TD3C TCE Calculation Process, July 2017) fits the Strait of Malacca.
SPECIAL_LEGS: Sequence[tuple[str, str, str]] = (("galveston", "ningbo", "no_canals_no_sunda"),)

ROUTING_LABELS: Mapping[str, str] = {
    "direct": "shortest route, canals open",
    "no_suez": "Suez Canal and Red Sea avoided",
    "no_panama": "Panama Canal avoided",
    "no_canals": "Suez and Panama avoided",
    "no_canals_no_sunda": "Suez, Panama and the Sunda Strait avoided",
}


def restrictions(routing: str) -> tuple[str, ...]:
    """The passages searoute is told to avoid under a routing."""
    if routing in ROUTINGS:
        return tuple(ROUTINGS[routing])
    return tuple(SPECIAL_ROUTINGS[routing])


#: Ports whose nearest node of the network lies behind land: the route is asked
#: of searoute from a gate at sea, and the stretch from the gate's node to the
#: port is added to the line as a straight segment. Amsterdam's nearest node is
#: in the IJmeer, behind the Markermeer and the IJsselmeer; ships reach the port
#: by the North Sea Canal from IJmuiden. port id -> (lon, lat, source)
SEA_GATES: Mapping[str, tuple[float, float, str]] = {
    "amsterdam": (
        4 + 34 / 60,
        52 + 28 / 60,
        "IJmuiden, NGA Pub. 151 printed page 44: 'Subtract 14 miles from Amsterdam distances'",
    ),
}

#: Ports whose nearest node lies 10 nm or more out across open water, with the
#: study's legs running on from it: the straight stretch from the port to the
#: node is added to the line (searoute's lines start at the node). Elsewhere the
#: stretch is under 10 nm, or runs up a river or ship channel the network does
#: not draw (Ningbo 14.2 nm, Houston 9.1 nm), or would double back on the line
#: (Tubarao 45.6 nm out, where adding it would overstate each leg by about 24 nm,
#: so each C3 leg is about 21.5 nm short). port id -> why
PORT_ENDS: Mapping[str, str] = {
    "port_hedland": "the node lies 43 nm north of the port, on the way out; Pub. 151 page 84 measures from the port",
    "jubail": "the node lies 12 nm out in open water, on the way out",
}

#: A point in each passage a route can be tested against, with the distance
#: within which a route counts as passing it, in nautical miles. Positions are
#: (longitude, latitude); the Cape is rounded offshore, so its radius is wider.
REFERENCE_POINTS: Mapping[str, tuple[float, float, float]] = {
    "Strait of Hormuz": (56.45, 26.55, 30.0),
    "Bab el Mandeb": (43.4, 12.6, 30.0),
    "Suez Canal": (32.55, 30.6, 30.0),
    "Strait of Gibraltar": (-5.6, 35.95, 30.0),
    "Dover Strait": (1.45, 51.0, 30.0),
    "Strait of Malacca": (101.0, 2.6, 60.0),
    "Sunda Strait": (105.8, -6.0, 30.0),
    "Lombok Strait": (115.7, -8.6, 30.0),
    "Cape of Good Hope": (18.47, -34.36, 200.0),
    "Panama Canal": (-79.7, 9.1, 30.0),
    "Yucatan Channel": (-85.9, 21.9, 60.0),
    "Florida Strait": (-81.0, 24.1, 60.0),
    "Strait of Magellan": (-70.5, -53.5, 150.0),
    # Not a passage: a guard, since a route from the network's node nearest
    # Amsterdam, in the IJmeer, runs through the lakes (see SEA_GATES).
    "IJsselmeer": (5.25, 52.75, 10.0),
}

#: The legs the study's voyages sail, with what each must and must not pass.
#: (from, to, routing, passes, avoids)
STUDY_LEGS: Sequence[tuple[str, str, str, tuple[str, ...], tuple[str, ...]]] = (
    ("tubarao", "qingdao", "direct", ("Cape of Good Hope",), ("Suez Canal", "Panama Canal")),
    ("qingdao", "tubarao", "direct", ("Cape of Good Hope",), ("Suez Canal", "Panama Canal")),
    ("port_hedland", "qingdao", "direct", (), ("Strait of Malacca", "Suez Canal")),
    ("qingdao", "port_hedland", "direct", (), ("Strait of Malacca", "Suez Canal")),
    ("new_orleans", "qingdao", "direct", ("Panama Canal",), ("Cape of Good Hope", "Suez Canal")),
    ("qingdao", "new_orleans", "direct", ("Panama Canal",), ("Cape of Good Hope", "Suez Canal")),
    ("new_orleans", "qingdao", "no_canals", ("Cape of Good Hope",), ("Panama Canal", "Suez Canal")),
    ("qingdao", "new_orleans", "no_canals", ("Cape of Good Hope",), ("Panama Canal", "Suez Canal")),
    ("new_orleans", "rotterdam", "direct", ("Dover Strait",), ("Panama Canal",)),
    ("rotterdam", "new_orleans", "direct", ("Dover Strait",), ("Panama Canal",)),
    ("ras_tanura", "ningbo", "direct", ("Strait of Hormuz", "Strait of Malacca"), ("Lombok Strait",)),
    ("ningbo", "ras_tanura", "direct", ("Strait of Hormuz", "Strait of Malacca"), ("Lombok Strait",)),
    ("mina_al_fahal", "ningbo", "direct", ("Strait of Malacca",), ("Strait of Hormuz",)),
    ("ningbo", "mina_al_fahal", "direct", ("Strait of Malacca",), ("Strait of Hormuz",)),
    ("galveston", "ningbo", "no_canals", ("Cape of Good Hope",), ("Panama Canal", "Suez Canal")),
    (
        "galveston",
        "ningbo",
        "no_canals_no_sunda",
        ("Cape of Good Hope", "Strait of Malacca"),
        ("Panama Canal", "Suez Canal", "Sunda Strait"),
    ),
    ("ningbo", "galveston", "no_canals", ("Cape of Good Hope",), ("Panama Canal", "Suez Canal")),
    ("ningbo", "galveston", "no_panama", ("Suez Canal", "Bab el Mandeb"), ("Panama Canal", "Cape of Good Hope")),
    ("bonny", "rotterdam", "direct", ("Dover Strait",), ("Strait of Gibraltar",)),
    ("rotterdam", "bonny", "direct", ("Dover Strait",), ("Strait of Gibraltar",)),
    ("houston", "rotterdam", "direct", ("Dover Strait",), ("Panama Canal",)),
    ("rotterdam", "houston", "direct", ("Dover Strait",), ("Panama Canal",)),
    ("rotterdam", "new_york", "direct", ("Dover Strait",), ()),
    ("new_york", "rotterdam", "direct", ("Dover Strait",), ()),
    ("houston", "amsterdam", "direct", ("Dover Strait",), ("Panama Canal", "IJsselmeer")),
    ("amsterdam", "houston", "direct", ("Dover Strait",), ("Panama Canal", "IJsselmeer")),
    ("ras_tanura", "yokohama", "direct", ("Strait of Hormuz", "Strait of Malacca"), ()),
    ("yokohama", "ras_tanura", "direct", ("Strait of Hormuz", "Strait of Malacca"), ()),
    ("jubail", "rotterdam", "direct", ("Strait of Hormuz", "Bab el Mandeb", "Suez Canal"), ("Cape of Good Hope",)),
    ("rotterdam", "jubail", "direct", ("Strait of Hormuz", "Bab el Mandeb", "Suez Canal"), ("Cape of Good Hope",)),
    ("jubail", "rotterdam", "no_suez", ("Strait of Hormuz", "Cape of Good Hope"), ("Suez Canal",)),
    ("rotterdam", "jubail", "no_suez", ("Strait of Hormuz", "Cape of Good Hope"), ("Suez Canal",)),
    ("qingdao", "rotterdam", "direct", ("Strait of Malacca", "Suez Canal"), ("Cape of Good Hope",)),
    ("rotterdam", "qingdao", "direct", ("Strait of Malacca", "Suez Canal"), ("Cape of Good Hope",)),
    ("qingdao", "rotterdam", "no_canals", ("Cape of Good Hope",), ("Suez Canal", "Panama Canal")),
    ("rotterdam", "qingdao", "no_canals", ("Cape of Good Hope",), ("Suez Canal", "Panama Canal")),
    ("qingdao", "rotterdam", "no_suez", ("Panama Canal",), ("Suez Canal", "Cape of Good Hope")),
    ("amsterdam", "le_havre", "direct", ("Dover Strait",), ("IJsselmeer",)),
    ("le_havre", "amsterdam", "direct", ("Dover Strait",), ("IJsselmeer",)),
    ("ras_tanura", "fujairah", "direct", ("Strait of Hormuz",), ()),
    ("fujairah", "ras_tanura", "direct", ("Strait of Hormuz",), ()),
    ("fujairah", "ningbo", "direct", ("Strait of Malacca",), ("Strait of Hormuz",)),
    ("ningbo", "fujairah", "direct", ("Strait of Malacca",), ("Strait of Hormuz",)),
)


def leg_key(origin: str, destination: str, routing: str) -> str:
    """The identifier of a directed leg under a routing, as the seed files key it."""
    return "%s__%s__%s" % (origin, destination, routing)


def passes(coordinates: Sequence[Sequence[float]]) -> dict[str, float]:
    """The nearest approach of a line to every reference point, in nautical miles."""
    return {
        name: round(geo.nearest_distance_nm(coordinates, (lon, lat)), 1)
        for name, (lon, lat, _) in REFERENCE_POINTS.items()
    }


def passed(nearest: Mapping[str, float]) -> list[str]:
    """The reference points a line comes within their stated radius of."""
    return [name for name, (_, _, radius) in REFERENCE_POINTS.items() if nearest[name] <= radius]


def leg_problems(document: Mapping[str, Any], lines: Mapping[str, Sequence[Sequence[float]]]) -> list[str]:
    """Everything wrong with the committed routes, as sentences."""
    problems: list[str] = []
    legs = document.get("legs", {})
    for key, leg in legs.items():
        coordinates = lines.get(key)
        if coordinates is None:
            problems.append("%s has no line in the GeoJSON" % key)
            continue
        measured = geo.polyline_length_nm(coordinates)
        if leg["distance_nm"] > 0 and abs(measured / leg["distance_nm"] - 1.0) > 0.005:
            problems.append(
                "%s: the line measures %.1f nm, the seed records %.1f nm" % (key, measured, leg["distance_nm"])
            )
    for origin, destination, routing, must, must_not in STUDY_LEGS:
        key = leg_key(origin, destination, routing)
        coordinates = lines.get(key)
        if coordinates is None:
            problems.append("study leg %s is missing" % key)
            continue
        through = passed(passes(coordinates))
        for name in must:
            if name not in through:
                problems.append("%s should pass %s" % (key, name))
        for name in must_not:
            if name in through:
                problems.append("%s should avoid %s" % (key, name))
    return problems
