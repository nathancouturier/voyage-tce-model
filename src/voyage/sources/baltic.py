"""The Baltic Exchange's Guide to Market Benchmarks, fetched and recorded, never committed.

The guide is a static PDF on the Baltic's content store and answers a script;
the Baltic's HTML pages, the circular archive included, answer scripted
requests with a browser challenge and are not fetched. The PDF is the Baltic's
copyright: it is kept in data/raw/licensed/, which git ignores, and only its
URL and sha256 are committed in data/raw/manifest.json. The figures the study
uses are transcribed, with their pages, in voyage.baltic.
"""

from __future__ import annotations

from typing import Any

from .. import baltic
from . import base

GMB_PATH = base.RAW_LICENSED / "baltic" / "GMB.pdf"

#: The Baltic's worked TD3C TCE calculation of July 2017, a circular attachment:
#: vessel, mileage, days and fuel tonnes, no prices. voyage.anchors reproduces it.
TD3C_NOTE_URL = (
    "https://www.balticexchange.com/content/dam/balticexchange/consumer/data-services-/historicalcircular_docs/"
    "TD3C-TCE_Calculation_Process_0717.pdf"
)
TD3C_NOTE_KEY = "baltic_td3c_tce_process_2017"
TD3C_NOTE_PATH = base.RAW_LICENSED / "baltic" / "TD3C-TCE_Calculation_Process_0717.pdf"


def fetch_gmb() -> dict[str, Any]:
    """Download the current guide and record it in the raw manifest."""
    response = base.http_get(baltic.GMB["url"], headers={"Accept": "application/pdf"})
    if not response.content.startswith(b"%PDF"):
        raise base.SourceError("the Guide to Market Benchmarks did not come back as a PDF")
    return base.record_raw(
        key=baltic.GMB["raw_key"],
        url=baltic.GMB["url"],
        path=GMB_PATH,
        content=response.content,
        committable=False,
        publisher=baltic.GMB["publisher"],
        licence="Copyright Baltic Exchange Information Services Ltd; figures cited with page numbers, "
        "not redistributed",
        note="Guide to Market Benchmarks, version 8.8, September 2026",
    )


def fetch_td3c_note() -> dict[str, Any]:
    """Download the Baltic's TD3C TCE calculation process note (July 2017) and record it."""
    response = base.http_get(TD3C_NOTE_URL, headers={"Accept": "application/pdf"})
    if not response.content.startswith(b"%PDF"):
        raise base.SourceError("the TD3C TCE calculation note did not come back as a PDF")
    return base.record_raw(
        key=TD3C_NOTE_KEY,
        url=TD3C_NOTE_URL,
        path=TD3C_NOTE_PATH,
        content=response.content,
        committable=False,
        publisher=baltic.GMB["publisher"],
        licence="Copyright Baltic Exchange Information Services Ltd; figures cited, not redistributed",
        note="TD3C Time Charter Equivalent (TCE) Calculation Process, July 2017, two pages",
    )
