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
 *   tooltip     the readout a pointer, a tap or the arrow keys open on a chart
 *
 * Missing is never zero. A null ends the current line and the next value
 * starts a new one; a bar with no value is not drawn and its row says why.
 *
 * Words whose room decides the drawing (tick values, an axis title, a mark's
 * label) are measured on the page, in the face and at the size the stylesheet
 * gives their class, so an axis carries only as many values as stand apart
 * and a title wraps before it leaves the plot.
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
  LABEL_COLUMN_MAX: 340,
  /* The most of a chart's width the label column may take; beyond it the
   * labels go above their rows. */
  LABEL_SHARE: 0.42,
  GROUP_HEAD: 30,
  VALUE_ROOM: 112,
  /* Room per character of a label in the caption size, a little over the
   * glyph, so a label measured this way ends where it is drawn; and the
   * distance between two lines of a wrapped label. */
  CHAR: 7,
  LABEL_LINE: 16,
  /* A line chart's plot. */
  LINE_HEIGHT: 260,
  LINE_HEIGHT_NARROW: 200,
  /* The readout's distance from the pointer. */
  TOOLTIP_OFFSET: 14,
  /* A label's reach above and below its baseline in the meta size, and the
   * margin of the ground plate under a label set above its row. */
  LABEL_ASCENT: 11,
  LABEL_DESCENT: 4,
  PLATE_PAD: 2,
});

/* How far a dot and its ring of the ground reach from its centre. */
const DOT_REACH = GEOMETRY.DOT_RADIUS + GEOMETRY.RING_WIDTH;
/* Two dots this far apart, centre to centre, both show whole with the ring
 * between them: a dot's width and its ring. Dots of one row nearer than this
 * are stacked, this far apart, above and below the row's rule. */
const DOT_STEP = GEOMETRY.DOT_RADIUS + GEOMETRY.DOT_RADIUS + GEOMETRY.RING_WIDTH;
/* A label's box, from its reach above the baseline to its reach below. */
const LABEL_HEIGHT = GEOMETRY.LABEL_ASCENT + GEOMETRY.LABEL_DESCENT;

/** A plate of the ground under a label set above its row, so no gridline or
 *  rule runs through the label: the halo, the size of the label's box. */
function plate(group, x, y, lines, anchor) {
  const g = GEOMETRY;
  const width = Math.max(...lines.map((line) => String(line).length)) * g.CHAR;
  const left = anchor === "end" ? x - width : x;
  group.appendChild(svgEl("rect", {
    class: "chart-plate",
    x: px(left - g.PLATE_PAD),
    y: px(y - g.LABEL_ASCENT - g.PLATE_PAD),
    width: px(width + g.PLATE_PAD + g.PLATE_PAD),
    height: px((lines.length - 1) * g.LABEL_LINE + g.LABEL_ASCENT + g.LABEL_DESCENT + g.PLATE_PAD + g.PLATE_PAD),
  }));
}

/** Whether the segment from p to q enters the box (Liang and Barsky). */
function segmentCrosses(box, p, q) {
  let enter = 0;
  let leave = 1;
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  for (const [step, room] of [[-dx, p.x - box.left], [dx, box.right - p.x], [-dy, p.y - box.top], [dy, box.bottom - p.y]]) {
    if (step === 0) {
      if (room < 0) return false;
      continue;
    }
    const t = room / step;
    if (step < 0) {
      if (t > leave) return false;
      if (t > enter) enter = t;
    } else {
      if (t < enter) return false;
      if (t < leave) leave = t;
    }
  }
  return enter <= leave;
}

/** Whether two boxes overlap. */
function overlaps(a, b) {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

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
 *  closed; the observer fires again when it is. A face still loading when the
 *  chart is drawn draws it again once it has arrived, since its words were
 *  measured in the face standing in for it. Returns a function that stops
 *  watching. */
export function onWidthChange(node, draw) {
  let last = 0;
  let waiting = false;
  const run = () => {
    const width = node.clientWidth;
    if (width === 0 || width === last) return;
    last = width;
    draw(width);
    if (!waiting && document.fonts && document.fonts.status === "loading") {
      waiting = true;
      document.fonts.ready.then(() => {
        waiting = false;
        last = 0;
        run();
      });
    }
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

/* ============================================================ measure === */

/* The hidden svg on the page that chart words are measured in. */
let ruler = null;

/** The width in px of `text` set in a chart text class, measured on the page
 *  in the face and at the size the stylesheet gives the class; CHAR a
 *  character where the page cannot measure it. */
function textWidth(className, text) {
  const words = String(text);
  const estimate = words.length * GEOMETRY.CHAR;
  if (typeof document === "undefined" || !document.body) return estimate;
  if (!ruler || !ruler.isConnected) {
    ruler = svgEl("svg", {
      class: "chart",
      width: 0,
      height: 0,
      "aria-hidden": "true",
      focusable: "false",
      style: "position: absolute; visibility: hidden; pointer-events: none",
    });
    document.body.appendChild(ruler);
  }
  const node = ruler.appendChild(svgEl("text", { class: className }, words));
  const width = node.getComputedTextLength();
  node.remove();
  return width > 0 ? width : estimate;
}

/** Words wrapped into lines no wider than `room` px in a chart text class; a
 *  word wider than that keeps a line of its own. */
function wrapToWidth(className, text, room) {
  const lines = [];
  let line = "";
  for (const word of String(text || "").split(" ")) {
    const next = line ? line + " " + word : word;
    if (line && textWidth(className, next) > room) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/* =============================================================== axes === */

/** The next round step up the ladder from `step` across a span, or `step`
 *  itself when no coarser one leaves an interval. */
function coarserStep(low, high, step) {
  for (let count = Math.floor((high - low) / step); count >= 1; count -= 1) {
    const next = tickStep(low, high, count);
    if (next > step) return next;
  }
  return step;
}

/** The values of a horizontal axis, each with its label and where the label
 *  is set: on the given step, or the next coarser one on the ladder until no
 *  two labels, each as wide as it is drawn, come within LABEL_GAP of each
 *  other. A label too wide to centre on the first or last tick is set inside
 *  the chart from it. Returns [{ value, label, x, anchor }]. */
function horizontalTicks(xOf, low, high, step, width) {
  const g = GEOMETRY;
  let current = step;
  for (;;) {
    const ticks = tickValues(low, high, current).map((value) => {
      const label = tickLabel(value, current);
      const size = textWidth("tick", label);
      const at = xOf(value);
      if (at - size * g.HALF < 0) {
        const from = Math.max(at, 0);
        return { value, label, x: from, anchor: "start", from, to: from + size };
      }
      if (at + size * g.HALF > width) return { value, label, x: at, anchor: "end", from: at - size, to: at };
      return { value, label, x: at, anchor: "middle", from: at - size * g.HALF, to: at + size * g.HALF };
    });
    const apart = ticks.every((tick, at) => at === 0 || tick.from - ticks[at - 1].to >= g.LABEL_GAP);
    const next = apart ? current : coarserStep(low, high, current);
    if (next === current) return ticks;
    current = next;
  }
}

/** The step of a vertical axis: the given one, or the next coarser one on the
 *  ladder until two neighbouring values stand a label's height apart. */
function verticalStep(yOf, low, high, step) {
  let current = step;
  while (Math.abs(yOf(low + current) - yOf(low)) < LABEL_HEIGHT) {
    const next = coarserStep(low, high, current);
    if (next === current) break;
    current = next;
  }
  return current;
}

/** An axis title in the lines it needs to stay over the plot, from the plot's
 *  left edge to `right`, where each line is set right aligned. */
function axisTitleLines(title, left, right) {
  return title ? wrapToWidth("chart-axis-title", title, right - left) : [];
}

/** The axis title's lines, right aligned at `x`, the first on `y`. */
function axisTitle(svg, lines, x, y) {
  if (!lines.length) return;
  const text = svgEl("text", { class: "chart-axis-title", x: px(x), y: px(y), "text-anchor": "end" });
  lines.forEach((line, at) => {
    text.appendChild(svgEl("tspan", { x: px(x), dy: at === 0 ? null : px(GEOMETRY.LABEL_LINE) }, line));
  });
  svg.appendChild(text);
}

/** The room under a horizontal plot for its tick values and its title. */
function axisRoom(lines) {
  const g = GEOMETRY;
  return g.AXIS_GAP + g.AXIS_BELOW + g.LABEL_GAP + Math.max(lines.length - 1, 0) * g.LABEL_LINE;
}

/** Vertical gridlines and tick values under a horizontal plot, and the axis
 *  title's lines under them. The gridline at zero is the darker rule, unless
 *  the chart draws its own (`rule` false). */
function bottomAxis(svg, xOf, fit, { top, bottom, width, title, rule }) {
  const g = GEOMETRY;
  for (const tick of horizontalTicks(xOf, fit.low, fit.high, fit.step, width)) {
    const x = xOf(tick.value);
    if (tick.value !== 0 || rule !== false) {
      svg.appendChild(svgEl("line", { class: tick.value === 0 ? "mark-context" : "mark-grid", x1: px(x), x2: px(x), y1: px(top), y2: px(bottom) }));
    }
    svg.appendChild(svgEl("text", { class: "tick", x: px(tick.x), y: px(bottom + g.AXIS_GAP), "text-anchor": tick.anchor, "dominant-baseline": "middle" }, tick.label));
  }
  axisTitle(svg, title, width, bottom + g.AXIS_GAP + g.AXIS_BELOW);
}

/** Where a horizontal chart sets its row labels: in a column left of the
 *  marks, as wide as the longest label needs, or, when that column would take
 *  more than LABEL_SHARE of the width or the chart is narrow, above each row.
 *  Returns { narrow, labelColumn }. */
export function labelLayout(width, labels) {
  const g = GEOMETRY;
  const longest = Math.max(0, ...labels.map((label) => String(label || "").length));
  const needed = longest * g.CHAR + g.LABEL_GAP;
  if (width < g.NARROW_WIDTH || needed > width * g.LABEL_SHARE) return { narrow: true, labelColumn: 0 };
  return { narrow: false, labelColumn: Math.min(Math.max(needed, g.LABEL_GAP), g.LABEL_COLUMN_MAX) };
}

/* ============================================================ tooltip === */

/** Where a readout `w` by `h` px goes beside `anchor`, both boxes in the
 *  window's coordinates: inside the frame across, and inside the window both
 *  ways. A pointer's readout opens below and to the right of it, and turns to
 *  the left, or above, where it would pass the frame's edge or the window's
 *  foot. The keyboard's (`beside`) sits right or left of its row's marks,
 *  centred on them as far as the frame's height allows, or, with no room on
 *  either side, under them, or over them where the window ends. Returns
 *  { x, y }. */
function readoutPlace(w, h, anchor, beside, frameRect, frameWidth) {
  const g = GEOMETRY;
  const viewWidth = document.documentElement.clientWidth || window.innerWidth;
  const viewHeight = window.innerHeight;
  const minX = Math.max(frameRect.left, 0);
  const maxX = Math.min(frameRect.left + frameWidth, viewWidth);
  const across = (x) => Math.max(Math.min(x, maxX - w), minX);
  const down = (y) => Math.max(Math.min(y, viewHeight - h), 0);
  const right = anchor.right + g.TOOLTIP_OFFSET;
  const left = anchor.left - g.TOOLTIP_OFFSET - w;
  const under = anchor.bottom + g.TOOLTIP_OFFSET;
  const over = anchor.top - g.TOOLTIP_OFFSET - h;
  // Under where it fits, over where that fits, else the side with more room.
  const vertical = () => {
    if (under + h <= viewHeight) return down(under);
    if (over >= 0) return down(over);
    return down(viewHeight - under >= over + h ? under : over);
  };
  if (beside) {
    // Centred on the row, kept over the chart rather than the words round it.
    const centred = down(Math.max(Math.min((anchor.top + anchor.bottom - h) * g.HALF, frameRect.bottom - h), frameRect.top));
    if (right + w <= maxX) return { x: right, y: centred };
    if (left >= minX) return { x: left, y: centred };
    return { x: across((anchor.left + anchor.right - w) * g.HALF), y: vertical() };
  }
  return { x: across(right + w <= maxX ? right : left), y: vertical() };
}

/** The readout of a chart. `regions` are boxes in the svg's own units, each
 *  with the lines it shows and, where the chart gives it, the box its marks
 *  take: [{ x, y, w, h, mark: { x, y, w, h } | null, lines: [string] }]. A
 *  mouse over a box shows its lines. A tap (touch or pen) on a box opens them,
 *  and a second tap on the same box, or a tap outside the chart, closes them.
 *  With the chart focused, the arrow keys step through the boxes in order,
 *  each readout beside its row's marks, and Escape hides it. The same values
 *  are always in a table under the chart, so nothing is only here. */
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
  // The region a tap opened, so a second tap on it closes the readout; and
  // the kind of pointer that last went down on the chart, for a click event
  // that does not say.
  let tapped = -1;
  let pointer = "";

  const scale = () => {
    const rect = svg.getBoundingClientRect();
    const view = svg.viewBox.baseVal;
    const width = view && view.width ? view.width : rect.width;
    return { rect, k: rect.width / width, x0: view ? view.x : 0, y0: view ? view.y : 0 };
  };
  // A region's marks, or the region itself where it names none, in the
  // window's coordinates.
  const marksOf = (region) => {
    const { rect, k, x0, y0 } = scale();
    const m = region.mark || region;
    return { left: rect.left + (m.x - x0) * k, top: rect.top + (m.y - y0) * k, right: rect.left + (m.x - x0 + m.w) * k, bottom: rect.top + (m.y - y0 + m.h) * k };
  };
  // A pointer as a box of no size, in the window's coordinates.
  const pointOf = (ev) => ({ left: ev.clientX, right: ev.clientX, top: ev.clientY, bottom: ev.clientY });
  const show = (region, anchor, beside) => {
    box.replaceChildren(...region.lines.map((line, n) => {
      const p = document.createElement("p");
      p.className = n === 0 ? "chart-tooltip__head" : "chart-tooltip__line";
      p.textContent = line;
      return p;
    }));
    box.hidden = false;
    // Measured at the frame's left edge, where it has the frame's whole width
    // to take, then placed.
    box.style.left = px(0) + "px";
    box.style.top = px(0) + "px";
    const frameRect = frame.getBoundingClientRect();
    const place = readoutPlace(box.offsetWidth, box.offsetHeight, anchor, beside, frameRect, frame.clientWidth);
    box.style.left = px(place.x - frameRect.left) + "px";
    box.style.top = px(place.y - frameRect.top) + "px";
  };
  const outside = (ev) => {
    if (!svg.contains(ev.target)) hide();
  };
  const hide = () => {
    box.hidden = true;
    tapped = -1;
    document.removeEventListener("pointerdown", outside, true);
  };
  const find = (clientX, clientY) => {
    const { rect, k, x0, y0 } = scale();
    const x = (clientX - rect.left) / k + x0;
    const y = (clientY - rect.top) / k + y0;
    return regions.findIndex((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
  };
  // A finger sends no move over the chart before it touches it, and leaves
  // the chart as it lifts, so a touch, and a pen taken the same way, opens
  // the readout with a tap rather than by hovering.
  const tapping = (type) => type === "touch" || type === "pen";
  svg.addEventListener("pointermove", (ev) => {
    if (tapping(ev.pointerType)) return;
    const found = find(ev.clientX, ev.clientY);
    if (found < 0) {
      hide();
      return;
    }
    index = found;
    show(regions[found], pointOf(ev), false);
  });
  svg.addEventListener("pointerleave", (ev) => {
    if (!tapping(ev.pointerType)) hide();
  });
  svg.addEventListener("pointerdown", (ev) => {
    pointer = ev.pointerType;
  });
  svg.addEventListener("click", (ev) => {
    if (!tapping(ev.pointerType || pointer)) return;
    const found = find(ev.clientX, ev.clientY);
    if (found < 0 || found === tapped) {
      hide();
      return;
    }
    index = found;
    show(regions[found], pointOf(ev), false);
    tapped = found;
    document.addEventListener("pointerdown", outside, true);
  });
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
    tapped = -1;
    show(regions[index], marksOf(regions[index]), true);
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

/** Words wrapped into lines of at most maxChars characters; a word longer
 *  than that keeps a line of its own. */
export function wrapWords(text, maxChars) {
  const lines = [];
  let line = "";
  for (const word of String(text || "").split(" ")) {
    const next = line ? line + " " + word : word;
    if (next.length > maxChars && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines.length ? lines : [""];
}

/** Lines of text, each LABEL_LINE below the last, over a halo of the ground. */
function haloLines(group, attrs, lines) {
  for (const halo of [true, false]) {
    const text = svgEl("text", { ...attrs, class: (attrs.class || "") + (halo ? " halo" : "") });
    lines.forEach((line, at) => {
      text.appendChild(svgEl("tspan", { x: attrs.x, dy: at === 0 ? null : px(GEOMETRY.LABEL_LINE) }, line));
    });
    group.appendChild(text);
  }
}

/** The rows of a horizontal chart laid down the plot: a heading wherever the
 *  group changes, wrapped to the width, and, when narrow, each row's label
 *  wrapped above its mark. `extra(row, index)`, where given, is how much
 *  taller than the others a row must be for what it holds. Returns { layout,
 *  bottom }. */
function rowLayout(rows, width, narrow, rowHeight, extra) {
  const g = GEOMETRY;
  const maxChars = Math.max(1, Math.floor(width / g.CHAR));
  const layout = [];
  let y = g.LABEL_GAP;
  let group = null;
  rows.forEach((row, index) => {
    if (row.group && row.group !== group) {
      group = row.group;
      const lines = wrapWords(row.group, maxChars);
      layout.push({ kind: "group", lines, y: y + g.GROUP_HEAD - g.LABEL_GAP });
      y += g.GROUP_HEAD + (lines.length - 1) * g.LABEL_LINE;
    }
    const lines = narrow ? wrapWords(row.label, maxChars) : [row.label];
    const height = rowHeight + (lines.length - 1) * g.LABEL_LINE + (extra ? extra(row, index) : 0);
    layout.push({ kind: "row", row, index, y, lines, height });
    y += height;
  });
  return { layout, bottom: y };
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
  const { narrow, labelColumn } = labelLayout(width, rows.map((row) => row.label));
  const totals = rows.map((row) => (row.segments || []).reduce((sum, s) => sum + (present(s.value) ? s.value : 0), 0));
  const negatives = rows.map((row) => (row.segments || []).reduce((sum, s) => sum + (present(s.value) && s.value < 0 ? s.value : 0), 0));
  const fit = domain || niceDomain([...totals, ...negatives], g.X_TICKS, true);
  const left = labelColumn + (narrow ? g.SMALL_RADIUS : g.LABEL_GAP);
  // The plot as wide as it can be with each row's value written right of its
  // own bar inside the chart: a long value on a short bar needs no room at
  // the right of the longest one.
  let right = width - g.VALUE_ROOM;
  rows.forEach((row, at) => {
    if (!row.valueText) return;
    const need = String(row.valueText).length * g.CHAR + g.LABEL_GAP;
    const share = (Math.max(totals[at], 0) - fit.low) / (fit.high - fit.low);
    if (share > 0) right = Math.min(right, left + (width - need - left) / share);
  });
  right = Math.max(right, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;

  // Lay the rows out first: a heading row wherever the group changes.
  const { layout, bottom: plotBottom } = rowLayout(rows, width, narrow, rowHeight);
  const title = axisTitleLines(words.axis, left, width);
  const height = plotBottom + axisRoom(title);
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--bars" });
  bottomAxis(svg, xOf, fit, { top: 0, bottom: plotBottom, width, title, rule: false });
  // A row's bar: narrow, under its label, LABEL_GAP above the row's foot;
  // wide, in the middle of the row.
  const barTopOf = (item) => (narrow ? item.y + item.height - g.BAR_THICKNESS - g.LABEL_GAP : item.y + (item.height - g.BAR_THICKNESS) * g.HALF);
  // Plates of the ground under the group headings and, when narrow, under the
  // labels set above their bars: drawn over the gridlines, under every mark.
  for (const item of layout) {
    if (item.kind === "group") plate(svg, 0, item.y, item.lines, "start");
    else if (narrow) plate(svg, 0, barTopOf(item) - g.LABEL_GAP * g.HALF - (item.lines.length - 1) * g.LABEL_LINE, item.lines, "start");
  }
  // The zero rule runs beside the bars only, from the first bar of a run of
  // rows to its last, and a heading, or narrow, a label set above its bar,
  // ends the run: no piece of it shows above a heading or between two plates.
  // Narrow, each piece is the height of its own bar, and a row with no bar
  // has none.
  if (fit.low <= 0 && fit.high >= 0) {
    const zero = xOf(0);
    let run = null;
    for (const item of layout) {
      if (item.kind === "group") {
        run = null;
        continue;
      }
      if (narrow && !(item.row.segments || []).some((s) => present(s.value) && s.value !== 0)) continue;
      const top = barTopOf(item);
      if (narrow || !run) run = svg.appendChild(svgEl("line", { class: "mark-context", x1: px(zero), x2: px(zero), y1: px(top) }));
      run.setAttribute("y2", px(top + g.BAR_THICKNESS));
    }
  }

  const regions = [];
  const labelsToDraw = [];
  for (const item of layout) {
    if (item.kind === "group") {
      haloLines(svg, { class: "chart-group", x: 0, y: px(item.y) }, item.lines);
      continue;
    }
    const { row } = item;
    const barTop = barTopOf(item);
    const labelY = narrow ? barTop - g.LABEL_GAP * g.HALF - (item.lines.length - 1) * g.LABEL_LINE : barTop + g.BAR_THICKNESS * g.HALF;
    labelsToDraw.push({
      attrs: {
        class: "chart-label",
        x: px(narrow ? 0 : labelColumn),
        y: px(labelY),
        "text-anchor": narrow ? "start" : "end",
        "dominant-baseline": narrow ? "auto" : "middle",
      },
      lines: item.lines,
    });
    let positive = 0;
    let negative = 0;
    let start = xOf(0);
    let end = xOf(0);
    const segments = (row.segments || []).filter((s) => present(s.value) && s.value !== 0);
    segments.forEach((segment, at) => {
      const from = segment.value >= 0 ? positive : negative;
      const stop = from + segment.value;
      if (segment.value >= 0) positive = stop;
      else negative = stop;
      const x0 = xOf(Math.min(from, stop));
      const x1 = xOf(Math.max(from, stop));
      // A 2px gap of the ground between two stacked segments.
      const gap = at > 0 && segment.value >= 0 ? g.SEGMENT_GAP : 0;
      const className = segment.className || (segment.family ? "mark-family mark-family--" + segment.family : "mark-series-fill");
      if (x1 - x0 - gap < g.SMALL_STEP) {
        svg.appendChild(svgEl("circle", { class: className, cx: px(segment.value >= 0 ? x1 : x0), cy: px(barTop + g.BAR_THICKNESS * g.HALF), r: g.SMALL_RADIUS }));
      } else {
        svg.appendChild(svgEl("rect", { class: className, x: px(x0 + gap), y: px(barTop), width: px(x1 - x0 - gap), height: g.BAR_THICKNESS }));
      }
      start = Math.min(start, x0);
      end = Math.max(end, x1);
    });
    // The row's marks, the bar and the value written after it, for the
    // keyboard's readout to sit beside.
    let reach = end;
    if (row.valueText) {
      const valueClass = segments.length ? "chart-value" : "chart-label--context";
      const valueX = (segments.length ? end : xOf(0)) + g.LABEL_GAP;
      haloText(svg, {
        class: valueClass,
        x: px(valueX),
        y: px(barTop + g.BAR_THICKNESS * g.HALF),
        "dominant-baseline": "middle",
      }, row.valueText);
      reach = valueX + textWidth(valueClass, row.valueText);
    }
    regions.push({
      x: 0,
      y: item.y,
      w: width,
      h: item.height,
      mark: { x: start, y: barTop, w: reach - start, h: g.BAR_THICKNESS },
      lines: row.tip || [row.label, row.valueText || ""],
    });
  }
  // The labels last, each on a plate of the ground when it is set above its
  // bar, so no gridline runs through it.
  for (const label of labelsToDraw) haloLines(svg, label.attrs, label.lines);
  return { svg, regions };
}

/* ========================================================== dot chart === */

/** The first lane, the rule, then a step below it and above it, two steps
 *  and so on, where no dot already placed lies within DOT_STEP of `x`. */
function freeLane(placed, x) {
  for (let depth = 0; ; depth += 1) {
    for (const lane of depth === 0 ? [0] : [depth, -depth]) {
      if (!placed.some((other) => other.lane === lane && Math.abs(other.x - x) < DOT_STEP)) return lane;
    }
  }
}

/** A row of a dot chart, planned before the rows are laid down.
 *
 *  Each dot takes a lane, the first where it covers no dot already placed, so
 *  dots that would overlap stack a step apart and each shows whole; the
 *  span's two dots are placed first, so they keep the rule where they can.
 *  The span's label, wrapped to the plot where it is wider, takes the first
 *  place where it covers no dot and stays inside the plot: just above the
 *  rule, centred on the span's midpoint, starting at it, ending at it, or slid
 *  inside the plot; then the same over the stack. Offsets are from the rule,
 *  down positive. Returns { dots, span, label, above, below, reach, extra }:
 *  how far the row reaches above and below its rule and across, and how much
 *  taller than a row of single dots it must be. */
function dotRow(row, xOf, left, right) {
  const g = GEOMETRY;
  const span = row.span && present(row.span.from) && present(row.span.to) ? row.span : null;
  const ends = span ? [span.from, span.to] : [];
  const dots = row.dots.filter((dot) => present(dot.value)).map((dot) => ({ dot, x: xOf(dot.value), lane: 0 }));
  const placed = [];
  for (const item of [...dots.filter((d) => ends.includes(d.dot.value)), ...dots.filter((d) => !ends.includes(d.dot.value))]) {
    item.lane = freeLane(placed, item.x);
    placed.push(item);
  }
  let above = Math.max(0, ...dots.map((d) => -d.lane)) * DOT_STEP + DOT_REACH;
  const below = Math.max(0, ...dots.map((d) => d.lane)) * DOT_STEP + DOT_REACH;
  const xs = dots.map((d) => d.x).concat(span ? [xOf(span.from), xOf(span.to)] : []);
  const reach = xs.length ? { left: Math.min(...xs) - DOT_REACH, right: Math.max(...xs) + DOT_REACH } : null;

  let label = null;
  if (span && span.label && reach) {
    const lines = wrapToWidth("tick", span.label, right - left);
    const size = Math.max(...lines.map((line) => textWidth("tick", line)));
    const tall = LABEL_HEIGHT + (lines.length - 1) * g.LABEL_LINE;
    const middle = (xOf(span.from) + xOf(span.to)) * g.HALF;
    const covers = dots.map((d) => ({ left: d.x - DOT_REACH, right: d.x + DOT_REACH, top: d.lane * DOT_STEP - DOT_REACH, bottom: d.lane * DOT_STEP + DOT_REACH }));
    const starts = [middle - size * g.HALF, middle, middle - size, Math.max(Math.min(middle - size * g.HALF, right - size), left)];
    const places = [];
    // Its foot a ring's width above the rule, then on the stack's top.
    for (const foot of [-g.RING_WIDTH, -above]) {
      for (const start of starts) places.push({ left: start, right: start + size, top: foot - tall, bottom: foot });
    }
    const box = places.find((p) => p.left >= left && p.right <= right && !covers.some((c) => overlaps(c, p))) || places[places.length - 1];
    label = { lines, x: box.left, y: box.top + g.LABEL_ASCENT };
    above = Math.max(above, -box.top);
    reach.left = Math.min(reach.left, box.left);
    reach.right = Math.max(reach.right, box.right);
  }
  return { dots, span, label, above, below, reach, extra: above - DOT_REACH + below - DOT_REACH };
}

/** Dots on one horizontal axis by category, with an optional span between two
 *  values drawn as a rule.
 *
 *    rows    [{ id, label, group, dots: [{ value, className, text }],
 *               span: { from, to, text, label } | null, tip: [lines] }]
 *            A span's label, where given, is written beside its midpoint,
 *            above the rule, in the style of the tick values.
 *    domain  { low, high, step } or null to fit the dots
 *    words   { title, desc, axis }
 *
 *  A dot is ringed in the ground so dots that touch stay apart, and dots of a
 *  row that would overlap are stacked a step apart above and below its rule,
 *  the row as much taller as the stack needs. */
export function dotChart({ width, rows, domain, words, keepZero }) {
  const g = GEOMETRY;
  const { narrow, labelColumn } = labelLayout(width, rows.map((row) => row.label));
  const values = rows.flatMap((row) => row.dots.map((dot) => dot.value));
  const fit = domain || niceDomain(values, g.X_TICKS, keepZero === true);
  const left = labelColumn + g.LABEL_GAP + g.DOT_RADIUS;
  const right = Math.max(width - g.PAD_RIGHT - g.DOT_RADIUS, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;

  // Each row's dots in their lanes and its span's label in place before the
  // rows are laid down, so a row is as tall as what it holds.
  const plans = rows.map((row) => dotRow(row, xOf, left, right));
  const { layout, bottom: plotBottom } = rowLayout(rows, width, narrow, rowHeight, (row, index) => plans[index].extra);
  const title = axisTitleLines(words.axis, left, width);
  const height = plotBottom + axisRoom(title);
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--dots" });
  bottomAxis(svg, xOf, fit, { top: 0, bottom: plotBottom, width, title });

  const regions = [];
  for (const item of layout) {
    if (item.kind === "group") {
      plate(svg, 0, item.y, item.lines, "start");
      haloLines(svg, { class: "chart-group", x: 0, y: px(item.y) }, item.lines);
      continue;
    }
    const { row } = item;
    const plan = plans[item.index];
    // The row's rule: wide, with the row's top margin over whatever the row
    // holds above it; narrow, with the row's foot as far under the lowest dot
    // as under a single one, and the label above all it holds.
    const middle = narrow
      ? item.y + item.height - (plan.below - g.RING_WIDTH) - g.LABEL_GAP
      : item.y + g.ROW * g.HALF - DOT_REACH + plan.above;
    const labelY = narrow ? middle - (plan.above - g.RING_WIDTH) - g.LABEL_GAP - (item.lines.length - 1) * g.LABEL_LINE : middle;
    svg.appendChild(svgEl("line", { class: "mark-grid", x1: px(left), x2: px(right), y1: px(middle), y2: px(middle) }));
    if (narrow) plate(svg, 0, labelY, item.lines, "start");
    haloLines(svg, {
      class: "chart-label",
      x: px(narrow ? 0 : labelColumn),
      y: px(labelY),
      "text-anchor": narrow ? "start" : "end",
      "dominant-baseline": narrow ? "auto" : "middle",
    }, item.lines);
    if (plan.span) {
      svg.appendChild(svgEl("line", { class: "mark-span", x1: px(xOf(plan.span.from)), x2: px(xOf(plan.span.to)), y1: px(middle), y2: px(middle) }));
    }
    if (plan.label) haloLines(svg, { class: "tick", x: px(plan.label.x), y: px(middle + plan.label.y) }, plan.label.lines);
    // Filled dots first, each ringed in the ground, then the open dots, so a
    // ring is drawn whole over the rule.
    const open = (d) => d.dot.className === "mark-printed";
    for (const d of [...plan.dots.filter((d) => !open(d)), ...plan.dots.filter(open)]) {
      const cy = middle + d.lane * DOT_STEP;
      if (!open(d)) svg.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(d.x), cy: px(cy), r: DOT_REACH }));
      svg.appendChild(svgEl("circle", { class: d.dot.className || "mark-series-fill", cx: px(d.x), cy: px(cy), r: g.DOT_RADIUS }));
    }
    regions.push({
      x: 0,
      y: item.y,
      w: width,
      h: item.height,
      mark: plan.reach ? { x: plan.reach.left, y: middle - plan.above, w: plan.reach.right - plan.reach.left, h: plan.above + plan.below } : null,
      lines: row.tip || [row.label],
    });
  }
  return { svg, regions };
}

/* ============================================================ tornado === */

/** The TCE with one input lower and higher, a row per input, the widest
 *  first. Each bar runs from the base TCE to the TCE with the input changed:
 *  outlined for the lower case, filled for the higher one, so the two read
 *  apart without colour. The base TCE is a vertical rule.
 *
 *    rows   [{ label, low, high, lowText, highText, bothText, tip }]: TCEs in
 *           USD a day; bothText writes the two values together, for a row whose
 *           cases both fall on one side of the base
 *    base   the TCE at the inputs as entered
 *    words  { title, desc, axis } */
export function tornadoChart({ width, rows, base, words }) {
  const g = GEOMETRY;
  const { narrow, labelColumn } = labelLayout(width, rows.map((row) => row.label));
  const values = rows.flatMap((row) => [row.low, row.high]).concat([base]);
  const fit = niceDomain(values, g.X_TICKS, false);
  const left = labelColumn + g.LABEL_GAP + g.VALUE_ROOM * g.HALF;
  const right = Math.max(width - g.VALUE_ROOM * g.HALF, left + g.VALUE_ROOM);
  const xOf = linear(fit.low, fit.high, left, right);
  const rowHeight = narrow ? g.ROW_NARROW : g.ROW;
  const { layout, bottom: plotBottom } = rowLayout(rows, width, narrow, rowHeight);
  const title = axisTitleLines(words.axis, left, width);
  const height = plotBottom + axisRoom(title);
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--tornado" });
  bottomAxis(svg, xOf, fit, { top: 0, bottom: plotBottom, width, title });
  // The base rule under the bars, and a plate of the ground under each label
  // set above its row, so neither the rule nor a gridline runs through it.
  svg.appendChild(svgEl("line", { class: "mark-accent-rule", x1: px(xOf(base)), x2: px(xOf(base)), y1: 0, y2: px(plotBottom) }));
  const regions = [];
  const rowLabels = [];
  layout.forEach((item) => {
    const { row } = item;
    const top = item.y;
    const barTop = narrow ? top + item.height - g.BAR_THICKNESS - g.LABEL_GAP : top + (item.height - g.BAR_THICKNESS) * g.HALF;
    const middle = barTop + g.BAR_THICKNESS * g.HALF;
    rowLabels.push({ x: narrow ? 0 : labelColumn, y: narrow ? barTop - g.LABEL_GAP * g.HALF - (item.lines.length - 1) * g.LABEL_LINE : middle, narrow, lines: item.lines });
    if (narrow) plate(svg, 0, barTop - g.LABEL_GAP * g.HALF - (item.lines.length - 1) * g.LABEL_LINE, item.lines, "start");
    // An input that moves nothing has one side to write, not two on the same spot.
    const sides = [{ value: row.low, text: row.lowText, className: "mark-negative" }, { value: row.high, text: row.highText, className: "mark-series-fill" }];
    if (row.low === row.high) sides.pop();
    // Both cases on one side of the base (the speed round its best, say): each
    // bar takes half the thickness, the lower case's above, and one label at
    // the far end gives both values in that order, so neither covers the other.
    const oneSide = sides.length > 1 && present(row.low) && present(row.high)
      && row.low !== base && Math.sign(row.low - base) === Math.sign(row.high - base);
    const thickness = oneSide ? g.BAR_THICKNESS * g.HALF : g.BAR_THICKNESS;
    // The row's marks, its bars and the values written beside them, for the
    // keyboard's readout to sit beside.
    let reachLeft = xOf(base);
    let reachRight = xOf(base);
    sides.forEach((side, index) => {
      if (!present(side.value)) return;
      const sideTop = oneSide ? barTop + index * thickness : barTop;
      const x0 = xOf(Math.min(base, side.value));
      const x1 = xOf(Math.max(base, side.value));
      const outline = side.className === "mark-negative";
      if (x1 - x0 >= g.SMALL_STEP) {
        svg.appendChild(svgEl("rect", {
          class: side.className,
          x: px(outline ? x0 + g.OUTLINE_INSET : x0),
          y: px(outline ? sideTop + g.OUTLINE_INSET : sideTop),
          width: px(Math.max(outline ? x1 - x0 - g.OUTLINE_INSET - g.OUTLINE_INSET : x1 - x0, 0)),
          height: px(outline ? thickness - g.OUTLINE_INSET - g.OUTLINE_INSET : thickness),
        }));
      } else if (side.value !== base) {
        svg.appendChild(svgEl("circle", { class: side.className, cx: px(xOf(side.value)), cy: px(sideTop + thickness * g.HALF), r: g.SMALL_RADIUS }));
      }
      reachLeft = Math.min(reachLeft, x0);
      reachRight = Math.max(reachRight, x1);
      if (side.text && !oneSide) {
        const toLeft = side.value < base;
        const textX = toLeft ? x0 - g.LABEL_GAP * g.HALF : x1 + g.LABEL_GAP * g.HALF;
        haloText(svg, {
          class: "chart-value",
          x: px(textX),
          y: px(middle),
          "text-anchor": toLeft ? "end" : "start",
          "dominant-baseline": "middle",
        }, side.text);
        const size = textWidth("chart-value", side.text);
        if (toLeft) reachLeft = Math.min(reachLeft, textX - size);
        else reachRight = Math.max(reachRight, textX + size);
      }
    });
    const both = oneSide ? row.bothText || row.lowText : "";
    if (both) {
      const far = Math.abs(row.low - base) >= Math.abs(row.high - base) ? row.low : row.high;
      const size = textWidth("chart-value", both);
      let toLeft = far < base;
      let textX = toLeft ? xOf(far) - g.LABEL_GAP * g.HALF : xOf(far) + g.LABEL_GAP * g.HALF;
      // With no room past the far end, the label sits across the base rule.
      if (toLeft && textX - size < 0) {
        toLeft = false;
        textX = xOf(base) + g.LABEL_GAP * g.HALF;
      } else if (!toLeft && textX + size > width) {
        toLeft = true;
        textX = xOf(base) - g.LABEL_GAP * g.HALF;
      }
      haloText(svg, {
        class: "chart-value",
        x: px(textX),
        y: px(middle),
        "text-anchor": toLeft ? "end" : "start",
        "dominant-baseline": "middle",
      }, both);
      if (toLeft) reachLeft = Math.min(reachLeft, textX - size);
      else reachRight = Math.max(reachRight, textX + size);
    }
    regions.push({ x: 0, y: top, w: width, h: item.height, mark: { x: reachLeft, y: barTop, w: reachRight - reachLeft, h: g.BAR_THICKNESS }, lines: row.tip || [row.label] });
  });
  // The labels last, with a halo of the ground, so a label read on a phone,
  // above its bar, stays legible where the base rule crosses it.
  for (const label of rowLabels) {
    haloLines(svg, {
      class: "chart-label",
      x: px(label.x),
      y: px(label.y),
      "text-anchor": label.narrow ? "start" : "end",
      "dominant-baseline": label.narrow ? "auto" : "middle",
    }, label.lines);
  }
  return { svg, regions };
}

/* ========================================================= line chart === */

/** Where a mark's label goes in a line chart: the first place, nearest the
 *  dot first, where no line runs through it, a plate's margin round it, and
 *  it covers no dot or label already `taken`, inside the plot. Above the dot
 *  (below it where asked), centred, starting at the dot or ending at it, then
 *  beside it; then each of those a step of LABEL_GAP further away, along and
 *  across, as src/map.js places a port's name. With no clear place, the first
 *  inside the plot that covers no dot or label, then the first inside it.
 *  Returns { x, y, anchor, box }. */
function markLabelPlace({ cx, cy, size, below, segments, taken, plot }) {
  const g = GEOMETRY;
  const step = g.LABEL_GAP;
  const over = cy - g.DOT_RADIUS - g.LABEL_GAP;
  const under = cy + g.DOT_RADIUS + g.LABEL_GAP + g.LABEL_GAP;
  const beside = g.DOT_RADIUS + g.LABEL_GAP;
  const level = cy + g.LABEL_DESCENT;
  // Each first place, and the ways it moves a step further from the dot.
  const bases = [];
  for (const y of below ? [under, over] : [over, under]) {
    const away = y === over ? -step : step;
    bases.push(
      { x: cx, y, anchor: "middle", moves: [[0, away]] },
      { x: cx, y, anchor: "start", moves: [[step, 0], [0, away]] },
      { x: cx, y, anchor: "end", moves: [[-step, 0], [0, away]] },
    );
  }
  bases.push(
    { x: cx + beside, y: level, anchor: "start", moves: [[step, 0], [0, -step], [0, step]] },
    { x: cx - beside, y: level, anchor: "end", moves: [[-step, 0], [0, -step], [0, step]] },
  );
  const boxOf = (p) => {
    const from = p.anchor === "start" ? p.x : (p.anchor === "end" ? p.x - size : p.x - size * g.HALF);
    return { left: from, right: from + size, top: p.y - g.LABEL_ASCENT, bottom: p.y + g.LABEL_DESCENT };
  };
  const inside = (b) => b.left >= plot.left && b.right <= plot.right && b.top >= plot.top && b.bottom <= plot.bottom;
  const free = (b) => !taken.some((o) => overlaps(o, b));
  const unlined = (b) => {
    const room = { left: b.left - g.PLATE_PAD, right: b.right + g.PLATE_PAD, top: b.top - g.PLATE_PAD, bottom: b.bottom + g.PLATE_PAD };
    return !segments.some(([p, q]) => segmentCrosses(room, p, q));
  };
  const tried = [];
  for (let k = 0; ; k += 1) {
    const ring = k === 0
      ? bases.map((b) => ({ x: b.x, y: b.y, anchor: b.anchor }))
      : bases.flatMap((b) => b.moves.map(([dx, dy]) => ({ x: b.x + dx * k, y: b.y + dy * k, anchor: b.anchor })));
    const within = ring.filter((p) => inside(boxOf(p)));
    if (!within.length) break;
    const clear = within.find((p) => free(boxOf(p)) && unlined(boxOf(p)));
    if (clear) return { ...clear, box: boxOf(clear) };
    tried.push(...within);
  }
  const place = tried.find((p) => free(boxOf(p))) || tried[0] || bases[0];
  return { x: place.x, y: place.y, anchor: place.anchor, box: boxOf(place) };
}

/** A line over a numeric x axis, with marked points.
 *
 *    series   [{ points: [[x, y]], className }]
 *    marks    [{ x, y, className, label, below }]: a dot ringed in the ground,
 *             labelled above it (below where asked), or wherever nearest that
 *             no line runs through the label
 *    x, y     { low, high, step } from the caller, the artifact's figures
 *    words    { title, desc, xAxis, yAxis }
 *    regions  one readout per x value, the lines given by `tipFor(x)` */
export function lineChart({ width, series, marks, x, y, words, tipFor }) {
  const g = GEOMETRY;
  const narrow = width < g.NARROW_WIDTH;
  const top = g.PAD_TOP;
  const bottom = top + (narrow ? g.LINE_HEIGHT_NARROW : g.LINE_HEIGHT);
  const left = g.PAD_LEFT;
  const right = Math.max(width - g.PAD_RIGHT, left + g.PAD_LEFT);
  const title = axisTitleLines(words.xAxis, left, right);
  const height = bottom + axisRoom(title);
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--line" });
  const xOf = linear(x.low, x.high, left, right);
  const yOf = linear(y.low, y.high, bottom, top);

  const yStep = verticalStep(yOf, y.low, y.high, y.step);
  for (const value of tickValues(y.low, y.high, yStep)) {
    const at = yOf(value);
    svg.appendChild(svgEl("line", { class: "mark-grid", x1: px(left), x2: px(right), y1: px(at), y2: px(at) }));
    svg.appendChild(svgEl("text", { class: "tick", x: px(left - g.LABEL_GAP), y: px(at), "text-anchor": "end", "dominant-baseline": "middle" }, tickLabel(value, yStep)));
  }
  svg.appendChild(svgEl("text", { class: "chart-axis-title", x: 0, y: px(g.AXIS_GAP) }, words.yAxis));
  if (y.low < 0 && y.high > 0) {
    svg.appendChild(svgEl("line", { class: "mark-context", x1: px(left), x2: px(right), y1: px(yOf(0)), y2: px(yOf(0)) }));
  }
  for (const tick of horizontalTicks(xOf, x.low, x.high, x.step, width)) {
    const at = xOf(tick.value);
    svg.appendChild(svgEl("line", { class: "mark-context", x1: px(at), x2: px(at), y1: px(bottom), y2: px(bottom + g.TICK_LENGTH) }));
    svg.appendChild(svgEl("text", { class: "tick", x: px(tick.x), y: px(bottom + g.AXIS_GAP), "text-anchor": tick.anchor, "dominant-baseline": "middle" }, tick.label));
  }
  axisTitle(svg, title, right, bottom + g.AXIS_GAP + g.AXIS_BELOW);

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
  // The series as pixel segments, so a mark's label is set where no line runs.
  const segments = [];
  for (const line of series) {
    let previous = null;
    for (const [vx, vy] of line.points) {
      if (!present(vy)) {
        previous = null;
        continue;
      }
      const point = { x: xOf(vx), y: yOf(vy) };
      if (previous) segments.push([previous, point]);
      previous = point;
    }
  }
  // What a mark's label may not cover: every mark's dot and ring, the y axis
  // title, and each label already set.
  const drawn = (marks || []).filter((mark) => present(mark.x) && present(mark.y));
  const taken = drawn.map((mark) => {
    const cx = xOf(mark.x);
    const cy = yOf(mark.y);
    return { left: cx - DOT_REACH, right: cx + DOT_REACH, top: cy - DOT_REACH, bottom: cy + DOT_REACH };
  });
  if (words.yAxis) {
    taken.push({ left: 0, right: textWidth("chart-axis-title", words.yAxis), top: g.AXIS_GAP - g.LABEL_ASCENT, bottom: g.AXIS_GAP + g.LABEL_DESCENT });
  }
  for (const mark of drawn) {
    const cx = xOf(mark.x);
    const cy = yOf(mark.y);
    svg.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(cx), cy: px(cy), r: DOT_REACH }));
    svg.appendChild(svgEl("circle", { class: mark.className || "mark-series-fill", cx: px(cx), cy: px(cy), r: g.DOT_RADIUS }));
  }
  for (const mark of drawn) {
    if (!mark.label) continue;
    const place = markLabelPlace({
      cx: xOf(mark.x),
      cy: yOf(mark.y),
      size: textWidth("chart-label", mark.label),
      below: mark.below,
      segments,
      taken,
      plot: { left, right, top: 0, bottom },
    });
    taken.push(place.box);
    haloText(svg, { class: mark.className === "mark-accent-dot" ? "chart-label text-accent" : "chart-label", x: px(place.x), y: px(place.y), "text-anchor": place.anchor }, mark.label);
  }

  const regions = [];
  const points = series.length ? series[0].points : [];
  const xs = points.map(([vx]) => vx);
  xs.forEach((vx, index) => {
    const prev = index > 0 ? xOf(xs[index - 1]) : left;
    const next = index < xs.length - 1 ? xOf(xs[index + 1]) : right;
    const at = xOf(vx);
    const x0 = index > 0 ? (prev + at) * g.HALF : left;
    const x1 = index < xs.length - 1 ? (at + next) * g.HALF : right;
    // The point on the line at this x, for the keyboard's readout to sit beside.
    const vy = points[index][1];
    const mark = present(vy) ? { x: at - DOT_REACH, y: yOf(vy) - DOT_REACH, w: DOT_REACH + DOT_REACH, h: DOT_REACH + DOT_REACH } : null;
    regions.push({ x: x0, y: top, w: x1 - x0, h: bottom - top, mark, lines: tipFor ? tipFor(vx, index) : [String(vx)] });
  });
  return { svg, regions };
}

/** The plain text of a sentence of segments, for a title or desc. */
export function words(segments, decimals) {
  return segmentsText(segments || [], decimals);
}
