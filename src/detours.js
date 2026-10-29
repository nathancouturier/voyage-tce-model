/* detours.js
 *
 * The Detours view: what a longer or riskier way costs. The key chart puts
 * every detour on one scale, the freight a tonne of cargo must rise by for the
 * voyage to earn what it earns without it: the Cape against Suez for an LR2
 * and a Panamax, the Red Sea premium, and the Hormuz scenarios for a VLCC
 * (war risk, waiting to transit, loading by transfer off Fujairah or outside
 * the strait). Each case has its own panel behind a button, with days,
 * distance and the toll or wait each routing can bear.
 *
 * Every figure is from data/detours.json.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, formatDay, UNITS } from "./format.js";
import { barChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["detours"]);

const VIEW = "detours";
let sections = null;

export function render(root, data, route) {
  const detours = data.detours;
  const page = detours.page;
  const decimals = detours.conventions.decimals;
  const title = viewHead(root, page.title, page.takeaway, decimals);

  root.appendChild(chartFigure({
    title: page.chart.title,
    decimals,
    legend: page.chart.legend.map((item) => ({ swatch: item.family === "routing" ? "ink" : item.family, text: item.text })),
    source: page.chart.source,
    draw: (width, titleText) => barChart({
      width,
      rows: page.chart.rows.map((row) => ({
        id: row.label,
        label: row.label,
        group: row.group,
        segments: [{ value: row.value, className: row.family === "routing" ? "mark-series-fill" : null, family: row.family === "routing" ? null : row.family }],
        valueText: formatNumber(row.value, "usd_t", decimals, { signed: true }) + (row.detail ? ", " + row.detail : ""),
        tip: [row.group, row.label, formatNumber(row.value, "usd_t", decimals, { signed: true }) + " " + UNITS.usd_t].concat(row.detail ? [row.detail] : []),
      })),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    suez: (inner) => suezSection(inner, detours, decimals),
    dry: (inner) => drySection(inner, detours, decimals),
    hormuz: (inner) => hormuzSection(inner, detours, decimals),
    method: (inner) => methodSection(inner, detours),
    data: (inner) => dataSection(inner),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function leavesOut(list) {
  return el("td", { class: "words", text: list.join("; ") });
}

function suezSection(inner, detours, decimals) {
  const st = detours.suez_tanker;
  inner.appendChild(sentence("p", detours.page.suez_tanker.lead, decimals, "lead block"));
  const head = el("tr", {}, [
    el("th", { text: "Routing", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Laden, " + UNITS.nm, attrs: { scope: "col", "data-short": "laden" } }),
    el("th", { class: "col-num", text: "Round voyage, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Voyage costs, " + UNITS.usd, attrs: { scope: "col", "data-short": "voyage costs" } }),
    el("th", { class: "col-num", text: "War risk, " + UNITS.usd, attrs: { scope: "col", "data-short": "war risk" } }),
    el("th", { class: "col-num", text: "TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE" } }),
    el("th", { text: "Leaves out", attrs: { scope: "col", "data-short": "leaves out" } }),
  ]);
  const body = el("tbody");
  for (const option of st.options) {
    body.appendChild(el("tr", {}, [
      el("th", { text: option.name, attrs: { scope: "row" } }),
      figureCell(formatCell(option.laden_nm, "nm", decimals), "laden_nm"),
      figureCell(formatCell(option.days, "days", decimals), "days"),
      figureCell(formatCell(option.costs_usd, "usd", decimals), "costs_usd"),
      figureCell(formatCell(option.war_risk_usd, "usd", decimals), "war_risk_usd"),
      figureCell(formatCell(option.tce_usd_day, "usd_day", decimals), "tce_usd_day"),
      leavesOut(option.excluded),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([st.route + " at the Baltic's lump sum of " + formatNumber(st.rate_usd, "usd", decimals) + " " + UNITS.usd + ", week to " + formatDay(st.as_of) + "."], table)]));
}

function drySection(inner, detours, decimals) {
  const sd = detours.suez_dry;
  inner.appendChild(sentence("p", detours.page.suez_dry.lead, decimals, "lead block"));
  const head = el("tr", {}, [
    el("th", { text: "Routing", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Laden, " + UNITS.nm, attrs: { scope: "col", "data-short": "laden" } }),
    el("th", { class: "col-num", text: "Round voyage, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Freight to earn the P4 rate, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "freight" } }),
    el("th", { class: "col-num", text: "Extra against Suez, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "extra" } }),
    el("th", { class: "col-num", text: "Tolls and waiting it can bear, " + UNITS.usd, attrs: { scope: "col", "data-short": "budget" } }),
    el("th", { class: "col-num", text: "The same in days of P4 hire", attrs: { scope: "col", "data-short": "days of hire" } }),
  ]);
  const body = el("tbody");
  for (const option of sd.options) {
    body.appendChild(el("tr", {}, [
      el("th", { text: option.name, attrs: { scope: "row" } }),
      figureCell(formatCell(option.laden_nm, "nm", decimals), "laden_nm"),
      figureCell(formatCell(option.days, "days", decimals), "days"),
      figureCell(formatCell(option.freight_for_target_usd_t, "usd_t", decimals), "freight_for_target_usd_t"),
      figureCell(formatCell(option.extra_freight_vs_suez_usd_t, "usd_t", decimals, true), "extra_freight_vs_suez_usd_t"),
      figureCell(formatCell(option.toll_and_waiting_budget_usd, "usd", decimals), "toll_and_waiting_budget_usd"),
      figureCell(formatCell(option.waiting_days_budget, "days", decimals), "waiting_days_budget"),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([sd.target + "."], table)]));
  inner.appendChild(el("p", { class: "note block", text: "Every routing leaves out " + sd.options[0].excluded.join("; ") + "." }));
}

function hormuzSection(inner, detours, decimals) {
  const hz = detours.hormuz;
  inner.appendChild(sentence("p", detours.page.hormuz.lead, decimals, "lead block"));
  const head = el("tr", {}, [
    el("th", { text: "Scenario", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Round voyage, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Laden, " + UNITS.nm, attrs: { scope: "col", "data-short": "laden" } }),
    el("th", { class: "col-num", text: "War risk, " + UNITS.usd, attrs: { scope: "col", "data-short": "war risk" } }),
    ...hz.levels.map((level) => el("th", {
      class: "col-num",
      text: "Extra freight, " + UNITS.usd_t + ": " + level.label + ", TCE " + formatNumber(level.tce_usd_day, "usd_day", decimals) + " a day",
      attrs: { scope: "col", "data-short": level.label },
    })),
  ]);
  const body = el("tbody");
  for (const scenario of hz.scenarios) {
    body.appendChild(el("tr", {}, [
      el("th", { text: scenario.label, attrs: { scope: "row" } }),
      figureCell(formatCell(scenario.days, "days", decimals), "days"),
      figureCell(formatCell(scenario.laden_nm, "nm", decimals), "laden_nm"),
      figureCell(formatCell(scenario.war_risk_usd, "usd", decimals), "war_risk_usd"),
      ...scenario.levels.map((level) => figureCell(formatCell(level.extra_freight_usd_t, "usd_t", decimals, true), "extra_freight_usd_t")),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["TD3C, Ras Tanura to Ningbo, bunkers of the week to " + formatDay(hz.as_of) + "; each column keeps the Baltic's TD3C TCE of its week."], table)]));
  inner.appendChild(el("p", { class: "note block", text: "Every scenario leaves out " + hz.scenarios[0].excluded.join("; ") + "; the transfer leaves out its own cost and the shuttle through the strait, which have no public figure." }));
}

function methodSection(inner, detours) {
  const block = el("div", { class: "block" }, detours.page.method.map((text) => el("p", { class: "prose", text })));
  inner.appendChild(block);
  const list = el("ul", { class: "plain-list" });
  for (const event of detours.events) {
    list.appendChild(el("li", {}, [el("span", { class: "fig", text: formatDay(event.date) + ", " + event.area + ". " }), event.text]));
  }
  inner.appendChild(el("div", { class: "block" }, [el("h3", { class: "block__heading", text: detours.page.events_heading }), list]));
}

function dataSection(inner) {
  inner.appendChild(el("p", { class: "block" }, [el("a", { class: "text-link", text: "The Hormuz scenarios at three dated TCE levels, CSV", attrs: { href: "data/downloads/detours_hormuz.csv" } })]));
}
