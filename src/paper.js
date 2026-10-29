/* paper.js
 *
 * The Paper view: the physical fixture against the FFA. The key chart sets,
 * for each anchor week and Capesize route, the voyage's TCE grossed up by its
 * commission beside the 5TC FFA over the voyage's days and the spot 5TC on
 * the fixture date, on one axis in dollars a day; the rule between the first
 * two is the basis. Then a fixture against its index, a box that converts a
 * route FFA typed in dollars a tonne into a TCE with the browser engine, and
 * behind buttons the hedges, the tanker figures, the settlement rules, the
 * assumptions and the curves as printed.
 *
 * Every figure is from data/paper.json, or the engine's output for its inputs.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable, figureCell } from "./dom.js";
import { formatCell, formatNumber, formatDay, UNITS } from "./format.js";
import { dotChart } from "./charts.js";
import { chartFigure, viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";
import * as engine from "./engine.js";

export const artifacts = Object.freeze(["paper", "engine"]);

const VIEW = "paper";
let sections = null;

export function render(root, data, route) {
  const paper = data.paper;
  const page = paper.page;
  const decimals = paper.conventions.decimals;
  engine.configure(data.engine.constants);
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
          { value: row.spot_182_usd_day, className: "mark-context-fill" },
          { value: row.physical_tce_gross_usd_day, className: "mark-series-fill" },
          { value: row.ffa.usd_day, className: "mark-printed" },
        ],
        span: {
          from: row.physical_tce_gross_usd_day,
          to: row.ffa.usd_day,
          label: page.chart.basis_label.replace("{basis}", formatNumber(row.basis_usd_day, "usd_day", decimals, { signed: true })),
        },
        tip: [
          row.route + ", " + formatDay(row.date) + ", at " + formatNumber(row.freight_usd_t, "usd_t", decimals) + " " + UNITS.usd_t,
          physical.text + ": " + day(row.physical_tce_gross_usd_day) + " (" + day(row.physical_tce_usd_day) + " net)",
          ffa.text + ", curve of " + formatDay(row.ffa.dated) + ": " + day(row.ffa.usd_day),
          spot.text + ": " + day(row.spot_182_usd_day),
        ],
      })),
      words: { title: titleText, desc: page.chart.desc, axis: page.chart.axis },
    }),
  }));

  root.appendChild(el("div", { class: "block" }, [sentence("p", page.fixture.lead, decimals, "prose")]));

  sections = buildSections(VIEW, withBuilders(page.sections, {
    hedge: (inner) => {
      inner.appendChild(routeFfaBox(paper, decimals, data.engine.constants.PERCENT));
      hedgeSection(inner, paper, decimals);
    },
    tankers: (inner) => tankerSection(inner, paper, decimals),
    method: (inner) => methodSection(inner, paper),
    assumptions: (inner) => assumptionsSection(inner, paper, decimals),
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
      figureCell(formatCell(row.physical_tce_gross_usd_day, "usd_day", decimals), "physical_tce_gross_usd_day"),
      el("td", { class: "words", text: paper.page.months_words[row.route + " " + row.date] }),
      figureCell(formatCell(row.ffa.usd_day, "usd_day", decimals), "ffa.usd_day"),
      figureCell(formatCell(row.basis_usd_day, "usd_day", decimals, true), "basis_usd_day"),
      otherPrint(row, decimals),
      figureCell(formatCell(row.freight_matching_ffa_usd_t, "usd_t", decimals), "freight_matching_ffa_usd_t"),
      figureCell(formatCell(row.spot_182_usd_day, "usd_day", decimals), "spot_182_usd_day"),
      figureCell(formatCell(row.timing_basis_usd_day, "usd_day", decimals, true), "timing_basis_usd_day"),
      figureCell(formatCell(row.hedge_days, "days", decimals), "hedge_days"),
      figureCell(formatCell(row.hedge_days_net, "days", decimals), "hedge_days_net"),
    ]));
  }
  const table = el("table", { class: "table table--wide" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([paper.page.hedge_caption], table)]));
  const f = paper.c5_fixture;
  const line = (label, usdT, tce, field, signed) => el("tr", signed ? { class: "is-total" } : {}, [
    el("th", { text: label, attrs: { scope: "row" } }),
    figureCell(formatCell(usdT, "usd_t", decimals, signed), field + "_usd_t"),
    figureCell(tce === null ? null : formatCell(tce, "usd_day", decimals, signed), field + "_usd_day", { missing: "not priced" }),
  ]);
  const fixture = el("table", { class: "table" }, [
    el("thead", {}, [el("tr", {}, [
      el("th", { text: "C5", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: UNITS.usd_t, attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "TCE, " + UNITS.usd_day, attrs: { scope: "col" } }),
    ])]),
    el("tbody", {}, [
      line("Fixture, " + formatDay(f.date) + ", " + f.laycan, f.fixture_usd_t, f.fixture_tce_usd_day, "fixture"),
      line("The route that day, the report's narrative", f.route_on_day_usd_t, f.route_on_day_tce_usd_day, "route_on_day"),
      line("Basis on the day", f.basis_usd_t, f.basis_usd_day, "basis", true),
      line("C5 index, " + formatDay(f.next_day) + ", the report's table", f.index_next_day_usd_t, f.index_next_day_tce_usd_day, "index_next_day"),
      line("The same close in the report's narrative", f.narrative_next_day_usd_t, null, "narrative_next_day"),
      line("Basis on the day on the table's series", f.basis_table_series_usd_t, f.basis_table_series_usd_day, "basis_table_series", true),
    ]),
  ]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([paper.page.fixture.table_caption], fixture)]));
}

/* The basis on the curve's other print, where the same date was printed twice. */
function otherPrint(row, decimals) {
  const other = row.printings.find((p) => !p.used);
  return figureCell(other ? formatCell(other.basis_usd_day, "usd_day", decimals, true) : null, "other_print_basis_usd_day", { missing: "one print" });
}

/* A route FFA typed in dollars a tonne, priced on an anchor voyage by the
 * browser engine: the TCE net and grossed up, against the 5TC (182) strip. */
function routeFfaBox(paper, decimals, percent) {
  const words = paper.page.route_ffa;
  const select = el("select", { class: "field__select", id: "field-route-ffa-voyage" });
  paper.capesize.forEach((row, index) => select.appendChild(el("option", { text: row.route + ", " + formatDay(row.date), attrs: { value: String(index) } })));
  const input = el("input", { class: "field__input", id: "field-route-ffa", attrs: { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false" } });
  const out = el("p", { class: "field__source route-ffa__result", attrs: { role: "status" }, text: words.empty });
  const usd = (value, format) => "USD " + formatNumber(value, format, decimals, { context: "prose" });
  const draw = () => {
    const typed = input.value.replace(/,/g, "").trim();
    if (typed === "") {
      out.textContent = words.empty;
      return;
    }
    const value = Number(typed);
    if (!Number.isFinite(value)) {
      out.textContent = words.invalid;
      return;
    }
    const row = paper.capesize[Number(select.value)];
    const net = engine.evaluate({ ...row.inputs, freight_basis: "usd_t", freight_value: value }).tce_usd_day;
    const gross = net / (1 - row.commission_pct / percent);
    const basis = gross - row.ffa.usd_day;
    out.textContent = words.result
      .replace("{ffa}", usd(value, "usd_t"))
      .replace("{net}", usd(net, "usd_day"))
      .replace("{gross}", usd(gross, "usd_day"))
      .replace("{basis}", usd(Math.abs(basis), "usd_day"))
      .replace("{side}", basis < 0 ? "below" : "above")
      .replace("{strip}", usd(row.ffa.usd_day, "usd_day"));
  };
  input.addEventListener("input", draw);
  select.addEventListener("change", draw);
  return el("div", { class: "block route-ffa" }, [
    el("h3", { class: "block__heading", text: words.title }),
    el("p", { class: "prose", text: words.lead }),
    el("div", { class: "calc-fields route-ffa__fields" }, [
      el("div", { class: "field" }, [el("label", { class: "field__label", text: words.voyage_label, attrs: { for: "field-route-ffa-voyage" } }), select]),
      el("div", { class: "field field--wide" }, [el("label", { class: "field__label", text: words.ffa_label, attrs: { for: "field-route-ffa" } }), el("div", { class: "field__row" }, [input, el("span", { class: "field__unit", text: UNITS.usd_t })])]),
    ]),
    out,
  ]);
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

function assumptionsSection(inner, paper, decimals) {
  inner.appendChild(el("div", { class: "block" }, paper.page.assumptions.map((segments) => sentence("p", segments, decimals, "prose"))));
}

/* Each curve as its report prints it: the Capesize columns of the report's
 * date and of the previous date beside it, with the columns an anchor week's
 * strip is read from named in the caption. */
function curvesSection(inner, paper, decimals) {
  for (const curve of paper.curves) {
    const segment = curve.segments.capesize;
    const columns = [["usd_day", curve.assessed], ["previous_usd_day", curve.previous]];
    const head = el("tr", {}, [
      el("th", { text: "Period", attrs: { scope: "col" } }),
      ...columns.map(([, dated]) => el("th", { class: "col-num", text: segment.index + ", " + formatDay(dated) + ", " + UNITS.usd_day, attrs: { scope: "col", "data-short": formatDay(dated) } })),
    ]);
    const body = el("tbody");
    for (const point of segment.points) {
      body.appendChild(el("tr", {}, [
        el("th", { text: formatDay(point.period), attrs: { scope: "row" } }),
        ...columns.map(([column]) => figureCell(point[column] === undefined ? null : formatCell(point[column], "usd_day", decimals), column, { missing: "not printed" })),
      ]));
    }
    const used = paper.capesize.flatMap((row) => row.printings
      .filter((p) => p.used && p.curve === curve.id)
      .map((p) => row.route + ", " + formatDay(row.date) + ", the " + formatDay(p.column === "usd_day" ? curve.assessed : curve.previous) + " column"));
    const caption = curve.source + ", printed at " + formatDay(curve.assessed) + " beside its previous column of " + formatDay(curve.previous) + ". "
      + (used.length ? "The strips read: " + used.join("; ") + "." : "No anchor week's strip reads this print; the hedge table gives the basis on it.");
    const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
    inner.appendChild(el("div", { class: "block" }, [scrollTable([caption], table)]));
  }
}
