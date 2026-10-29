"""Sulphur emission control areas (ECAs): their boundaries, their dates, and the miles a route sails in them.

Inside an ECA a ship burns fuel of at most 0.10 percent sulphur by mass, outside
at most 0.50 percent (MARPOL Annex VI, regulation 14.1 and 14.4, as revised by
resolution MEPC.328(76), pages 26 and 27). A ship with an approved scrubber
may burn high sulphur fuel instead, where the port state allows its washwater.

The areas, each built from the legal text it cites:

* North American (Atlantic and Gulf of Mexico, Pacific, Hawaii) and United
  States Caribbean Sea: MARPOL Annex VI Appendix VII, MEPC.328(76) pages 67 to
  75, the coordinate lists read by voyage.sources.imo. The seaward lines run
  from coast to coast; each Pacific and Atlantic list is closed into a polygon
  through points well inland, which changes no sea area.
* North Sea: MARPOL Annex V regulation 1.14.6 (MEPC.201(62), page 4): south of
  62 N and east of 4 W, the Skagerrak to the Skaw's parallel 57 44.8 N, and the
  English Channel east of 5 W and north of 48 30 N.
* Baltic Sea: MARPOL Annex I regulation 1.11.2 (MEPC.117(52), page 3): the
  Baltic proper, the Gulfs of Bothnia and Finland and the entrance to the
  Baltic bounded by the Skaw's parallel, 57 44.8 N.
* Mediterranean Sea: MEPC.361(79), Appendix VII paragraph 4, in force from 1
  May 2025: all waters bounded by the coasts of Europe, Africa and Asia, the
  line Cape Trafalgar to Cape Spartel, the line across the Dardanelles from
  Mehmetcik Burnu to Kumkale Burnu (so the Sea of Marmara is outside), and the
  northern entrance of the Suez Canal less a four point box.

The North Sea, Baltic and Mediterranean polygons follow their legal lines at
sea and run over land elsewhere, where they change nothing for a ship. The
Canadian Arctic and Norwegian Sea areas (MEPC.392(82), in force 1 March 2026,
0.10 percent from 1 March 2027 under regulation 14.7) and the North-East
Atlantic area (MEPC.407(84), in force 1 September 2027) are listed with their
dates; no study route enters the first two, and the third is not yet in force.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import geo

Ring = list[tuple[float, float]]


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    #: first day the 0.10 percent limit applies, ISO date
    in_force_from: str
    source: str
    construction: str
    #: polygon rings, (lon, lat), outer ring first
    rings: tuple[Ring, ...]


def _dm(degrees: float, minutes: float, hemisphere: str) -> float:
    value = degrees + minutes / 60.0
    return -value if hemisphere in ("S", "W") else value


#: Dates the 0.10 percent sulphur limit applies, MARPOL Annex VI and the IMO's
#: table of special areas: Baltic 19 May 2006, North Sea 22 November 2007,
#: North American 1 August 2012, United States Caribbean 1 January 2014; the
#: limit itself fell from 1.00 to 0.10 percent on 1 January 2015
#: (regulation 14.4.3 of MEPC.176(58)), the level this study prices.
IN_FORCE = {
    "baltic": "2006-05-19",
    "north_sea": "2007-11-22",
    "na_atlantic_gulf": "2012-08-01",
    "na_pacific": "2012-08-01",
    "na_hawaii": "2012-08-01",
    "us_caribbean": "2014-01-01",
    "mediterranean": "2025-05-01",
}

#: Areas designated but entered by no study route, for the conventions table.
OTHER_AREAS: Sequence[Mapping[str, str]] = (
    {
        "name": "Canadian Arctic",
        "resolution": "MEPC.392(82), adopted 4 October 2024",
        "in_force": "2026-03-01",
        "limit_applies": "2027-03-01",
        "note": "0.10 percent from 1 March 2027, twelve months after entry into force (regulation 14.7)",
    },
    {
        "name": "Norwegian Sea",
        "resolution": "MEPC.392(82), adopted 4 October 2024",
        "in_force": "2026-03-01",
        "limit_applies": "2027-03-01",
        "note": "0.10 percent from 1 March 2027, twelve months after entry into force (regulation 14.7)",
    },
    {
        "name": "North-East Atlantic",
        "resolution": "MEPC.407(84)",
        "in_force": "2027-09-01",
        "limit_applies": "",
        "note": "listed by the IMO with entry into force on 1 September 2027; its text was awaiting certification",
    },
)

# Inland closing points, (lon, lat): over land, they change no sea area.
_ATLANTIC_CLOSE: Ring = [
    (-99.0, 26.5),
    (-100.0, 31.0),
    (-95.0, 38.0),
    (-88.0, 44.0),
    (-80.0, 47.0),
    (-73.0, 51.0),
    (-68.5, 55.0),
    (-65.2, 58.5),
]
_PACIFIC_CLOSE: Ring = [
    (-152.0, 61.5),
    (-145.0, 62.5),
    (-137.0, 60.5),
    (-129.5, 56.0),
    (-122.0, 50.0),
    (-121.0, 42.0),
    (-116.5, 34.0),
]

#: Annex V regulation 1.14.6: from 4 W, 62 N east along 62 N, over Norway and
#: Sweden to the Skaw's parallel, west along it to the Skaw, over Jutland,
#: Germany, the Low Countries and France to 48 30 N, west along it to 5 W, north
#: along 5 W to Cornwall, then over Britain to 4 W on the Scottish north coast
#: and north along 4 W to 62 N.
_SKAW_LAT = _dm(57, 44.8, "N")
_NORTH_SEA: Ring = [
    (-4.0, 62.0),
    (8.0, 62.0),
    (11.6, 59.0),
    (12.0, _SKAW_LAT),
    (10.645, _SKAW_LAT),
    (9.0, 55.0),
    (8.0, 53.0),
    (4.0, 50.5),
    (0.0, 48.8),
    (-4.0, 48.5),
    (-5.0, 48.5),
    (-5.0, 50.2),
    (-4.0, 50.6),
    (-1.5, 51.5),
    (-2.0, 54.0),
    (-3.8, 56.0),
    (-4.5, 57.5),
    (-4.0, 58.6),
]

#: Annex I regulation 1.11.2: east of the Skaw's parallel line and all the
#: Baltic beyond it, closed over Sweden, Finland, Russia, the Baltic states,
#: Poland, Germany and Jutland.
_BALTIC: Ring = [
    (10.645, _SKAW_LAT),
    (12.0, _SKAW_LAT),
    (14.0, 60.0),
    (20.0, 67.0),
    (27.0, 66.0),
    (31.0, 61.0),
    (29.0, 58.0),
    (25.0, 55.0),
    (20.0, 53.5),
    (14.0, 53.5),
    (10.0, 53.9),
    (9.5, 55.0),
    (10.0, 57.0),
]

#: MEPC.361(79), Appendix VII paragraph 4.
_TRAFALGAR = (_dm(6, 2.00, "W"), _dm(36, 11.00, "N"))
_SPARTEL = (_dm(5, 55.00, "W"), _dm(35, 48.00, "N"))
_MEHMETCIK = (_dm(26, 11, "E"), _dm(40, 3, "N"))
_KUMKALE = (_dm(26, 12.00, "E"), _dm(40, 1.00, "N"))
_SUEZ_BOX = [  # points 1 to 4
    (_dm(32, 16.00, "E"), _dm(31, 29.00, "N")),
    (_dm(32, 28.48, "E"), _dm(31, 29.00, "N")),
    (_dm(32, 32.62, "E"), _dm(31, 14.00, "N")),
    (_dm(32, 16.00, "E"), _dm(31, 14.00, "N")),
]
_MEDITERRANEAN: Ring = [
    _TRAFALGAR,
    _SPARTEL,
    # North Africa, inland
    (-5.0, 34.5),
    (0.0, 34.0),
    (10.0, 32.5),
    (19.5, 29.8),
    (25.0, 30.5),
    (29.5, 30.6),
    # the Suez box's western, northern and eastern sides, so the box stays outside
    _SUEZ_BOX[3],
    _SUEZ_BOX[0],
    _SUEZ_BOX[1],
    _SUEZ_BOX[2],
    # the Levant and Anatolia, inland
    (33.5, 30.8),
    (35.0, 31.0),
    (36.5, 33.5),
    (37.0, 36.5),
    (30.0, 38.0),
    (27.5, 39.5),
    # the Dardanelles line, then Gallipoli and Thrace, inland
    _KUMKALE,
    _MEHMETCIK,
    (26.6, 40.4),
    (26.9, 40.9),
    (25.0, 41.5),
    # the Balkans, the Alps, southern France and Spain, inland
    (22.0, 42.0),
    (19.0, 44.5),
    (14.5, 46.2),
    (12.0, 45.9),
    (8.5, 44.8),
    (4.0, 44.0),
    (0.0, 42.5),
    (-3.0, 38.0),
    (-5.0, 36.8),
    (-5.75, 36.35),
]


def build(appendix_vii: Mapping[str, Mapping[str, Any]]) -> list[Zone]:
    """Every ECA as a polygon, from the Appendix VII lists and the regulations' lines.

    appendix_vii is voyage.sources.imo.appendix_vii(): part -> {"points": [(n, lat, lon)]}.
    """

    def ring(part: str) -> Ring:
        return [(lon, lat) for _, lat, lon in appendix_vii[part]["points"]]

    vii = "MARPOL Annex VI Appendix VII, resolution MEPC.328(76), pages 67 to 75"
    zones = [
        Zone(
            "na_atlantic_gulf",
            "North American ECA, Atlantic and Gulf of Mexico",
            IN_FORCE["na_atlantic_gulf"],
            vii + ", 206 points",
            "the listed line, closed over the continent",
            (ring("na_atlantic_gulf") + _ATLANTIC_CLOSE,),
        ),
        Zone(
            "na_pacific",
            "North American ECA, Pacific",
            IN_FORCE["na_pacific"],
            vii + ", 47 points",
            "the listed line, closed over the continent",
            (ring("na_pacific") + _PACIFIC_CLOSE,),
        ),
        Zone(
            "na_hawaii",
            "North American ECA, Hawaii",
            IN_FORCE["na_hawaii"],
            vii + ", 45 points",
            "the listed ring",
            (ring("na_hawaii"),),
        ),
        Zone(
            "us_caribbean",
            "United States Caribbean Sea ECA",
            IN_FORCE["us_caribbean"],
            vii + ", 55 points",
            "the listed ring",
            (ring("us_caribbean"),),
        ),
        Zone(
            "north_sea",
            "North Sea ECA",
            IN_FORCE["north_sea"],
            "MARPOL Annex V regulation 1.14.6, resolution MEPC.201(62), page 4",
            "62 N, 4 W, the Skaw's parallel and the Channel lines at 5 W and 48 30 N, closed over land",
            (_NORTH_SEA,),
        ),
        Zone(
            "baltic",
            "Baltic Sea ECA",
            IN_FORCE["baltic"],
            "MARPOL Annex I regulation 1.11.2, resolution MEPC.117(52), page 3",
            "the Skaw's parallel, 57 44.8 N, closed over land",
            (_BALTIC,),
        ),
        Zone(
            "mediterranean",
            "Mediterranean Sea ECA",
            IN_FORCE["mediterranean"],
            "resolution MEPC.361(79), Appendix VII paragraph 4; in force 1 May 2024, ships exempt until 1 May 2025",
            "Cape Trafalgar to Cape Spartel, Mehmetcik Burnu to Kumkale Burnu, and the Suez box excluded, "
            "closed over land",
            (_MEDITERRANEAN,),
        ),
    ]
    return zones


def in_force(zones: Iterable[Zone], on_date: str) -> list[Zone]:
    """The zones whose 0.10 percent limit applies on an ISO date."""
    return [zone for zone in zones if zone.in_force_from <= on_date]


def miles_in(coordinates: Sequence[Sequence[float]], zones: Iterable[Zone], step_nm: float = 2.0) -> dict[str, float]:
    """Nautical miles of a line inside each zone, zone id -> miles (zones with none left out)."""
    out: dict[str, float] = {}
    for zone in zones:
        miles = geo.length_inside_nm(coordinates, [zone.rings], step_nm=step_nm)
        if miles > 0:
            out[zone.id] = miles
    return out


def as_records(zones: Iterable[Zone]) -> list[dict[str, Any]]:
    return [
        {
            "id": z.id,
            "name": z.name,
            "in_force_from": z.in_force_from,
            "source": z.source,
            "construction": z.construction,
            "rings": [[[round(lon, 5), round(lat, 5)] for lon, lat in r] for r in z.rings],
        }
        for z in zones
    ]
