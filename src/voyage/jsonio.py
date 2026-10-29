"""Writing JSON the same way everywhere, so a rebuild on any machine is byte identical.

UTF-8 encoded but ASCII only, LF line endings, two space indent, keys in the
order given, floats rounded where the caller rounds them, and written
atomically so a crash never leaves half a file that the gate would then read.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def dumps(payload: Any, *, indent: int | None = 2) -> str:
    """The canonical text of a JSON payload, with a final newline."""
    text = json.dumps(payload, indent=indent, ensure_ascii=True, allow_nan=False)
    return text + "\n"


def write(path: Path, payload: Any, *, indent: int | None = 2) -> bool:
    """Write payload to path unless the bytes are unchanged. Returns True when written."""
    text = dumps(payload, indent=indent)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return True


def read(path: Path) -> Any:
    """Read a JSON file written by this package."""
    return json.loads(path.read_text(encoding="utf-8"))
