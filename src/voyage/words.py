"""The pieces every sentence of the site is built from.

A sentence travels to the page as segments: a plain string for words, or a figure
{"value", "format", "field"} with an optional "prefix" and "suffix" ("USD ",
" million") that stay with it, or {"text", "field"} for a word or a date that came
from a field. The page sets each figure in its own span with its field, so a test
can walk any figure on the page back to where it was computed, and formats it with
the decimals the artifact declares for its format, in DECIMALS below.
"""

from __future__ import annotations

import math
from typing import Any

#: The decimals of every format the artifacts use. One table, so a figure has the
#: same precision on every view.
DECIMALS = {
    "usd_day": 0,
    "usd": 0,
    "usd_m": 2,
    "usd_m_0": 0,
    "usd_t": 2,
    "usd_bbl": 2,
    "ws": 2,
    "days": 1,
    "days_2": 2,
    "nm": 0,
    "knots": 1,
    "knots_2": 2,
    "t": 0,
    "tpd": 1,
    "percent": 1,
    "percent_0": 0,
    "percent_2": 2,
    "eur_t": 2,
    "usd_per_eur": 4,
    "tco2": 0,
    "share": 3,
    "exponent": 2,
    "count": 0,
    "year": 0,
    "error_percent": 1,
    "g_mj": 2,
    "tonne_miles_bn": 2,
    "days_4": 4,
    "t_2": 2,
    "mj": 0,
    "eur": 0,
}

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def fig(value: float | None, fmt: str, field: str, **extra: Any) -> dict[str, Any]:
    """A figure segment; extra keys are prefix, suffix, signed, missing."""
    if fmt not in DECIMALS:
        raise KeyError(fmt)
    out = {"value": value, "format": fmt, "field": field}
    out.update(extra)
    return out


def usd(value: float, field: str, fmt: str = "usd") -> dict[str, Any]:
    return fig(value, fmt, field, prefix="USD ")


def usd_m(value: float, field: str, fmt: str = "usd_m") -> dict[str, Any]:
    """Dollars written in millions, USD 58.22 million; a round sum such as a hull value with fmt usd_m_0."""
    return fig(value / 1e6, fmt, field, prefix="USD ", suffix=" million")


def word(text: str, field: str) -> dict[str, Any]:
    return {"text": text, "field": field}


def date_label(iso: str) -> str:
    """2026-10-23 as 23 October 2026; 2026-08 as August 2026; a quarter or a year as written."""
    parts = iso.split("-")
    if len(parts) == 2 and parts[1].isdigit():
        return "%s %s" % (MONTHS[int(parts[1]) - 1], parts[0])
    if len(parts) == 3:
        return "%d %s %s" % (int(parts[2]), MONTHS[int(parts[1]) - 1], parts[0])
    return iso


def plain(segments: list[Any]) -> str:
    """The words of a sentence without its figures' formatting, for a check or a CSV."""
    out = []
    for s in segments:
        if isinstance(s, str):
            out.append(s)
        elif "text" in s:
            out.append(s["text"])
        else:
            places = DECIMALS[s["format"]]
            value = s["value"]
            out.append(
                "%s%s%s"
                % (
                    s.get("prefix", ""),
                    "" if value is None else "{:,.{p}f}".format(value, p=places),
                    s.get("suffix", ""),
                )
            )
    return "".join(out)


def market_words(label: str) -> str:
    """A market's label in words: "week of 2026-10-23" as "week of 23 October 2026", "2025-Q4 average" as
    "Q4 2025 average"; anything else as written."""
    if label.startswith("week of "):
        return "week of " + date_label(label[len("week of ") :])
    head = label.split(" ")[0]
    if len(head) == 7 and head[4:6] == "-Q":
        return "%s %s%s" % (head[5:], head[:4], label[len(head) :])
    return label


def rounded_parts(parts: list[float], fmt: str) -> list[float]:
    """Parts rounded to a format's places so that they add up to their total rounded the same way.

    Each part is rounded down, and the units the total still needs go to the
    parts with the largest remainders (the largest remainder method).
    """
    scale = 10 ** DECIMALS[fmt]
    total = round(math.fsum(parts) * scale)
    floors = [int(part * scale // 1) for part in parts]
    order = sorted(range(len(parts)), key=lambda i: parts[i] * scale - floors[i], reverse=True)
    for i in order[: max(0, total - sum(floors))]:
        floors[i] += 1
    return [value / scale for value in floors]
