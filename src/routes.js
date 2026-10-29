/* routes.js
 *
 * The Routes view: the route library at one common dated market. The key
 * chart is the voyage cost of every route per day of its round voyage, split
 * into the cost families that have a public figure; the table under it gives
 * each route's ship, cargo, commission, distances by routing, the share of its
 * miles inside emission control areas, its port days and its sourced voyage
 * costs.
 * The Gulf loadings are shown again with the Hormuz war risk premium, which
 * would swamp the chart. Method, Assumptions and Data sit behind buttons.
 *
 * Every figure is from data/routes.json.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, UNITS } from "./format.js";
import { barChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["routes"]);

const VIEW = "routes";
let sections = null;

export function render(root, data, route) {
  const routes = data.routes;
  const page = routes.page;
  const decimals = routes.conventions.decimals;
  const title = viewHead(root, page.title, page.takeaway, decimals);

  root.appendChild(chartFigure({
    title: page.chart.title,
    decimals,
    legend: page.chart.legend.map((item) => ({ swatch: item.family, text: item.text })),
    source: page.chart.source,
    draw: (width, titleText) => barChart({
      width,
      rows: routes.rows.map((row) => ({
        id: row.route,
        label: row.label + ", " + row.name,
        group: page.segments[row.segment],
        segments: [
          { value: row.costs_usd.bunkers / row.days, family: "bunkers" },
          { value: row.costs_usd.ets / row.days, family: "ets" },
        ],
        valueText: formatNumber(row.per_day_usd, "usd_day", decimals),
        tip: [
          row.label + ", " + row.name,
          page.chart.legend[0].text + ": USD " + formatNumber(row.costs_usd.bunkers / row.days, "usd_day", decimals, { context: "prose" }) + " a day",
          page.chart.legend[1].text + ": USD " + formatNumber(row.costs_usd.ets / row.days, "usd_day", decimals, { context: "prose" }) + " a day",
          "Round voyage: " + formatNumber(row.days, "days", decimals) + " " + UNITS.days,
        ],
      })),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  // The routes on the Baltic routes map, under the chart so the takeaway leads straight to it.
  root.appendChild(el("p", { class: "note block" }, [
    page.chart.note + " ",
    page.baltic_map.before,
    el("a", { class: "text-link", text: page.baltic_map.link, attrs: { href: routes.baltic_map_url } }),
    page.baltic_map.after,
  ]));
  root.appendChild(el("div", { class: "block" }, [routeTable(routes, decimals)]));
  root.appendChild(hormuzBlock(routes, decimals));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    method: (inner) => paragraphs(inner, page.method),
    assumptions: (inner) => assumptions(inner, routes),
    data: (inner) => dataSection(inner, routes, decimals),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function paragraphs(inner, list) {
  inner.appendChild(el("div", { class: "block" }, list.map((text) => el("p", { class: "prose", text }))));
}

function routeTable(routes, decimals) {
  const scale = routes.conventions.scale;
  const head = el("tr", {}, [
    el("th", { text: "Route", attrs: { scope: "col" } }),
    el("th", { text: "Ship", attrs: { scope: "col", "data-short": "ship" } }),
    el("th", { class: "col-num", text: "Cargo, " + UNITS.t, attrs: { scope: "col", "data-short": "cargo" } }),
    el("th", { class: "col-num", text: "Commission, percent", attrs: { scope: "col", "data-short": "commission" } }),
    el("th", { text: "Laden distance by routing, " + UNITS.nm, attrs: { scope: "col", "data-short": "distance by routing" } }),
    el("th", { class: "col-num", text: "Miles inside ECAs, percent", attrs: { scope: "col", "data-short": "ECA miles" } }),
    el("th", { text: "Port days: loading, discharging, waiting", attrs: { scope: "col", "data-short": "port days" } }),
    el("th", { class: "col-num", text: "Round voyage, days", attrs: { scope: "col", "data-short": "days" } }),
    el("th", { class: "col-num", text: "Sourced voyage costs, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "voyage costs" } }),
    el("th", { class: "col-num", text: "EU allowances, percent of sourced costs", attrs: { scope: "col", "data-short": "EU allowances" } }),
    el("th", { text: "Bunker hub", attrs: { scope: "col", "data-short": "bunker hub" } }),
  ]);
  const body = el("tbody");
  for (const row of routes.rows) {
    const routings = row.by_routing.map((r) => r.label + ": " + formatNumber(r.laden_nm, "nm", routes.conventions.decimals) + (r.priced ? " " + routes.page.priced_mark : "")).join("; ");
    const port = row.port_days;
    const portDays = [port.load_days, port.discharge_days, port.waiting_days].map((d) => formatNumber(d, "days_2", decimals));
    if (row.load_turn_only) portDays[0] += " " + routes.page.turn_time_mark;
    body.appendChild(el("tr", { attrs: { "data-route": row.route } }, [
      el("th", { attrs: { scope: "row" } }, [el("span", { class: "row-code", text: row.label }), el("span", { class: "row-name", text: row.name })]),
      el("td", { class: "nowrap", text: row.vessel }),
      figureCell(formatCell(row.cargo_t, "t", decimals), "cargo_t", { missing: row.contract === "trip" ? "a trip, hire by the day" : null }),
      figureCell(formatCell(row.commission_pct, "percent_2", decimals), "commission_pct"),
      el("td", { class: "words", text: routings }),
      figureCell(formatCell(row.eca_share * scale.percent, "percent", decimals), "eca_share"),
      el("td", { class: "words", text: portDays.join(", ") }),
      figureCell(formatCell(row.days, "days", decimals), "days"),
      figureCell(formatCell(row.per_day_usd, "usd_day", decimals), "per_day_usd"),
      figureCell(formatCell(row.shares.ets * scale.percent, "percent", decimals), "shares.ets"),
      el("td", { class: "nowrap", text: row.hub_name }),
    ]));
  }
  const table = el("table", { class: "table table--routes" }, [el("thead", {}, [head]), body]);
  return scrollTable([routes.page.table_caption], table);
}

function hormuzBlock(routes, decimals) {
  const page = routes.page;
  const scale = routes.conventions.scale;
  const rows = routes.rows.filter((row) => row.with_hormuz_war_risk);
  const head = el("tr", {}, [
    el("th", { text: "Route", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Hull value, " + UNITS.usd_m, attrs: { scope: "col", "data-short": "hull value" } }),
    el("th", { class: "col-num", text: "Days inside the Gulf", attrs: { scope: "col", "data-short": "days inside" } }),
    el("th", { class: "col-num", text: "Seven day periods", attrs: { scope: "col", "data-short": "periods" } }),
    el("th", { class: "col-num", text: "War risk premium, the charterer's, " + UNITS.usd, attrs: { scope: "col", "data-short": "premium" } }),
    el("th", { class: "col-num", text: "The same a tonne of cargo, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "premium a tonne" } }),
    el("th", { class: "col-num", text: "Premium over the voyage's bunkers, times", attrs: { scope: "col", "data-short": "premium over bunkers" } }),
  ]);
  const body = el("tbody");
  for (const row of rows) {
    const w = row.with_hormuz_war_risk;
    const cells = [el("th", { attrs: { scope: "row" } }, [el("span", { class: "row-code", text: row.label }), el("span", { class: "row-name", text: row.name })])];
    if (w.hull_value_usd) {
      cells.push(
        figureCell(formatCell(w.hull_value_usd / scale.million, "usd_m", decimals), "hull_value_usd"),
        figureCell(formatCell(w.days_inside, "days", decimals), "days_inside"),
        figureCell(formatCell(w.periods, "count", decimals), "periods"),
        figureCell(formatCell(w.premium_usd, "usd", decimals), "premium_usd"),
        figureCell(formatCell(w.per_tonne_usd, "usd_t", decimals), "per_tonne_usd"),
        figureCell(formatCell(w.premium_to_bunkers, "exponent", decimals), "premium_to_bunkers"),
      );
    } else {
      cells.push(el("td", { class: "num is-missing", text: w.why_empty, attrs: { colspan: String(head.children.length - 1) } }));
    }
    body.appendChild(el("tr", {}, cells));
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
  return el("div", { class: "block" }, [
    el("h2", { class: "block__heading", text: page.hormuz.title }),
    sentence("p", page.hormuz.lead, decimals, "prose"),
    scrollTable([page.hormuz.caption], table),
  ]);
}

function assumptions(inner, routes) {
  paragraphs(inner, routes.page.assumptions);
  const list = el("ul", { class: "plain-list" });
  for (const row of routes.rows) {
    list.appendChild(el("li", {}, [el("span", { class: "row-code", text: row.label + ". " }), "Leaves out " + row.excluded.join("; ") + "."]));
  }
  inner.appendChild(el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "What each TCE leaves out" }), list]));
}

function dataSection(inner, routes, decimals) {
  const scale = routes.conventions.scale;
  const head = el("tr", {}, [
    el("th", { text: "Pair", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: routes.page.pub151.published_head + ", " + UNITS.nm, attrs: { scope: "col", "data-short": routes.page.pub151.published_head } }),
    el("th", { class: "col-num", text: "Searoute, " + UNITS.nm, attrs: { scope: "col", "data-short": "searoute" } }),
    el("th", { class: "col-num", text: "Difference, percent", attrs: { scope: "col", "data-short": "difference" } }),
    el("th", { text: routes.page.pub151.within_head, attrs: { scope: "col", "data-short": "within" } }),
    el("th", { text: "How the published figure is built", attrs: { scope: "col", "data-short": "note" } }),
  ]);
  const body = el("tbody");
  for (const check of routes.pub151.checks) {
    body.appendChild(el("tr", {}, [
      el("th", { text: check.pair_words, attrs: { scope: "row" } }),
      figureCell(formatCell(check.published_nm, "nm", decimals), "published_nm"),
      figureCell(formatCell(check.searoute_nm, "nm", decimals), "searoute_nm"),
      // Two decimals, so a check just outside the 2 percent line does not read as on it.
      figureCell(formatCell(check.error * scale.percent, "percent_2", decimals, true), "error"),
      el("td", { text: check.within_tolerance ? "Yes" : "No" }),
      el("td", { class: "words", text: check.note || (check.parts || []).map((part) => part.entry + ", " + part.line + ", page " + String(part.page)).join("; ") }),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([routes.page.pub151.caption], table)]));
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: routes.page.downloads_words }),
    el("ul", { class: "plain-list" }, routes.page.downloads.map((d) => el("li", {}, [el("a", { class: "text-link", text: d.text, attrs: { href: d.file } })]))),
  ]));
}
