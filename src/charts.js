/* charts.js
 *
 * SVG drawn by hand. No chart library is vendored: every mark this study needs
 * is specific to it, and a library's defaults (a legend card, colour cycling)
 * are each something the page does without. The helpers follow the sibling
 * studies' src/charts.js: a namespace helper, a path that breaks at a gap, a
 * 1, 2, 5, 10 tick ladder and a redraw on width change, so type inside a plot
 * stays the size the stylesheet says. Marks take colour from the role and
 * palette classes in styles/components.css, never from a fill or stroke
 * attribute holding a value, so a theme change needs no redraw.
 *
 * The drawings:
 *   bridgeBar   one row's bar in the bridge from gross freight to the result
 *   barChart    horizontal bars by category, stacked by family where asked,
 *               grouped under headings (cost structure, detours, carbon)
 *   dotChart    dots on one axis by category, with a span between two of them
 *               (physical against paper, the validation errors)
 *   lineChart   a line over a numeric x axis with marked points (TCE against
 *               speed)
 *   tooltip     the readout a pointer or the arrow keys open on a chart
 *
 * Missing is never zero. A null ends the current line and the next value
 * starts a new one; a bar with no value is not drawn and its row says why.
 *
 * NUMERIC LITERALS. GEOMETRY is the drawing surface: heights, paddings, a dot
 * radius, each declared with its value in tools/check-literals.mjs. Every
 * quantity about the market arrives from a JSON artifact through the caller,
 * and every word drawn is handed in by the caller from the artifact.
 */

import { formatNumber, segmentsText } from "./format.js";

export const GEOMETRY = Object.freeze({
  /* Room above a plot for the unit title. */
  PAD_TOP: 28,
  /* Room left of a plot for the tick values. */
  PAD_LEFT: 64,
  /* Room right of a plot, so the last tick value is not cut. */
  PAD_RIGHT: 24,
  /* From the plot's bottom edge to the middle of the x tick values. */
  AXIS_GAP: 16,
  /* Room under the x tick values for the axis title. */
  AXIS_BELOW: 24,
  TICK_LENGTH: 4,
  /* Space between a mark and its label. */
  LABEL_GAP: 8,
  /* The accent dot and its ring, and a printed point. */
  DOT_RADIUS: 4,
  RING_WIDTH: 2,
  HALF: 0.5,
  /* Pixel coordinates are written to two places. */
  COORD_DECIMALS: 2,
  /* A bar inside a table row or a bar chart. A step narrower than SMALL_STEP
   * px is drawn as a circle. */
  BAR_THICKNESS: 14,
  SMALL_STEP: 4,
  SMALL_RADIUS: 2.5,
  OUTLINE_INSET: 0.75,
  /* The 2px --bg gap between two stacked segments. */
  SEGMENT_GAP: 2,
  /* About this many tick intervals on each axis. */
  Y_TICKS: 5,
  X_TICKS: 5,
  /* Below this width a bar chart sets each label above its bar. */
  NARROW_WIDTH: 600,
  /* A bar chart's row, wide and narrow, its label column, its group heading,
   * and the room right of the longest bar for the value written there. */
  ROW: 30,
  ROW_NARROW: 44,
  LABEL_COLUMN: 220,
  /* The label column's share of a chart's width, up to LABEL_COLUMN. */
  LABEL_SHARE: 0.32,
  GROUP_HEAD: 30,
  VALUE_ROOM: 112,
  /* Room per character of a label in the caption size, a little over the
   * glyph, so a label measured this way ends where it is drawn. */
  CHAR: 7,
  /* A line chart's plot. */
  LINE_HEIGHT: 260,
  LINE_HEIGHT_NARROW: 200,
  /* The readout's distance from the pointer. */
  TOOLTIP_OFFSET: 14,
});

/* The mantissas of decimal notation, a fact about how numbers are written. */
const TICK_LADDER = Object.freeze([1, 2, 5, 10]);

/* The SVG namespace, read from an element the parser made, so this file holds
 * no URL. */
let svgNamespace = null;
function svgNs() {
  if (svgNamespace === null) {
    const holder = document.createElement("div");
    holder.innerHTML = "<svg></svg>";
    svgNamespace = holder.firstChild.namespaceURI;
  }
  return svgNamespace;
}

let idCounter = 0;
/** A document unique id for a title or desc. */
export function uid(prefix) {
  idCounter += 1;
  return prefix + "-" + String(idCounter);
}

/** An SVG element with attributes. null and undefined attributes are skipped. */
export function svgEl(tag, attrs, text) {
  const node = document.createElementNS(svgNs(), tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined) continue;
    node.setAttribute(name, String(value));
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

/** A coordinate as an attribute string. */
export function px(value) {
  return value.toFixed(GEOMETRY.COORD_DECIMALS);
}

/** Missing is null, undefined, NaN or an infinity, and never zero. */
export function present(value) {
  return typeof value === "number" && Number.isFinite(value);
}

/** A root svg that is an image with a title and a description: role img,
 *  aria-labelledby naming both. */
export function imageSvg({ width, height, title, desc, className, viewBox }) {
  const titleId = uid("chart-title");
  const descId = uid("chart-desc");
  const svg = svgEl("svg", {
    class: className ? "chart " + className : "chart",
    width,
    height,
    viewBox: viewBox || [0, 0, width, height].join(" "),
    role: "img",
    "aria-labelledby": titleId + " " + descId,
    focusable: "false",
  });
  svg.appendChild(svgEl("title", { id: titleId }, title));
  svg.appendChild(svgEl("desc", { id: descId }, desc));
  return svg;
}

/** A decorative svg whose values are all printed beside it. */
export function hiddenSvg({ width, height, className }) {
  return svgEl("svg", {
    class: className ? "chart " + className : "chart",
    width,
    height,
    viewBox: [0, 0, width, height].join(" "),
    "aria-hidden": "true",
    focusable: "false",
  });
}

/** A linear map from a domain that came from an artifact to pixels. */
export function linear(domainLow, domainHigh, rangeLow, rangeHigh) {
  const span = domainHigh - domainLow;
  const map = (value) => (span === 0 ? rangeLow : rangeLow + ((value - domainLow) / span) * (rangeHigh - rangeLow));
  map.domain = [domainLow, domainHigh];
  map.range = [rangeLow, rangeHigh];
  return map;
}

function powerOfTenBelow(value) {
  return Math.pow(TICK_LADDER[TICK_LADDER.length - 1], Math.floor(Math.log10(value)));
}

/** The round step for about `count` intervals across a span. */
export function tickStep(low, high, count) {
  if (!(high > low) || !(count > 0)) return 0;
  const rough = (high - low) / count;
  const magnitude = powerOfTenBelow(rough);
  for (const rung of TICK_LADDER) {
    if (magnitude * rung >= rough) return magnitude * rung;
  }
  return magnitude * TICK_LADDER[TICK_LADDER.length - 1];
}

/** A domain widened to round ticks, zero kept inside when asked. */
export function niceDomain(values, count, keepZero) {
  const finite = values.filter(present);
  let low = finite.length ? Math.min(...finite) : 0;
  let high = finite.length ? Math.max(...finite) : 0;
  if (keepZero) {
    low = Math.min(low, 0);
    high = Math.max(high, 0);
  }
  if (high === low) high = low + 1;
  const step = tickStep(low, high, count);
  return { low: Math.floor(low / step) * step, high: Math.ceil(high / step) * step, step };
}

/** Tick values across a domain on a step. */
export function tickValues(low, high, step) {
  if (!(step > 0)) return [low];
  const places = stepPlaces(step);
  const out = [];
  for (let k = Math.ceil(low / step - Number.EPSILON); k * step <= high + step * Number.EPSILON; k += 1) {
    out.push(Number((k * step).toFixed(places)));
  }
  return out;
}

/** A tick label with as many places as the step needs and no more, thousands
 *  grouped. */
export function tickLabel(value, step) {
  return formatNumber(value, "tick", { tick: stepPlaces(step) }, { context: "table" });
}

function stepPlaces(step) {
  return step > 0 && step < 1 ? Math.ceil(-Math.log10(step) - Number.EPSILON) : 0;
}

/** Redraw on a width change, never scale a viewBox. A zero width means the
 *  node is not laid out yet, for example inside a section that is still
 *  closed; the observer fires again when it is. Returns a function that stops
 *  watching. */
export function onWidthChange(node, draw) {
  let last = 0;
  const run = () => {
    const width = node.clientWidth;
    if (width === 0 || width === last) return;
    last = width;
    draw(width);
  };
  if (typeof ResizeObserver === "function") {
    // The redraw changes the node's height, so it waits for the next frame
    // rather than running inside the observer's own notification.
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(run);
    });
    observer.observe(node);
    run();
    return () => observer.disconnect();
  }
  window.addEventListener("resize", run, { passive: true });
  run();
  return () => window.removeEventListener("resize", run);
}

/** A text label with a --bg halo, so it reads where it crosses a line. */
export function haloText(group, attrs, text) {
  group.appendChild(svgEl("text", { ...attrs, class: (attrs.class || "") + " halo" }, text));
  return group.appendChild(svgEl("text", attrs, text));
}

/** Vertical gridlines and tick values under a horizontal plot. */
function bottomAxis(svg, xOf, low, high, step, top, bottom, title, width) {
  const g = GEOMETRY;
  for (const value of tickValues(low, high, step)) {
    const x = xOf(value);
    svg.appendChild(svgEl("line", { class: value === 0 ? "mark-context" : "mark-grid", x1: px(x), x2: px(x), y1: px(top), y2: px(bottom) }));
    svg.appendChild(svgEl("text", { class: "tick", x: px(x), y: px(bottom + g.AXIS_GAP), "text-anchor": "middle", "dominant-baseline": "middle" }, tickLabel(value, step)));
  }
  if (title) {
    svg.appendChild(svgEl("text", { class: "chart-axis-title", x: px(width), y: px(bottom + g.AXIS_GAP + g.AXIS_BELOW), "text-anchor": "end" }, title));
  }
}

/* ============================================================ tooltip === */

/** The readout of a chart. `regions` are boxes in the svg's own units, each
 *  with the lines it shows: [{ x, y, w, h, lines: [string] }]. A pointer over
 *  a box shows its lines; with the chart focused, the arrow keys step through
 *  the boxes in order and Escape hides the readout. The same values are always
 *  in a table under the chart, so nothing is only here. */
export function tooltip(frame, svg, regions) {
  const box = document.createElement("div");
  box.className = "chart-tooltip";
  box.hidden = true;
  box.setAttribute("aria-hidden", "true");
  frame.appendChild(box);
  if (!regions.length) return;
  svg.tabIndex = 0;
  svg.setAttribute("focusable", "true");
  let index = -1;

  const scale = () => {
    const rect = svg.getBoundingClientRect();
    const view = svg.viewBox.baseVal;
    const width = view && view.width ? view.width : rect.width;
    return { rect, k: rect.width / width, x0: view ? view.x : 0, y0: view ? view.y : 0 };
  };
  const show = (region, clientX, clientY) => {
    box.replaceChildren(...region.lines.map((line, at) => {
      const p = document.createElement("p");
      p.className = at === 0 ? "chart-tooltip__head" : "chart-tooltip__line";
      p.textContent = line;
      return p;
    }));
    box.hidden = false;
    const frameRect = frame.getBoundingClientRect();
    const { rect, k, x0, y0 } = scale();
    const anchorX = clientX === undefined ? rect.left + (region.x - x0 + region.w) * k : clientX;
    const anchorY = clientY === undefined ? rect.top + (region.y - y0) * k : clientY;
    let left = anchorX - frameRect.left + GEOMETRY.TOOLTIP_OFFSET;
    const top = anchorY - frameRect.top + GEOMETRY.TOOLTIP_OFFSET;
    if (left + box.offsetWidth > frame.clientWidth) left = Math.max(anchorX - frameRect.left - box.offsetWidth - GEOMETRY.TOOLTIP_OFFSET, 0);
    box.style.left = px(left) + "px";
    box.style.top = px(top) + "px";
  };
  const hide = () => {
    box.hidden = true;
  };
  const find = (clientX, clientY) => {
    const { rect, k, x0, y0 } = scale();
    const x = (clientX - rect.left) / k + x0;
    const y = (clientY - rect.top) / k + y0;
    return regions.findIndex((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
  };
  svg.addEventListener("pointermove", (ev) => {
    const at = find(ev.clientX, ev.clientY);
    if (at < 0) {
      hide();
      return;
    }
    index = at;
    show(regions[at], ev.clientX, ev.clientY);
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", (ev) => {
    const forward = ev.key === "ArrowDown" || ev.key === "ArrowRight";
    const back = ev.key === "ArrowUp" || ev.key === "ArrowLeft";
    if (ev.key === "Escape") {
      hide();
      return;
    }
    if (!forward && !back) return;
    ev.preventDefault();
    index = forward ? (index + 1) % regions.length : (index - 1 + regions.length) % regions.length;
    show(regions[index]);
  });
}

/* ========================================================= bridge bar === */

/** One row's bar in the bridge table, at the size of its cell.
 *
 *    row       { kind: "total" | "deduction" | "cost", from_usd, to_usd,
 *                family, accent }
 *    previous  the row before it, or null, for the connector
 *    isLast    no connector below the last row
 *    scale     [low, high] from the artifact, zero inside
 *    enter     the bar grows from its running total, after `delay` ms
 *
 *  A total in ink, or the accent where the artifact marks it; a deduction an
 *  ink outline; a cost filled in its family's colour. A step under SMALL_STEP
 *  px is a dot, so a small cost is never drawn as nothing. */
export function bridgeBar({ width, height, row, previous, isLast, scale, enter, delay }) {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width, height, className: "chart--bar" });
  const inset = g.SMALL_RADIUS + g.RING_WIDTH;
  const xOf = linear(scale[0], scale[1], inset, Math.max(width - inset, inset));
  const barTop = (height - g.BAR_THICKNESS) * g.HALF;
  const barBottom = barTop + g.BAR_THICKNESS;
  const middle = (barTop + barBottom) * g.HALF;

  const zero = xOf(0);
  svg.appendChild(svgEl("line", { class: "mark-context", x1: px(zero), x2: px(zero), y1: 0, y2: height }));
  if (previous && present(previous.to_usd)) {
    const x = xOf(previous.to_usd);
    svg.appendChild(svgEl("line", { class: "mark-connector", x1: px(x), x2: px(x), y1: 0, y2: px(barTop) }));
  }
  if (!isLast && present(row.to_usd)) {
    const x = xOf(row.to_usd);
    svg.appendChild(svgEl("line", { class: "mark-connector", x1: px(x), x2: px(x), y1: px(barBottom), y2: height }));
  }
  if (!present(row.from_usd) || !present(row.to_usd)) return svg;

  const from = xOf(Math.min(row.from_usd, row.to_usd));
  const to = xOf(Math.max(row.from_usd, row.to_usd));
  const falling = row.to_usd < row.from_usd;
  let className;
  if (row.kind === "total") className = row.accent ? "mark-accent-bar" : "mark-series-fill";
  else if (row.kind === "deduction") className = "mark-negative";
  else className = "mark-family mark-family--" + row.family;
  if (to - from < g.SMALL_STEP) {
    if (row.from_usd === row.to_usd) return svg;
    svg.appendChild(svgEl("circle", { class: className === "mark-negative" ? "mark-negative" : className, cx: px(xOf(row.to_usd)), cy: px(middle), r: g.SMALL_RADIUS }));
    return svg;
  }
  const outline = row.kind === "deduction";
  const rect = svgEl("rect", {
    class: className + (enter ? " is-entering" : ""),
    x: px(outline ? from + g.OUTLINE_INSET : from),
    y: px(outline ? barTop + g.OUTLINE_INSET : barTop),
    width: px(Math.max(outline ? to - from - g.OUTLINE_INSET - g.OUTLINE_INSET : to - from, 0)),
    height: px(outline ? g.BAR_THICKNESS - g.OUTLINE_INSET - g.OUTLINE_INSET : g.BAR_THICKNESS),
  });
  if (enter) {
    // Grows from the running total it starts at: a cost from its right end,
    // the freight and the result from zero.
    rect.style.transformOrigin = falling ? "right center" : "left center";
    rect.style.animationDelay = String(delay || 0) + "ms";
  }
  svg.appendChild(rect);
  return svg;
}

/* ========================================================== bar chart === */

/** Horizontal bars by category.
 *
 *    rows     [{ id, label, group, segments: [{ value, family | className }],
 *               valueText, tip: [lines] }]
 *             A row's segments stack from zero in the order given; a row
 *             whose first segment is null has no bar and shows its valueText
 *             (the reason) where the bar would be.
 *    domain   { low, high, step } or null to fit the rows
 *    words    { title, desc, axis }
 *
 *  Wide, the label sits in a column left of the bar; narrow, above it. A
 *  group starts with its name in a heading row. The value is written right of
 *  the bar's end, in the label's ink, never in the bar's colour. */
export function barChart({ width, rows, domain, words }) {
  const g = GEOMETRY;
  const narrow = width < g.NARROW_WIDTH;
  const totals = rows.map((row) => (row.segments || []).reduce((sum, s) => sum + (present(s.value) ? s.value : 0), 0));
  const negatives = rows.map((row) => (row.segments || []).reduce((sum, s) => sum + (present(s.value) && s.value < 0 ? s.value : 0), 0));
  const fit = domain || niceDomain([...totals, ...negatives], g.X_TICKS, true);
  const labelColumn = narrow ? 0 : Math.min(g.LABEL_COLUMN, width * g.LABEL_SHARE);
  const left = labelColumn + (narrow ? g.SMALL_RADIUS : g.LABEL_GAP);
  const right = Math.max(width - g.VALUE_ROOM, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;

  // Lay the rows out first: a heading row wherever the group changes.
  const layout = [];
  let y = g.LABEL_GAP;
  let group = null;
  rows.forEach((row, index) => {
    if (row.group && row.group !== group) {
      group = row.group;
      layout.push({ kind: "group", text: row.group, y: y + g.GROUP_HEAD - g.LABEL_GAP });
      y += g.GROUP_HEAD;
    }
    layout.push({ kind: "row", row, index, y });
    y += rowHeight;
  });
  const plotBottom = y;
  const height = plotBottom + g.AXIS_GAP + g.AXIS_BELOW + g.LABEL_GAP;
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--bars" });
  bottomAxis(svg, xOf, fit.low, fit.high, fit.step, 0, plotBottom, words.axis, width);

  const regions = [];
  for (const item of layout) {
    if (item.kind === "group") {
      svg.appendChild(svgEl("text", { class: "chart-group", x: 0, y: px(item.y) }, item.text));
      continue;
    }
    const { row } = item;
    const barTop = narrow ? item.y + rowHeight - g.BAR_THICKNESS - g.LABEL_GAP : item.y + (rowHeight - g.BAR_THICKNESS) * g.HALF;
    const labelY = narrow ? barTop - g.LABEL_GAP * g.HALF : barTop + g.BAR_THICKNESS * g.HALF;
    svg.appendChild(svgEl("text", {
      class: "chart-label",
      x: px(narrow ? 0 : labelColumn),
      y: px(labelY),
      "text-anchor": narrow ? "start" : "end",
      "dominant-baseline": narrow ? "auto" : "middle",
    }, row.label));
    let positive = 0;
    let negative = 0;
    let end = xOf(0);
    const segments = (row.segments || []).filter((s) => present(s.value) && s.value !== 0);
    segments.forEach((segment, at) => {
      const start = segment.value >= 0 ? positive : negative;
      const stop = start + segment.value;
      if (segment.value >= 0) positive = stop;
      else negative = stop;
      const x0 = xOf(Math.min(start, stop));
      const x1 = xOf(Math.max(start, stop));
      // A 2px gap of the ground between two stacked segments.
      const gap = at > 0 && segment.value >= 0 ? g.SEGMENT_GAP : 0;
      const className = segment.className || (segment.family ? "mark-family mark-family--" + segment.family : "mark-series-fill");
      if (x1 - x0 - gap < g.SMALL_STEP) {
        svg.appendChild(svgEl("circle", { class: className, cx: px(segment.value >= 0 ? x1 : x0), cy: px(barTop + g.BAR_THICKNESS * g.HALF), r: g.SMALL_RADIUS }));
      } else {
        svg.appendChild(svgEl("rect", { class: className, x: px(x0 + gap), y: px(barTop), width: px(x1 - x0 - gap), height: g.BAR_THICKNESS }));
      }
      end = Math.max(end, x1);
    });
    if (row.valueText) {
      svg.appendChild(svgEl("text", {
        class: segments.length ? "chart-value" : "chart-label--context",
        x: px((segments.length ? end : xOf(0)) + g.LABEL_GAP),
        y: px(barTop + g.BAR_THICKNESS * g.HALF),
        "dominant-baseline": "middle",
      }, row.valueText));
    }
    regions.push({ x: 0, y: item.y, w: width, h: rowHeight, lines: row.tip || [row.label, row.valueText || ""] });
  }
  return { svg, regions };
}

/* ========================================================== dot chart === */

/** Dots on one horizontal axis by category, with an optional span between two
 *  values drawn as a rule and labelled.
 *
 *    rows    [{ id, label, group, dots: [{ value, className, text }],
 *               span: { from, to, text } | null, tip: [lines] }]
 *    domain  { low, high, step } or null to fit the dots
 *    words   { title, desc, axis }
 *
 *  A dot is ringed in the ground so dots that touch stay apart. */
export function dotChart({ width, rows, domain, words, keepZero }) {
  const g = GEOMETRY;
  const narrow = width < g.NARROW_WIDTH;
  const values = rows.flatMap((row) => row.dots.map((dot) => dot.value));
  const fit = domain || niceDomain(values, g.X_TICKS, keepZero === true);
  const labelColumn = narrow ? 0 : Math.min(g.LABEL_COLUMN, width * g.LABEL_SHARE);
  const left = labelColumn + g.LABEL_GAP + g.DOT_RADIUS;
  const right = Math.max(width - g.PAD_RIGHT - g.DOT_RADIUS, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;

  const layout = [];
  let y = g.LABEL_GAP;
  let group = null;
  rows.forEach((row) => {
    if (row.group && row.group !== group) {
      group = row.group;
      layout.push({ kind: "group", text: row.group, y: y + g.GROUP_HEAD - g.LABEL_GAP });
      y += g.GROUP_HEAD;
    }
    layout.push({ kind: "row", row, y });
    y += rowHeight;
  });
  const plotBottom = y;
  const height = plotBottom + g.AXIS_GAP + g.AXIS_BELOW + g.LABEL_GAP;
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--dots" });
  bottomAxis(svg, xOf, fit.low, fit.high, fit.step, 0, plotBottom, words.axis, width);

  const regions = [];
  for (const item of layout) {
    if (item.kind === "group") {
      svg.appendChild(svgEl("text", { class: "chart-group", x: 0, y: px(item.y) }, item.text));
      continue;
    }
    const { row } = item;
    const middle = narrow ? item.y + rowHeight - g.DOT_RADIUS - g.LABEL_GAP : item.y + rowHeight * g.HALF;
    svg.appendChild(svgEl("line", { class: "mark-grid", x1: px(left), x2: px(right), y1: px(middle), y2: px(middle) }));
    svg.appendChild(svgEl("text", {
      class: "chart-label",
      x: px(narrow ? 0 : labelColumn),
      y: px(narrow ? middle - g.DOT_RADIUS - g.LABEL_GAP : middle),
      "text-anchor": narrow ? "start" : "end",
      "dominant-baseline": narrow ? "auto" : "middle",
    }, row.label));
    if (row.span && present(row.span.from) && present(row.span.to)) {
      svg.appendChild(svgEl("line", { class: "mark-span", x1: px(xOf(row.span.from)), x2: px(xOf(row.span.to)), y1: px(middle), y2: px(middle) }));
    }
    for (const dot of row.dots) {
      if (!present(dot.value)) continue;
      svg.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(xOf(dot.value)), cy: px(middle), r: g.DOT_RADIUS + g.RING_WIDTH }));
      svg.appendChild(svgEl("circle", { class: dot.className || "mark-series-fill", cx: px(xOf(dot.value)), cy: px(middle), r: g.DOT_RADIUS }));
    }
    regions.push({ x: 0, y: item.y, w: width, h: rowHeight, lines: row.tip || [row.label] });
  }
  return { svg, regions };
}

/* ============================================================ tornado === */

/** The TCE with one input lower and higher, a row per input, the widest
 *  first. Each bar runs from the base TCE to the TCE with the input changed:
 *  outlined for the lower case, filled for the higher one, so the two read
 *  apart without colour. The base TCE is a vertical rule.
 *
 *    rows   [{ label, low, high, lowText, highText, tip }]: TCEs in USD a day
 *    base   the TCE at the inputs as entered
 *    words  { title, desc, axis } */
export function tornadoChart({ width, rows, base, words }) {
  const g = GEOMETRY;
  const narrow = width < g.NARROW_WIDTH;
  const values = rows.flatMap((row) => [row.low, row.high]).concat([base]);
  const fit = niceDomain(values, g.X_TICKS, false);
  const labelColumn = narrow ? 0 : Math.min(g.LABEL_COLUMN, width * g.LABEL_SHARE);
  const left = labelColumn + g.LABEL_GAP + g.VALUE_ROOM * g.HALF;
  const right = Math.max(width - g.VALUE_ROOM * g.HALF, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;
  const plotBottom = g.LABEL_GAP + rows.length * rowHeight;
  const height = plotBottom + g.AXIS_GAP + g.AXIS_BELOW + g.LABEL_GAP;
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--tornado" });
  bottomAxis(svg, xOf, fit.low, fit.high, fit.step, 0, plotBottom, words.axis, width);
  const regions = [];
  const rowLabels = [];
  rows.forEach((row, index) => {
    const top = g.LABEL_GAP + index * rowHeight;
    const barTop = narrow ? top + rowHeight - g.BAR_THICKNESS - g.LABEL_GAP : top + (rowHeight - g.BAR_THICKNESS) * g.HALF;
    const middle = barTop + g.BAR_THICKNESS * g.HALF;
    rowLabels.push({ x: narrow ? 0 : labelColumn, y: narrow ? barTop - g.LABEL_GAP * g.HALF : middle, narrow, text: row.label });
    for (const side of [{ value: row.low, text: row.lowText, className: "mark-negative" }, { value: row.high, text: row.highText, className: "mark-series-fill" }]) {
      if (!present(side.value)) continue;
      const x0 = xOf(Math.min(base, side.value));
      const x1 = xOf(Math.max(base, side.value));
      const outline = side.className === "mark-negative";
      if (x1 - x0 >= g.SMALL_STEP) {
        svg.appendChild(svgEl("rect", {
          class: side.className,
          x: px(outline ? x0 + g.OUTLINE_INSET : x0),
          y: px(outline ? barTop + g.OUTLINE_INSET : barTop),
          width: px(Math.max(outline ? x1 - x0 - g.OUTLINE_INSET - g.OUTLINE_INSET : x1 - x0, 0)),
          height: px(outline ? g.BAR_THICKNESS - g.OUTLINE_INSET - g.OUTLINE_INSET : g.BAR_THICKNESS),
        }));
      } else if (side.value !== base) {
        svg.appendChild(svgEl("circle", { class: side.className, cx: px(xOf(side.value)), cy: px(middle), r: g.SMALL_RADIUS }));
      }
      if (side.text) {
        const toLeft = side.value < base;
        svg.appendChild(svgEl("text", {
          class: "chart-value",
          x: px(toLeft ? x0 - g.LABEL_GAP * g.HALF : x1 + g.LABEL_GAP * g.HALF),
          y: px(middle),
          "text-anchor": toLeft ? "end" : "start",
          "dominant-baseline": "middle",
        }, side.text));
      }
    }
    regions.push({ x: 0, y: top, w: width, h: rowHeight, lines: row.tip || [row.label] });
  });
  const x = xOf(base);
  svg.appendChild(svgEl("line", { class: "mark-accent-rule", x1: px(x), x2: px(x), y1: 0, y2: px(plotBottom) }));
  // The labels last, with a halo of the ground, so a label read on a phone,
  // above its bar, stays legible where the base rule crosses it.
  for (const label of rowLabels) {
    haloText(svg, {
      class: "chart-label",
      x: px(label.x),
      y: px(label.y),
      "text-anchor": label.narrow ? "start" : "end",
      "dominant-baseline": label.narrow ? "auto" : "middle",
    }, label.text);
  }
  return { svg, regions };
}

/* ========================================================= line chart === */

/** A line over a numeric x axis, with marked points.
 *
 *    series   [{ points: [[x, y]], className }]
 *    marks    [{ x, y, className, label, below }]: a dot ringed in the ground,
 *             labelled above it (below where asked)
 *    x, y     { low, high, step } from the caller, the artifact's figures
 *    words    { title, desc, xAxis, yAxis }
 *    regions  one readout per x value, the lines given by `tipFor(x)` */
export function lineChart({ width, series, marks, x, y, words, tipFor }) {
  const g = GEOMETRY;
  const narrow = width < g.NARROW_WIDTH;
  const top = g.PAD_TOP;
  const bottom = top + (narrow ? g.LINE_HEIGHT_NARROW : g.LINE_HEIGHT);
  const height = bottom + g.AXIS_GAP + g.AXIS_BELOW + g.LABEL_GAP;
  const left = g.PAD_LEFT;
  const right = Math.max(width - g.PAD_RIGHT, left + g.PAD_LEFT);
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--line" });
  const xOf = linear(x.low, x.high, left, right);
  const yOf = linear(y.low, y.high, bottom, top);

  for (const value of tickValues(y.low, y.high, y.step)) {
    const at = yOf(value);
    svg.appendChild(svgEl("line", { class: "mark-grid", x1: px(left), x2: px(right), y1: px(at), y2: px(at) }));
    svg.appendChild(svgEl("text", { class: "tick", x: px(left - g.LABEL_GAP), y: px(at), "text-anchor": "end", "dominant-baseline": "middle" }, tickLabel(value, y.step)));
  }
  svg.appendChild(svgEl("text", { class: "chart-axis-title", x: 0, y: px(g.AXIS_GAP) }, words.yAxis));
  if (y.low < 0 && y.high > 0) {
    svg.appendChild(svgEl("line", { class: "mark-context", x1: px(left), x2: px(right), y1: px(yOf(0)), y2: px(yOf(0)) }));
  }
  for (const value of tickValues(x.low, x.high, x.step)) {
    const at = xOf(value);
    svg.appendChild(svgEl("line", { class: "mark-context", x1: px(at), x2: px(at), y1: px(bottom), y2: px(bottom + g.TICK_LENGTH) }));
    svg.appendChild(svgEl("text", { class: "tick", x: px(at), y: px(bottom + g.AXIS_GAP), "text-anchor": "middle", "dominant-baseline": "middle" }, tickLabel(value, x.step)));
  }
  svg.appendChild(svgEl("text", { class: "chart-axis-title", x: px(right), y: px(bottom + g.AXIS_GAP + g.AXIS_BELOW), "text-anchor": "end" }, words.xAxis));

  for (const line of series) {
    const group = svgEl("g", { class: "line " + (line.className || "") });
    let d = "";
    let open = false;
    for (const [vx, vy] of line.points) {
      if (!present(vy)) {
        open = false;
        continue;
      }
      d += (open ? "L" : "M") + px(xOf(vx)) + " " + px(yOf(vy)) + " ";
      open = true;
    }
    group.appendChild(svgEl("path", { class: "mark-series", d: d.trim() }));
    svg.appendChild(group);
  }
  for (const mark of marks || []) {
    if (!present(mark.x) || !present(mark.y)) continue;
    const cx = xOf(mark.x);
    const cy = yOf(mark.y);
    svg.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(cx), cy: px(cy), r: g.DOT_RADIUS + g.RING_WIDTH }));
    svg.appendChild(svgEl("circle", { class: mark.className || "mark-series-fill", cx: px(cx), cy: px(cy), r: g.DOT_RADIUS }));
    if (mark.label) {
      const room = mark.label.length * g.CHAR;
      const anchor = cx + room * g.HALF > right ? "end" : (cx - room * g.HALF < left ? "start" : "middle");
      const ly = mark.below ? cy + g.DOT_RADIUS + g.LABEL_GAP + g.LABEL_GAP : cy - g.DOT_RADIUS - g.LABEL_GAP;
      haloText(svg, { class: mark.className === "mark-accent-dot" ? "chart-label text-accent" : "chart-label", x: px(cx), y: px(ly), "text-anchor": anchor }, mark.label);
    }
  }

  const regions = [];
  const xs = series.length ? series[0].points.map(([vx]) => vx) : [];
  xs.forEach((vx, index) => {
    const prev = index > 0 ? xOf(xs[index - 1]) : left;
    const next = index < xs.length - 1 ? xOf(xs[index + 1]) : right;
    const at = xOf(vx);
    const x0 = index > 0 ? (prev + at) * g.HALF : left;
    const x1 = index < xs.length - 1 ? (at + next) * g.HALF : right;
    regions.push({ x: x0, y: top, w: x1 - x0, h: bottom - top, lines: tipFor ? tipFor(vx, index) : [String(vx)] });
  });
  return { svg, regions };
}

/** The plain text of a sentence of segments, for a title or desc. */
export function words(segments, decimals) {
  return segmentsText(segments || [], decimals);
}
