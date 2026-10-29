"""The ports the study's voyages use, each placed from a public domain source.

Positions come from the World Port Index (NGA Pub. 150), keyed by its port
number, read from the committed raw file through voyage.sources.nga. One port
the Baltic Exchange names is not in the Index: Bonny's offshore terminal, the
TD20 load point. It takes the position NGA's Pub. 151 prints for Bonny,
Nigeria, on printed page 15, which lies on Bonny Island, inshore of the terminal; the
route line starts from the nearest node of the sea route network either way.

Two Baltic load areas are wider than a port, and the study picks one, each
choice recorded here and in docs/methodology.md:

* C5, "West Australia": Port Hedland, the largest iron ore port of the Pilbara.
* P7, "Mississippi river" (minimum 13 m arrival draft): New Orleans, the
  Index's port for the lower river grain elevators; Pub. 151 prints distances
  from the same port.
* TD22, "Galveston O/S lightering area" (the Baltic's TSA1): the Index's
  Galveston position, because the lightering zone's coordinates sit in a US
  regulation this environment cannot reach (33 CFR 156.300, on ecfr.gov and
  govinfo.gov, both refused).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .sources import nga


@dataclass(frozen=True)
class Port:
    id: str
    name: str
    country: str
    lat: float
    lon: float
    #: "WPI <number>" or "Pub. 151 page <n>"
    source: str
    #: what the study uses the port for
    role: str
    #: True for a port inside the European Economic Area, for the EU ETS
    eea: bool


#: port id -> (World Port Index number or None, display name, ISO country, EEA member, role)
_SPEC: Mapping[str, tuple[int | None, str, str, bool, str]] = {
    "tubarao": (12855, "Tubarao", "BR", False, "C3 load port"),
    "port_hedland": (54620, "Port Hedland", "AU", False, "C5 load port (the Baltic names West Australia)"),
    "qingdao": (60140, "Qingdao", "CN", False, "C3, C5 and P7 discharge port; Panamax Asia to Europe detour load port"),
    "new_orleans": (8860, "New Orleans", "US", False, "P7 and S4A load port (the Baltic names the Mississippi river)"),
    "ras_tanura": (48340, "Ras Tanura", "SA", False, "TD3C, TC1 and TC5 load port"),
    "mina_al_fahal": (48255, "Mina Al Fahal", "OM", False, "TD34 load port, outside the Strait of Hormuz"),
    "fujairah": (
        48262,
        "Fujairah",
        "AE",
        False,
        "Gulf of Oman anchorage for waiting and ship to ship transfers; bunker price hub",
    ),
    "jubail": (48338, "Jubail", "SA", False, "TC20 load port, the Suez against Cape detour"),
    "ningbo": (59940, "Ningbo", "CN", False, "TD3C, TD22 and TD34 discharge port"),
    "yokohama": (61390, "Yokohama", "JP", False, "TC1 and TC5 discharge port"),
    "galveston": (9150, "Galveston", "US", False, "TD22 load area (the Baltic names the offshore lightering area)"),
    "houston": (9240, "Houston", "US", False, "TD25 and TC14 load port; bunker price hub"),
    "new_york": (7640, "New York", "US", False, "TC2 discharge port"),
    "rotterdam": (
        31140,
        "Rotterdam",
        "NL",
        True,
        "TD20, TD25 and TC20 discharge, TC2 load, S4A redelivery; bunker price hub",
    ),
    "amsterdam": (31060, "Amsterdam", "NL", True, "TC14 discharge, TC23 load"),
    "le_havre": (35840, "Le Havre", "FR", True, "TC23 discharge, the intra-EEA carbon example"),
    "bonny": (None, "Bonny", "NG", False, "TD20 load (offshore terminal)"),
    "singapore": (50000, "Singapore", "SG", False, "Bunker price hub; the Panamax detour passes it"),
}

#: The ports with dated public bunker prices for all three grades (Ship & Bunker
#: and the brokers' weekly tables): a route is priced at the one nearest its
#: load port by sea, the rule the Baltic Exchange applies to its tanker TCEs.
BUNKER_HUBS: tuple[str, ...] = ("singapore", "fujairah", "rotterdam", "houston")

#: Pub. 151, printed page 15 (PDF page 25): BONNY, NIGERIA (4 deg 27'21"N., 7 deg 10'22"E.)
_BONNY = (4 + 27 / 60 + 21 / 3600, 7 + 10 / 60 + 22 / 3600)


def load() -> dict[str, Port]:
    """Every study port, positioned from the committed World Port Index."""
    wpi = nga.wpi_ports()
    out: dict[str, Port] = {}
    for port_id, (number, name, country, eea, role) in _SPEC.items():
        if number is None:
            lat, lon = _BONNY
            source = "Pub. 151 page 15"
        else:
            entry = wpi[number]
            if entry["countryCode"] != country:
                raise ValueError("WPI %d is in %s, expected %s" % (number, entry["countryCode"], country))
            lat, lon = float(entry["ycoord"]), float(entry["xcoord"])
            source = "WPI %d (%s)" % (number, " ".join(entry["portName"].split()))
        out[port_id] = Port(port_id, name, country, round(lat, 4), round(lon, 4), source, role, eea)
    return out


def as_records(ports: Mapping[str, Port]) -> list[dict[str, Any]]:
    """The ports as plain records, for the seed file."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "country": p.country,
            "lat": p.lat,
            "lon": p.lon,
            "eea": p.eea,
            "source": p.source,
            "role": p.role,
        }
        for p in ports.values()
    ]
