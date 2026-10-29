"""IMO resolutions that define the sulphur emission control areas, fetched and recorded, not committed.

The resolutions are IMO documents. They are kept in data/raw/licensed/imo/
with their URL and sha256 in data/raw/manifest.json; what the study commits is
the coordinates and boundary lines it reads from them, in data/seed/eca.json,
each with its resolution and page.

* MEPC.328(76), the 2021 revised MARPOL Annex VI (in force 1 November 2022):
  regulation 14 (pages 26 and 27) and Appendix VII (pages 67 to 75), which
  lists the North American area (Pacific coast 47 points, Atlantic and Gulf of
  Mexico coasts 206 points, Hawaii 45 points) and the United States Caribbean
  Sea area (55 points).
* MEPC.361(79), the Mediterranean Sea emission control area for sulphur
  oxides: adopted 16 December 2022, in force 1 May 2024, ships exempt until
  1 May 2025; its Appendix VII paragraph 4 draws the boundary lines.
* MEPC.117(52), revised Annex I, regulation 1.11.2: the Baltic Sea area.
* MEPC.201(62), revised Annex V, regulation 1.14.6: the North Sea area.
* MEPC.392(82): the Canadian Arctic and Norwegian Sea areas, adopted 4 October
  2024, in force 1 March 2026; none of the study's routes enters them.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pdfplumber

from . import base

_CDN = "https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/"

DOCUMENTS: dict[str, dict[str, str]] = {
    "imo_mepc_328_76": {"file": "MEPC.328(76).pdf", "title": "Resolution MEPC.328(76), 2021 revised MARPOL Annex VI"},
    "imo_mepc_361_79": {"file": "MEPC.361(79).pdf", "title": "Resolution MEPC.361(79), Mediterranean Sea ECA for SOx"},
    "imo_mepc_117_52": {"file": "MEPC.117(52).pdf", "title": "Resolution MEPC.117(52), revised MARPOL Annex I"},
    "imo_mepc_201_62": {"file": "MEPC.201(62).pdf", "title": "Resolution MEPC.201(62), revised MARPOL Annex V"},
    "imo_mepc_392_82": {
        "file": "MEPC.392(82).pdf",
        "title": "Resolution MEPC.392(82), Canadian Arctic and Norwegian Sea ECAs",
    },
}

LICENCE = "IMO document; boundaries and dates cited with resolution and page, the PDF not redistributed"


def fetch(key: str) -> dict[str, Any]:
    """Download one resolution and record it in the raw manifest."""
    spec = DOCUMENTS[key]
    url = _CDN + spec["file"]
    response = base.http_get(url, headers={"Accept": "application/pdf"})
    if not response.content.startswith(b"%PDF"):
        raise base.SourceError("%s did not come back as a PDF" % spec["file"])
    return base.record_raw(
        key=key,
        url=url,
        path=base.RAW_LICENSED / "imo" / spec["file"],
        content=response.content,
        committable=False,
        publisher="International Maritime Organization",
        licence=LICENCE,
        note=spec["title"],
    )


def _text(key: str) -> list[tuple[int, str]]:
    """(PDF page number, text) for every page of a recorded resolution."""
    with pdfplumber.open(io.BytesIO(base.raw_bytes(key))) as pdf:
        return [(number, page.extract_text() or "") for number, page in enumerate(pdf.pages, start=1)]


_POINT = re.compile(
    r"^\s*(\d{1,3})\s+(\d{1,2})\s*\u00b0\s*(\d{1,2})\s*[\u2032'`]\s*\.?\s*(\d{1,2})\s*([NS])\s+"
    r"(\d{1,3})\s*\u00b0\s*(\d{1,2})\s*[\u2032'`]\s*\.?\s*(\d{1,2})\s*([EW])\s*$"
)
_PRINTED_PAGE = re.compile(r"-\s*(\d{1,3})\s*-")


def _minutes(whole: str, hundredths: str) -> float:
    return int(whole) + int(hundredths) / 100.0


def appendix_vii(key: str = "imo_mepc_328_76") -> dict[str, dict[str, Any]]:
    """The coordinate lists of Annex VI Appendix VII: part -> points and printed pages.

    Parts: na_pacific, na_atlantic_gulf, na_hawaii, us_caribbean. Each point is
    (point number, latitude, longitude) in decimal degrees, west and south
    negative. Coordinates are printed as degrees, minutes and hundredths of a
    minute (32 deg 32'.10 N is 32 degrees 32.10 minutes north).
    """
    parts: dict[str, dict[str, Any]] = {}
    current: str | None = None
    started = False
    for _, text in _text(key):
        printed = _PRINTED_PAGE.search(text)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("Appendix VII"):
                started = True
            if not started:
                continue
            if stripped.startswith("Appendix VIII"):
                return parts
            lowered = stripped.lower()
            if "pacific coasts of the united states and canada" in lowered:
                current = "na_pacific"
            elif "atlantic coasts of the united states" in lowered:
                current = "na_atlantic_gulf"
            elif "hawaiian islands" in lowered:
                current = "na_hawaii"
            elif "commonwealth of puerto rico" in lowered:
                current = "us_caribbean"
            match = _POINT.match(line)
            if match and current:
                number = int(match.group(1))
                lat = int(match.group(2)) + _minutes(match.group(3), match.group(4)) / 60.0
                lon = int(match.group(6)) + _minutes(match.group(7), match.group(8)) / 60.0
                lat = -lat if match.group(5) == "S" else lat
                lon = -lon if match.group(9) == "W" else lon
                entry = parts.setdefault(current, {"points": [], "pages": set()})
                entry["points"].append((number, round(lat, 6), round(lon, 6)))
                if printed:
                    entry["pages"].add(int(printed.group(1)))
    return parts
