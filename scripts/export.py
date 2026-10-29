#!/usr/bin/env python
"""Write the site's artifacts from the seeds, the caches and the engine.

    python scripts/export.py           write data/*.json and data/downloads/*.csv
    python scripts/export.py --check   rebuild in memory and fail if any committed file differs

The files are the same bytes on every run, so the check holds in the gate and in CI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voyage import export, versions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = export.build()
    if args.check:
        stale = export.check(files)
        stale += versions.check()
        if stale:
            print("stale: " + ", ".join(stale) + " (run python scripts/export.py)")
            return 1
        print("%d artifacts match a rebuild, and index.html's versions match the bytes" % len(files))
        return 0
    changed = export.write(files)
    changed += versions.write()
    print("wrote %d of %d artifacts%s" % (len(changed), len(files), (": " + ", ".join(changed)) if changed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
