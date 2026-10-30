#!/usr/bin/env python
"""The research note, Voyage-Economics-TCE-Research-Note.pdf, written from the study's own code.

    python scripts/note.py               write the note at the repository root
    python scripts/note.py --out PATH    write it elsewhere

Every figure in the note is computed here by the code that writes the site,
from the committed seeds and caches: the presets and artifacts of
src/voyage/export.py (so a sentence the site prints is printed here from the
same segments), the analysis of src/voyage/analysis.py and the anchors of
src/voyage/anchors.py. Nothing is typed in. The charts are drawn by matplotlib
in the site's palette, read from styles/tokens.css (light theme); the tables
are set by ReportLab; the body is Liberation Serif. ReportLab's invariant mode
and charts saved without a timestamp make two runs on the same data and
library versions write the same bytes.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from matplotlib import font_manager  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from reportlab import rl_config  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT, TA_RIGHT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from voyage import analysis, anchors, baltic, cases, engine, export, pages  # noqa: E402
from voyage.words import DECIMALS, date_label, market_words  # noqa: E402

OUT = REPO_ROOT / "Voyage-Economics-TCE-Research-Note.pdf"
SITE = "https://nathancouturier.github.io/voyage-tce-model/"
REPO = "https://github.com/nathancouturier/voyage-tce-model"
PORTFOLIO = "https://nathancouturier.github.io"
FONTS = Path("/usr/share/fonts/truetype/liberation")
MINUS = "\u2212"

# --------------------------------------------------------------------------
# The palette, from the site's own stylesheet
# --------------------------------------------------------------------------

TOKENS = ("bg", "border", "text", "text-muted", "accent", "data-bunkers", "data-ets", "data-war", "data-mgo")


def palette() -> dict[str, str]:
    """The light theme's colours: the first value each token takes in styles/tokens.css."""
    css = (REPO_ROOT / "styles" / "tokens.css").read_text(encoding="utf-8")
    out = {}
    for token in TOKENS:
        match = re.search(r"--%s:\s*(#[0-9a-fA-F]{6})\s*;" % re.escape(token), css)
        if not match:
            raise SystemExit("styles/tokens.css has no hex value for --%s" % token)
        out[token] = match.group(1)
    return out


C = palette()

# --------------------------------------------------------------------------
# Numbers and sentences, written as the site writes them
# --------------------------------------------------------------------------


def number(value: float, fmt: str, signed: bool = False) -> str:
    """One figure at its format's decimals, grouped, with a true minus sign."""
    places = DECIMALS[fmt]
    body = ("{:.%df}" if fmt == "year" else "{:,.%df}") % places
    text = body.format(abs(value))
    if not re.search(r"[1-9]", text):
        return text
    if value < 0:
        return MINUS + text
    return ("+" + text) if signed else text


#: A space no line breaks at, between a currency and its figure.
NBSP = "&nbsp;"


def usd(value: float, fmt: str = "usd") -> str:
    return "USD" + NBSP + number(value, fmt)


def usd_m(value: float, fmt: str = "usd_m") -> str:
    return "USD%s%s million" % (NBSP, number(value / 1e6, fmt))


def times(value: float) -> str:
    """A multiple, to one decimal."""
    return f"{value:,.1f}"


def short(value: float) -> str:
    """A setting as written: 5, 3.75, 0.01."""
    return f"{value:g}"


def plain(segments: list[Any]) -> str:
    """A sentence of the site's artifacts as text: words, dates, and figures with their prefix and suffix."""
    out = []
    for s in segments:
        if isinstance(s, str):
            out.append(s)
        elif "text" in s:
            out.append(s["text"])
        elif s.get("value") is None:
            out.append(s.get("missing", "no figure"))
        else:
            out.append(
                s.get("prefix", "") + number(s["value"], s["format"], s.get("signed", False)) + s.get("suffix", "")
            )
    return "".join(out)


def escape(text: str) -> str:
    """Text for a paragraph: markup characters escaped, and no line break between a currency and its figure."""
    out = text.replace(NBSP, "\x00").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return out.replace("\x00", NBSP).replace("USD ", "USD" + NBSP).replace("EUR ", "EUR" + NBSP)


# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------


def register_fonts() -> None:
    needed = ("LiberationSerif-Regular.ttf", "LiberationSans-Regular.ttf", "LiberationMono-Regular.ttf")
    missing = [name for name in needed if not (FONTS / name).exists()]
    if missing:
        raise SystemExit(
            "the note is set in the Liberation fonts, expected in %s (Debian and Ubuntu: apt install "
            "fonts-liberation); missing: %s" % (FONTS, ", ".join(missing))
        )
    pdfmetrics.registerFont(
        TTFont("LiberationSerif", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf")
    )
    pdfmetrics.registerFont(TTFont("LiberationSerif-Bold", str(FONTS / "LiberationSerif-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("LiberationSerif-Italic", str(FONTS / "LiberationSerif-Italic.ttf")))
    pdfmetrics.registerFont(TTFont("LiberationSerif-BoldItalic", str(FONTS / "LiberationSerif-BoldItalic.ttf")))
    pdfmetrics.registerFontFamily(
        "LiberationSerif",
        normal="LiberationSerif",
        bold="LiberationSerif-Bold",
        italic="LiberationSerif-Italic",
        boldItalic="LiberationSerif-BoldItalic",
    )
    for name in ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationMono-Regular.ttf"):
        font_manager.fontManager.addfont(str(FONTS / name))


INK = colors.HexColor(C["text"])
MUTED = colors.HexColor(C["text-muted"])
RULE = colors.HexColor(C["border"])

BODY = ParagraphStyle("body", fontName="LiberationSerif", fontSize=9.8, leading=13.4, textColor=INK, spaceAfter=5)
TITLE = ParagraphStyle("title", parent=BODY, fontName="LiberationSerif-Bold", fontSize=18, leading=22, spaceAfter=4)
SUBTITLE = ParagraphStyle("subtitle", parent=BODY, fontSize=11, leading=14.5, textColor=INK, spaceAfter=6)
BYLINE = ParagraphStyle("byline", parent=BODY, fontSize=8.6, leading=11.5, textColor=MUTED, spaceAfter=10)
H2 = ParagraphStyle(
    "h2", parent=BODY, fontName="LiberationSerif-Bold", fontSize=12, leading=15, spaceBefore=8, keepWithNext=1
)
CAPTION = ParagraphStyle("caption", parent=BODY, fontName="LiberationSerif-Bold", fontSize=9.4, leading=12.4)
SOURCE = ParagraphStyle("source", parent=BODY, fontSize=7.6, leading=9.8, textColor=MUTED, spaceAfter=9)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.2, leading=10.4, spaceAfter=0)
CELL_RIGHT = ParagraphStyle("cell_right", parent=CELL, alignment=TA_RIGHT)
HEAD = ParagraphStyle("head", parent=CELL, fontSize=7.8, leading=9.8, textColor=MUTED)
HEAD_RIGHT = ParagraphStyle("head_right", parent=HEAD, alignment=TA_RIGHT)
BULLET = ParagraphStyle("bullet", parent=BODY, spaceAfter=3, alignment=TA_LEFT)

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 17 * mm
MARGIN_BOTTOM = 17 * mm
TEXT_W = PAGE_W - 2 * MARGIN_X
DPI = 200


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, BULLET), leftIndent=11, value="circle") for item in items],
        bulletType="bullet",
        start="\u2022",
        bulletFontName="LiberationSerif",
        bulletFontSize=8,
        leftIndent=11,
        bulletColor=INK,
    )


def table(head: list[str], rows: list[list[str]], widths: list[float], right: set[int]) -> Table:
    """A table in the site's manner: a rule under the head, hairlines between rows, figures right aligned."""
    data = [[p(escape(h), HEAD_RIGHT if i in right else HEAD) for i, h in enumerate(head)]]
    for row in rows:
        data.append([p(escape(v), CELL_RIGHT if i in right else CELL) for i, v in enumerate(row)])
    out = Table(data, colWidths=[w * TEXT_W for w in widths], repeatRows=1, hAlign="LEFT")
    out.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ]
        )
    )
    return out


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------


def style_axes(ax: Any) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C["border"])
    ax.tick_params(axis="both", colors=C["text-muted"], length=0, labelsize=7)
    ax.tick_params(axis="x", pad=4)
    ax.grid(axis="x", color=C["border"], linewidth=0.6)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels():
        label.set_fontfamily("Liberation Mono")


#: A value written over a chart's grid keeps a patch of the ground under it.
HALO = {"boxstyle": "square,pad=0.12", "facecolor": "white", "edgecolor": "none"}

#: Layout passes, and the room, in pixels at the figure's DPI, kept at the figure's edges and between an axis
#: title and the legend hung under it.
SETTLE_PASSES = 4
EDGE_PX = 6.0
LEGEND_GAP_PX = 8.0

#: The longest value label, in characters, written beside a bar of Figure 3.
DETAIL_CHARS = 32

#: Dots closer than this share of the x range are drawn apart, the spot index under the line by DOT_STEP rows.
DOT_CLEARANCE = 0.02
DOT_STEP = 0.24


def dot(face: str, edge: str, text: str) -> Line2D:
    return Line2D(
        [0], [0], marker="o", linestyle="", markersize=5, markerfacecolor=face, markeredgecolor=edge, label=text
    )


def key(ax: Any, handles: list[Any], **where: Any) -> Any:
    """The legend of a chart, in words beside a sample of each mark."""
    legend = ax.legend(handles=handles, frameon=False, fontsize=6.8, handlelength=1.1, borderaxespad=0.2, **where)
    for text in legend.get_texts():
        text.set_color(C["text"])
    return legend


def settle(fig: Any, ax: Any, legend: Any = None, values: list[Any] | None = None) -> None:
    """Lay a figure out with its legend hung under the x axis title and every value label inside the figure: after
    the tight layout, each pass narrows the axes by what the longest value label overruns the figure's right edge,
    hangs the legend's top just under the axis title, and raises the axes by what the legend overruns the bottom."""
    fig.tight_layout(pad=0.4)
    for _ in range(SETTLE_PASSES):
        fig.canvas.draw()
        width, height = fig.bbox.width, fig.bbox.height
        right, bottom = fig.subplotpars.right, fig.subplotpars.bottom
        if values:
            over = max(text.get_window_extent().x1 for text in values) - (width - EDGE_PX)
            if over > 0:
                right -= over / width
        if legend is not None:
            box = ax.get_window_extent()
            title = ax.xaxis.label.get_window_extent()
            anchor = legend.get_bbox_to_anchor().transformed(ax.transAxes.inverted())
            legend.set_bbox_to_anchor((anchor.x0, (title.y0 - LEGEND_GAP_PX - box.y0) / box.height), ax.transAxes)
            fig.canvas.draw()
            low = legend.get_window_extent().y0
            if low < EDGE_PX:
                bottom += (EDGE_PX - low) / height
        fig.subplots_adjust(right=right, bottom=bottom)


def picture(fig: Any, height_in: float) -> Image:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=DPI, facecolor="white", metadata={"Software": None})
    plt.close(fig)
    buffer.seek(0)
    width = TEXT_W
    return Image(buffer, width=width, height=width * height_in / FIG_W)


FIG_W = 6.69


def new_figure(height_in: float) -> tuple[Any, Any]:
    plt.rcParams.update(
        {
            "font.family": "Liberation Sans",
            "font.size": 7.5,
            "text.color": C["text"],
            "axes.labelcolor": C["text-muted"],
            "axes.labelsize": 7.2,
        }
    )
    return plt.subplots(figsize=(FIG_W, height_in))


def bridge_chart(rows: list[dict[str, Any]]) -> Image:
    """Figure 1: the bridge from gross freight to the voyage result, in USD million."""
    height = 2.35
    fig, ax = new_figure(height)
    families = {"bunkers": C["data-bunkers"], "ets": C["data-ets"], "war_risk": C["data-war"]}
    labels = []
    for at, row in enumerate(rows):
        y = -at
        lo, hi = sorted((row["from_usd"] / 1e6, row["to_usd"] / 1e6))
        labels.append(row["label"])
        if row["kind"] == "total":
            face = C["accent"] if row["id"] == "result" else C["text"]
            ax.barh(y, hi - lo, left=lo, height=0.5, color=face)
            ax.text(
                hi + 0.8,
                y,
                number(row["value_usd"] / 1e6, "usd_m"),
                va="center",
                fontsize=7,
                family="Liberation Mono",
                bbox=HALO,
            )
        elif row["value_usd"]:
            face = families.get(row["id"], "white")
            edge = C["text"] if face == "white" else face
            ax.barh(y, hi - lo, left=lo, height=0.5, color=face, edgecolor=edge, linewidth=0.8)
            ax.text(
                hi + 0.8,
                y,
                number(row["value_usd"] / 1e6, "usd_m"),
                va="center",
                fontsize=7,
                family="Liberation Mono",
                bbox=HALO,
            )
        else:
            ax.text(lo + 0.8, y, row["zero"] or "", va="center", fontsize=6.8, color=C["text-muted"], bbox=HALO)
    ax.set_yticks([-i for i in range(len(rows))], labels)
    ax.set_ylim(-len(rows) + 0.4, 0.6)
    ax.set_xlim(0, max(r["to_usd"] for r in rows) / 1e6 * 1.32)
    ax.set_xlabel("USD million")
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    fig.tight_layout(pad=0.4)
    return picture(fig, height)


def validation_chart(rows: list[dict[str, Any]], words: dict[str, Any]) -> Image:
    """Figure 2: the engine against the Baltic's published TCE, week by week, marked by how fresh the bunkers were."""
    height = 0.62 + 0.135 * len(rows)
    fig, ax = new_figure(height)
    marks = {
        "fresh": (C["text"], C["text"]),
        "week_old": ("white", C["text"]),
        "older": (C["text-muted"], C["text-muted"]),
    }
    labels = []
    for at, r in enumerate(rows):
        y = -at
        face, edge = marks[r["bunker_freshness"]]
        labels.append("%s, %s" % (r["route"], date_label(r["week_ending"])))
        ax.scatter([r["error"] * 100.0], [y], s=24, color=face, edgecolors=edge, linewidths=1.1, zorder=3)
        ax.text(
            r["error"] * 100.0 + (0.6 if r["error"] >= 0 else -0.6),
            y,
            number(r["error"] * 100.0, "error_percent", signed=True),
            va="center",
            ha="left" if r["error"] >= 0 else "right",
            fontsize=6.6,
            family="Liberation Mono",
            bbox=HALO,
        )
    ax.axvline(0, color=C["text-muted"], linewidth=0.8)
    ax.set_yticks([-i for i in range(len(rows))], labels)
    ax.set_ylim(-len(rows) + 0.5, 0.5)
    ax.set_xlim(min(-2.5, min(r["error"] for r in rows) * 100.0 - 3.0), max(r["error"] for r in rows) * 100.0 + 4.0)
    ax.set_xlabel(words["axis"])
    kinds = {"ink": "fresh", "ring": "week_old", "muted": "older"}
    key(
        ax,
        [dot(*marks[kinds[item["kind"]]], item["text"]) for item in words["legend"]],
        loc="upper left",
        bbox_to_anchor=(-0.02, -0.16 * 3.0 / height),
        ncol=3,
    )
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    fig.tight_layout(pad=0.4)
    return picture(fig, height)


def detours_chart(rows: list[dict[str, Any]], words: dict[str, Any]) -> Image:
    """Figure 3: what a tonne of cargo costs more, detour by detour: the owner's freight and the charterer's premium."""
    groups: list[str] = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])
    lines = []
    for g in groups:
        lines.append(("group", g, None))
        lines += [("row", r["label"], r) for r in rows if r["group"] == g]
    height = 0.85 + 0.155 * len(lines)
    fig, ax = new_figure(height)
    faces = {"routing": C["text"], "war": C["data-war"]}
    ticks, labels = [], []
    totals = []
    values = []
    for at, (kind, text, r) in enumerate(lines):
        y = -at
        if kind == "group":
            ax.text(
                -0.01,
                y,
                text,
                transform=ax.get_yaxis_transform(),
                ha="right",
                va="center",
                fontsize=7.2,
                fontweight="bold",
            )
            continue
        start = 0.0
        for segment in r["segments"]:
            ax.barh(y, segment["value"], left=start, height=0.55, color=faces[segment["family"]])
            start += segment["value"]
        totals.append(start)
        # The site writes every clause of a row's detail; the page keeps those that fit beside the bar, the rest
        # being in the text (the tonne miles of the Cape routing).
        clauses = [number(start, "usd_t", signed=True)]
        for clause in r["detail"].split(", ") if r["detail"] else []:
            if len(", ".join([*clauses, clause])) > DETAIL_CHARS:
                break
            clauses.append(clause)
        value = ", ".join(clauses)
        values.append(
            ax.text(start + 3.0, y, value, va="center", ha="left", fontsize=6.6, family="Liberation Mono", bbox=HALO)
        )
        ticks.append(y)
        labels.append(text)
    ax.set_yticks(ticks, labels)
    ax.set_ylim(-len(lines) + 0.5, 0.6)
    ax.set_xlim(0, max(totals) * 1.45)
    ax.axvline(0, color=C["text-muted"], linewidth=0.8)
    ax.set_xlabel(words["axis"])
    legend = key(
        ax,
        [Patch(facecolor=faces[item["family"]], label=item["text"]) for item in words["legend"]],
        loc="upper left",
        bbox_to_anchor=(-0.02, -0.1),
        ncol=1,
    )
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    settle(fig, ax, legend, values)
    return picture(fig, height)


def paper_chart(rows: list[dict[str, Any]], words: dict[str, Any]) -> Image:
    """Figure 4: the voyage TCE grossed up by its commission against the 5TC FFA over its days and the spot 5TC."""
    height = 0.95 + 0.25 * len(rows)
    fig, ax = new_figure(height)
    labels = []
    marks = [v for r in rows for v in (r["ffa"]["usd_day"], r["physical_tce_gross_usd_day"], r["spot_182_usd_day"])]
    clearance = DOT_CLEARANCE * (max(marks) - min(marks))
    for at, r in enumerate(rows):
        y = -at
        labels.append("%s, %s" % (r["route"], date_label(r["date"])))
        ffa = r["ffa"]["usd_day"]
        gross = r["physical_tce_gross_usd_day"]
        spot = r["spot_182_usd_day"]
        ax.plot([gross, ffa], [y, y], color=C["text-muted"], linewidth=1, zorder=1)
        # The spot index steps under the line where it would sit on another dot, as the site stacks them.
        crowded = min(abs(spot - gross), abs(spot - ffa)) < clearance
        ax.scatter([spot], [y - DOT_STEP if crowded else y], s=20, color=C["text-muted"], zorder=2)
        ax.scatter([gross], [y], s=26, color=C["text"], zorder=3)
        ax.scatter([ffa], [y], s=26, color="none", edgecolors=C["text"], linewidths=1.1, zorder=4)
    ax.set_yticks([-i for i in range(len(rows))], labels)
    ax.set_ylim(-len(rows) + 0.5, 0.5)
    ax.set_xlabel(words["axis"])
    faces = {"ink": (C["text"], C["text"]), "ring": ("white", C["text"]), "muted": (C["text-muted"], C["text-muted"])}
    legend = key(
        ax,
        [dot(*faces[item["kind"]], item["text"]) for item in words["legend"]],
        loc="upper center",
        bbox_to_anchor=(0.45, -0.38),
        ncol=2,
    )
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: number(v, "usd_day")))
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    settle(fig, ax, legend)
    return picture(fig, height)


# --------------------------------------------------------------------------
# The note
# --------------------------------------------------------------------------


def build(out: Path) -> int:
    register_fonts()
    presets = export.presets()
    overview = export.overview(presets)
    detours = export.detours_artifact()
    paper = export.paper_artifact()
    method = export.method_artifact()
    featured = next(x for x in presets if x["id"] == overview["featured"])
    result = engine.evaluate(featured["inputs"])
    structure = analysis.cost_structure()
    speed = analysis.speed()
    carbon = analysis.carbon()
    tanker = anchors.tanker_weekly()
    summary = anchors.lump_sum_summary()
    cross = anchors.broker_cross_check()
    reproducible = summary["rows"]
    implied = anchors.implied_summary()
    ws = [r for r in tanker if not r["reproducible"] and not r.get("implied") and r["rate_basis"] == "ws"]
    distances = anchors.distances()
    within = [c for c in distances["checks"] if c["within_tolerance"]]
    misses = sorted((c for c in distances["checks"] if not c["within_tolerance"]), key=lambda c: -abs(c["error"]))
    b2017 = anchors.baltic_2017()
    early = {r["id"]: r for r in anchors.early_march()}
    st, sd, hz = detours["suez_tanker"], detours["suez_dry"], detours["hormuz"]
    cape = st["cape_vs_suez"]
    capesize = paper["capesize"]
    published = featured["published"]["tce_usd_day"]
    error = result["tce_usd_day"] / published - 1.0
    market = cases.common_market()
    retrieved = date_label(pages.retrieval_days()[-1])
    case_count = len(json.loads((REPO_ROOT / "data" / "fixtures" / "engine-cases.json").read_text())["cases"])
    dry_commission = next(x for x in presets if x["route"] == "C5")["inputs"]["commission_pct"]
    tanker_commission = featured["inputs"]["commission_pct"]

    story: list[Any] = []
    story.append(p("Voyage economics and the time charter equivalent", TITLE))
    story.append(
        p(
            "What a dry bulk or tanker voyage earns a day, the freight it needs, the costs that decide it, and the "
            "physical fixture against the FFA, on the Baltic Exchange's routes in 2026",
            SUBTITLE,
        )
    )
    story.append(
        p(
            'Research note by <a href="%s" color="%s">Nathan Couturier</a>, %s. Interactive site: '
            '<a href="%s" color="%s">%s</a>. Code and data: <a href="%s" color="%s">%s</a>.'
            % (PORTFOLIO, C["text-muted"], retrieved, SITE, C["text-muted"], SITE, REPO, C["text-muted"], REPO),
            BYLINE,
        )
    )

    # ---------------------------------------------------------------- summary
    hz_scen = {s["id"]: s for s in hz["scenarios"]}
    latest_level = hz["levels"][-1]

    def hz_owner(sid: str, week: str | None = None) -> float:
        week = week or latest_level["week_ending"]
        return next(lv["extra_freight_usd_t"] for lv in hz_scen[sid]["levels"] if lv["week_ending"] == week)

    ets_rows = [r for r in structure["rows"] if r["shares"]["ets"] > 0]
    td3c = next(r for r in structure["rows"] if r["route"] == "TD3C")
    war = td3c["with_hormuz_war_risk"]
    red = st["red_sea_war_risk"]
    rows_27 = [r for r in capesize if r["date"] == capesize[0]["date"]]
    c3_27 = next(r for r in rows_27 if r["route"] == "C3")
    c5_27 = next(r for r in rows_27 if r["route"] == "C5")
    c3_43 = next(r for r in capesize if r["route"] == "C3" and r["date"] != c3_27["date"])
    textbook = speed["textbook"]
    holds = all(t["freight_pushes_speed_up"] == "holds" and t["bunkers_push_speed_down"] == "holds" for t in textbook)
    low, high = summary["gap_low"], summary["gap_high"]

    def side(value: float) -> str:
        return "below" if value < 0 else "above"

    def range_words(span: list[float]) -> str:
        """A basis given on two prints of a curve: 'between USD 419 and 4,060 a day above'."""
        low_end, high_end = span
        if low_end >= 0 or high_end < 0:
            near, far = sorted((abs(low_end), abs(high_end)))
            return "between %s and %s a day %s" % (usd(near, "usd_day"), number(far, "usd_day"), side(high_end))
        return "between %s a day below and %s above" % (usd(abs(low_end), "usd_day"), number(high_end, "usd_day"))

    story.append(p("Summary", H2))
    story.append(
        bullets(
            [
                escape(plain(overview["verdict"]))
                + " The Baltic's own TCE that week was %s; the engine reads %s percent higher, partly the port charges "
                "it leaves out." % (usd(published, "usd_day"), number(error * 100.0, "error_percent")),
                "On routes outside Europe, bunkers are every sourced dollar of voyage cost at the %s market; on "
                "voyages into or out of the EEA, EU allowances at the %d phase in are %s to %s percent of it (EUA "
                "EUR %s a tonne). A Hormuz war risk premium of %s percent of a %s VLCC hull would cost the charterer "
                "%s for each seven days inside the Gulf, %s times TD3C's bunker bill."
                % (
                    market.label,
                    cases.ETS_FULL_FROM,
                    number(min(r["shares"]["ets"] for r in ets_rows) * 100.0, "percent"),
                    number(max(r["shares"]["ets"] for r in ets_rows) * 100.0, "percent"),
                    number(market.eua_eur_t, "eur_t"),
                    number(war["premium_pct"], "percent"),
                    usd_m(war["hull_value_usd"], "usd_m_0"),
                    usd_m(war["premium_usd"]),
                    times(war["premium_to_bunkers"]),
                ),
                "Round the Cape of Good Hope an LR2 on TC20 sails %s more days than by Suez and needs %s (%s a tonne) "
                "more freight, before Suez tolls, to earn what it earns by Suez, where the Red Sea premium on the "
                "laden transit costs its charterer %s a tonne; Suez stays the better way for the owner until its tolls "
                "for the %d transits together pass %s."
                % (
                    number(cape["extra_days"], "days"),
                    usd_m(cape["extra_freight_lump_sum_usd"]),
                    usd(cape["extra_freight_usd_t"], "usd_t"),
                    usd(red["per_tonne_usd"], "usd_t"),
                    st["break_even_suez_transits"],
                    usd_m(st["break_even_suez_toll_usd"]),
                ),
                "For a VLCC from the Gulf a %s percent premium costs the charterer %s a tonne for one seven day "
                "period; 20 days of waiting inside the Gulf make %d periods, %s a tonne, and the owner needs %s a "
                "tonne more freight to keep the TCE of the week to %s."
                % (
                    number(war["premium_pct"], "percent"),
                    usd(hz_scen["war_low"]["charterer_war_risk_usd_t"], "usd_t"),
                    hz_scen["wait_20"]["periods"],
                    usd(hz_scen["wait_20"]["charterer_war_risk_usd_t"], "usd_t"),
                    usd(hz_owner("wait_20"), "usd_t"),
                    date_label(latest_level["week_ending"]),
                ),
                "In the week to %s a C3 cargo at %s a tonne earned %s a day grossed up to the 5TC's gross hire (%s "
                "net), %s the 5TC FFA over its days, by which of two prints of the 29 June curve is read; C5 sat %s "
                "it. By %s the C3 voyage sat %s a day %s the curve."
                % (
                    date_label(c3_27["date"]),
                    usd(c3_27["freight_usd_t"], "usd_t"),
                    usd(c3_27["physical_tce_gross_usd_day"], "usd_day"),
                    usd(c3_27["physical_tce_usd_day"], "usd_day"),
                    range_words(c3_27["basis_range_usd_day"]),
                    range_words(c5_27["basis_range_usd_day"]),
                    date_label(c3_43["date"]),
                    usd(abs(c3_43["basis_usd_day"]), "usd_day"),
                    side(c3_43["basis_usd_day"]),
                ),
                "Higher freight raises the speed that maximises the TCE and dearer bunkers lower it, %s of the routes "
                "tested (%s); for the tankers only at the lowest public freight, their best speed otherwise at the "
                "top of the range."
                % ("on every one" if holds else "but not on every one", ", ".join(t["route"] for t in textbook)),
            ]
        )
    )
    story.append(
        p(
            "A TCE here is an estimate of what a voyage earns at stated inputs, not a forecast, and it is set against "
            "operating and capital costs, never net of them.",
            BODY,
        )
    )

    story.append(
        KeepTogether(
            [
                p(
                    escape(plain(overview["bridge"]["title"])) + " " + escape(plain(overview["bridge"]["result_line"])),
                    CAPTION,
                ),
                bridge_chart(overview["bridge"]["rows"]),
                p(
                    "Figure 1. " + escape(plain(overview["bridge"]["source"])),
                    SOURCE,
                ),
            ]
        )
    )

    # ----------------------------------------------------------------- method
    story.append(p("1. The question and the method", H2))
    story.append(
        p(
            "For a given ship, route and market: what does the voyage earn a day, what freight does it need, which "
            "costs decide the answer, and is fixing the cargo better than hedging it on paper? The routes are the "
            "Baltic Exchange's (Guide to Market Benchmarks v8.8, September 2026): C3, C5, P7 and the S4A trip for "
            "dry bulk; TD3C, TD22, TD20 and TD25 dirty; TC2, TC14, TC1 and TC5 clean; TC20 and TD34 where needed."
        )
    )
    story.append(
        p(
            "TCE = (freight + other revenue %s commission %s voyage costs) / voyage days, over the whole round "
            "voyage, the ballast leg included. Voyage costs are bunkers by sulphur zone (MGO inside emission control "
            "areas, measured on the route line), port charges, canal tolls, EU allowances and, where the owner pays "
            "it, the war risk premium. The tanker TCE follows the Baltic's own method (Appendix 3 of the guide): a 5 "
            "percent weather margin on steaming days, the round voyage from the discharge port, the port and waiting "
            "days and consumptions of the route's description, and bunkers at the hub nearest the load port; C3 alone "
            "is priced at Singapore, about 270 nm off its ballast leg, since the hub nearest Tubarao lies off it. The "
            "guide leaves a dry route's weather allowance to its panellists, so the same 5 percent on the dry routes "
            "is the study's choice. Worldscale freight is WS / 100 x flat rate, priced with the reader's own licensed "
            "flat rate. Commission is %s percent on dry routes and %s percent on tankers, address commission and "
            "brokerage together." % (MINUS, MINUS, short(dry_commission), short(tanker_commission))
        )
    )
    story.append(
        p(
            "Every input is sourced, derived by a stated rule, the study's choice, left out as the Baltic leaves it "
            "out (a war risk premium) or empty: a figure with no public source, such as port charges and canal tolls, "
            "stays out of the TCE and the result names it. A dated market reads no price from after its date. The "
            "engine is a Python package, mirrored in the browser and held to it within one part in a billion on %d "
            "cases." % case_count
        )
    )
    # ------------------------------------------------------------- validation
    story.append(p("2. Validation", H2))
    exception = summary["exception"]
    stale = summary["stale"]
    story.append(
        p(
            "The Baltic publishes its tanker routes on a Worldscale and a TCE basis. Only two study routes are "
            "assessed as a lump sum in dollars, TD22 and TC20, so only they can be priced without a licensed flat "
            "rate: %d weeks between %s and %s. With bunker prices first printed in the week, the engine reads %s to "
            "%s percent above the Baltic's TCE, and %s to %s percent with prices up to a week old, always above it. "
            "The gap grows with freight, from %s a day at a %s lump sum (%s) to %s at %s (%s), so the port charges "
            "the engine leaves out, a fixed sum a voyage, explain only part of it. The weeks to %s, just after the "
            "closure of Hormuz, read %s percent above with tables of the same weeks, and why is not established; "
            "TD3C, priced at Fujairah, shows no such jump in those weeks (below), which points to TD22's Houston "
            "prices or to the hub the Baltic priced TD22 at before its guide rewrote the fuel price text in May 2026."
            % (
                summary["weeks"],
                date_label(min(r["week_ending"] for r in reproducible)),
                date_label(max(r["week_ending"] for r in reproducible)),
                number(summary["fresh_error"][0] * 100.0, "error_percent"),
                number(summary["fresh_error"][1] * 100.0, "error_percent"),
                number(summary["usual_error"][0] * 100.0, "error_percent"),
                number(summary["usual_error"][1] * 100.0, "error_percent"),
                usd(low["gap_usd_day"], "usd_day"),
                usd_m(low["row"]["rate_value"]),
                date_label(low["row"]["week_ending"]),
                usd(high["gap_usd_day"], "usd_day"),
                usd_m(high["row"]["rate_value"]),
                date_label(high["row"]["week_ending"]),
                " and ".join(date_label(r["week_ending"]) for r in exception),
                " and ".join(number(r["error"] * 100.0, "error_percent") for r in exception),
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p(
                    "The engine against the Baltic's TD22 and TC20 TCEs, week by week: %s to %s percent above with "
                    "bunker prices up to a week old, the two weeks after the closure of Hormuz aside."
                    % (
                        number(summary["usual_error"][0] * 100.0, "error_percent"),
                        number(summary["usual_error"][1] * 100.0, "error_percent"),
                    ),
                    CAPTION,
                ),
                validation_chart(
                    sorted(reproducible, key=lambda r: (r["route"] != "TD22", r["week_ending"])),
                    method["page"]["chart"],
                ),
                p(
                    # The site's chart adds TD3C at its implied flat rate; this one plots the lump sums only.
                    "Figure 2. "
                    + escape(plain(method["page"]["chart"]["source"])).replace(
                        " TD3C's flat rate implied by Platts' pairs of 2 and 13 January 2026 (Hellenic Shipping News, "
                        "17 January 2026);",
                        "",
                    ),
                    SOURCE,
                ),
            ]
        )
    )

    story.append(
        p(
            "The bunker table matters too: Star Asia sometimes reprints a week's table (%s, priced with Houston "
            "prices first printed on %s, reads %s percent %s), and for %s Intermodal's Houston VLSFO, USD %s, against "
            "Star Asia's USD&nbsp;%s moves the comparison from %s to %s percent. No public source states a flat rate "
            "for a study route's ports, but Platts printed its Persian Gulf to China rate in both units in January "
            "2026 (w53.5 and USD&nbsp;11.07 a tonne, w93 and USD&nbsp;19.24), which implies USD&nbsp;%s a tonne for "
            "its route, whose ports it does not state. At that rate the Baltic's TD3C weeks of 2026 read %s to %s "
            "percent against its TCE, the two weeks after the closure within that range. The other %d Worldscale "
            "anchors need "
            "a licensed flat rate and are recorded, not tuned. The Baltic's worked TD3C calculation of July 2017, the "
            "one fully worked public example found, is reproduced line by line: laden %s days, ballast %s, %s in all, "
            "%s t of fuel laden; it prints no prices, so no dollar figure is checked against it. Searoute distances "
            "fall within 2 percent of NGA Pub. 151 for %d of %d port pairs; the largest miss is %s (%s percent)."
            % (
                ", ".join("the week to %s" % date_label(r["week_ending"]) for r in stale) or "no week",
                ", ".join(date_label(r["bunkers_first_printed"]) for r in stale) or "",
                ", ".join(number(abs(r["error"]) * 100.0, "error_percent") for r in stale) or "",
                ", ".join(side(r["error"]) for r in stale) or "",
                date_label(cross["date"]),
                number(cross["vlsfo_other_usd_t"], "usd_t"),
                number(cross["vlsfo_study_usd_t"], "usd"),
                number(cross["error_study"] * 100.0, "error_percent"),
                number(cross["error_other"] * 100.0, "error_percent"),
                number(implied["flat_rates"]["TD3C"], "usd_t"),
                number(implied["error"][0] * 100.0, "error_percent", signed=True),
                number(implied["error"][1] * 100.0, "error_percent", signed=True),
                len(ws),
                number(b2017["computed"]["laden_days"], "days_2"),
                number(b2017["computed"]["ballast_days"], "days_2"),
                number(b2017["computed"]["total_days"], "days_2"),
                number(b2017["computed"]["laden_fuel_t"], "t_2"),
                len(within),
                len(distances["checks"]),
                "%s to %s" % (misses[0]["from"], misses[0]["to"]) if misses else "none",
                number(misses[0]["error"] * 100.0, "percent", signed=True) if misses else "0",
            )
        )
    )
    platts = early["platts_pg_china_2026_03_02"]
    rumour = early["oilprice_gulf_china_2026_03_03"]
    seed_market = cases.seed("market.json")
    early_hull = seed_market["hull_values_usd"]["march_2026_vlcc"]["value"]
    early_premium = next(r for r in seed_market["war_risk"]["rates_pct"] if r["id"] == "hormuz_2026_03_early")["low"]
    td3c_weeks = sorted(
        (r for r in tanker if r["route"] == "TD3C" and r["published_tce_usd_day"]), key=lambda r: r["week_ending"]
    )
    before = [r for r in td3c_weeks if r["week_ending"] < platts["date"]][-1]
    after = next(r for r in td3c_weeks if r["week_ending"] >= platts["date"])
    story.append(
        p(
            "Early March 2026: Platts' %s a tonne for the Gulf to China on %s gives %s a day with the bunkers of the "
            "%s, and %s with the early March premium of %s percent of a %s hull in the owner's costs; the %s that "
            "Oilprice.com reported on %s names no primary assessment and would give %s. The Baltic's TD3C TCE was %s "
            "in the week to %s and %s in the week to %s."
            % (
                usd(platts["freight_usd_t"], "usd_t"),
                date_label(platts["date"]),
                usd(platts["engine_tce_usd_day"], "usd_day"),
                market_words(platts["bunkers"]),
                usd(platts["engine_tce_with_war_risk_usd_day"], "usd_day"),
                number(early_premium, "percent"),
                usd_m(early_hull, "usd_m_0"),
                usd(rumour["freight_usd_t"], "usd_t"),
                date_label(rumour["date"]),
                usd(rumour["engine_tce_usd_day"], "usd_day"),
                usd(before["published_tce_usd_day"], "usd_day"),
                date_label(before["week_ending"]),
                usd(after["published_tce_usd_day"], "usd_day"),
                date_label(after["week_ending"]),
            )
        )
    )
    # -------------------------------------------------------- cost structure
    story.append(p("3. Where the money goes", H2))
    story.append(
        p(
            "At one common dated market, %s (the EU allowance at EUR %s a tonne and %s dollars a euro), sourced voyage "
            "costs are bunkers and, on voyages that touch the EEA, EU allowances. The share of MGO in the bunker bill "
            "follows the miles inside emission control areas and the days at EU berths."
            % (escape(market.label), number(market.eua_eur_t, "eur_t"), number(market.usd_per_eur, "usd_per_eur"))
        )
    )
    cost_rows = []
    for r in structure["rows"]:
        grades = r["bunkers_by_grade_usd"]
        bunker_total = math.fsum(grades.values())
        cost_rows.append(
            [
                baltic.ROUTES[r["route"]].code.split("_")[0] if r["route"] != "S4A_63" else "S4A",
                r["name"],
                number(r["days"], "days"),
                number(r["total_usd"], "usd"),
                number(r["shares"]["bunkers"] * 100.0, "percent"),
                number(r["shares"]["ets"] * 100.0, "percent"),
                number(grades.get("mgo", 0.0) / bunker_total * 100.0 if bunker_total else 0.0, "percent"),
            ]
        )
    story.append(
        KeepTogether(
            [
                p("Table 1. Sourced voyage costs at the %s market, by route." % escape(market.label), CAPTION),
                table(
                    [
                        "Route",
                        "Voyage",
                        "Days",
                        "Sourced voyage costs, USD",
                        "Bunkers, %",
                        "EU ETS, %",
                        "MGO in bunkers, %",
                    ],
                    cost_rows,
                    [0.07, 0.36, 0.07, 0.16, 0.1, 0.1, 0.14],
                    {2, 3, 4, 5, 6},
                ),
                p(
                    "Engine output at the common market: bunkers, Ship &amp; Bunker's August and third quarter "
                    "averages at each route's hub; allowances, DEHSt's August average at the %d phase in; dollars, the "
                    "Federal Reserve's H.10. Port charges and canal tolls have no public figure. S4A's row holds the "
                    "charterer's trip costs and the owner's ballast leg. Sources %s."
                    % (cases.ETS_FULL_FROM, pages.retrieval_words()),
                    SOURCE,
                ),
            ]
        )
    )

    # ------------------------------------------------------------------ speed
    story.append(p("4. Speed", H2))
    speed_rows = []
    for r in speed["routes"]:
        by = {(g["freight_level"], g["bunker_level"]): g for g in r["grid"]}

        def kn(f: str, b: str, by: dict = by) -> str:
            g = by[(f, b)]
            return number(g["optimal_laden_kn"], "knots") + (
                " (top)" if g["at_top"] else " (bottom)" if g["at_bottom"] else ""
            )

        speed_rows.append(
            [
                r["route"],
                kn("low", "mid"),
                kn("mid", "mid"),
                kn("high", "mid"),
                kn("mid", "low"),
                kn("mid", "high"),
                number(r["power_fit_laden"]["b"], "exponent"),
            ]
        )
    story.append(
        p(
            "The TCE was computed on a %s knot grid from %s knot below the slowest published speed to %s knot above "
            "the fastest, at the lowest, median and highest public freight of the weeks studied (December 2025 to "
            "October 2026) and at the lowest weekly, the %s and the highest weekly bunker price at the route's hub. "
            "Along every line of that grid the best speed never falls as freight rises or rises as bunkers rise, and "
            "somewhere it moves: the textbook result %s. Tanker consumption comes at two speeds, so the fitted "
            "exponent is low and the best tanker speed sits at the top of the range except at the lowest freight."
            % (
                short(speed["step_kn"]),
                short(speed["margin_kn"]),
                short(speed["margin_kn"]),
                escape(market.label),
                "holds on every route tested" if holds else "does not hold on every route tested",
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p("Table 2. Laden speed that maximises the TCE, knots.", CAPTION),
                table(
                    [
                        "Route",
                        "Low freight",
                        "Median freight",
                        "High freight",
                        "Cheap bunkers",
                        "Dear bunkers",
                        "Fitted exponent",
                    ],
                    speed_rows,
                    [0.1, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15],
                    {1, 2, 3, 4, 5, 6},
                ),
                p(
                    "Freight columns at the common market's bunkers, bunker columns at the median freight; top, "
                    "bottom: an end of the range searched. Engine output on the guide's speed pairs; freight: the "
                    "Baltic's reports and the dry weeks' rates; bunkers: Star Asia, Ship &amp; Bunker. Sources %s."
                    % pages.retrieval_words(),
                    SOURCE,
                ),
            ]
        )
    )

    # ---------------------------------------------------------------- detours
    story.append(p("5. Detours: Suez, the Cape and Hormuz", H2))
    dry = {o["name"]: o for o in sd["options"]}
    chains = hz["chains"]
    shuttle = pages._shuttle(hz)
    story.append(
        p(
            "Asia to Europe. An LR2 on TC20, Jubail to Rotterdam at the Baltic's lump sum of %s in the week to %s, "
            "earns the owner %s a day by Suez before any toll and %s round the Cape, %s days and %s tonne miles more. "
            "The charterer pays the Gulf's premium on both routings and the Red Sea's on the laden Suez transit, %s a "
            "tonne; the ballast transit, the approach to the next loading, is the owner's (Gard, March 2026) and comes "
            "off the Suez TCE. A Panamax one way from Qingdao to Rotterdam, like the P4 trip, needs %s a tonne by Suez "
            "to earn P4's hire net of commission (%s a day), %s by Panama and %s round the Cape, before port time, "
            "port charges and tolls; at the Cape's freight, Suez could bear %s of tolls and waiting, Panama %s."
            % (
                usd_m(st["rate_usd"]),
                date_label(st["as_of"]),
                usd(st["options"][0]["tce_usd_day"], "usd_day"),
                usd(st["options"][1]["tce_usd_day"], "usd_day"),
                number(cape["extra_days"], "days"),
                number(cape["extra_tonne_miles"] / 1e9, "tonne_miles_bn") + " billion",
                usd(red["per_tonne_usd"], "usd_t"),
                usd(dry["Suez"]["freight_for_target_usd_t"], "usd_t"),
                usd(sd["target_tce_usd_day"], "usd_day"),
                usd(dry["Panama"]["freight_for_target_usd_t"], "usd_t"),
                usd(dry["Cape of Good Hope"]["freight_for_target_usd_t"], "usd_t"),
                usd(dry["Suez"]["toll_and_waiting_budget_usd"]),
                usd(dry["Panama"]["toll_and_waiting_budget_usd"]),
            )
        )
    )
    story.append(
        p(
            "Hormuz. A TD3C voyage spends %s days inside the Gulf, one seven day period of premium; each further week "
            "of waiting adds a period for the charterer and the TCE it forgoes for the owner. Loading off Fujairah, "
            "the export VLCC sails %s fewer days, but the shuttle through the "
            "strait was reported at USD&nbsp;%s to %s a barrel (about %s to %s a tonne) and at %s a transit, and the "
            "transfer's own cost has no public figure. The Baltic assessed TD34, a cargo loading outside the strait, "
            "at %s a day against TD3C's %s in the week to %s, which the engine turns into freight of %s a tonne "
            "against %s."
            % (
                number(hz_scen["war_low"]["days_inside_gulf"], "days"),
                number(abs(chains["sts"]["extra_days"]), "days"),
                short(shuttle["bbl_low"]),
                short(shuttle["bbl_high"]),
                usd(shuttle["bbl_low_t"], "usd_t"),
                usd(shuttle["bbl_high_t"], "usd_t"),
                usd_m(shuttle["transit_usd"], "usd_m_0"),
                usd(chains["td34"]["published_tce_usd_day"], "usd_day"),
                usd(hz["td34_vs_td3c_published"]["td3c_tce_usd_day"], "usd_day"),
                date_label(latest_level["week_ending"]),
                usd(chains["td34"]["freight_at_own_tce_usd_t"], "usd_t"),
                usd(chains["td3c_freight_at_own_tce_usd_t"], "usd_t"),
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p(escape(plain(detours["page"]["chart"]["title"])), CAPTION),
                detours_chart(detours["page"]["chart"]["rows"], detours["page"]["chart"]),
                p(
                    "Figure 3. "
                    + escape(plain(detours["page"]["chart"]["source"])).replace("under Hormuz, VLCC", "in section 5"),
                    SOURCE,
                ),
            ]
        )
    )

    # ----------------------------------------------------------------- carbon
    story.append(p("6. Carbon", H2))
    carbon_rows = []
    for r in carbon["rows"]:
        years = {y["year"]: y for y in r["years"]}
        carbon_rows.append(
            [
                "%s, %s" % (r["route"], r["kind"]),
                usd(years[2024]["cost_usd"]),
                usd(years[2025]["cost_usd"]),
                usd(years[2026]["cost_usd"]),
                number(years[2026]["per_tonne_cargo_usd"], "usd_t"),
            ]
        )
    tc = carbon["time_charter"]
    story.append(
        p(
            "EU allowances cover half the emissions of a voyage into or out of the EEA and all of one between two "
            "EEA ports and within a port of call, for %s percent of %d emissions, %s percent of %d and 100 percent "
            "from %d, with methane and nitrous oxide (Directive 2003/87/EC, Articles 3ga and 3gb, Annex I). On a time "
            "charter the charterer provides the allowances for the charter's emissions (BIMCO ETS Allowances Clause, "
            "2022) and the owner surrenders them (Article 3gc): on the S4A trip the charterer pays %s and the owner %s "
            "for the ballast leg back. FuelEU's penalty is assessed on a ship's year, so it stays out of the TCE."
            % (
                short(cases.ETS_PHASE_IN[2024] * 100.0),
                2024,
                short(cases.ETS_PHASE_IN[2025] * 100.0),
                2025,
                cases.ETS_FULL_FROM,
                usd(tc["trip_ets_usd"]),
                usd(tc["owner_ets_usd"]),
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p("Table 3. EU ETS cost of one voyage by phase in year, at the August 2026 allowance price.", CAPTION),
                table(
                    ["Voyage", "2024", "2025", "2026", "2026, USD a tonne of cargo"],
                    carbon_rows,
                    [0.34, 0.15, 0.15, 0.15, 0.21],
                    {1, 2, 3, 4},
                ),
                p(
                    "Engine output at EUR %s a tonne (%s) and %s dollars a euro (%s); emission factors of Regulation "
                    "(EU) 2015/757 Annex I as amended, global warming potentials %s for methane and %s for nitrous "
                    "oxide. Sources %s."
                    % (
                        number(carbon["eua_eur_t"], "eur_t"),
                        escape(carbon["eua_source"]),
                        number(carbon["usd_per_eur"], "usd_per_eur"),
                        escape(market.fx_source),
                        short(engine.GWP_CH4),
                        short(engine.GWP_N2O),
                        pages.retrieval_words(),
                    ),
                    SOURCE,
                ),
            ]
        )
    )

    # ------------------------------------------------------------------ paper
    story.append(p("7. Physical against paper", H2))
    fixture = paper["c5_fixture"]
    basis = anchors.capesize_basis_2026_07_03()
    story.append(
        p(
            "5TC FFAs settle on the month's average of the daily index in dollars a day (EEX's C5TM on the 182,000 t "
            "ship), C3, C5 and the ICE tanker routes on the month's average in dollars a tonne (TC5 and the 75,000 t "
            "Arab Gulf to Japan contract on Platts, the rest on the Baltic). A voyage's net TCE is grossed up by its "
            "commission before it meets gross hire (guide, 7.4.3), here the FFA strip over the voyage's days from the "
            "fixture date; the 29 June curve was printed twice (July USD&nbsp;31,367, then 36,232). The C3 voyage of "
            "the week to %s is hedged with %s days of 5TC (%s hedge its net earnings) or %s tonnes of C3; that day's "
            "spot 5TC, USD&nbsp;%s, is the 180,000 t basis, so the 182,000 t ship meets USD&nbsp;%s. A C5 cargo fixed "
            "on %s at %s a tonne for %s matched the route that day in the report's narrative, %s; its table and "
            "narrative differ by %s at the next close, about %s a day."
            % (
                date_label(c3_27["date"]),
                number(c3_27["hedge_days"], "days"),
                number(c3_27["hedge_days_net"], "days"),
                number(baltic.ROUTES["C3"].cargo_t, "t"),
                number(basis["printed_usd_day"], "usd_day"),
                number(basis["basket_182_if_180_usd_day"], "usd_day"),
                date_label(fixture["date"]),
                usd(fixture["fixture_usd_t"], "usd_t"),
                fixture["laycan"],
                usd(fixture["route_on_day_usd_t"], "usd_t"),
                usd(fixture["series_gap_usd_t"], "usd_t"),
                usd(abs(fixture["basis_table_series_usd_day"]), "usd_day"),
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p(escape(plain(paper["page"]["chart"]["title"])), CAPTION),
                paper_chart(capesize, paper["page"]["chart"]),
                p(
                    "Figure 4. " + escape(plain(paper["page"]["chart"]["source"])),
                    SOURCE,
                ),
            ]
        )
    )

    # ------------------------------------------------------------ limitations
    story.append(p("8. What the study cannot do", H2))
    per_day = {r["route"]: r["excluded_block_per_day_usd"] for r in structure["rows"]}
    margin_effect = [r["no_margin_tce_gross_usd_day"] / r["physical_tce_gross_usd_day"] - 1.0 for r in capesize]
    story.append(
        bullets(
            [
                "Port charges have no public per call figure: every TCE leaves them out (each USD&nbsp;100,000 is %s a "
                "day on C3, %s on C5 and %s on TD22), and they explain only part of the gap to the Baltic."
                % (usd(per_day["C3"]), usd(per_day["C5"]), usd(per_day["TD22"])),
                "No public source states a Worldscale flat rate for a study route's ports, nor a fully worked voyage "
                "estimate with prices: Worldscale rates need the reader's own flat rate (TD3C's 2026 check aside), "
                "and the Baltic's 2017 TD3C note checks days and fuel only.",
                "Suez and Panama tolls, and canal time on the dry routings, are left out. Bulk carrier speeds and the "
                "5 percent dry weather margin are the study's choices; without the margin the Capesize TCEs here read "
                "%s to %s percent higher."
                % (
                    number(min(margin_effect) * 100.0, "percent_0"),
                    number(max(margin_effect) * 100.0, "percent_0"),
                ),
                "Bunker prices are broker tables and averages at four hubs, not what a ship paid, and two brokers can "
                "differ widely for the same day; the dry FFA curves are dated assessments, one date printed twice "
                "with different values, and no public tanker or route FFA quote in dollars a tonne was found.",
                "War risk premiums are the latest dated rates, from July 2026; the listed area is taken to end at the "
                "strait, a lower bound, though the Joint War Committee widened it in 2026.",
            ]
        )
    )
    story.append(p("Sources and reproduction", H2))
    story.append(
        p(
            "Baltic Exchange (Guide to Market Benchmarks v8.8; TD3C TCE calculation, July 2017), its weekly tanker "
            "reports, %s to %s, and the brokers' and insurers' reports cited, via Hellenic Shipping News; Ship &amp; "
            "Bunker; European Commission and DEHSt; Federal Reserve H.10; EUR-Lex and IMO; NGA Pub. 150 and 151; "
            "searoute 1.6.0 over Eurostat SeaRoute; EEX and ICE. Retrievals and hashes: data/raw/manifest.json; "
            "scripts/note.py writes this note."
            % (
                date_label(min(r["week_ending"] for r in tanker)[:7]),
                date_label(max(r["week_ending"] for r in tanker)[:7]),
            )
        )
    )

    rl_config.invariant = 1
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="Voyage economics and the time charter equivalent",
        author="Nathan Couturier",
        subject="Voyage economics and TCE for dry bulk and tanker routes, 2026",
        creator="scripts/note.py, voyage-tce-model",
    )

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("LiberationSerif", 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, 10 * mm, "Voyage economics and the time charter equivalent, " + retrieved)
        canvas.drawRightString(PAGE_W - MARGIN_X, 10 * mm, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return doc.page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT, help="where to write the note")
    args = parser.parse_args()
    pages = build(args.out)
    print(
        "wrote %s: %d pages"
        % (args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out, pages)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
