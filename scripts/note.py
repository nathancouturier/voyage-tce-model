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


def usd(value: float, fmt: str = "usd") -> str:
    return "USD " + number(value, fmt)


def usd_m(value: float, fmt: str = "usd_m") -> str:
    return "USD %s million" % number(value / 1e6, fmt)


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
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------


def register_fonts() -> None:
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
H2 = ParagraphStyle("h2", parent=BODY, fontName="LiberationSerif-Bold", fontSize=12, leading=15, spaceBefore=8)
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


def dot(face: str, edge: str, text: str) -> Line2D:
    return Line2D(
        [0], [0], marker="o", linestyle="", markersize=5, markerfacecolor=face, markeredgecolor=edge, label=text
    )


def key(ax: Any, handles: list[Any], **where: Any) -> None:
    """The legend of a chart, in words beside a sample of each mark."""
    legend = ax.legend(handles=handles, frameon=False, fontsize=6.8, handlelength=1.1, borderaxespad=0.2, **where)
    for text in legend.get_texts():
        text.set_color(C["text"])


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
    height = 2.55
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
    """Figure 2: the engine against the Baltic's published TCE, week by week."""
    height = 0.42 + 0.21 * len(rows)
    fig, ax = new_figure(height)
    labels = []
    for at, r in enumerate(rows):
        y = -at
        same = r["bunkers"] == "week of " + r["week_ending"]
        labels.append("%s, %s" % (r["route"], date_label(r["week_ending"])))
        ax.scatter(
            [r["error"] * 100.0],
            [y],
            s=26,
            color=C["text"] if same else "white",
            edgecolors=C["text"],
            linewidths=1.1,
            zorder=3,
        )
        ax.text(
            r["error"] * 100.0 + 0.6,
            y,
            number(r["error"] * 100.0, "error_percent", signed=True),
            va="center",
            fontsize=6.8,
            family="Liberation Mono",
            bbox=HALO,
        )
    ax.axvline(0, color=C["text-muted"], linewidth=0.8)
    ax.set_yticks([-i for i in range(len(rows))], labels)
    ax.set_ylim(-len(rows) + 0.5, 0.5)
    ax.set_xlim(-1, max(r["error"] for r in rows) * 100.0 + 3.5)
    ax.set_xlabel(words["axis"])
    ink, ring = (next(item["text"] for item in words["legend"] if item["kind"] == kind) for kind in ("ink", "ring"))
    key(ax, [dot(C["text"], C["text"], ink), dot("white", C["text"], ring)], loc="lower right")
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    fig.tight_layout(pad=0.4)
    return picture(fig, height)


def detours_chart(rows: list[dict[str, Any]], words: dict[str, Any]) -> Image:
    """Figure 3: the extra freight a tonne that keeps the TCE, detour by detour."""
    groups: list[str] = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])
    lines = []
    for g in groups:
        lines.append(("group", g, None))
        lines += [("row", r["label"], r) for r in rows if r["group"] == g]
    height = 0.45 + 0.19 * len(lines)
    fig, ax = new_figure(height)
    ticks, labels = [], []
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
        face = C["data-war"] if r["family"] == "war" else C["text"]
        ax.barh(y, r["value"], height=0.55, color=face)
        value = number(r["value"], "usd_t", signed=True) + (", " + r["detail"] if r["detail"] else "")
        ax.text(
            r["value"] + (1.5 if r["value"] >= 0 else -1.5),
            y,
            value,
            va="center",
            ha="left" if r["value"] >= 0 else "right",
            fontsize=6.8,
            family="Liberation Mono",
            bbox=HALO,
        )
        ticks.append(y)
        labels.append(text)
    ax.set_yticks(ticks, labels)
    ax.set_ylim(-len(lines) + 0.5, 0.6)
    low = min(r["value"] for r in rows)
    ax.set_xlim(min(0, low) * 2.6, max(r["value"] for r in rows) * 1.8)
    ax.axvline(0, color=C["text-muted"], linewidth=0.8)
    ax.set_xlabel(words["axis"])
    faces = {"routing": C["text"], "war": C["data-war"]}
    key(ax, [Patch(facecolor=faces[item["family"]], label=item["text"]) for item in words["legend"]], loc="lower right")
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    fig.tight_layout(pad=0.4)
    return picture(fig, height)


def paper_chart(rows: list[dict[str, Any]], words: dict[str, Any]) -> Image:
    """Figure 4: the physical voyage TCE against the 5TC FFA for the month and the spot 5TC."""
    height = 0.75 + 0.27 * len(rows)
    fig, ax = new_figure(height)
    labels = []
    for at, r in enumerate(rows):
        y = -at
        labels.append("%s, %s" % (r["route"], date_label(r["date"])))
        ffa = r["ffa"]["usd_day"]
        ax.plot([r["physical_tce_usd_day"], ffa], [y, y], color=C["text-muted"], linewidth=1, zorder=1)
        ax.scatter([r["spot_index_usd_day"]], [y], s=20, color=C["text-muted"], zorder=2)
        ax.scatter([ffa], [y], s=26, color="white", edgecolors=C["text"], linewidths=1.1, zorder=3)
        ax.scatter([r["physical_tce_usd_day"]], [y], s=26, color=C["text"], zorder=4)
    ax.set_yticks([-i for i in range(len(rows))], labels)
    ax.set_ylim(-len(rows) + 0.5, 0.5)
    ax.set_xlabel(words["axis"])
    marks = {"ink": (C["text"], C["text"]), "ring": ("white", C["text"]), "muted": (C["text-muted"], C["text-muted"])}
    key(
        ax,
        [dot(*marks[item["kind"]], item["text"]) for item in words["legend"]],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.42),
        ncol=len(words["legend"]),
    )
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: number(v, "usd_day")))
    style_axes(ax)
    for label in ax.get_yticklabels():
        label.set_color(C["text"])
    fig.tight_layout(pad=0.4)
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
    reproducible = [r for r in tanker if r["reproducible"]]
    same_week = [r for r in reproducible if r["bunkers"] == "week of " + r["week_ending"]]
    ws = [r for r in tanker if not r["reproducible"] and r["rate_basis"] == "ws"]
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

    def hz_extra(sid: str) -> float:
        return next(
            lv["extra_freight_usd_t"]
            for lv in hz_scen[sid]["levels"]
            if lv["week_ending"] == latest_level["week_ending"]
        )

    ets_rows = [r for r in structure["rows"] if r["shares"]["ets"] > 0]
    td3c = next(r for r in structure["rows"] if r["route"] == "TD3C")
    war = td3c["with_hormuz_war_risk"]
    rows_27 = [r for r in capesize if r["date"] == capesize[0]["date"]]
    c3_27 = next(r for r in rows_27 if r["route"] == "C3")
    c5_27 = next(r for r in rows_27 if r["route"] == "C5")
    textbook = speed["textbook"]
    holds = all(t["freight_pushes_speed_up"] and t["bunkers_push_speed_down"] for t in textbook)
    story.append(p("Summary", H2))
    story.append(
        bullets(
            [
                escape(plain(overview["verdict"]))
                + " The Baltic's own round voyage TCE that week was %s; the engine reads %s percent higher, about the "
                "port charges it leaves out." % (usd(published, "usd_day"), number(error * 100.0, "error_percent")),
                "On routes outside Europe, bunkers are every sourced dollar of voyage cost at the %s market; on "
                "voyages into or out of the EEA, EU allowances at the %d phase in are %s to %s percent of it (EUA "
                "EUR %s a tonne). A Hormuz war risk premium of %s percent of a %s VLCC hull would cost %s a transit, "
                "%s times TD3C's bunker bill."
                % (
                    market.label,
                    cases.ETS_FULL_FROM,
                    number(min(r["shares"]["ets"] for r in ets_rows) * 100.0, "percent"),
                    number(max(r["shares"]["ets"] for r in ets_rows) * 100.0, "percent"),
                    number(market.eua_eur_t, "eur_t"),
                    number(war["premium_pct"], "percent"),
                    usd_m(war["hull_value_usd"], "usd_m_0"),
                    usd_m(war["costs_usd"]["war_risk"]),
                    times(war["war_risk_to_bunkers"]),
                ),
                "Round the Cape of Good Hope an LR2 on TC20 sails %s more days than by Suez and needs %s (%s a tonne) "
                "more freight to earn what Suez earns with the Red Sea premium paid; Suez stays the better way until "
                "its toll passes %s."
                % (
                    number(cape["extra_days"], "days"),
                    usd_m(cape["extra_freight_lump_sum_usd"]),
                    usd(cape["extra_freight_usd_t"], "usd_t"),
                    usd_m(st["break_even_suez_toll_usd"]),
                ),
                "For a VLCC from the Gulf, a %s percent Hormuz premium needs %s a tonne more freight to keep its TCE; "
                "with 20 days of waiting to transit, at the TCE of the week to %s, %s."
                % (
                    number(war["premium_pct"], "percent"),
                    usd(hz_extra("war_low"), "usd_t"),
                    date_label(latest_level["week_ending"]),
                    usd(hz_extra("wait_20"), "usd_t"),
                ),
                "In the week to %s a C3 cargo at %s a tonne earned %s a day, %s a day %s the %s Capesize 5TC FFA; "
                "a C5 cargo at %s earned %s a day, %s %s it. The FFA stood %s a day above the spot 5TC: the market "
                "priced the coming months above the week's spot."
                % (
                    date_label(c3_27["date"]),
                    usd(c3_27["freight_usd_t"], "usd_t"),
                    usd(c3_27["physical_tce_usd_day"], "usd_day"),
                    usd(abs(c3_27["basis_usd_day"]), "usd_day"),
                    "below" if c3_27["basis_usd_day"] < 0 else "above",
                    date_label(c3_27["ffa"]["period"]),
                    usd(c5_27["freight_usd_t"], "usd_t"),
                    usd(c5_27["physical_tce_usd_day"], "usd_day"),
                    usd(abs(c5_27["basis_usd_day"]), "usd_day"),
                    "below" if c5_27["basis_usd_day"] < 0 else "above",
                    usd(c3_27["timing_basis_usd_day"], "usd_day"),
                ),
                "Higher freight raises the speed that maximises the TCE and dearer bunkers lower it, %s of the routes "
                "tested (%s)."
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
            "costs decide the answer, and is fixing the cargo physically better than hedging the same exposure on "
            "paper? The study covers the routes the Baltic Exchange defines in its Guide to Market Benchmarks v8.8 "
            "(September 2026): Capesize C3 and C5, Panamax P7 and the Supramax trip S4A for dry bulk; TD3C, TD22, "
            "TD20 and TD25 for dirty tankers; TC2, TC14, TC1 and TC5 for clean, with TC20 and TD34 where the "
            "Baltic's lump sums and the Hormuz bypass need them."
        )
    )
    story.append(
        p(
            "The TCE is gross freight and other revenue, less commission and voyage costs, over the days of the "
            "whole round voyage, the ballast leg included: TCE = (freight + other revenue %s commission %s voyage "
            "costs) / voyage days. Voyage costs are bunkers by sulphur zone (MGO inside emission control areas, "
            "measured on the route line), port charges, canal tolls, EU allowances and war risk premiums. The tanker "
            "TCE follows the Baltic's own method (Appendix 3 of the guide): a 5 percent weather margin on steaming "
            "days, the round voyage from the discharge port, the port and waiting days and consumptions of the "
            "route's description, and bunkers at the hub nearest the load port. Worldscale freight is WS / 100 x "
            "flat rate; flat rates are licensed and none is public for 2025 or 2026, so a Worldscale rate is priced "
            "only with the reader's own. Commission is %s percent on dry routes and %s percent on tankers."
            % (MINUS, MINUS, short(dry_commission), short(tanker_commission))
        )
    )
    story.append(
        p(
            "Every input is either sourced (a dated public document, with the passage it was read from), derived "
            "(a stated rule on sourced values) or empty: a figure with no public source stays out of the TCE and the "
            "result names it. Port charges have no public per call figure for any study port and Suez and Panama "
            "tolls depend on each ship's canal tonnage, so every TCE here leaves them out and reads high by their "
            "amount. A dated market reads no price from after its date. The engine is a Python package, mirrored "
            "in the browser and held to it within one part in a billion on %d cases." % case_count
        )
    )
    # ------------------------------------------------------------- validation
    story.append(p("2. Validation", H2))
    story.append(
        p(
            "The Baltic publishes its tanker routes on a Worldscale and a TCE basis. Only two study routes are "
            "assessed as a lump sum in dollars, TD22 and TC20, so only they can be priced without a licensed flat "
            "rate: %d weeks between %s and %s, with bunker prices of the same week, reproduce the Baltic's TCE within "
            "%s to %s percent, the engine always above it by about the port charges it leaves out. The %d "
            "Worldscale anchors cannot be reproduced without a licensed flat rate, and are recorded as such rather "
            "than tuned. The Baltic's "
            "own worked TD3C calculation of July 2017 is reproduced line by line: laden %s days, ballast %s days, "
            "%s days in all, and %s tonnes of fuel laden; it prints no prices. Searoute distances fall within 2 "
            "percent of NGA Pub. 151 for %d of %d port pairs; the largest miss is %s (%s percent)."
            % (
                len(same_week),
                date_label(min(r["week_ending"] for r in same_week)),
                date_label(max(r["week_ending"] for r in same_week)),
                number(min(r["error"] for r in same_week) * 100.0, "error_percent"),
                number(max(r["error"] for r in same_week) * 100.0, "error_percent"),
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
            "Early March 2026: Platts assessed the Gulf to China VLCC rate at %s a tonne on %s, which the engine "
            "turns into %s a day with the bunkers of the %s (%s with the early March war risk premium of %s "
            "percent of a %s hull). The %s a tonne widely reported on %s names no primary assessment; it would "
            "give %s a day. The Baltic's TD3C TCE was %s in the week to %s and %s in the week to %s."
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
    story.append(
        KeepTogether(
            [
                p(escape(plain(method["page"]["chart"]["title"])), CAPTION),
                validation_chart(
                    sorted(reproducible, key=lambda r: (r["route"] != "TD22", r["week_ending"])),
                    method["page"]["chart"],
                ),
                p(
                    "Figure 2. " + escape(plain(method["page"]["chart"]["source"])),
                    SOURCE,
                ),
            ]
        )
    )

    # -------------------------------------------------------- cost structure
    story.append(p("3. Where the money goes", H2))
    story.append(
        p(
            "At one common dated market, %s (Ship &amp; Bunker's monthly averages, the EU allowance at EUR %s a tonne "
            "and %s dollars a euro), sourced voyage costs are bunkers and, on voyages that touch the EEA, EU "
            "allowances. The share of MGO in the bunker bill follows the miles inside emission control areas and the "
            "days at EU berths."
            % (escape(market.label), number(market.eua_eur_t, "eur_t"), number(market.usd_per_eur, "usd_per_eur"))
        )
    )
    cost_rows = []
    for r in structure["rows"]:
        grades = r["bunkers_by_grade_usd"]
        bunker_total = sum(grades.values())
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
                    ["Route", "Voyage", "Days", "Voyage costs, USD", "Bunkers, %", "EU ETS, %", "MGO in bunkers, %"],
                    cost_rows,
                    [0.07, 0.38, 0.07, 0.14, 0.1, 0.1, 0.14],
                    {2, 3, 4, 5, 6},
                ),
                p(
                    "Engine output; bunkers: Ship &amp; Bunker, %s averages (quarterly where no monthly figure "
                    "exists); allowances: %s, at the %d phase in; dollars: %s. Port charges and canal tolls have no "
                    "public figure and are not in the costs. Sources %s."
                    % (
                        escape(market.label),
                        escape(market.eua_source),
                        cases.ETS_FULL_FROM,
                        escape(market.fx_source),
                        pages.retrieval_words(),
                    ),
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
            return number(g["optimal_laden_kn"], "knots") + (" (edge)" if g["at_bound"] else "")

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
            "The TCE was computed at every laden speed on a %s knot grid from %s knot below the slowest published "
            "consumption to %s knot above the fastest, at the lowest, median and highest public freight of 2026 and "
            "at the lowest weekly, the %s and the highest weekly bunker price at the route's hub. The textbook "
            "result %s: freight pushes the best speed up, bunkers push it down. The guide gives tanker consumption "
            "at two speeds only, so the fitted exponent is low and, at 2026 freight, the best tanker speed sits at "
            "the top of the range: the curves cannot say whether that speed is reachable."
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
                    "Freight columns at the August bunker price, bunker columns at the median freight. Edge: the best "
                    "speed is at an end of the range searched. Engine output on the Baltic's published speed and "
                    "consumption pairs (Guide to Market Benchmarks v8.8).",
                    SOURCE,
                ),
            ]
        )
    )

    # ---------------------------------------------------------------- detours
    story.append(p("5. Detours: Suez, the Cape and Hormuz", H2))
    dry = {o["name"]: o for o in sd["options"]}
    story.append(
        p(
            "Asia to Europe. An LR2 on TC20, Jubail to Rotterdam at the Baltic's lump sum of %s in the week to %s, "
            "earns %s a day by Suez with the Red Sea premium paid, before any toll, and %s round the Cape, %s days and "
            "%s tonne miles more. A "
            "Panamax from Qingdao to Rotterdam needs %s a tonne to earn the P4 trip rate by Suez, %s by Panama and %s "
            "round the Cape; at the Cape's freight, Suez could bear %s of tolls and waiting, Panama %s."
            % (
                usd_m(st["rate_usd"]),
                date_label(st["as_of"]),
                usd(st["options"][1]["tce_usd_day"], "usd_day"),
                usd(st["options"][2]["tce_usd_day"], "usd_day"),
                number(cape["extra_days"], "days"),
                number(cape["extra_tonne_miles"] / 1e9, "tonne_miles_bn") + " billion",
                usd(dry["Suez"]["freight_for_target_usd_t"], "usd_t"),
                usd(dry["Panama"]["freight_for_target_usd_t"], "usd_t"),
                usd(dry["Cape of Good Hope"]["freight_for_target_usd_t"], "usd_t"),
                usd(dry["Suez"]["toll_and_waiting_budget_usd"]),
                usd(dry["Panama"]["toll_and_waiting_budget_usd"]),
            )
        )
    )
    story.append(
        p(
            "Hormuz. For a VLCC from Ras Tanura, the premium and the waiting outweigh every routing choice. Loading by "
            "a ship to ship transfer off Fujairah shortens the voyage by %s days, and loading at Mina Al Fahal outside "
            "the strait (the Baltic's TD34) by %s, but the cost of the transfer and of the shuttle through the strait "
            "has no public figure. The Baltic's TD34 TCE was %s a day in the week to %s, against %s on TD3C."
            % (
                number(-hz_scen["sts"]["extra_days"], "days"),
                number(-hz_scen["td34"]["extra_days"], "days"),
                usd(hz["td34_vs_td3c_published"]["td34_tce_usd_day"], "usd_day"),
                date_label(latest_level["week_ending"]),
                usd(hz["td34_vs_td3c_published"]["td3c_tce_usd_day"], "usd_day"),
            )
        )
    )
    story.append(
        KeepTogether(
            [
                p(escape(plain(detours["page"]["chart"]["title"])), CAPTION),
                detours_chart(detours["page"]["chart"]["rows"], detours["page"]["chart"]),
                p(
                    "Figure 3. " + escape(plain(detours["page"]["chart"]["source"])),
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
            "EEA ports, for %s percent of %d emissions, %s percent of %d and 100 percent from %d, when methane "
            "and nitrous oxide join carbon dioxide (Directive 2003/87/EC, Articles 3ga and 3gb). Under the BIMCO ETS "
            "Allowances Clause for time charter parties the charterer provides the allowances for the ship's "
            "emissions during the charter: on the S4A trip the charterer pays %s and the owner %s for the ballast leg "
            "back. FuelEU Maritime's penalty is assessed on a ship's yearly energy, not a voyage's, so it is shown "
            "beside the TCE and kept out of it."
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
    story.append(
        p(
            "Time charter FFAs such as Capesize 5TC settle on the month's average of the daily index in dollars a "
            "day; voyage route FFAs such as C3 and C5, and the tanker routes on ICE, on the month's average in "
            "dollars a tonne. A voyage is hedged with 5TC days equal to its days, or with route FFA tonnes equal to "
            "its cargo: %s days of 5TC or %s tonnes of C3 for the C3 voyage of the week to %s. The basis between a "
            "fixture and its index can be small: a C5 cargo fixed on %s at %s a tonne for %s, against a C5 index of "
            "%s, earns %s a day more than a cargo at the index. Public FFA quotes in dollars a tonne for tanker "
            "routes were not found."
            % (
                number(c3_27["hedge_days"], "days"),
                number(c3_27.get("hedge_tonnes", baltic.ROUTES["C3"].cargo_t), "t"),
                date_label(c3_27["date"]),
                date_label(fixture["date"]),
                usd(fixture["fixture_usd_t"], "usd_t"),
                fixture["laycan"],
                usd(fixture["index_usd_t"], "usd_t"),
                usd(fixture["basis_usd_day"], "usd_day"),
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
    story.append(bullets([escape(item) for item in method["page"]["limitations"]]))
    story.append(p("Sources and reproduction", H2))
    story.append(
        p(
            "Baltic Exchange, Guide to Market Benchmarks v8.8 (September 2026) and its TD3C TCE calculation process "
            "(July 2017); the Baltic's weekly tanker reports as republished by Hellenic Shipping News, %s "
            "to %s; Ship &amp; Bunker monthly analyses and quarterly tables; Star Asia Shipbroking and "
            "Banchero Costa weekly reports; Signal Group and Xclusiv Shipbrokers weekly reports; Marsh and S&amp;P "
            "Global Platts as reported in July 2026; EIA, Today in Energy, 26 March 2026; the European "
            "Commission's auction reports and DEHSt's German auction reports; the Federal Reserve's H.10; EUR-Lex "
            "(Directive 2003/87/EC as amended by Directive (EU) 2023/959, Regulation (EU) 2015/757 as amended, "
            "Regulation (EU) 2023/1805); IMO resolutions MEPC.328(76), MEPC.361(79) and MEPC.392(82); NGA Pub. 150 "
            "and Pub. 151; searoute 1.6.0 over Eurostat SeaRoute; EEX and ICE Futures Europe contract "
            "specifications. Every figure's document, retrieval time and hash are in the repository's "
            "data/raw/manifest.json; licensed documents are cited, never redistributed."
            % (
                date_label(min(r["week_ending"] for r in tanker)[:7]),
                date_label(max(r["week_ending"] for r in tanker)[:7]),
            )
        )
    )
    story.append(
        p(
            "This note is written by scripts/note.py from the committed data; make gate checks the data, the engine "
            "and the site, and make note writes the note again."
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
