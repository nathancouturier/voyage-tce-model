"""Every figure a seed quotes is printed in the document it cites (where the raw file is on disk)."""

import pytest

from voyage import cases, provenance
from voyage.sources import base

SEEDS = ("market.json", "anchors.json", "ffa.json", "canals.json", "events.json", "conventions.json")


@pytest.mark.parametrize("name", SEEDS)
def test_quotes_are_found(name):
    result = provenance.check(cases.seed(name))
    assert not result["missing"], result["missing"]
    if not result["found"]:
        pytest.skip("the raw files behind %s are not on this machine (licensed, not committed)" % name)


@pytest.mark.parametrize("name", SEEDS)
def test_every_cited_key_is_in_the_manifest(name):
    manifest = base.raw_manifest()["files"]
    for path, node in provenance.cited(cases.seed(name)):
        assert node["raw_key"] in manifest, path


def test_normalise_plains_dashes_and_spacing():
    assert provenance.normalise("US Gulf–Qingdao  at  $76.29/mt ,") == "US Gulf-Qingdao at $76.29/mt,"
