"""Content hashes in index.html, so a deploy changes every URL whose bytes changed.

GitHub Pages serves every file with a short max age and no version in its name.
The site is an ES module graph plus data/*.json fetched by relative URLs, so
after a deploy a cache could hand the page yesterday's module beside today's
data, and an old module reading a new artifact can print a wrong number without
any error. The pattern is the sibling studies' (crack-spread-study,
jkm-ttf-arbitrage), with no build step and no bundler. Three things in
index.html are rewritten from the bytes on disk, and nothing else:

1. an import map between BLOCK_START and BLOCK_END mapping every module in src/
   and every artifact in data/ to the same path with ?v=<the first 12 hex digits
   of its sha256>; src/state.js asks for artifacts through import.meta.resolve,
   which applies the map;
2. the ?v= on each stylesheet link;
3. the ?v= on the entry module, src/ui.js.

The map is sorted and written with LF and no timestamp: an unchanged tree
rewrites nothing. src/state.js also refuses any artifact whose schema version or
name it does not know, which covers what a query string cannot.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = "index.html"
HASH_LENGTH = 12
BLOCK_START = "<!-- build:versions, written by voyage.versions from the bytes on disk; do not edit by hand -->"
BLOCK_END = "<!-- /build:versions -->"
MODULES = ("src", ".js")
ARTIFACTS = ("data", ".json")
STYLES = ("styles", ".css")
ENTRY_MODULE = "src/ui.js"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def _files(root: Path, directory: str, suffix: str) -> list[str]:
    folder = root / directory
    if not folder.is_dir():
        return []
    return sorted("%s/%s" % (directory, p.name) for p in folder.iterdir() if p.is_file() and p.name.endswith(suffix))


def hashes(root: Path = REPO_ROOT) -> dict[str, str]:
    out: dict[str, str] = {}
    for directory, suffix in (MODULES, ARTIFACTS, STYLES):
        for relative in _files(root, directory, suffix):
            out[relative] = content_hash((root / relative).read_bytes())
    return out


def versioned(relative: str, digest: str) -> str:
    return "%s?v=%s" % (relative, digest)


def import_map(table: Mapping[str, str]) -> str:
    imports = {
        "./" + rel: "./" + versioned(rel, digest)
        for rel, digest in sorted(table.items())
        if rel.startswith(MODULES[0] + "/") or rel.startswith(ARTIFACTS[0] + "/")
    }
    body = json.dumps({"imports": imports}, indent=2, ensure_ascii=True, sort_keys=True)
    return "\n".join([BLOCK_START, '<script type="importmap">', body, "</script>", BLOCK_END])


_BLOCK = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
_STYLE_LINK = re.compile(r'href="(styles/[\w.-]+\.css)(?:\?v=[0-9a-f]*)?"')
_ENTRY = re.compile(r'src="(' + re.escape(ENTRY_MODULE) + r')(?:\?v=[0-9a-f]*)?"')


class VersionsError(ValueError):
    """index.html has no place to write the versions into."""


def render(html: str, table: Mapping[str, str]) -> str:
    if html.count(BLOCK_START) != 1 or html.count(BLOCK_END) != 1:
        raise VersionsError("%s must hold the version markers exactly once each" % INDEX)
    out = _BLOCK.sub(lambda _: import_map(table), html)

    def style(match: re.Match) -> str:
        relative = match.group(1)
        if relative not in table:
            raise VersionsError("%s links %s, which does not exist" % (INDEX, relative))
        return 'href="%s"' % versioned(relative, table[relative])

    out = _STYLE_LINK.sub(style, out)
    if len(_ENTRY.findall(out)) != 1:
        raise VersionsError("%s must load %s exactly once" % (INDEX, ENTRY_MODULE))
    return _ENTRY.sub(lambda m: 'src="%s"' % versioned(m.group(1), table[m.group(1)]), out)


def write(root: Path = REPO_ROOT) -> list[str]:
    """Rewrite index.html if its versions are stale; the names written."""
    path = root / INDEX
    if not path.exists():
        return []
    current = path.read_text(encoding="utf-8")
    wanted = render(current, hashes(root))
    if wanted == current:
        return []
    path.write_text(wanted, encoding="utf-8", newline="\n")
    return [INDEX]


def check(root: Path = REPO_ROOT) -> list[str]:
    """[] when index.html versions every module, artifact and stylesheet at its bytes."""
    path = root / INDEX
    if not path.exists():
        return [INDEX + " is missing"]
    crlf = [rel for rel in sorted(hashes(root)) if b"\r\n" in (root / rel).read_bytes()]
    if crlf:
        return ["CRLF in " + ", ".join(crlf)]
    html = path.read_text(encoding="utf-8")
    try:
        wanted = render(html, hashes(root))
    except VersionsError as exc:
        return [str(exc)]
    return [] if wanted == html else [INDEX + " versions"]
