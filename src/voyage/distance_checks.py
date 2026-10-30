"""Published port to port distances the sea routes are checked against: NGA Pub. 151.

Pub. 151, Distances Between Ports, eleventh edition (2001), National
Geospatial-Intelligence Agency, a work of the United States Government. Page
numbers are the printed ones (the PDF page less ten). Its preface: "Distances
in this table are in nautical miles ... The distances are between positions
shown for each port and are generally over routes that afford the safest
passage", and long voyages are read as sums through its junction points,
which is how the composite checks below are built.

Each check measures searoute between the two positions Pub. 151 prints (the
World Port Index's where Pub. 151 prints none, for ports that appear only as
destinations), under the routing that matches the published path, and the
study requires agreement within two percent. Positions at
a study port are measured with the study's own port rules (STUDY_PORTS). The
published figures are typed here from the pages named; tests/test_distances.py
reads those pages of the committed PDF again and finds each one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def dms(degrees: float, minutes: float, seconds: float, hemisphere: str) -> float:
    value = degrees + minutes / 60.0 + seconds / 3600.0
    return -value if hemisphere in ("S", "W") else value


#: name -> (lon, lat, where the position is printed)
POSITIONS: dict[str, tuple[float, float, str]] = {
    "Singapore": (dms(103, 50, 0, "E"), dms(1, 16, 0, "N"), "Pub. 151 p. 103"),
    "Port Said": (dms(32, 19, 0, "E"), dms(31, 16, 0, "N"), "Pub. 151 p. 85"),
    "Al Jubayl": (dms(49, 42, 0, "E"), dms(27, 1, 0, "N"), "Pub. 151 p. 2"),
    "Fujayrah": (dms(56, 26, 45, "E"), dms(25, 9, 0, "N"), "Pub. 151 p. 35"),
    "Galveston": (dms(94, 47, 0, "W"), dms(29, 19, 0, "N"), "Pub. 151 p. 36"),
    "Houston": (dms(95, 17, 20, "W"), dms(29, 45, 0, "N"), "Pub. 151 p. 44"),
    "New Orleans": (dms(90, 3, 30, "W"), dms(29, 57, 0, "N"), "Pub. 151 p. 69"),
    "New York": (dms(74, 1, 0, "W"), dms(40, 42, 0, "N"), "Pub. 151 p. 69"),
    "Qingdao": (dms(120, 19, 0, "E"), dms(36, 5, 30, "N"), "Pub. 151 p. 90"),
    "Port Hedland": (dms(118, 34, 50, "E"), dms(20, 17, 45, "S"), "Pub. 151 p. 84"),
    "Rotterdam": (dms(4, 28, 0, "E"), dms(51, 54, 0, "N"), "Pub. 151 p. 94"),
    "Bonny": (dms(7, 10, 22, "E"), dms(4, 27, 21, "N"), "Pub. 151 p. 15"),
    "Yokohama": (dms(139, 39, 0, "E"), dms(35, 27, 0, "N"), "Pub. 151 p. 125"),
    "Shanghai": (dms(121, 29, 30, "E"), dms(31, 14, 0, "N"), "Pub. 151 p. 102"),
    "Busan": (dms(129, 3, 0, "E"), dms(35, 6, 0, "N"), "Pub. 151 p. 18"),
    "Rio de Janeiro": (dms(43, 11, 0, "W"), dms(22, 53, 30, "S"), "Pub. 151 p. 93"),
    "Panama": (dms(79, 31, 0, "W"), dms(8, 53, 0, "N"), "Pub. 151 p. 76"),
    "Cape of Good Hope": (dms(18, 23, 0, "E"), dms(34, 22, 0, "S"), "Pub. 151 p. 21"),
    "Amsterdam": (dms(4, 54, 0, "E"), dms(52, 23, 0, "N"), "Pub. 151 p. 4"),
    "Le Havre": (dms(0, 6, 0, "E"), dms(49, 29, 0, "N"), "Pub. 151 p. 56"),
    "Selat Lombok": (dms(115, 43, 0, "E"), dms(8, 50, 0, "S"), "Pub. 151 p. 100"),
    # Destinations only in Pub. 151: positions from the World Port Index.
    "Ras Tanura": (50.166667, 26.633333, "WPI 48340"),
    "Mina al Ahmadi": (48.166667, 29.066667, "WPI 48361"),
}


#: Positions at a study port, measured with the same port rules as the study's
#: legs (voyage.sea_routes.SEA_GATES and PORT_ENDS): position name -> port id.
STUDY_PORTS: dict[str, str] = {"Amsterdam": "amsterdam", "Port Hedland": "port_hedland", "Al Jubayl": "jubail"}


@dataclass(frozen=True)
class Part:
    """One figure printed in Pub. 151: a departure entry, a line under it, its distance."""

    entry: str
    line: str
    nm: int
    page: int


@dataclass(frozen=True)
class Check:
    id: str
    origin: str
    destination: str
    routing: str
    parts: tuple[Part, ...]
    #: a published rule added to the parts, in nautical miles (Bonny: less 28)
    adjustment_nm: int = 0
    note: str = ""

    @property
    def published_nm(self) -> int:
        return sum(part.nm for part in self.parts) + self.adjustment_nm

    @property
    def composite(self) -> bool:
        return len(self.parts) > 1 or self.adjustment_nm != 0


CHECKS: Sequence[Check] = (
    Check(
        "singapore_ras_tanura",
        "Singapore",
        "Ras Tanura",
        "direct",
        (Part("SINGAPORE", "Ras Tannurah, Saudi Arabia", 3701, 104),),
    ),
    Check("singapore_qingdao", "Singapore", "Qingdao", "direct", (Part("SINGAPORE", "Qingdao, China", 2466, 104),)),
    Check("singapore_yokohama", "Singapore", "Yokohama", "direct", (Part("SINGAPORE", "Yokohama, Japan", 2889, 104),)),
    Check("singapore_shanghai", "Singapore", "Shanghai", "direct", (Part("SINGAPORE", "Shanghai, China", 2207, 104),)),
    Check(
        "singapore_mina_al_ahmadi",
        "Singapore",
        "Mina al Ahmadi",
        "direct",
        (Part("SINGAPORE", "Mina al Ahmadi, Kuwait", 3825, 104),),
    ),
    Check(
        "port_said_ras_tanura",
        "Port Said",
        "Ras Tanura",
        "direct",
        (Part("PORT SAID, EGYPT", "Ras Tannurah, Saudi Arabia", 3162, 86),),
    ),
    Check(
        "jubail_port_said",
        "Al Jubayl",
        "Port Said",
        "direct",
        (Part("AL JUBAYL, SAUDI ARABIA", "Port Said, Egypt", 3164, 2),),
    ),
    Check(
        "jubail_singapore", "Al Jubayl", "Singapore", "direct", (Part("AL JUBAYL, SAUDI ARABIA", "Singapore", 3723, 2),)
    ),
    Check(
        "fujairah_singapore",
        "Fujayrah",
        "Singapore",
        "direct",
        (Part("FUJAYRAH, UNITED ARAB EMIRATES", "Singapore", 3356, 35),),
    ),
    Check(
        "galveston_panama",
        "Galveston",
        "Panama",
        "direct",
        (Part("GALVESTON, TEXAS, U.S.A.", "Panama, Panama", 1536, 36),),
    ),
    Check(
        "new_orleans_panama",
        "New Orleans",
        "Panama",
        "direct",
        (Part("NEW ORLEANS, LOUISIANA, U.S.A.", "Panama, Panama (via South Pass)", 1433, 69),),
    ),
    Check("qingdao_panama", "Qingdao", "Panama", "direct", (Part("QINGDAO, CHINA", "Panama, Panama", 8575, 90),)),
    Check(
        "port_hedland_busan",
        "Port Hedland",
        "Busan",
        "direct",
        (Part("PORT HEDLAND, AUSTRALIA", "Busan, South Korea (via west of Timor and Korea Strait)", 3484, 84),),
    ),
    Check(
        "rio_cape",
        "Rio de Janeiro",
        "Cape of Good Hope",
        "direct",
        (Part("CAPE OF GOOD HOPE, SOUTH AFRICA", "Rio de Janeiro, Brazil", 3323, 22),),
    ),
    Check(
        "ras_tanura_cape",
        "Ras Tanura",
        "Cape of Good Hope",
        "direct",
        (Part("CAPE OF GOOD HOPE, SOUTH AFRICA", "Ras Tannurah, Saudi Arabia", 4980, 22),),
    ),
    Check(
        "new_york_rotterdam",
        "New York",
        "Rotterdam",
        "direct",
        (
            Part("NEW YORK, NEW YORK, U.S.A.", "Bishop Rock, England", 2937, 70),
            Part("ROTTERDAM, NETHERLANDS", "Bishop Rock, England", 454, 94),
        ),
        note="through the junction point Bishop Rock, the TC2 route",
    ),
    Check(
        "galveston_rotterdam",
        "Galveston",
        "Rotterdam",
        "direct",
        (
            Part("GALVESTON, TEXAS, U.S.A.", "Straits of Florida", 698, 36),
            Part("BISHOP ROCK, ENGLAND", "Straits of Florida", 3859, 14),
            Part("BISHOP ROCK, ENGLAND", "Rotterdam, Netherlands", 454, 14),
        ),
        note="through the Straits of Florida and Bishop Rock, the US Gulf to Continent routes",
    ),
    Check(
        "houston_rotterdam",
        "Houston",
        "Rotterdam",
        "direct",
        (
            Part("GALVESTON, TEXAS, U.S.A.", "Straits of Florida", 698, 36),
            Part("BISHOP ROCK, ENGLAND", "Straits of Florida", 3859, 14),
            Part("BISHOP ROCK, ENGLAND", "Rotterdam, Netherlands", 454, 14),
        ),
        adjustment_nm=47,
        note="Galveston's route plus 47 miles, the rule Pub. 151 prints for Houston on p. 44 (TD25)",
    ),
    Check(
        "houston_amsterdam",
        "Houston",
        "Amsterdam",
        "direct",
        (
            Part("GALVESTON, TEXAS, U.S.A.", "Straits of Florida", 698, 36),
            Part("BISHOP ROCK, ENGLAND", "Straits of Florida", 3859, 14),
            Part("BISHOP ROCK, ENGLAND", "Amsterdam, Netherlands", 481, 14),
        ),
        adjustment_nm=47,
        note="Galveston's route plus 47 miles, the rule Pub. 151 prints for Houston on p. 44 (TC14), to Pub. 151's "
        "Amsterdam position, a little nearer IJmuiden than the World Port Index position the priced leg ends at",
    ),
    Check(
        "amsterdam_le_havre",
        "Amsterdam",
        "Le Havre",
        "direct",
        (Part("AMSTERDAM, NETHERLANDS", "Le Havre, France", 273, 4),),
        note="the TC23 route, from Pub. 151's Amsterdam position, a little nearer IJmuiden than the World Port Index "
        "position the priced leg starts from",
    ),
    Check(
        "galveston_shanghai_cape",
        "Galveston",
        "Shanghai",
        "no_canals",
        (
            Part("GALVESTON, TEXAS, U.S.A.", "Straits of Florida", 698, 36),
            Part("CAPE OF GOOD HOPE, SOUTH AFRICA", "Straits of Florida", 6770, 21),
            Part("CAPE OF GOOD HOPE, SOUTH AFRICA", "Selat Sunda, Indonesia", 5164, 21),
            Part("SELAT SUNDA, INDONESIA", "Shanghai, China", 2535, 101),
        ),
        note="through the Straits of Florida, the Cape of Good Hope and Selat Sunda, the routing of TD22's ballast "
        "leg; its laden leg leaves it for the Strait of Malacca and has no Pub. 151 figure of its own",
    ),
    Check(
        "port_hedland_lombok",
        "Port Hedland",
        "Selat Lombok",
        "direct",
        (Part("PORT HEDLAND, AUSTRALIA", "Selat Lombok, Indonesia", 715, 84),),
        note="the first stretch of the C5 route, from the port",
    ),
    Check(
        "bonny_rotterdam",
        "Bonny",
        "Rotterdam",
        "direct",
        (
            Part("PORT HARCOURT, NIGERIA", "Ile d'Ouessant, France", 3974, 84),
            Part("ROTTERDAM, NETHERLANDS", "Ile d'Ouessant, France", 444, 94),
        ),
        adjustment_nm=-28,
        note="Port Harcourt's route less 28 miles, the rule Pub. 151 prints for Bonny on p. 15 (TD20)",
    ),
    Check(
        "jubail_rotterdam_suez",
        "Al Jubayl",
        "Rotterdam",
        "direct",
        (
            Part("AL JUBAYL, SAUDI ARABIA", "Port Said, Egypt", 3164, 2),
            Part("PORT SAID, EGYPT", "Strait of Gibraltar", 1943, 85),
            Part("STRAIT OF GIBRALTAR", "Ile d'Ouessant, France", 918, 108),
            Part("ROTTERDAM, NETHERLANDS", "Ile d'Ouessant, France", 444, 94),
        ),
        note="through Port Said, Gibraltar and Ushant, the TC20 route by Suez",
    ),
    Check(
        "jubail_rotterdam_cape",
        "Al Jubayl",
        "Rotterdam",
        "no_suez",
        (
            Part("AL JUBAYL, SAUDI ARABIA", "Cape of Good Hope, South Africa", 5109, 2),
            Part("CAPE OF GOOD HOPE, SOUTH AFRICA", "Ile d'Ouessant, France", 5746, 21),
            Part("ROTTERDAM, NETHERLANDS", "Ile d'Ouessant, France", 444, 94),
        ),
        note="through the Cape of Good Hope and Ushant, the TC20 route round the Cape",
    ),
)

#: The study's bar: searoute within two percent of the published figure.
TOLERANCE = 0.02
