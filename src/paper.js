/* paper.js
 *
 * The Paper view: the physical fixture against the FFA. The key chart sets,
 * for each anchor week and Capesize route, the voyage's TCE beside the 5TC FFA
 * for the voyage month and the spot 5TC average of the week, on one axis in
 * dollars a day; the rule between the first two is the basis. Then a fixture
 * against its index, and behind buttons the hedges, the tanker comparison,
 * the settlement rules and the curves as assessed.
 *
 * Every figure is from data/paper.json.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, formatDay, UNITS } from "./format.js";
import { dotChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["paper"]);

const VIEW = "paper";
let sections = null;

export function render(root, data, route) {
  const paper = data.paper;
  const page = paper.page;
  const decimals = paper.conventions.decimals;
  const title = viewHead(root, page.title, page.takeaway, decimals);
  const day = (value) => formatNumber(value, "usd_day", decimals) + " " + UNITS.usd_day;
  const [physical, ffa, spot] = page.chart.legend;

  root.appendChild(chartFigure({
    title: page.chart.title,
    decimals,
    legend: page.chart.legend.map((item) => ({ swatch: item.kind === "ink" ? "ink swatch--dot" : item.kind, text: item.text })),
    source: page.chart.source,
    draw: (width, titleText) => dotChart({
      width,
      rows: paper.capesize.map((row) => ({
        id: row.route + row.date,
        label: row.route + ", " + formatDay(row.date),
        group: null,
        dots: [
          { value: row.spot_index_usd_day, className: "mark-context-fill" },
          { value: row.ffa.usd_day, className: "mark-printed" },
          { value: row.physical_tce_usd_day, className: "mark-series-fill" },
        ],
        span: { from: row.physical_tce_usd_day, to: row.ffa.usd_day },
        tip: [
          row.route + ", " + formatDay(row.date) + ", at " + formatNumber(row.freight_usd_t, "usd_t", decimals) + " " + UNITS.usd_t,
          physical.text + ": " + day(row.physical_tce_usd_day),
          ffa.text + " (" + formatDay(row.ffa.period) + "): " + day(row.ffa.usd_day),
          spot.text + ": " + day(row.spot_index_usd_day),
        ],
      })),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  root.appendChild(el("div", { class: "block" }, [sentence("p", page.fixture.lead, decimals, "prose")]));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    hedge: (inner) => hedgeSection(inner, paper, decimals),
    tankers: (inner) => tankerSection(inner, paper, decimals),
    method: (inner) => methodSection(inner, paper),
    data: (inner) => curvesSection(inner, paper, decimals),
  }), decimals, route);
  root.appendChild(sections.node);
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
}

function hedgeSection(inner, paper, decimals) {
  // The column heads name the contracts, so they are the artifact's words.
  const head = el("tr", {}, paper.page.hedge_columns.map((column, at) => el("th", {
    class: at === 0 || column.words ? "" : "col-num",
    text: column.text,
    attrs: { scope: "col", "data-short": column.short },
  })));
  const body = el("tbody");
  for (const row of paper.capesize) {
    body.appendChild(el("tr", {}, [
      el("th", { text: row.route + ", " + formatDay(row.date), attrs: { scope: "row" } }),
      figureCell(formatCell(row.freight_usd_t, "usd_t", decimals), "freight_usd_t"),
      figureCell(formatCell(row.physical_tce_usd_day, "usd_day", decimals), "physical_tce_usd_day"),
      el("td", { class: "nowrap", text: formatDay(row.ffa.period) }),
      figureCell(formatCell(row.ffa.usd_day, "usd_day", decimals), "ffa.usd_day"),
      figureCell(formatCell(row.basis_usd_day, "usd_day", decimals, true), "basis_usd_day"),
      figureCell(formatCell(row.freight_matching_ffa_usd_t, "usd_t", decimals), "freight_matching_ffa_usd_t"),
      figureCell(formatCell(row.spot_index_usd_day, "usd_day", decimals), "spot_index_usd_day"),
      figureCell(formatCell(row.timing_basis_usd_day, "usd_day", decimals, true), "timing_basis_usd_day"),
      figureCell(formatCell(row.hedge_days, "days", decimals), "hedge_days"),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["Each anchor week: the physical TCE, the FFA for the voyage month, the basis between them, the freight that would earn the FFA, the spot average, the timing basis and the hedge."], table)]));
  const f = paper.c5_fixture;
  const fixture = el("table", { class: "table" }, [
    el("thead", {}, [el("tr", {}, [
      el("th", { text: "C5", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: UNITS.usd_t, attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "TCE, " + UNITS.usd_day, attrs: { scope: "col" } }),
    ])]),
    el("tbody", {}, [
      el("tr", {}, [el("th", { text: "Fixture, " + formatDay(f.date) + ", " + f.laycan, attrs: { scope: "row" } }), figureCell(formatCell(f.fixture_usd_t, "usd_t", decimals), "fixture_usd_t"), figureCell(formatCell(f.fixture_tce_usd_day, "usd_day", decimals), "fixture_tce_usd_day")]),
      el("tr", {}, [el("th", { text: "C5 index", attrs: { scope: "row" } }), figureCell(formatCell(f.index_usd_t, "usd_t", decimals), "index_usd_t"), figureCell(formatCell(f.index_tce_usd_day, "usd_day", decimals), "index_tce_usd_day")]),
      el("tr", { class: "is-total" }, [el("th", { text: "Basis", attrs: { scope: "row" } }), figureCell(formatCell(f.basis_usd_t, "usd_t", decimals, true), "basis_usd_t"), figureCell(formatCell(f.basis_usd_day, "usd_day", decimals, true), "basis_usd_day")]),
    ]),
  ]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["A fixture against the index it would be hedged with."], fixture)]));
}

function tankerSection(inner, paper, decimals) {
  inner.appendChild(sentence("p", paper.page.td3c.lead, decimals, "lead block"));
}

function methodSection(inner, paper) {
  inner.appendChild(el("div", { class: "block" }, paper.page.method.map((text) => el("p", { class: "prose", text }))));
  const head = el("tr", {}, [
    el("th", { text: "Contract", attrs: { scope: "col" } }),
    el("th", { text: "Unit", attrs: { scope: "col", "data-short": "unit" } }),
    el("th", { text: "Settles on", attrs: { scope: "col", "data-short": "settlement" } }),
  ]);
  const body = el("tbody");
  for (const row of paper.settlement) {
    body.appendChild(el("tr", {}, [
      el("th", { text: row.contract, attrs: { scope: "row" } }),
      el("td", { class: "words", text: row.unit }),
      el("td", { class: "words", text: row.rule }),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable(["How each FFA settles, from the exchanges' contract specifications."], table)]));
}

function curvesSection(inner, paper, decimals) {
  for (const curve of paper.curves) {
    const segments = Object.entries(curve.segments);
    const periods = [...new Set(segments.flatMap(([, s]) => s.points.map((p) => p.period)))];
    const head = el("tr", {}, [
      el("th", { text: "Period", attrs: { scope: "col" } }),
      ...segments.map(([name, s]) => el("th", { class: "col-num", text: name.charAt(0).toUpperCase() + name.slice(1) + ", " + s.index + ", " + UNITS.usd_day, attrs: { scope: "col", "data-short": name } })),
    ]);
    const body = el("tbody");
    for (const period of periods) {
      body.appendChild(el("tr", {}, [
        el("th", { text: formatDay(period), attrs: { scope: "row" } }),
        ...segments.map(([, s]) => {
          const point = s.points.find((p) => p.period === period);
          return figureCell(point ? formatCell(point.usd_day, "usd_day", decimals) : null, "usd_day", { missing: "not assessed" });
        }),
      ]));
    }
    const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
    inner.appendChild(el("div", { class: "block" }, [scrollTable([curve.source + ", assessed " + formatDay(curve.assessed) + "."], table)]));
  }
}
