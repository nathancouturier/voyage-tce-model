"""The committed seeds: routes, emission control areas, Baltic definitions."""

import pytest

from voyage import baltic, cases, geo, jsonio, sea_routes
from voyage.sources import base


def test_committed_routes_pass_their_checks():
    assert sea_routes.leg_problems(cases.seed("sea_routes.json"), cases.lines()) == []


def test_eca_polygons_contain_and_exclude_known_waters():
    zones = {z.id: z for z in cases.zones()}
    inside = {
        "north_sea": (3.0, 54.0),
        "baltic": (19.0, 57.5),
        "mediterranean": (18.0, 35.0),
        "na_atlantic_gulf": (-75.0, 38.0),
        "na_pacific": (-125.5, 45.0),
    }
    for zone_id, point in inside.items():
        assert geo.point_in_polygon(point, zones[zone_id].rings), zone_id
    # The Sea of Marmara lies outside the Mediterranean ECA (MEPC.361(79): the Dardanelles line).
    assert not geo.point_in_polygon((28.0, 40.8), zones["mediterranean"].rings)
    # The Atlantic off Portugal lies outside every area in force.
    assert not any(geo.point_in_polygon((-12.0, 40.0), z.rings) for z in zones.values())


def test_appendix_vii_point_counts():
    counts = cases.seed("eca.json")["appendix_vii_points"]
    assert counts == {"na_atlantic_gulf": 206, "na_hawaii": 45, "na_pacific": 47, "us_caribbean": 55}


def test_baltic_seed_matches_the_module():
    document = dict(baltic.as_records(), schema="voyage-tce-model seed: Baltic Exchange routes and vessels")
    assert jsonio.dumps(document) == (base.SEED / "baltic.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("code", baltic.STUDY_ROUTES)
def test_study_routes_carry_the_guide_commission(code):
    route = baltic.ROUTES[code]
    assert route.commission_pct == (5.0 if route.segment == "dry" else 3.75)
