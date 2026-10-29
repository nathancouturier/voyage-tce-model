"""NGA Maritime Safety Information: the World Port Index (Pub. 150) and Distances Between Ports (Pub. 151).

Both are works of the United States Government: Pub. 151 reads "NO COPYRIGHT
CLAIMED UNDER TITLE 17 U.S.C." on its title page, and the World Port Index is
published by the same agency on the same terms. Both raw files are committed.

* The World Port Index is read from the agency's own JSON service, the one its
  web page queries, and stored gzipped. Port positions are degrees, the
  service's ycoord (latitude) and xcoord (longitude).
* Pub. 151, eleventh edition (2001), is read from the agency's publication
  store. Its tables are four columns to a page; only the pages holding the
  pairs the study checks are ever parsed, by voyage.distances.
"""

from __future__ import annotations

import json
from typing import Any

from . import base

WPI_URL = "https://msi.nga.mil/api/publications/world-port-index?output=json"
WPI_KEY = "nga_wpi_ports"
WPI_PATH = base.RAW_PUBLIC / "nga" / "wpi_ports.json.gz"

PUB151_URL = "https://msi.nga.mil/api/publications/download?key=16694076/SFH00000/Pub151bk.pdf&type=view"
PUB151_KEY = "nga_pub151"
PUB151_PATH = base.RAW_PUBLIC / "nga" / "Pub151bk.pdf"

PUBLISHER = "National Geospatial-Intelligence Agency, Maritime Safety Information"
LICENCE = "Work of the United States Government, no copyright claimed under Title 17 U.S.C."


def fetch_wpi() -> dict[str, Any]:
    """Download the whole World Port Index and record it in the raw manifest."""
    response = base.http_get(WPI_URL, headers={"Accept": "application/json"})
    payload = response.json()
    ports = payload.get("ports") or []
    if len(ports) < 1000:
        raise base.SourceError("the World Port Index answered with %d ports, expected thousands" % len(ports))
    return base.record_raw(
        key=WPI_KEY,
        url=WPI_URL,
        path=WPI_PATH,
        content=response.content,
        committable=True,
        publisher=PUBLISHER,
        licence=LICENCE,
        note="World Port Index (Pub. 150), every port, as the agency's JSON service returns it",
        compress=True,
    )


def fetch_pub151() -> dict[str, Any]:
    """Download Pub. 151 and record it in the raw manifest."""
    response = base.http_get(PUB151_URL, headers={"Accept": "application/pdf"})
    if not response.content.startswith(b"%PDF"):
        raise base.SourceError("Pub. 151 did not come back as a PDF")
    return base.record_raw(
        key=PUB151_KEY,
        url=PUB151_URL,
        path=PUB151_PATH,
        content=response.content,
        committable=True,
        publisher=PUBLISHER,
        licence=LICENCE,
        note="Pub. 151, Distances Between Ports, eleventh edition, 2001",
    )


def wpi_ports() -> dict[int, dict[str, Any]]:
    """Every World Port Index entry by port number, from the committed raw file."""
    payload = json.loads(base.raw_bytes(WPI_KEY))
    return {int(port["portNumber"]): port for port in payload["ports"]}
