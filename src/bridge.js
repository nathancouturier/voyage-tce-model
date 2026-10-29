/* bridge.js
 *
 * The bridge from gross freight to the voyage result: a table, one row per
 * step, a bar in a cell, the figure at the right, and under it the sentence
 * that divides the result by the days. The overview draws it from
 * data/overview.json; the calculator draws the same table from the engine's
 * output on every change of an input.
 *
 * The table is the text alternative of its own bars: every bar's value is the
 * figure in its row, so the bars are aria-hidden. A step with no figure keeps
 * its row, says why in the figure's place (left out, none on this routing),
 * and draws no bar. At 600px and below each row becomes two lines by CSS grid
 * on the tr, which is why the roles are written into the markup.
 *
 * Colour: freight and the result in ink, the result in the accent, commission
 * an ink outline (a deduction from revenue, not a voyage cost), each voyage
 * cost in its family's colour, and a swatch of that colour beside its name.
 *
 * THE ONE ORCHESTRATED MOMENT. The overview's bridge builds once on first
 * load: each bar grows from its running total in turn, ENTER_STAGGER apart
 * (styles/components.css holds the duration and the reduced motion rule). A
 * redraw for a width change never replays it.
 *
 * Numeric literals: none; the stagger is read from the stylesheet.
 */

import { el, appendSegments, figureCell } from "./dom.js";
import { formatCell, UNITS } from "./format.js";
import { bridgeBar } from "./charts.js";

/** The bridge table.
 *
 *    rows      [{ id, label, kind, family, from_usd, to_usd, value_usd,
 *                 detail (segments or a string), zero (words or null),
 *                 accent }]
 *    decimals  the artifact's conventions.decimals
 *    options   { caption, enter }: enter animates the first draw
 *
 *  Returns { node, redraw(rows) }: redraw replaces the bars and figures in
 *  place, for the calculator. */
export function bridgeTable(rows, decimals, options) {
  const opts = options || {};
  const body = el("tbody", { attrs: { role: "rowgroup" } });
  const table = el("table", { class: "table waterfall bridge", attrs: { role: "table" } }, [
    el("caption", { class: "visually-hidden", text: opts.caption || "" }),
    el("thead", { attrs: { role: "rowgroup" } }, [
      el("tr", { attrs: { role: "row" } }, [
        el("th", { text: "Step", attrs: { scope: "col", role: "columnheader" } }),
        el("th", { class: "waterfall__bar-head", attrs: { scope: "col", role: "columnheader" } }, [el("span", { class: "visually-hidden", text: "Bar from the running total" })]),
        el("th", { class: "col-num", text: UNITS.usd, attrs: { scope: "col", role: "columnheader" } }),
      ]),
    ]),
    body,
  ]);

  let current = rows;
  let cells = [];
  let entering = opts.enter === true;

  const build = () => {
    body.replaceChildren();
    cells = [];
    current.forEach((row, index) => {
      const isTotal = row.kind === "total";
      const name = el("span", { class: "waterfall__line" }, [
        row.family ? el("span", { class: "swatch swatch--" + row.family, attrs: { "aria-hidden": "true" } }) : null,
        row.label,
      ]);
      const nameCell = el("th", { class: "waterfall__name", attrs: { scope: "row", role: "rowheader" } }, [name]);
      if (row.detail) {
        const detail = el("span", { class: "waterfall__detail" });
        if (typeof row.detail === "string") detail.textContent = row.detail;
        else appendSegments(detail, row.detail, decimals);
        nameCell.appendChild(detail);
      }
      const barCell = el("td", { class: "waterfall__bar", attrs: { role: "cell" } });
      cells.push({ cell: barCell, row, previous: index > 0 ? current[index - 1] : null, isLast: index === current.length - 1, index });
      let figure;
      if (row.zero && !row.value_usd) {
        figure = el("td", { class: "num is-missing waterfall__zero", text: row.zero, attrs: { role: "cell", "data-missing": row.id } });
      } else {
        figure = figureCell(formatCell(row.value_usd, "usd", decimals), "bridge." + row.id,
          [isTotal ? "num--total" : "", row.accent ? "text-accent" : ""].filter(Boolean).join(" "));
        figure.setAttribute("role", "cell");
      }
      body.appendChild(el("tr", {
        class: "waterfall__row" + (isTotal ? " is-total" : "") + (row.zero && !row.value_usd ? " is-zero" : ""),
        attrs: { role: "row", "data-row": row.id },
      }, [nameCell, barCell, figure]));
    });
  };

  // Every bar at the size of its cell, drawn again whenever the table resizes.
  const scale = () => {
    const ends = current.flatMap((row) => [row.from_usd, row.to_usd]).filter((v) => typeof v === "number" && Number.isFinite(v));
    return [Math.min(0, ...ends), Math.max(0, ...ends)];
  };
  const stagger = () => {
    const raw = getComputedStyle(table).getPropertyValue("--bridge-stagger").trim();
    const value = parseFloat(raw);
    return Number.isFinite(value) ? value : 0;
  };
  const draw = () => {
    const range = scale();
    const step = entering ? stagger() : 0;
    let drawn = false;
    for (const item of cells) {
      const width = item.cell.clientWidth;
      const height = item.cell.clientHeight;
      if (width === 0 || height === 0) continue;
      drawn = true;
      item.cell.replaceChildren(bridgeBar({
        width, height, row: item.row, previous: item.previous, isLast: item.isLast, scale: range,
        enter: entering, delay: step * item.index,
      }));
    }
    if (drawn) entering = false;
  };

  build();
  if (typeof ResizeObserver === "function") new ResizeObserver(() => draw()).observe(table);
  else window.addEventListener("resize", draw, { passive: true });
  requestAnimationFrame(draw);

  return {
    node: table,
    redraw(next) {
      current = next;
      build();
      draw();
    },
  };
}
