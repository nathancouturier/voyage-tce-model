"""Check that every figure a seed file cites is printed in the document it cites.

A seeded figure carries the manifest key of the raw file it was read from and
a quote: the words around the figure, copied from that file. quote_found()
extracts the file's readable text (an HTML page's text, a PDF's text layer),
normalises the white space, and looks for the quote. The raw files of
licensed sources are not committed, so on a fresh clone the check reports them
as unavailable rather than failing; everywhere the files are present (the
machine that fetched them) every quote must be found.
"""

from __future__ import annotations

import html
import io
import re
from collections.abc import Iterator, Mapping
from functools import lru_cache
from typing import Any

from .sources import base

_SPACE = re.compile(r"\s+")
_BEFORE_PUNCT = re.compile(r" ([,.;:)%])")
_AFTER_OPEN = re.compile(r"([($]) ")
_PLAIN = {
    "\u00a0": " ",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
}


def normalise(text: str) -> str:
    """Collapse white space, drop the spaces markup leaves around punctuation, and plain the typography.

    Sources print ranges and pairs with long dashes and curly quotes; the study
    writes neither, so a quote carries a hyphen and straight quotes where the
    source has them, and both sides are compared that way.
    """
    for fancy, plain in _PLAIN.items():
        text = text.replace(fancy, plain)
    text = _SPACE.sub(" ", text).strip()
    text = _BEFORE_PUNCT.sub(r"\1", text)
    return _AFTER_OPEN.sub(r"\1", text)


@lru_cache(maxsize=64)
def document_text(raw_key: str) -> str:
    """The readable, normalised text of a raw file; an empty string when it is not on disk."""
    try:
        content = base.raw_bytes(raw_key)
    except FileNotFoundError:
        return ""
    if content[:4] == b"%PDF":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    elif raw_key.endswith("_xml"):
        # The Suez Canal Authority's article service returns its circulars as
        # escaped HTML inside XML: unescape once, then read the text.
        from bs4 import BeautifulSoup

        unescaped = html.unescape(content.decode("utf-8", errors="replace"))
        text = BeautifulSoup(unescaped, "lxml").get_text(" ")
    elif raw_key.endswith(("_csv", "_json", "_txt", "_js")) or content[:1] in (b"{", b"["):
        text = content.decode("utf-8", errors="replace")
    else:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ")
    return normalise(text)


def quote_found(raw_key: str, quote: str) -> bool | None:
    """True when the quote is in the document, False when not, None when the file is absent."""
    text = document_text(raw_key)
    if not text:
        return None
    return normalise(quote) in text


def cited(node: Any, path: str = "") -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Every mapping in a seed that cites a raw file and a quote, with its path in the seed."""
    if isinstance(node, Mapping):
        if "raw_key" in node and "quote" in node:
            yield path, node
        for key, value in node.items():
            yield from cited(value, "%s.%s" % (path, key) if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from cited(value, "%s[%d]" % (path, index))


def check(seed: Any) -> dict[str, list[str]]:
    """Quotes found, missing and unavailable, by their path in the seed."""
    out: dict[str, list[str]] = {"found": [], "missing": [], "unavailable": []}
    manifest = base.raw_manifest()["files"]
    for path, node in cited(seed):
        quotes = node["quote"] if isinstance(node["quote"], list) else [node["quote"]]
        if node["raw_key"] not in manifest:
            out["missing"].append("%s: %s is not in the raw manifest" % (path, node["raw_key"]))
            continue
        for quote in quotes:
            result = quote_found(node["raw_key"], quote)
            if result is None:
                out["unavailable"].append(path)
            elif result:
                out["found"].append(path)
            else:
                out["missing"].append("%s: %r not found in %s" % (path, quote, node["raw_key"]))
    return out
