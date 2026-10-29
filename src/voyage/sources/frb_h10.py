"""US dollars per euro, daily, from the Federal Reserve Board's H.10 release.

The noon buying rate in New York for cable transfers payable in euros,
certified for customs purposes by the Federal Reserve Bank of New York, quoted
in US dollars per euro: the direction the study's EU ETS conversion needs. The
Board publishes the release as one SDMX-ML package with every series; this
module keeps RXI$US_N.B.EU, as the sibling study jkm-ttf-arbitrage does
(lngarb.sources.h10 and lngarb.sources.frb, adapted without pandas).

A day with no rate carries OBS_STATUS NA, ND or NC and the sentinel -9999,
which is never read as a price. The package is a work of the United States
Government; it is large and re-issued weekly, so it is kept in data/raw/bulk/
with its hash, and the derived series is committed as
data/cache/usd_per_eur_daily.csv from 2023 onwards, the years the study prices.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from xml.etree import ElementTree

from . import base

ZIP_URL = "https://www.federalreserve.gov/releases/h10/data/FRB_h10_xml.zip"
PAGE_URL = "https://www.federalreserve.gov/releases/h10/hist/dat00_eu.htm"
KEY = "frb_h10_package"
PATH = base.RAW_BULK / "frb" / "FRB_h10_xml.zip"
MEMBER = "H10_data.xml"
SERIES = "RXI$US_N.B.EU"
DESCRIPTION = "EMU Members Euro (USD per EUR)"
CACHE = base.CACHE / "usd_per_eur_daily.csv"
FIRST_DAY = "2023-01-01"
#: The euro's range on H.10 since 1999, from 0.8270 to 1.6010: a guard against
#: a misread series or a rate quoted the other way up.
BOUNDS = (0.8, 1.7)


def fetch() -> dict:
    response = base.http_get(ZIP_URL, headers={"Accept": "*/*"})
    return base.record_raw(
        key=KEY,
        url=ZIP_URL,
        path=PATH,
        content=response.content,
        committable=True,
        bulk=True,
        publisher="Board of Governors of the Federal Reserve System, H.10",
        licence="Work of the United States Government, public domain",
        note="H.10 release package, every series, SDMX-ML",
    )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse(payload: bytes, first_day: str = FIRST_DAY) -> tuple[list[tuple[str, float | None, str]], str]:
    """(day, USD per EUR or None, status) from first_day, and the package's Prepared time."""
    archive = zipfile.ZipFile(io.BytesIO(payload))
    rows: list[tuple[str, float | None, str]] = []
    prepared = ""
    found = 0
    described = False
    in_series = False
    with archive.open(MEMBER) as handle:
        for event, element in ElementTree.iterparse(handle, events=("start", "end")):
            name = _local(element.tag)
            if event == "end" and name == "Prepared" and not prepared:
                prepared = (element.text or "").strip()
            if name == "Series":
                if event == "start":
                    in_series = element.attrib.get("SERIES_NAME") == SERIES
                    if in_series:
                        found += 1
                        if element.attrib.get("UNIT_MULT") != "1":
                            raise base.SourceError("%s has UNIT_MULT %r" % (SERIES, element.attrib.get("UNIT_MULT")))
                else:
                    in_series = False
                    element.clear()
                continue
            if not in_series or event != "end":
                continue
            if name == "AnnotationText" and (element.text or "").strip() == DESCRIPTION:
                described = True
            elif name == "Obs":
                day = element.attrib["TIME_PERIOD"]
                status = element.attrib.get("OBS_STATUS", "")
                if day >= first_day:
                    if status == "A":
                        value = float(element.attrib["OBS_VALUE"])
                        if not BOUNDS[0] <= value <= BOUNDS[1]:
                            raise base.SourceError("%s on %s reads %s, outside %s" % (SERIES, day, value, BOUNDS))
                        rows.append((day, value, status))
                    elif status in ("NA", "ND", "NC"):
                        rows.append((day, None, status))
                    else:
                        raise base.SourceError("%s on %s has unknown status %r" % (SERIES, day, status))
                element.clear()
    if found != 1 or not described:
        raise base.SourceError("%s found %d times, described=%s" % (SERIES, found, described))
    rows.sort()
    return rows, prepared


def write_cache(rows: list[tuple[str, float | None, str]]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "usd_per_eur", "obs_status"])
        for day, value, status in rows:
            writer.writerow([day, "" if value is None else "%.4f" % value, status])


def read_cache() -> list[tuple[str, float | None]]:
    with open(CACHE, encoding="utf-8") as handle:
        return [
            (row["date"], float(row["usd_per_eur"]) if row["usd_per_eur"] else None) for row in csv.DictReader(handle)
        ]


def monthly_mean(month: str) -> tuple[float, int]:
    """The mean of the month's published days (YYYY-MM), and how many days it averages."""
    values = [v for d, v in read_cache() if d.startswith(month) and v is not None]
    if not values:
        raise base.SourceError("no H.10 euro rate published in %s" % month)
    return math.fsum(values) / len(values), len(values)


def refresh() -> dict:
    entry = fetch()
    rows, prepared = parse(base.raw_bytes(KEY))
    write_cache(rows)
    entry = dict(entry)
    entry["prepared"] = prepared
    entry["rows"] = len(rows)
    return entry
