/* method.js
 *
 * The Method and data view: how far the engine can be trusted and where every
 * input comes from. The key chart is the engine's TCE against the Baltic's
 * published TCE, week by week, for the two tanker routes whose rate converts to
 * dollars without a licensed flat rate. Behind buttons: the conventions with
 * the texts they are read from, the formulas, every validation anchor
 * (reproduced or not, and why), the sources with their dates and licences,
 * the limitations and the sites that could not be reached, and the
 * downloads with the research note.
 *
 * Every figure is from data/method.json and data/manifest.json.
 *
 * Numeric literals: none.
 */

import { el, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, formatDay, formatDayShort, UNITS } from "./format.js";
import { dotChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["method", "manifest"]);

const VIEW = "method";
let sections = null;

export function render(root, data, route) {
  const method = data.method;
  const page = method.page;
  const decimals = method.conventions.decimals;
  const scale = method.conventions.scale;
  const title = viewHead(root, page.title, page.takeaway, decimals);

  const anchors = method.validation.tanker.filter((row) => row.reproducible);
  root.appendChild(chartFigure({
    title: page.chart.title,
    decimals,
    legend: page.chart.legend.map((item) => ({ swatch: item.kind === "ink" ? "ink swatch--dot" : item.kind, text: item.text })),
    source: page.chart.source,
    draw: (width, titleText) => dotChart({
      width,
      keepZero: true,
      rows: anchors.map((row) => {
        const sameWeek = row.bunkers.endsWith(row.week_ending);
        return {
          id: row.route + row.week_ending,
          label: row.route + ", " + formatDay(row.week_ending),
          group: null,
          dots: [{ value: row.error * scale.percent, className: sameWeek ? "mark-series-fill" : "mark-printed" }],
          span: { from: 0, to: row.error * scale.percent },
          tip: [
            row.route + ", week to " + formatDay(row.week_ending),
            "Baltic: " + formatNumber(row.published_tce_usd_day, "usd_day", decimals) + " " + UNITS.usd_day,
            "Engine: " + formatNumber(row.engine_tce_usd_day, "usd_day", decimals) + " " + UNITS.usd_day,
            formatNumber(row.error * scale.percent, "error_percent", decimals, { signed: true }) + " percent",
          ],
        };
      }),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    conventions: (inner) => conventionsSection(inner, method),
    formulas: (inner) => formulasSection(inner, method),
    validation: (inner) => validationSection(inner, method, decimals, scale),
    sources: (inner) => sourcesSection(inner, data.manifest),
    limitations: (inner) => limitationsSection(inner, method),
    downloads: (inner) => downloadsSection(inner, method),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function quoteText(quote) {
  return Array.isArray(quote) ? quote.join(" [...] ") : String(quote || "");
}

function conventionsSection(inner, method) {
  const head = el("tr", {}, [
    el("th", { text: "Convention", attrs: { scope: "col" } }),
    el("th", { text: "As the engine applies it", attrs: { scope: "col", "data-short": "rule" } }),
    el("th", { text: "Source", attrs: { scope: "col", "data-short": "source" } }),
    el("th", { text: "The text it is read from", attrs: { scope: "col", "data-short": "quote" } }),
  ]);
  const body = el("tbody");
  for (const item of method.convention_items) {
    body.appendChild(el("tr", {}, [
      el("th", { text: item.topic, attrs: { scope: "row" } }),
      el("td", { class: "words", text: item.rule }),
      el("td", { class: "words" }, [item.url ? el("a", { class: "text-link", text: item.source, attrs: { href: item.url } }) : item.source]),
      el("td", { class: "words quote", text: quoteText(item.quote) }),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["Every market convention the engine applies, with the passage of the primary text it follows."], table)]));
}

function formulasSection(inner, method) {
  inner.appendChild(el("div", { class: "block" }, method.page.formulas.map((text) => el("p", { class: "formula", text }))));
}

function validationSection(inner, method, decimals, scale) {
  const v = method.validation;
  // Tanker anchors: every published pair, reproduced or not.
  const head = el("tr", {}, [
    el("th", { text: "Week to", attrs: { scope: "col" } }),
    el("th", { text: "Route", attrs: { scope: "col", "data-short": "route" } }),
    el("th", { class: "col-num", text: "Rate", attrs: { scope: "col", "data-short": "rate" } }),
    el("th", { class: "col-num", text: "Baltic TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "Baltic TCE" } }),
    el("th", { class: "col-num", text: "Engine TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "engine TCE" } }),
    el("th", { class: "col-num", text: "Difference, percent", attrs: { scope: "col", "data-short": "difference" } }),
    el("th", { text: "Why not reproduced, or the bunkers used", attrs: { scope: "col", "data-short": "note" } }),
  ]);
  const body = el("tbody");
  for (const row of v.tanker) {
    const rate = row.rate_basis === "ws" ? "WS " + formatNumber(row.rate_value, "ws", decimals) : formatNumber(row.rate_value, "usd", decimals) + " " + UNITS.usd;
    body.appendChild(el("tr", { attrs: { "data-reproducible": row.reproducible ? "yes" : "no" } }, [
      el("th", { class: "nowrap", text: formatDayShort(row.week_ending), attrs: { scope: "row" } }),
      el("td", { class: "nowrap" }, [row.url ? el("a", { class: "text-link", text: row.route_label, attrs: { href: row.url } }) : row.route_label]),
      el("td", { class: "num", text: rate }),
      figureCell(formatCell(row.published_tce_usd_day, "usd_day", decimals), "published_tce_usd_day", { missing: "not given" }),
      figureCell(formatCell(row.engine_tce_usd_day, "usd_day", decimals), "engine_tce_usd_day", { missing: "not priced" }),
      figureCell(row.error === null ? null : formatCell(row.error * scale.percent, "error_percent", decimals, true), "error", { missing: "not compared" }),
      el("td", { class: "words", text: row.reproducible ? "Bunkers of the " + row.bunkers_words : row.reason }),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["Every tanker rate and TCE the Baltic's weekly reports published in the weeks studied, as republished by Hellenic Shipping News, and the engine's TCE where the rate converts to dollars."], table)]));

  // Dry: route rates against the time charter averages.
  const dryHead = el("tr", {}, [
    el("th", { text: "Route and date", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Freight, " + UNITS.usd_t, attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Engine TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "engine TCE" } }),
    el("th", { text: "Benchmark", attrs: { scope: "col", "data-short": "benchmark" } }),
    el("th", { class: "col-num", text: "Benchmark, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "benchmark value" } }),
    el("th", { class: "col-num", text: "Gap, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "gap" } }),
  ]);
  const dryBody = el("tbody");
  for (const row of v.dry) {
    dryBody.appendChild(el("tr", {}, [
      el("th", { text: row.route + ", " + formatDay(row.date), attrs: { scope: "row" } }),
      figureCell(formatCell(row.freight_usd_t, "usd_t", decimals), "freight_usd_t"),
      figureCell(formatCell(row.engine_tce_usd_day, "usd_day", decimals), "engine_tce_usd_day"),
      el("td", { class: "nowrap", text: row.benchmark.replace(/_usd_day$/, "").replace(/_/g, " ") }),
      figureCell(formatCell(row.benchmark_usd_day, "usd_day", decimals), "benchmark_usd_day"),
      figureCell(formatCell(row.gap_usd_day, "usd_day", decimals, true), "gap_usd_day"),
    ]));
  }
  const dryTable = el("table", { class: "table table--wide" }, [el("thead", {}, [dryHead]), dryBody]);
  inner.appendChild(el("div", { class: "block" }, [
    scrollTable(["Dry route rates priced by the engine against the time charter average of the same week. The gap is not an error: the averages are gross time charter rates over a basket of routes, the TCEs are net of commission on one round voyage and leave out port charges and loading time."], dryTable),
  ]));

  // Early March 2026: the VLCC rates reported in dollars a tonne.
  const marchHead = el("tr", {}, [
    el("th", { text: "Rate", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: UNITS.usd_t, attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Engine TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "engine TCE" } }),
    el("th", { class: "col-num", text: "With the early March war risk premium, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "with war risk" } }),
    el("th", { text: "Bunkers", attrs: { scope: "col", "data-short": "bunkers" } }),
  ]);
  const marchBody = el("tbody");
  for (const row of v.early_march) {
    marchBody.appendChild(el("tr", {}, [
      el("th", { text: row.source + ", " + formatDay(row.date), attrs: { scope: "row" } }),
      figureCell(formatCell(row.freight_usd_t, "usd_t", decimals), "freight_usd_t"),
      figureCell(formatCell(row.engine_tce_usd_day, "usd_day", decimals), "engine_tce_usd_day"),
      figureCell(formatCell(row.engine_tce_with_war_risk_usd_day === undefined ? null : row.engine_tce_with_war_risk_usd_day, "usd_day", decimals), "engine_tce_with_war_risk_usd_day", { missing: "before the war" }),
      el("td", { class: "words", text: row.bunkers_words || row.bunkers }),
    ]));
  }
  const marchTable = el("table", { class: "table table--wide" }, [el("thead", {}, [marchHead]), marchBody]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([method.page.early_march_caption], marchTable)]));

  // The Baltic's own worked TD3C calculation of 2017.
  const b = v.baltic_2017;
  const keys = Object.keys(b.published);
  const bHead = el("tr", {}, [
    el("th", { text: "Line", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: method.page.baltic_2017_head, attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Engine", attrs: { scope: "col" } }),
  ]);
  const bBody = el("tbody");
  for (const key of keys) {
    const format = key.endsWith("_days") ? "days_4" : "t_2";
    bBody.appendChild(el("tr", {}, [
      el("th", { text: method.page.baltic_2017_labels[key], attrs: { scope: "row" } }),
      figureCell(formatCell(b.published[key], format, decimals), "published." + key),
      figureCell(formatCell(b.computed[key], format, decimals), "computed." + key),
    ]));
  }
  const bTable = el("table", { class: "table" }, [el("thead", {}, [bHead]), bBody]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([method.page.baltic_2017_caption], bTable)]));
}

function sourcesSection(inner, manifest) {
  const head = el("tr", {}, [
    el("th", { text: "Series", attrs: { scope: "col" } }),
    el("th", { text: "As of", attrs: { scope: "col", "data-short": "as of" } }),
    el("th", { text: "Retrieved", attrs: { scope: "col", "data-short": "retrieved" } }),
    el("th", { text: "Publisher", attrs: { scope: "col", "data-short": "publisher" } }),
    el("th", { text: "Licence", attrs: { scope: "col", "data-short": "licence" } }),
  ]);
  const body = el("tbody");
  for (const series of manifest.series) {
    body.appendChild(el("tr", {}, [
      el("th", { class: "manifest__series", attrs: { scope: "row" } }, [el("a", { class: "text-link", text: series.what, attrs: { href: series.source.url } })]),
      el("td", { class: "nowrap", text: formatDay(series.as_of) }),
      el("td", { class: "nowrap", text: formatDay(series.source.retrieved) }),
      el("td", { class: "manifest__words", text: series.source.publisher }),
      el("td", { class: "manifest__words", text: series.licence }),
    ]));
  }
  const table = el("table", { class: "table manifest-table" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([manifest.caption], table)]));
}

function limitationsSection(inner, method) {
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: method.page.limitations_heading }),
    el("ul", { class: "plain-list" }, method.page.limitations.map((text) => el("li", { text }))),
  ]));
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: method.page.blocked_heading }),
    el("ul", { class: "plain-list" }, method.page.blocked.map((text) => el("li", { text }))),
  ]));
}

function downloadsSection(inner, method) {
  inner.appendChild(el("ul", { class: "plain-list block" }, method.page.downloads.map((d) => el("li", {}, [el("a", { class: "text-link", text: d.text, attrs: { href: d.file } })]))));
}
