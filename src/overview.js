/* overview.js
 *
 * The overview, the view the site opens on: one featured voyage at the latest
 * dated anchor. The verdict sentence, the date and source of every input, the
 * three facts (the TCE, the freight that covers voyage costs, the bunkers'
 * share of them), the bridge from gross freight to the result, and the map of
 * the voyage with its ballast leg dashed and its emission control area miles
 * marked. Method, Assumptions and Data sit behind buttons.
 *
 * Every figure is from data/overview.json and the map from data/map.json, as
 * written by src/voyage/export.py. Nothing here computes a market quantity.
 *
 * Numeric literals: none.
 */

import { el, sentence, appendSegments, figureCell, scrollTable } from "./dom.js";
import { formatCell, formatDay, formatDayShort, UNITS } from "./format.js";
import { words } from "./charts.js";
import { voyageMap } from "./map.js";
import { bridgeTable } from "./bridge.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["overview", "map"]);

const VIEW = "overview";
let sections = null;
let animated = false;

export function render(root, data, route) {
  const view = data.overview;
  const decimals = view.conventions.decimals;

  const verdict = sentence("h1", view.verdict, decimals, "verdict");
  verdict.id = "view-title";
  verdict.setAttribute("tabindex", "-1");
  root.appendChild(verdict);

  root.appendChild(facts(view, decimals));

  // The bridge builds once, on the first load of the site, never on a return.
  const bridge = bridgeTable(view.bridge.rows, decimals, { caption: view.bridge.caption, enter: !animated });
  animated = true;
  const bridgeFigure = el("figure", { class: "block overview__bridge" }, [
    sentence("h2", view.bridge.title, decimals, "block__heading"),
    bridge.node,
    sentence("p", view.bridge.result_line, decimals, "result-line"),
    sentence("p", view.bridge.source, decimals, "source-line"),
  ]);

  const voyage = data.map.voyages[view.map.key];
  const mapFrame = el("div", { class: "map-frame" });
  const mapFigure = el("figure", { class: "block overview__map" }, [
    sentence("h2", view.map.title, decimals, "block__heading"),
    mapFrame,
    legend(view.map.legend),
    sentence("p", view.map.source, decimals, "source-line"),
  ]);
  root.appendChild(el("div", { class: "overview__grid" }, [bridgeFigure, mapFigure]));
  voyageMap(mapFrame, data.map.land, voyage, {
    title: words(view.map.title, decimals),
    desc: view.map.legend.map((item) => item.text).join(". ") + ".",
  });

  // The date and source of every input, under the bridge and the map so the figures come first on a phone.
  const dates = el("ul", { class: "data-dates", attrs: { "aria-label": "The date and source of every input" } });
  for (const line of view.dates) dates.appendChild(appendSegments(el("li"), line, decimals));
  root.appendChild(dates);

  root.appendChild(sentence("p", view.leaves_out, decimals, "lead block leaves-out"));

  sections = buildSections(VIEW, withBuilders(view.sections, {
    method: (inner) => methodSection(inner, view, decimals),
    assumptions: (inner) => assumptionsSection(inner, view, decimals),
    data: (inner) => dataSection(inner, view, decimals),
  }), decimals, route);
  root.appendChild(sections.node);
  return verdict;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function facts(view, decimals) {
  const list = el("dl", { class: "facts" });
  for (const fact of view.facts) {
    list.appendChild(el("div", { class: "fact", attrs: { "data-fact": fact.id } }, [
      el("dt", { class: "fact__label", text: fact.label }),
      el("dd", { class: "fact__value" }, [
        appendSegments(el("span", { class: "fact__figure" }), [fact.value], decimals),
        el("span", { class: "fact__unit", text: " " + fact.unit }),
      ]),
      el("dd", { class: "fact__note" }, [appendSegments(el("span"), fact.note, decimals)]),
      el("dd", { class: "fact__date", text: "As of " + formatDay(fact.as_of) }),
    ]));
  }
  return list;
}

/** The legend of the map, in words beside a sample of each line. */
export function legend(items) {
  return el("ul", { class: "map-legend" }, items.map((item) => el("li", { class: "map-legend__item" }, [
    el("span", { class: "map-legend__sample map-legend__sample--" + item.kind, attrs: { "aria-hidden": "true" } }),
    item.text,
  ])));
}

function methodSection(inner, view, decimals) {
  const method = view.method;
  const block = el("div", { class: "block" });
  for (const paragraph of method.paragraphs) block.appendChild(sentence("p", paragraph, decimals, "prose"));
  for (const formula of method.formulas) block.appendChild(el("p", { class: "formula", text: formula }));
  inner.appendChild(block);

  const head = el("tr", {}, [
    el("th", { text: "Week to", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Lump sum, " + UNITS.usd, attrs: { scope: "col", "data-short": "lump sum" } }),
    el("th", { class: "col-num", text: "Baltic TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "Baltic TCE" } }),
    el("th", { class: "col-num", text: "Engine TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "engine TCE" } }),
    el("th", { class: "col-num", text: "Engine against the Baltic, percent", attrs: { scope: "col", "data-short": "difference" } }),
    el("th", { text: "Bunker prices", attrs: { scope: "col", "data-short": "bunker prices" } }),
  ]);
  const body = el("tbody");
  for (const row of view.comparison) {
    body.appendChild(el("tr", {}, [
      el("th", { text: formatDayShort(row.week_ending), attrs: { scope: "row" } }),
      figureCell(formatCell(row.rate_usd, "usd", decimals), "rate_usd"),
      figureCell(formatCell(row.published_tce_usd_day, "usd_day", decimals), "published_tce_usd_day"),
      figureCell(formatCell(row.engine_tce_usd_day, "usd_day", decimals), "engine_tce_usd_day"),
      figureCell(formatCell(row.error_pct, "error_percent", decimals, true), "error_pct"),
      el("td", { class: "words", text: row.bunkers_words }),
    ]));
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [
    scrollTable([appendSegments(el("span"), method.comparison_title, decimals)], table),
    sentence("p", method.comparison_note, decimals, "note"),
  ]));
}

function assumptionsSection(inner, view, decimals) {
  const a = view.assumptions;
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: "What the TCE leaves out" }),
    el("ul", { class: "plain-list" }, a.leaves_out.map((item) => el("li", { text: item }))),
  ]));
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: "The ship and its port days" }),
    sentence("p", a.vessel, decimals, "prose"),
    sentence("p", a.port, decimals, "prose"),
  ]));
}

/** The table of every input of a voyage: label, value, status and source.
 *  Shared with the calculator's Data section. */
export function inputsTable(rows, decimals, captionWords) {
  const head = el("tr", {}, [
    el("th", { text: "Input", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Value", attrs: { scope: "col", "data-short": "value" } }),
    el("th", { text: "Unit", attrs: { scope: "col", "data-short": "unit" } }),
    el("th", { text: "Status", attrs: { scope: "col", "data-short": "status" } }),
    el("th", { text: "Source or reason", attrs: { scope: "col", "data-short": "source" } }),
  ]);
  const body = el("tbody");
  for (const row of rows) {
    let value;
    if (row.text) value = el("td", { class: "words", text: row.text, attrs: { "data-field": row.path } });
    else if (row.value === null) value = el("td", { class: "num is-missing", text: row.status_words, attrs: { "data-missing": row.path } });
    else value = figureCell(formatCell(row.value, row.format, decimals), row.path);
    body.appendChild(el("tr", { attrs: { "data-status": row.status } }, [
      el("th", { text: row.label, attrs: { scope: "row" } }),
      value,
      el("td", { class: "nowrap", text: row.format ? UNITS[row.format] : "" }),
      el("td", { class: "status status--" + row.status, text: row.status_words }),
      el("td", { class: "words", text: row.source }),
    ]));
  }
  const table = el("table", { class: "table table--inputs" }, [el("thead", {}, [head]), body]);
  return scrollTable([captionWords], table);
}

function dataSection(inner, view, decimals) {
  inner.appendChild(el("div", { class: "block" }, [inputsTable(view.inputs_table, decimals, view.data_caption)]));
}
