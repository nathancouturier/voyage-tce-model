"""Source adapters: robots rules, the auction report parser on its committed fixture, the caches."""

from voyage.sources import base, ec_eua, frb_h10


def test_robots_longest_match_wins_and_allow_breaks_ties():
    rules = base.parse_robots("User-agent: *\nDisallow: /private\nAllow: /private/open\n", "mozilla")
    assert not base.robots_allows(rules, "https://example.org/private/x")
    assert base.robots_allows(rules, "https://example.org/private/open/y")
    assert base.robots_allows(rules, "https://example.org/public")
    rules = base.parse_robots("User-agent: *\nDisallow: /*.pdf$\n", "mozilla")
    assert not base.robots_allows(rules, "https://example.org/a/b.pdf")
    assert base.robots_allows(rules, "https://example.org/a/b.pdf?x=1")


def test_auction_report_fixture_parses():
    rows = dict(ec_eua.parse_report(base.raw_bytes("ec_cap_report_202506"), "202506"))
    assert rows["2025-06"] == 72.06
    assert len(rows) >= 12


def test_caches_are_complete_for_the_study_months():
    eua = ec_eua.read_cache()
    assert eua["2026-08"]["eua_eur_t"] == "82.31"
    assert all(month in eua for month in ("2024-01", "2025-06", "2026-03"))
    value, count = frb_h10.monthly_mean("2026-08")
    assert count == 21
    assert 1.0 < value < 1.3
