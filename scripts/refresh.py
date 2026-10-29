#!/usr/bin/env python
"""Refresh the sourced series: the EU allowance price and the dollar rate.

    python scripts/refresh.py             fetch both, rewrite data/cache and data/raw/manifest.json, then export
    python scripts/refresh.py --offline   no network: check the committed caches against their rules and raw files
    python scripts/refresh.py --list      the jobs and the files each one owns, run nothing

Two inputs of the study are series a script can follow month by month: the EU
allowance price (the European Commission's auction reports, then the German
auctions DEHSt reports, as the sibling study jkm-ttf-arbitrage caches them) and
the Federal Reserve's H.10 dollar rate. Every other input is a dated figure read
by hand from a cited document into data/seed, with the passage it was read from:
a new bunker average, freight report or FFA assessment is a new document to
read, not a download to repeat, so no job fetches it.

The monthly workflow (.github/workflows/refresh.yml) runs this, then the gate,
and commits only if the gate passes.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import export, versions  # noqa: E402
from voyage.sources import base, ec_eua, frb_h10  # noqa: E402

JOBS = {
    "eua": ("data/cache/eua_monthly.csv", "EU allowance price, monthly: Commission auction reports, then DEHSt"),
    "fx": ("data/cache/usd_per_eur_daily.csv", "US dollars per euro, daily: Federal Reserve H.10"),
}


def check_eua() -> list[str]:
    """The committed EUA cache: months in order from the first, prices in bounds, DEHSt rows as published."""
    problems = []
    rows = ec_eua.read_cache()
    months = list(rows)
    if months != sorted(months) or len(set(months)) != len(months):
        problems.append("eua: the months are not in order or repeat")
    if months and months[0] != ec_eua.FIRST_MONTH:
        problems.append("eua: the cache starts at %s, not %s" % (months[0], ec_eua.FIRST_MONTH))
    for month, row in rows.items():
        price = float(row["eua_eur_t"])
        if not ec_eua.BOUNDS[0] <= price <= ec_eua.BOUNDS[1]:
            problems.append("eua: %s reads %s" % (month, price))
    dehst = base.raw_bytes(ec_eua.DEHST_KEY).decode("utf-8")
    published = {r["date"][:7]: "%.2f" % float(r["eua_eur_t"]) for r in csv.DictReader(io.StringIO(dehst))}
    for month, row in rows.items():
        if row["source"].startswith("DEHSt") and published.get(month) != row["eua_eur_t"]:
            problems.append("eua: %s reads %s, DEHSt published %s" % (month, row["eua_eur_t"], published.get(month)))
    return problems


def check_fx() -> list[str]:
    """The committed H.10 cache: days in order, every published rate in bounds."""
    problems = []
    days = frb_h10.read_cache()
    dates = [d for d, _ in days]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        problems.append("fx: the days are not in order or repeat")
    for day, value in days:
        if value is not None and not frb_h10.BOUNDS[0] <= value <= frb_h10.BOUNDS[1]:
            problems.append("fx: %s reads %s" % (day, value))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="check the committed caches, no network")
    parser.add_argument("--list", action="store_true", help="list the jobs and run nothing")
    args = parser.parse_args()
    if args.list:
        for name, (path, what) in JOBS.items():
            print("%-4s %s  %s" % (name, path, what))
        return 0
    if args.offline:
        problems = check_eua() + check_fx()
        for problem in problems:
            print("FAIL  " + problem)
        if problems:
            return 1
        print(
            "the committed caches hold %d months of EUA prices and %d days of the dollar rate, every one in bounds"
            % (len(ec_eua.read_cache()), len(frb_h10.read_cache()))
        )
        return 0
    rows = ec_eua.refresh()
    print("eua: %d months, %s to %s" % (len(rows), rows[0]["month"], rows[-1]["month"]))
    entry = frb_h10.refresh()
    print("fx: %d days, prepared %s" % (entry["rows"], entry["prepared"]))
    problems = check_eua() + check_fx()
    if problems:
        for problem in problems:
            print("FAIL  " + problem)
        return 1
    changed = export.write(export.build()) + versions.write()
    print("export: %d file(s) changed%s" % (len(changed), (": " + ", ".join(changed)) if changed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
