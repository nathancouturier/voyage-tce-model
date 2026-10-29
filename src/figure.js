/* figure.js
 *
 * The frame every chart of the study sits in: a heading that states the
 * takeaway, the chart drawn at the column's width (and again when the width
 * changes), its legend in words, its source line with the date of its data,
 * and the readout a pointer or the arrow keys open. The values are always
 * also in a table, in the chart's Data section or beside it.
 *
 * Numeric literals: none.
 */

import { el, sentence } from "./dom.js";
import { onWidthChange, tooltip, words } from "./charts.js";

/** A figure holding one chart.
 *
 *    title     the takeaway, as segments
 *    decimals  the artifact's conventions.decimals
 *    draw      (width, titleText) => { svg, regions }
 *    legend    [{ swatch, text }] or null: swatch is a swatch class suffix
 *    source    segments, or null
 *    note      segments, or null: a line under the source */
export function chartFigure({ title, decimals, draw, legend, source, note }) {
  const heading = sentence("h2", title, decimals, "block__heading");
  const frame = el("div", { class: "chart-frame" });
  const titleText = words(title, decimals);
  onWidthChange(frame, (width) => {
    const { svg, regions } = draw(width, titleText);
    frame.replaceChildren(svg);
    tooltip(frame, svg, regions || []);
  });
  return el("figure", { class: "block" }, [
    heading,
    frame,
    legend && legend.length ? legendList(legend) : null,
    source ? sentence("p", source, decimals, "source-line") : null,
    note ? sentence("p", note, decimals, "source-line") : null,
  ]);
}

/** A legend in words, a swatch beside each. */
export function legendList(items) {
  return el("ul", { class: "chart-legend" }, items.map((item) => el("li", { class: "chart-legend__item" }, [
    el("span", { class: "swatch swatch--" + item.swatch, attrs: { "aria-hidden": "true" } }),
    item.text,
  ])));
}

/** The view's opening: its title and its one sentence takeaway. Returns the
 *  title, which takes focus on a route change. */
export function viewHead(root, title, takeaway, decimals) {
  const heading = el("h1", { class: "view-title", id: "view-title", text: title, attrs: { tabindex: "-1" } });
  root.appendChild(heading);
  root.appendChild(sentence("p", takeaway, decimals, "lead view-lead"));
  return heading;
}
