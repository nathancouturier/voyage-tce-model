#!/usr/bin/env python
"""Build the emission control area polygons from the IMO resolutions and commit them as a seed.

    python scripts/eca.py            read the recorded resolutions, write data/seed/eca.json
    python scripts/eca.py --fetch    download the resolutions first (they are not committed)
    python scripts/eca.py --check    rebuild and compare with the committed seed, write nothing

The resolutions are IMO documents and stay out of git (data/raw/licensed/imo/);
the seed keeps what the study reads from them: the Appendix VII coordinate
lists, the boundary lines of the other areas, and their dates, each with its
source. Everything downstream reads the seed, so a fresh clone needs no IMO file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import eca, jsonio  # noqa: E402
from voyage.sources import base, imo  # noqa: E402

DOCUMENT = base.SEED / "eca.json"


def build() -> dict:
    parts = imo.appendix_vii()
    zones = eca.build(parts)
    return {
        "schema": "voyage-tce-model seed: sulphur emission control areas",
        "note": "Polygons as (longitude, latitude) rings. The North American and United States Caribbean areas are "
        "the coordinate lists of MARPOL Annex VI Appendix VII (resolution MEPC.328(76)), read by "
        "voyage.sources.imo; the North Sea, Baltic and Mediterranean areas follow their legal lines at sea and "
        "close over land. Built by scripts/eca.py.",
        "appendix_vii_points": {part: len(value["points"]) for part, value in sorted(parts.items())},
        "zones": eca.as_records(zones),
        "other_areas": list(eca.OTHER_AREAS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="download the IMO resolutions first")
    parser.add_argument("--check", action="store_true", help="compare with the committed seed and write nothing")
    args = parser.parse_args()
    if args.fetch:
        for key in imo.DOCUMENTS:
            imo.fetch(key)
    document = build()
    if args.check:
        if jsonio.dumps(document) != DOCUMENT.read_text(encoding="utf-8"):
            print("data/seed/eca.json differs from a rebuild")
            return 1
        print("data/seed/eca.json matches a rebuild")
        return 0
    jsonio.write(DOCUMENT, document)
    print("wrote %s: %s" % (DOCUMENT.relative_to(REPO_ROOT), ", ".join(z["id"] for z in document["zones"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
