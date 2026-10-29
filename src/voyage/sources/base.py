"""What every adapter shares: where files live, how to fetch politely, and the raw manifest.

Fetching follows the house rules of the sibling studies (jkm-ttf-arbitrage,
lngarb.sources.base, adapted): the project's own user agent (USER_AGENT below),
a polite pause before every request, retries only on statuses that can change,
and robots.txt read with the matching rules of RFC 9309 before anything is
sent. A URL robots.txt disallows is never requested; it becomes a manual step.

Every download is recorded in data/raw/manifest.json with its URL, the time it
was retrieved, its size and its sha256. Files whose terms allow redistribution
are kept under data/raw/public/ and committed; files whose terms do not are
kept under data/raw/licensed/, which git ignores, and only their manifest entry
is committed, so anyone can fetch the same bytes and check the hash.
"""

from __future__ import annotations

import gzip
import hashlib
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from .. import jsonio

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
DATA: Path = REPO_ROOT / "data"
RAW: Path = DATA / "raw"
RAW_PUBLIC: Path = RAW / "public"
RAW_LICENSED: Path = RAW / "licensed"
#: Public files that need not be committed (large, re-issued often, or kept only
#: as the record behind a cited figure): recorded with their hash, re-fetched
#: from their URL, and ignored by git; what the study derives from them is committed.
RAW_BULK: Path = RAW / "bulk"
RAW_MANIFEST: Path = RAW / "manifest.json"
SEED: Path = DATA / "seed"
CACHE: Path = DATA / "cache"
FIXTURES: Path = DATA / "fixtures"

#: The project's own name, sent everywhere. A string that claims to be a desktop
#: browser while the connection is not one gets HTTP 403 from the Baltic
#: Exchange's front end (measured 2026-10-29); an honest one is served.
USER_AGENT: str = "voyage-tce-model/0.1 (+https://github.com/nathancouturier/voyage-tce-model)"

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "close",
}

#: Statuses worth asking again. Any other 4xx is a permanent answer.
RETRY_STATUS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504, 509, 520, 522, 524})


class SourceError(Exception):
    """A source could not be read, or gave back something unusable."""


class RobotsDisallowedError(SourceError):
    """robots.txt asks automated clients not to fetch this URL, so nothing was sent."""


# --------------------------------------------------------------------------
# robots.txt, RFC 9309: the most specific group, the longest matching rule,
# Allow winning a tie, "*" inside a pattern and a final "$" anchor.
# --------------------------------------------------------------------------

_ROBOTS: dict[str, list[tuple[bool, str]]] = {}


def parse_robots(text: str, product_token: str) -> list[tuple[bool, str]]:
    """The (allow, pattern) rules that apply to product_token."""
    token = product_token.lower()
    groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
    names: list[str] = []
    rules: list[tuple[bool, str]] = []
    in_rules = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                groups.append((names, rules))
                names, rules, in_rules = [], [], False
            names.append(value.lower())
        elif key in ("allow", "disallow"):
            in_rules = True
            if value:
                rules.append((key == "allow", value))
    if names:
        groups.append((names, rules))
    specific = [r for names, r in groups if token in names]
    if specific:
        return [rule for r in specific for rule in r]
    wildcard = [r for names, r in groups if "*" in names]
    return [rule for r in wildcard for rule in r]


def _pattern_matches(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    pieces = body.split("*")
    if len(pieces) == 1:
        return path == body if anchored else path.startswith(body)
    if not path.startswith(pieces[0]):
        return False
    position = len(pieces[0])
    for piece in pieces[1:-1]:
        found = path.find(piece, position)
        if found == -1:
            return False
        position = found + len(piece)
    last = pieces[-1]
    if anchored:
        return path.endswith(last) and len(path) - len(last) >= position
    return path.find(last, position) != -1


def robots_allows(rules: Sequence[tuple[bool, str]], url: str) -> bool:
    """Whether the rules allow the URL's path and query, the longest match winning."""
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    best_length = -1
    best_allow = True
    for allow, pattern in rules:
        if _pattern_matches(pattern, path):
            length = len(pattern)
            if length > best_length or (length == best_length and allow):
                best_length = length
                best_allow = allow
    return best_allow


def check_robots(url: str) -> None:
    """Raise RobotsDisallowedError when the host's robots.txt disallows this URL.

    A robots.txt answering 4xx means no rules; one that cannot be read at all
    counts as a complete disallow (RFC 9309 section 2.3.1.4).
    """
    parts = urlsplit(url)
    if parts.path == "/robots.txt":
        return
    key = "%s://%s" % (parts.scheme, (parts.hostname or "").lower())
    if key not in _ROBOTS:
        robots_url = "%s://%s/robots.txt" % (parts.scheme, parts.netloc)
        try:
            response = requests.get(robots_url, headers=DEFAULT_HEADERS, timeout=30)
        except requests.RequestException as exc:
            raise RobotsDisallowedError("robots.txt for %s could not be read (%s)" % (key, type(exc).__name__)) from exc
        if response.status_code >= 500:
            raise RobotsDisallowedError("robots.txt for %s answered HTTP %d" % (key, response.status_code))
        text = response.text if response.status_code < 400 else ""
        _ROBOTS[key] = parse_robots(text, "mozilla")
    if not robots_allows(_ROBOTS[key], url):
        raise RobotsDisallowedError("robots.txt disallows %s; nothing was requested" % url)


def http_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 60,
    retries: int = 3,
    delay: float = 3.0,
    backoff: float = 2.0,
) -> requests.Response:
    """GET politely with retries; raise SourceError on a final failure."""
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    check_robots(url)
    last = "no attempt was made"
    for attempt in range(retries + 1):
        if delay > 0:
            time.sleep(delay)
        try:
            response = requests.get(url, headers=merged, timeout=timeout)
        except requests.RequestException as exc:
            last = "%s: %s" % (type(exc).__name__, exc)
        else:
            if response.status_code < 400:
                return response
            last = "HTTP %d" % response.status_code
            if response.status_code not in RETRY_STATUS:
                raise SourceError("GET %s failed with HTTP %d, not retryable" % (url, response.status_code))
        if attempt < retries:
            time.sleep(delay * backoff ** (attempt + 1))
    raise SourceError("GET %s failed after %d attempts, last problem %s" % (url, retries + 1, last))


def utc_now_iso() -> str:
    """The current time in UTC, to the second, ISO 8601 with a Z."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# --------------------------------------------------------------------------
# The raw manifest
# --------------------------------------------------------------------------


def raw_manifest() -> dict[str, Any]:
    """data/raw/manifest.json, or an empty one."""
    if RAW_MANIFEST.exists():
        return jsonio.read(RAW_MANIFEST)
    return {"schema_version": 1, "files": {}}


def record_raw(
    *,
    key: str,
    url: str,
    path: Path,
    content: bytes,
    committable: bool,
    publisher: str,
    licence: str,
    retrieved_at: str | None = None,
    note: str = "",
    compress: bool = False,
    bulk: bool = False,
) -> dict[str, Any]:
    """Write content to path and its entry to the raw manifest. Returns the entry.

    path must sit under data/raw/public/ when committable is True and under
    data/raw/licensed/ when it is False, so a file can never be committed by
    mistake: .gitignore excludes data/raw/licensed/. A public file stored with
    bulk=True goes under data/raw/bulk/, also ignored by git.

    With compress=True the file is stored gzipped (path must end in .gz, the
    gzip header carries no time, so the bytes are reproducible) and the
    manifest's size and sha256 are those of the content as it was served.
    """
    root = RAW_BULK if bulk else (RAW_PUBLIC if committable else RAW_LICENSED)
    if bulk and not committable:
        raise SourceError("a bulk raw file must be one whose terms allow redistribution")
    resolved = path.resolve()
    if root.resolve() not in resolved.parents:
        raise SourceError("%s must be under %s" % (path, root))
    if compress and resolved.suffix != ".gz":
        raise SourceError("a compressed raw file must end in .gz: %s" % path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(gzip.compress(content, mtime=0) if compress else content)
    manifest = raw_manifest()
    entry = {
        "url": url,
        "path": str(resolved.relative_to(REPO_ROOT)).replace("\\", "/"),
        "retrieved_at": retrieved_at or utc_now_iso(),
        "bytes": len(content),
        "sha256": sha256_bytes(content),
        "stored": "gzip" if compress else "as served",
        "committable": committable,
        "committed": committable and not bulk,
        "publisher": publisher,
        "licence": licence,
        "note": note,
    }
    manifest["files"][key] = entry
    manifest["files"] = dict(sorted(manifest["files"].items()))
    jsonio.write(RAW_MANIFEST, manifest)
    return entry


def raw_entry(key: str) -> dict[str, Any]:
    """One entry of the raw manifest; KeyError when absent."""
    return raw_manifest()["files"][key]


def raw_path(key: str) -> Path:
    """Where the raw file of a manifest entry lives on disk."""
    return REPO_ROOT / raw_entry(key)["path"]


def raw_bytes(key: str) -> bytes:
    """The content of a raw file as it was served, decompressed if stored gzipped.

    Raises SourceError when the bytes on disk no longer match the recorded hash.
    """
    entry = raw_entry(key)
    stored = (REPO_ROOT / entry["path"]).read_bytes()
    content = gzip.decompress(stored) if entry.get("stored") == "gzip" else stored
    if sha256_bytes(content) != entry["sha256"]:
        raise SourceError("%s does not match its recorded sha256" % entry["path"])
    return content
