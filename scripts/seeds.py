#!/usr/bin/env python
"""Write the seeds that come from the study's own modules: the Baltic route and vessel definitions.

    python scripts/seeds.py            write data/seed/baltic.json
    python scripts/seeds.py --check    compare with the committed seed, write nothing

The definitions live in src/voyage/baltic.py with the guide's page for each;
the seed is the same content as plain JSON for the site and for anyone who
reads the data without Python.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import baltic, jsonio  # noqa: E402
from voyage.sources import base  # noqa: E402

DOCUMENT = base.SEED / "baltic.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = dict(baltic.as_records(), schema="voyage-tce-model seed: Baltic Exchange routes and vessels")
    if args.check:
        same = jsonio.dumps(document) == DOCUMENT.read_text(encoding="utf-8")
        print("data/seed/baltic.json %s" % ("matches" if same else "differs from a rebuild"))
        return 0 if same else 1
    jsonio.write(DOCUMENT, document)
    print("wrote data/seed/baltic.json: %d vessels, %d routes" % (len(document["vessels"]), len(document["routes"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
