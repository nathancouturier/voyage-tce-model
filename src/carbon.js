/* carbon.js
 *
 * The Carbon view: what the EU ETS adds to a voyage. The key chart is the
 * cost of the allowances per day of the voyage, for a voyage between two EEA
 * ports, one into the EEA and one outside it, in each year of the phase in;
 * then the time charter split under BIMCO's clause, the table of every figure,
 * and behind buttons the rules with their texts, FuelEU Maritime and the
 * downloads.
 *
 * Every figure is from data/carbon.json.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, UNITS } from "./format.js";
import { barChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["carbon"]);

const VIEW = "carbon";
let sections = null;

export function render(root, data, route) {
  const carbon = data.carbon;
  const page = carbon.page;
  const decimals = carbon.conventions.decimals;
  const scale = carbon.conventions.scale;
  const title = viewHead(root, page.title, page.takeaway, decimals);

  const rows = [];
  for (const voyage of carbon.rows) {
    for (const year of voyage.years) {
      rows.push({
        id: voyage.route + "-" + String(year.year),
        label: String(year.year) + ", " + formatNumber(year.phase_in * scale.percent, "percent_0", decimals) + " percent surrendered",
        group: page.kinds[voyage.route],
        segments: [{ value: year.per_day_usd, family: "ets" }],
        valueText: year.per_day_usd ? formatNumber(year.per_day_usd, "usd_day", decimals) : page.chart.none,
        tip: [
          page.kinds[voyage.route],
          String(year.year) + ": " + formatNumber(year.cost_usd, "usd", decimals) + " " + UNITS.usd + " for the voyage",
          formatNumber(year.per_day_usd, "usd_day", decimals) + " " + UNITS.usd_day,
          formatNumber(year.per_tonne_cargo_usd, "usd_t", decimals) + " " + UNITS.usd_t + " of cargo",
        ],
      });
    }
  }
  root.appendChild(chartFigure({
    title: page.chart.title,
    decimals,
    legend: [{ swatch: "ets", text: "EU ETS allowances" }],
    source: page.chart.source,
    draw: (width, titleText) => barChart({ width, rows, words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis } }),
  }));

  root.appendChild(el("div", { class: "block" }, [costTable(carbon, decimals, scale)]));
  root.appendChild(el("div", { class: "block" }, [
    el("h2", { class: "block__heading", text: page.time_charter.title }),
    sentence("p", page.time_charter.lead, decimals, "prose"),
    el("p", { class: "note", text: carbon.time_charter.rule + "." }),
  ]));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    method: (inner) => methodSection(inner, carbon),
    fueleu: (inner) => fueleuSection(inner, carbon, decimals),
    data: (inner) => dataSection(inner),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function costTable(carbon, decimals, scale) {
  const head = el("tr", {}, [
    el("th", { text: "Voyage and year", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Covered emissions, t CO2e", attrs: { scope: "col", "data-short": "covered" } }),
    el("th", { class: "col-num", text: "Allowances, t", attrs: { scope: "col", "data-short": "allowances" } }),
    el("th", { class: "col-num", text: "Cost, " + UNITS.usd, attrs: { scope: "col", "data-short": "cost" } }),
    el("th", { class: "col-num", text: "Per day, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "per day" } }),
    el("th", { class: "col-num", text: "Per tonne of cargo, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "per tonne" } }),
    el("th", { class: "col-num", text: "Share of voyage costs, percent", attrs: { scope: "col", "data-short": "share" } }),
  ]);
  const body = el("tbody");
  for (const voyage of carbon.rows) {
    for (const year of voyage.years) {
      body.appendChild(el("tr", {}, [
        el("th", { text: voyage.route + ", " + String(year.year), attrs: { scope: "row" } }),
        figureCell(formatCell(year.covered_t, "tco2", decimals), "covered_t"),
        figureCell(formatCell(year.allowances_t, "tco2", decimals), "allowances_t"),
        figureCell(formatCell(year.cost_usd, "usd", decimals), "cost_usd"),
        figureCell(formatCell(year.per_day_usd, "usd_day", decimals), "per_day_usd"),
        figureCell(formatCell(year.per_tonne_cargo_usd, "usd_t", decimals), "per_tonne_cargo_usd"),
        figureCell(formatCell(year.share_of_voyage_costs * scale.percent, "percent", decimals), "share_of_voyage_costs"),
      ]));
    }
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
  return scrollTable(["Every voyage and year: the emissions the ETS covers, the allowances surrendered and their cost at the " + carbon.market + " allowance price."], table);
}

function methodSection(inner, carbon) {
  inner.appendChild(el("div", { class: "block" }, carbon.page.method.map((text) => el("p", { class: "prose", text }))));
  const head = el("tr", {}, [
    el("th", { text: "Rule", attrs: { scope: "col" } }),
    el("th", { text: "What it says", attrs: { scope: "col", "data-short": "rule" } }),
    el("th", { text: "Text", attrs: { scope: "col", "data-short": "source" } }),
  ]);
  const body = el("tbody");
  for (const row of carbon.conventions_rows) {
    body.appendChild(el("tr", {}, [
      el("th", { text: row.topic, attrs: { scope: "row" } }),
      el("td", { class: "words", text: row.rule }),
      el("td", { class: "words" }, [el("a", { class: "text-link", text: row.source, attrs: { href: carbon.convention_links[row.id] } })]),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["The rules the carbon figures follow, each with the text it is read from."], table)]));
}

function fueleuSection(inner, carbon, decimals) {
  inner.appendChild(el("div", { class: "block" }, carbon.page.fueleu.map((text) => el("p", { class: "prose", text }))));
  const head = el("tr", {}, [
    el("th", { text: "Voyage", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Energy in scope, MJ", attrs: { scope: "col", "data-short": "energy" } }),
    el("th", { class: "col-num", text: "Intensity, " + UNITS.g_mj, attrs: { scope: "col", "data-short": "intensity" } }),
    el("th", { class: "col-num", text: "Limit, " + UNITS.g_mj, attrs: { scope: "col", "data-short": "limit" } }),
    el("th", { class: "col-num", text: "Penalty, EUR", attrs: { scope: "col", "data-short": "penalty EUR" } }),
    el("th", { class: "col-num", text: "Penalty, " + UNITS.usd, attrs: { scope: "col", "data-short": "penalty USD" } }),
  ]);
  const body = el("tbody");
  for (const voyage of carbon.rows) {
    const f = voyage.fueleu;
    body.appendChild(el("tr", {}, [
      el("th", { text: voyage.route + ", " + voyage.kind, attrs: { scope: "row" } }),
      figureCell(formatCell(f.energy_mj, "mj", decimals), "energy_mj"),
      figureCell(f.energy_mj ? formatCell(f.intensity_g_mj, "g_mj", decimals) : null, "intensity_g_mj", { missing: "none in scope" }),
      figureCell(formatCell(f.target_g_mj, "g_mj", decimals), "target_g_mj"),
      figureCell(formatCell(f.penalty_eur, "eur", decimals), "penalty_eur"),
      figureCell(formatCell(f.penalty_usd, "usd", decimals), "penalty_usd"),
    ]));
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["The FuelEU penalty one voyage's energy would carry if the ship burnt the same fuel all year: shown, and kept out of the TCE."], table)]));
}

function dataSection(inner) {
  inner.appendChild(el("ul", { class: "plain-list block" }, [
    el("li", {}, [el("a", { class: "text-link", text: "EU ETS cost by voyage and year, CSV", attrs: { href: "data/downloads/carbon_ets.csv" } })]),
    el("li", {}, [el("a", { class: "text-link", text: "EU allowance price, monthly, CSV", attrs: { href: "data/downloads/eua_monthly.csv" } })]),
  ]));
}
