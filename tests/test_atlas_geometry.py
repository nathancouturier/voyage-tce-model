"""The atlas of the Map view, read from the served artifacts: every line inside the map, from its loading port
to its discharge port, inside its box, cut only at the map's sides; and every route's frames inside the map, at
the frame's shape, round the lines they show."""

import json
import re
from pathlib import Path

import pytest

from voyage import routemap

ROOT = Path(__file__).resolve().parents[1]
GEO = json.loads((ROOT / "data" / "map.json").read_text(encoding="utf-8"))["atlas"]
ATLAS = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
MOVE = re.compile(r"([ML])(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)")
# Coordinates are written to one decimal place of a map unit.
CLOSE = 0.051
LEFT, TOP, RIGHT, BOTTOM = routemap.atlas_window()
PROJECTION_BOTTOM = (routemap.LAT_MAX - routemap.LAT_MIN) * routemap.PX_PER_DEGREE


def pieces(d: str) -> list[list[tuple[float, float]]]:
    """A path's pieces, each a list of points: a new piece at every move."""
    out: list[list[tuple[float, float]]] = []
    for command, x, y in MOVE.findall(d):
        if command == "M":
            out.append([])
        out[-1].append((float(x), float(y)))
    return out


def legs_of(item: dict) -> list[str]:
    keys = [item["legs"]["laden"], item["legs"]["ballast"]]
    for alternative in item["alternatives"]:
        keys.extend(alternative["legs"])
    return [key for key in keys if key]


@pytest.mark.parametrize("key", sorted(GEO["legs"]))
def test_a_leg_lies_inside_the_map_and_inside_its_box(key: str) -> None:
    leg = GEO["legs"][key]
    x0, y0, x1, y1 = leg["box"]
    points = [p for piece in pieces(leg["d"]) for p in piece]
    assert points, key
    for x, y in points:
        assert LEFT - CLOSE <= x <= RIGHT + CLOSE, (key, x)
        assert 0.0 <= y <= PROJECTION_BOTTOM, (key, y)
        assert x0 - CLOSE <= x <= x1 + CLOSE and y0 - CLOSE <= y <= y1 + CLOSE, (key, x, y, leg["box"])


@pytest.mark.parametrize("key", sorted(GEO["legs"]))
def test_a_leg_runs_from_its_loading_port_to_its_discharge_port(key: str) -> None:
    leg = GEO["legs"][key]
    first, last = leg["start"], leg["end"]
    for port_id, point in ((leg["from"], first), (leg["to"], last)):
        port = GEO["ports"][port_id]
        assert abs(port["x"] - point[0]) <= CLOSE and abs(port["y"] - point[1]) <= CLOSE, (key, port_id, point)
    drawn = pieces(leg["d"])
    starts = [piece[0] for piece in drawn]
    ends = [piece[-1] for piece in drawn]
    assert any(abs(x - first[0]) <= CLOSE and abs(y - first[1]) <= CLOSE for x, y in starts), key
    assert any(abs(x - last[0]) <= CLOSE and abs(y - last[1]) <= CLOSE for x, y in ends), key


@pytest.mark.parametrize("key", sorted(GEO["legs"]))
def test_a_leg_is_cut_only_where_it_leaves_the_map_across_the_pacific(key: str) -> None:
    leg = GEO["legs"][key]
    drawn = pieces(leg["d"])
    # Two cut ends a crossing: one where the line leaves the map, one where it comes back.
    assert len(leg["edges"]) == 2 * (len(drawn) - 1), (key, leg["edges"])
    for x, _ in leg["edges"]:
        assert abs(x - LEFT) <= CLOSE or abs(x - RIGHT) <= CLOSE, (key, x)


@pytest.mark.parametrize("item", ATLAS["items"], ids=lambda item: item["id"])
def test_a_route_is_framed_inside_the_map_at_the_frame_shape(item: dict) -> None:
    window_aspect = (RIGHT - LEFT) / (BOTTOM - TOP)
    # A route too wide for the phone's taller frame keeps the window's.
    tall = item["view_tall"] != item["view"]
    for name, aspect, top, bottom in (
        ("view", window_aspect, TOP, BOTTOM),
        (
            "view_tall",
            routemap.ATLAS_TALL_ASPECT if tall else window_aspect,
            0.0 if tall else TOP,
            PROJECTION_BOTTOM if tall else BOTTOM,
        ),
    ):
        x, y, w, h = item[name]
        assert w / h == pytest.approx(aspect, rel=2e-3), (item["id"], name)
        assert x >= LEFT - CLOSE and x + w <= RIGHT + CLOSE, (item["id"], name)
        assert y >= top - CLOSE and y + h <= bottom + CLOSE, (item["id"], name)
        # No closer than the zoom the map allows.
        assert w >= (RIGHT - LEFT) / routemap.ATLAS_ZOOM_MAX - CLOSE, (item["id"], name)


@pytest.mark.parametrize("item", ATLAS["items"], ids=lambda item: item["id"])
def test_a_route_frame_holds_its_lines_and_its_alternatives(item: dict) -> None:
    for name in ("view", "view_tall"):
        x, y, w, h = item[name]
        for key in legs_of(item):
            x0, y0, x1, y1 = GEO["legs"][key]["box"]
            assert x - CLOSE <= x0 and x1 <= x + w + CLOSE, (item["id"], name, key)
            assert y - CLOSE <= y0 and y1 <= y + h + CLOSE, (item["id"], name, key)


def test_a_small_box_is_framed_at_the_closest_zoom_round_its_middle() -> None:
    x, y, w, h = routemap.frame_box([[700.0, 100.0, 702.0, 104.0]])
    assert w == pytest.approx((RIGHT - LEFT) / routemap.ATLAS_ZOOM_MAX, abs=CLOSE)
    assert w / h == pytest.approx((RIGHT - LEFT) / (BOTTOM - TOP), rel=2e-3)
    assert x + w / 2.0 == pytest.approx(701.0, abs=CLOSE)
    assert y + h / 2.0 == pytest.approx(102.0, abs=CLOSE)


def test_lines_too_wide_for_the_taller_frame_keep_the_window_frame() -> None:
    boxes = [[LEFT + 20.0, 60.0, RIGHT - 20.0, 200.0]]
    assert routemap.frame_box(boxes, routemap.ATLAS_TALL_ASPECT) == routemap.frame_box(boxes)


def test_a_box_wider_than_the_map_is_framed_as_the_whole_map() -> None:
    x, y, w, h = routemap.frame_box([[LEFT - 50.0, 40.0, RIGHT + 50.0, 60.0]])
    assert [x, w] == pytest.approx([LEFT, RIGHT - LEFT], abs=CLOSE)
    assert y >= TOP - CLOSE and y + h <= BOTTOM + CLOSE
