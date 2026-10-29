"""EU allowance prices, monthly, EUR per tonne of CO2: the Commission's auction reports, then DEHSt.

Adapted from the sibling study jkm-ttf-arbitrage (lngarb.sources.ec_eua and
lngarb.sources.dehst), as the study brief asks, and kept to the months the EU
ETS has covered shipping (from January 2024) and the year before.

* To June 2025: the European Commission's reports on the auctions held by the
  common auction platform, Table 1, "Average auction clearing price" of general
  allowances, one quarterly report printing fifteen months. A month printed by
  several reports is taken from the latest. Licence: CC BY 4.0 ("reuse is
  allowed, provided appropriate credit is given and changes are indicated",
  https://commission.europa.eu/legal-notice_en); the months are combined from
  several reports by this study. The latest report on the Commission's page on
  29 October 2026 covers April to June 2025.
* From July 2025: the German Emissions Trading Authority's (DEHSt) monthly
  average of Germany's own auctions on EEX, a proxy for the platform average
  (0.13 EUR/t above it on average over January 2013 to June 2025, measured by
  the sibling study). dehst.de refuses this environment's connections, so the
  months are read from the sibling study's committed cache of DEHSt's reports,
  pinned to commit cf42430b, which records the report each month comes from.
  Licence: CC BY-NC-ND 4.0, "Source: EEX, DEHSt"; reproduced unchanged for this
  non-commercial study.
"""

from __future__ import annotations

import csv
import io
import re
from urllib.parse import urljoin

import pdfplumber

from . import base

PAGE_URL = (
    "https://climate.ec.europa.eu/areas-action/carbon-markets/eu-emissions-trading-system-eu-ets/"
    "auctioning-allowances_en"
)
BASE_URL = "https://climate.ec.europa.eu"
#: Reports read: the quarterly reports whose fifteen months reach January 2023 onwards.
REPORTS = ("202403", "202406", "202409", "202412", "202503", "202506")
#: The one report committed, as the parser's test fixture; the others are kept
#: in the bulk store with their hashes.
FIXTURE_REPORT = "202506"
DEHST_URL = (
    "https://raw.githubusercontent.com/nathancouturier/jkm-ttf-arbitrage/"
    "cf42430bab2d22dc3c885bd48bc30badfdabbdc2/data/cache/dehst_eua_german_auction_monthly.csv"
)
DEHST_KEY = "jkm_dehst_eua_monthly_cf42430b"
CACHE = base.CACHE / "eua_monthly.csv"
FIRST_MONTH = "2023-01"
BOUNDS = (1.0, 200.0)

_LINK = re.compile(r'href="([^"]*filename=cap_report_(\d{6})_en\.pdf)"')
_MONTHS = {
    m: i
    for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)
}
_ROW = re.compile(
    r"^([A-Z][a-z]{2,8}\.?) ((?:20)?\d{2}) "
    r"([\d][\d ,]*?) ([\d][\d ,]*?) ([\d][\d ,]*?) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)$"
)
_TOTAL = re.compile(r"^20\d\d total\b", re.IGNORECASE)


def report_links(html: str) -> dict[str, str]:
    return {report: urljoin(BASE_URL, href.replace("&amp;", "&")) for href, report in _LINK.findall(html)}


def parse_report(pdf: bytes, report: str) -> list[tuple[str, float]]:
    """Table 1 of one report: (YYYY-MM, average clearing price EUR/t)."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = "\n".join((page.extract_text() or "") for page in document.pages)
    start = text.find("Table 1: General allowances")
    if start == -1:
        raise base.SourceError("report %s has no Table 1" % report)
    rows: list[tuple[str, float]] = []
    for line in text[start:].splitlines():
        line = line.strip()
        if rows and _TOTAL.match(line):
            break
        match = _ROW.match(line)
        if match:
            month = _MONTHS[match.group(1).rstrip(".").lower()[:3]]
            year = int(match.group(2)) if len(match.group(2)) == 4 else 2000 + int(match.group(2))
            price = float(match.group(9))
            if not BOUNDS[0] <= price <= BOUNDS[1]:
                raise base.SourceError("report %s: %s %s reads %s" % (report, year, month, price))
            rows.append(("%04d-%02d" % (year, month), price))
    if len(rows) < 3:
        raise base.SourceError("report %s: Table 1 gives %d months" % (report, len(rows)))
    return rows


def fetch_reports() -> dict[str, bytes]:
    links = report_links(base.http_get(PAGE_URL).text)
    out = {}
    for report in REPORTS:
        if report not in links:
            raise base.SourceError("the auctioning page no longer links report %s" % report)
        response = base.http_get(links[report], timeout=120)
        root = base.RAW_PUBLIC if report == FIXTURE_REPORT else base.RAW_BULK
        base.record_raw(
            key="ec_cap_report_%s" % report,
            url=links[report],
            path=root / "ec" / ("cap_report_%s_en.pdf" % report),
            content=response.content,
            committable=True,
            bulk=report != FIXTURE_REPORT,
            publisher="European Commission",
            licence="CC BY 4.0 (Commission legal notice)",
            note="Auction report, Table 1 monthly averages",
        )
        out[report] = response.content
    return out


def fetch_dehst() -> bytes:
    response = base.http_get(DEHST_URL, headers={"Accept": "text/plain"})
    base.record_raw(
        key=DEHST_KEY,
        url=DEHST_URL,
        path=base.RAW_PUBLIC / "dehst" / "dehst_eua_german_auction_monthly.csv",
        content=response.content,
        committable=True,
        publisher="DEHSt (German Emissions Trading Authority), as cached by jkm-ttf-arbitrage",
        licence="CC BY-NC-ND 4.0, Source: EEX, DEHSt; monthly averages reproduced unchanged",
        note="monthly average of Germany's auctions; dehst.de refuses this environment, read from the sibling cache",
    )
    return response.content


def combine(reports: dict[str, bytes], dehst_csv: bytes) -> list[dict[str, str]]:
    """One row per month from FIRST_MONTH: the Commission's figure to June 2025, DEHSt's after."""
    commission: dict[str, tuple[float, str]] = {}
    for report in sorted(reports):
        for month, price in parse_report(reports[report], report):
            commission[month] = (price, "cap_report_%s" % report)
    rows = []
    last_commission = max(commission)
    for month in sorted(commission):
        if month >= FIRST_MONTH:
            price, report = commission[month]
            rows.append(
                {"month": month, "eua_eur_t": "%.2f" % price, "source": "European Commission", "report": report}
            )
    reader = csv.DictReader(io.StringIO(dehst_csv.decode("utf-8")))
    for row in reader:
        month = row["date"][:7]
        if month > last_commission:
            price = float(row["eua_eur_t"])
            if not BOUNDS[0] <= price <= BOUNDS[1]:
                raise base.SourceError("DEHSt %s reads %s" % (month, price))
            rows.append(
                {
                    "month": month,
                    "eua_eur_t": "%.2f" % price,
                    "source": "DEHSt (German auctions, proxy)",
                    "report": row["report"],
                }
            )
    return rows


def write_cache(rows: list[dict[str, str]]) -> None:
    with open(CACHE, "w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=["month", "eua_eur_t", "source", "report"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_cache() -> dict[str, dict[str, str]]:
    with open(CACHE, encoding="utf-8") as handle:
        return {row["month"]: row for row in csv.DictReader(handle)}


def refresh() -> list[dict[str, str]]:
    rows = combine(fetch_reports(), fetch_dehst())
    write_cache(rows)
    return rows
