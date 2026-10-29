/* detours.js
 *
 * The Detours view: what a longer or riskier way costs. The key chart puts
 * every detour on one scale, what a tonne of cargo costs more: the freight the
 * owner needs to earn the base TCE (ink) and the charterer's war risk premium
 * at cost (coloured), for the Cape against Suez for an LR2 and a Panamax, the
 * Red Sea premium, and the Hormuz scenarios for a VLCC (war risk and waiting
 * inside the Gulf). Each case has its own panel behind a button, with days,
 * distance, the toll or wait each routing can bear and, for Hormuz, the
 * transfer chain and TD34.
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
        segments: row.segments.map((segment) => ({ value: segment.value, className: segment.family === "routing" ? "mark-series-fill" : null, family: segment.family === "routing" ? null : segment.family })),
        valueText: formatNumber(total(row), "usd_t", decimals, { signed: true }) + (row.detail ? ", " + row.detail : ""),
        tip: [row.group, row.label, formatNumber(total(row), "usd_t", decimals, { signed: true }) + " " + UNITS.usd_t]
          .concat(row.segments.length > 1 ? row.segments.map((segment) => legendText(page, segment.family) + ": " + formatNumber(segment.value, "usd_t", decimals)) : [])
          .concat(row.detail ? [row.detail] : []),
      })),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    suez: (inner) => suezSection(inner, detours, decimals),
    dry: (inner) => drySection(inner, detours, decimals),
    hormuz: (inner) => hormuzSection(inner, detours, decimals),
    method: (inner) => methodSection(inner, detours),
    assumptions: (inner) => assumptionsSection(inner, detours),
    data: (inner) => dataSection(inner),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

/* A bar's length: the owner's freight and the charterer's premium together. */
function total(row) {
  return row.segments.reduce((sum, segment) => sum + segment.value, 0);
}

function legendText(page, family) {
  return page.chart.legend.find((item) => item.family === family).text;
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
    el("th", { class: "col-num", text: "War risk premium, the charterer's, " + UNITS.usd, attrs: { scope: "col", "data-short": "charterer's premium" } }),
    el("th", { class: "col-num", text: "The same a tonne, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "premium a tonne" } }),
    el("th", { class: "col-num", text: "Owner's TCE, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE" } }),
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
      figureCell(formatCell(option.charterer_war_risk_usd_t, "usd_t", decimals), "charterer_war_risk_usd_t"),
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
    el("th", { class: "col-num", text: "One way, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Freight to earn P4 net of commission, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "freight" } }),
    el("th", { class: "col-num", text: "Extra freight against Suez, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "extra freight" } }),
    el("th", { class: "col-num", text: "Red Sea premium, the charterer's, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "charterer's premium" } }),
    el("th", { class: "col-num", text: "Tolls and waiting it can bear, " + UNITS.usd, attrs: { scope: "col", "data-short": "budget" } }),
    el("th", { class: "col-num", text: "The same in days of P4 hire after commission, before waiting fuel", attrs: { scope: "col", "data-short": "days of hire" } }),
  ]);
  const body = el("tbody");
  for (const option of sd.options) {
    body.appendChild(el("tr", {}, [
      el("th", { text: option.name, attrs: { scope: "row" } }),
      figureCell(formatCell(option.laden_nm, "nm", decimals), "laden_nm"),
      figureCell(formatCell(option.days, "days", decimals), "days"),
      figureCell(formatCell(option.freight_for_target_usd_t, "usd_t", decimals), "freight_for_target_usd_t"),
      figureCell(formatCell(option.extra_freight_vs_suez_usd_t, "usd_t", decimals, true), "extra_freight_vs_suez_usd_t"),
      figureCell(formatCell(option.charterer_war_risk_usd_t, "usd_t", decimals), "charterer_war_risk_usd_t"),
      figureCell(formatCell(option.toll_and_waiting_budget_usd, "usd", decimals), "toll_and_waiting_budget_usd"),
      figureCell(formatCell(option.waiting_days_budget, "days", decimals), "waiting_days_budget"),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([sd.target + "; " + sd.basis + "."], table)]));
  const list = el("ul", { class: "plain-list" }, sd.options.map((option) => el("li", {}, [option.name + " leaves out " + option.excluded.join("; ") + "."])));
  inner.appendChild(el("div", { class: "block note" }, [list]));
}

function hormuzSection(inner, detours, decimals) {
  const hz = detours.hormuz;
  inner.appendChild(sentence("p", detours.page.hormuz.lead, decimals, "lead block"));
  const head = el("tr", {}, [
    el("th", { text: "Scenario", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Round voyage, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Days inside the Gulf", attrs: { scope: "col", "data-short": "days inside" } }),
    el("th", { class: "col-num", text: "Seven day periods", attrs: { scope: "col", "data-short": "periods" } }),
    el("th", { class: "col-num", text: "War risk premium, the charterer's, " + UNITS.usd, attrs: { scope: "col", "data-short": "premium" } }),
    el("th", { class: "col-num", text: "The same a tonne, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "premium a tonne" } }),
    ...hz.levels.map((level) => el("th", {
      class: "col-num",
      text: "Extra freight the owner needs, " + UNITS.usd_t + ", at the TCE " + level.label + ", " + formatNumber(level.tce_usd_day, "usd_day", decimals) + " a day",
      attrs: { scope: "col", "data-short": detours.page.hormuz.levels_short[level.week_ending] },
    })),
  ]);
  const body = el("tbody");
  for (const scenario of hz.scenarios) {
    body.appendChild(el("tr", {}, [
      el("th", { text: scenario.label, attrs: { scope: "row" } }),
      figureCell(formatCell(scenario.days, "days", decimals), "days"),
      figureCell(formatCell(scenario.days_inside_gulf, "days", decimals), "days_inside_gulf"),
      figureCell(formatCell(scenario.periods, "count", decimals), "periods"),
      figureCell(formatCell(scenario.war_risk_usd, "usd", decimals), "war_risk_usd"),
      figureCell(formatCell(scenario.charterer_war_risk_usd_t, "usd_t", decimals), "charterer_war_risk_usd_t"),
      ...scenario.levels.map((level) => figureCell(formatCell(level.extra_freight_usd_t, "usd_t", decimals, true), "extra_freight_usd_t")),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["TD3C, Ras Tanura to Ningbo, bunkers of the week to " + formatDay(hz.as_of) + "; the premium is the charterer's, and each freight column keeps the Baltic's TD3C TCE of its week."], table)]));
  inner.appendChild(el("p", { class: "note block", text: "Every scenario leaves out " + hz.scenarios[0].excluded.join("; ") + "." }));
  inner.appendChild(sentence("p", detours.page.hormuz.chain, decimals, "prose block"));
}

function methodSection(inner, detours) {
  const block = el("div", { class: "block" }, detours.page.method.map((text) => el("p", { class: "prose", text })));
  inner.appendChild(block);
  const list = el("ul", { class: "plain-list" });
  for (const event of detours.events) {
    list.appendChild(el("li", {}, [el("span", { class: "event__when", text: formatDay(event.date) + ", " + event.area + ". " }), event.text]));
  }
  inner.appendChild(el("div", { class: "block" }, [el("h3", { class: "block__heading", text: detours.page.events_heading }), list]));
}

function assumptionsSection(inner, detours) {
  inner.appendChild(el("ul", { class: "plain-list block" }, detours.page.assumptions.map((text) => el("li", { class: "prose", text }))));
}

function dataSection(inner) {
  inner.appendChild(el("p", { class: "block" }, [el("a", { class: "text-link", text: "The Hormuz scenarios at three dated TCE levels, CSV", attrs: { href: "data/downloads/detours_hormuz.csv" } })]));
}
