"""The published distances the sea routes are checked against, read again from NGA Pub. 151."""

import re
from functools import cache

import pdfplumber
import pytest

from voyage import cases, distance_checks, sea_routes
from voyage.sources import base

PUB151 = base.REPO_ROOT / "data" / "raw" / "public" / "nga" / "Pub151bk.pdf"
#: Pub. 151 numbers its pages ten below the PDF's.
PAGE_OFFSET = 10


def flat(text: str) -> str:
    """No white space and straight apostrophes: the page's two columns break lines anywhere."""
    return re.sub(r"\s+", "", text.replace(chr(0x2019), "'"))


@cache
def page(printed: int) -> str:
    with pdfplumber.open(PUB151) as pdf:
        return flat(pdf.pages[printed + PAGE_OFFSET - 1].extract_text() or "")


PARTS = [(check.id, part) for check in distance_checks.CHECKS for part in check.parts]


@pytest.mark.parametrize(("check", "part"), PARTS, ids=["%s p%d" % (c, p.page) for c, p in PARTS])
def test_each_published_figure_is_printed_on_its_page(check, part):
    text = page(part.page)
    figure = f"{part.nm:,}"
    # A port's list can start on an earlier page and run on to this one.
    heading = page(part.page - 2) + page(part.page - 1) + text
    for word in part.entry.replace(",", " ").split():
        assert word in heading, (check, part.entry)
    line = flat(part.line)
    # A line that wraps is found by its place name and its figure on the same page.
    place = line.split("(")[0].split(",")[0]
    assert (line + "," + figure) in text or (place in text and figure in text), (check, part.line, figure)


def test_checks_cover_every_trade_and_most_pass():
    checks = cases.seed("sea_routes.json")["pub151_checks"]["checks"]
    assert {c["id"] for c in checks} == {c.id for c in distance_checks.CHECKS}
    within = [c for c in checks if c["within_tolerance"]]
    assert len(within) >= 10
    # TD22's ballast routing, round the Cape and through the Sunda Strait, is the longest check.
    td22 = next(c for c in checks if c["id"] == "galveston_shanghai_cape")
    assert td22["within_tolerance"]


def test_amsterdam_is_reached_from_ijmuiden_not_through_the_lakes():
    legs = cases.seed("sea_routes.json")["legs"]
    for key, leg in legs.items():
        if "amsterdam" in (leg["from"], leg["to"]):
            assert "IJsselmeer" not in leg["passes"], key
    gate = sea_routes.SEA_GATES["amsterdam"]
    line = cases.lines()[sea_routes.leg_key("amsterdam", "le_havre", "direct")]
    port = cases.ports()["amsterdam"]
    assert line[0] == [port["lon"], port["lat"]]
    # The canal stretch Pub. 151 prints as 14 miles (page 44).
    from voyage import geo

    assert geo.haversine_nm(line[0], line[1]) == pytest.approx(14.0, abs=1.0)
    assert abs(line[1][0] - gate[0]) < 0.1 and abs(line[1][1] - gate[1]) < 0.1


def test_eca_miles_are_the_same_both_ways_on_every_leg_that_crosses_180_degrees():
    legs = cases.seed("sea_routes.json")["legs"]
    lines = cases.lines()
    crossing = [leg for key, leg in legs.items() if max(c[0] for c in lines[key]) > 180.0]
    assert crossing
    for leg in crossing:
        there = sum(v for _, v in cases.eca_miles(leg["from"], leg["to"], leg["routing"], "2026-10-23"))
        back = sum(v for _, v in cases.eca_miles(leg["to"], leg["from"], leg["routing"], "2026-10-23"))
        assert there == pytest.approx(back, abs=1.0), (leg["from"], leg["to"], leg["routing"])
