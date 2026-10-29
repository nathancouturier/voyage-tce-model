/* calculator.js
 *
 * The calculator: price any study voyage. A route and a dated market are
 * chosen as presets; every input sits in one of five steps (Ship, Route,
 * Market, Costs, Advanced), each opened by its own button; every change runs
 * the engine again and redraws the outputs: the TCE sentence, the freight that
 * earns a target TCE in the units a desk quotes, the bridge, the sensitivities
 * and the TCE against speed.
 *
 * WHERE THE NUMBERS COME FROM. Every input starts from data/calculator.json,
 * where the export wrote it with its status and source: sourced (a dated
 * public document), derived (a stated rule on sourced values) or empty (no
 * public figure; it counts as zero and the result says it is left out). A
 * field the visitor edits says "Your figure" and gains a Reset button. The
 * outputs are computed here, by src/engine.js, the browser copy of the Python
 * engine (tools/validate-engine.mjs holds the two to 1e-9); the words around
 * them are the artifact's, with {name} filled by the figure computed.
 *
 * THE ADDRESS. #/calculator?preset=latest-c3&open=market keeps the preset and
 * the open steps, so a priced voyage can be linked; edits to single fields are
 * not written to the address.
 *
 * Numeric literals: none.
 */

import { el, clear, sentence, appendSegments, scrollTable, figureCell } from "./dom.js";
import { formatNumber, formatCell, formatDay, listWords, UNITS, MINUS_PROSE } from "./format.js";
import { onWidthChange, tornadoChart, lineChart, tooltip, niceDomain, GEOMETRY } from "./charts.js";
import * as engine from "./engine.js";
import * as router from "./router.js";
import { bridgeTable } from "./bridge.js";
import { buildSections, withBuilders } from "./sections.js";

export const artifacts = Object.freeze(["calculator", "engine", "speed"]);

const VIEW = "calculator";

const FAMILIES = Object.freeze({ bunkers: "bunkers", ports: "ports", canals: "canals", ets: "ets", war_risk: "war", other: "other", fueleu: "other" });

/* The state of the view: the artifacts, the preset, the working copy of its
 * inputs, the paths the visitor changed, and the live parts of the page. */
let data = null;
let calc = null;
let decimals = null;
let preset = null;
let inputs = null;
let changed = new Set();
let target = 0;
let live = {};
let stepSections = null;
let lowerSections = null;
let rootNode = null;

/* ------------------------------------------------------------ helpers --- */

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function get(object, path) {
  return path.split(".").reduce((node, key) => (node === null || node === undefined ? undefined : node[key]), object);
}

function set(object, path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  const parent = keys.reduce((node, key) => node[key], object);
  parent[last] = value;
}

/** "{tce} a day" with each {name} replaced by its text. */
function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, (all, name) => (Object.prototype.hasOwnProperty.call(values, name) ? values[name] : all));
}

function usdText(value, format) {
  const body = formatNumber(value, format || "usd", decimals, { context: "prose" });
  return body === null ? null : "USD " + body;
}

/** A sum of money in words: millions from a million up, dollars below. */
function moneyText(value) {
  const million = calc.conventions.scale.million;
  if (Math.abs(value) >= million) {
    return fill(calc.words.million, { value: formatNumber(value / million, "usd_m", decimals, { context: "prose" }) });
  }
  return usdText(value, "usd");
}

/** A number typed into a field: grouping commas and spaces ignored, the minus
 *  sign read as a minus. null for an empty field, NaN for anything else. */
function parse(text) {
  const clean = String(text).replace(/[,\s]/g, "").replace(MINUS_PROSE, "-");
  if (clean === "") return null;
  return Number(clean);
}

function display(value, format, scale) {
  if (value === null || value === undefined) return "";
  return formatNumber(value * (scale || 1), format, decimals, { context: "table" }) || "";
}

function sourceOf(path) {
  if (changed.has(path)) return { status: "changed", source: calc.words.changed };
  const cited = preset.sources[path];
  if (cited) return cited;
  return { status: "scenario", source: calc.words.not_cited };
}

function freightFormat() {
  const basis = calc.freight_bases.find((b) => b.id === inputs.freight_basis);
  return basis ? basis.format : "usd_t";
}

/** Whether the engine can price the inputs as they stand, or why not. */
function readiness() {
  // A Worldscale basis without a flat rate is said first: points typed
  // without one could not be priced either.
  if (inputs.freight_basis === "ws" && !inputs.flat_rate_usd_t) return { ok: false, why: calc.words.ws_missing };
  if (inputs.freight_value === null || inputs.freight_value === undefined || Number.isNaN(inputs.freight_value)) return { ok: false, why: calc.words.no_freight };
  return { ok: true };
}

/* ------------------------------------------------------------- render --- */

export function render(root, artifactsData, route) {
  data = artifactsData;
  calc = data.calculator;
  decimals = calc.conventions.decimals;
  engine.configure(data.engine.constants);
  rootNode = root;

  const asked = route && route.params ? route.params.preset : null;
  preset = calc.presets.find((p) => p.id === asked) || calc.presets.find((p) => p.id === calc.default_preset);
  inputs = clone(preset.inputs);
  changed = new Set();
  target = calc.target_tce.value;
  live = {};

  const title = el("h1", { class: "view-title", id: "view-title", text: calc.title, attrs: { tabindex: "-1" } });
  root.appendChild(title);
  root.appendChild(sentence("p", calc.lead, decimals, "lead block"));
  root.appendChild(presetChoices());

  const notes = el("p", { class: "source-line preset-note" }, [preset.title + ". " + preset.notes.join(" ")]);
  root.appendChild(notes);

  const inputsColumn = el("div", { class: "calc__inputs" });
  const outputsColumn = el("div", { class: "calc__outputs", attrs: { "aria-live": "off" } });
  root.appendChild(el("div", { class: "calc" }, [inputsColumn, outputsColumn]));

  stepSections = buildSections(VIEW, calc.steps.map((step) => ({
    id: step.id,
    name: step.label,
    summary: [step.summary],
    build: (inner) => buildStep(inner, step.id),
  })), decimals, route);
  stepSections.node.classList.add("calc-steps");
  inputsColumn.appendChild(stepSections.node);

  buildOutputs(outputsColumn);

  lowerSections = buildSections(VIEW, withBuilders(calc.sections, {
    method: (inner) => methodSection(inner),
    speed: (inner) => speedSection(inner),
    data: (inner) => dataSection(inner),
  }), decimals, route);
  root.appendChild(lowerSections.node);

  recompute();
  return title;
}

export function update(root, route) {
  const asked = route && route.params ? route.params.preset : null;
  if (asked && preset && asked !== preset.id) {
    rerender(route);
    return;
  }
  if (stepSections) stepSections.update(route);
  if (lowerSections) lowerSections.update(route);
}

function rerender(route) {
  clear(rootNode);
  const title = render(rootNode, data, route);
  title.focus({ preventScroll: true });
}

/* ------------------------------------------------------------ presets --- */

function presetChoices() {
  const routeRow = el("div", { class: "choice-row", attrs: { role: "group", "aria-label": calc.words.route_label } });
  for (const item of calc.route_order) {
    // A route opens on its latest dated preset.
    const first = calc.presets.filter((p) => p.route === item.code).reduce((a, b) => (b.date > a.date ? b : a));
    const button = el("button", {
      class: "choice",
      text: item.label,
      attrs: { type: "button", "aria-pressed": item.code === preset.route ? "true" : "false", "data-route": item.code },
    });
    button.addEventListener("click", () => choose(first.id));
    routeRow.appendChild(button);
  }
  const marketRow = el("div", { class: "choice-row", attrs: { role: "group", "aria-label": calc.words.market_label } });
  for (const p of calc.presets.filter((q) => q.route === preset.route)) {
    const button = el("button", {
      class: "choice",
      text: p.market_label,
      attrs: { type: "button", "aria-pressed": p.id === preset.id ? "true" : "false", "data-preset": p.id },
    });
    button.addEventListener("click", () => choose(p.id));
    marketRow.appendChild(button);
  }
  return el("div", { class: "presets" }, [
    el("div", { class: "choice-group" }, [el("p", { class: "choice-group__label", text: calc.words.route_label }), routeRow]),
    el("div", { class: "choice-group" }, [el("p", { class: "choice-group__label", text: calc.words.market_label }), marketRow]),
  ]);
}

function choose(id) {
  const params = { ...(router.current().params || {}), preset: id };
  router.replaceState(VIEW, params);
  rerender(router.current());
}

/* -------------------------------------------------------------- steps --- */

function buildStep(inner, stepId) {
  const fieldset = el("fieldset", { class: "calc-fields" }, [el("legend", { class: "visually-hidden", text: calc.steps.find((s) => s.id === stepId).label })]);
  if (stepId === "ship") shipExtras(fieldset);
  if (stepId === "route") routeExtras(fieldset);
  if (stepId === "market") marketExtras(fieldset);
  for (const spec of calc.fields.filter((f) => f.step === stepId)) {
    if (spec.path === "freight_value") continue; // drawn with its basis in marketExtras
    if (spec.path === "prices.hsfo_usd_t" && !inputs.scrubber) {
      fieldset.appendChild(numberField(spec, { note: true }));
      continue;
    }
    fieldset.appendChild(numberField(spec));
  }
  if (stepId === "costs") warRates(fieldset);
  if (stepId === "advanced") advancedExtras(fieldset);
  inner.appendChild(fieldset);
}

/** A field a figure is typed into, with its unit, its source and a Reset. */
function numberField(spec, options) {
  const opts = options || {};
  const id = "field-" + spec.path.replace(/\./g, "-");
  const sourceId = id + "-source";
  const format = spec.path === "freight_value" ? freightFormat() : spec.format;
  const scale = spec.scale || 1;
  const wrapper = el("div", { class: "field" + (opts.wide ? " field--wide" : ""), attrs: { "data-path": spec.path } });
  const input = el("input", {
    class: "field__input",
    id,
    attrs: { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false", "aria-describedby": sourceId },
  });
  const source = el("p", { class: "field__source", id: sourceId });
  const reset = el("button", { class: "field__reset", text: calc.words.reset, attrs: { type: "button" } });
  const unit = spec.path === "freight_value" ? UNITS[format] : spec.unit;

  const paint = () => {
    const info = sourceOf(spec.path);
    wrapper.setAttribute("data-status", info.status);
    const value = get(inputs, spec.path);
    const emptyNow = info.status === "empty" && !value;
    input.value = emptyNow ? "" : display(value, format, scale);
    input.placeholder = info.status === "empty" ? calc.words.empty_placeholder : "";
    const words = calc.status_words[info.status];
    source.replaceChildren(...(words ? [el("span", { class: "field__status", text: words + ". " })] : []), info.source);
    reset.hidden = !changed.has(spec.path);
  };

  input.addEventListener("input", () => {
    const value = parse(input.value);
    const info = preset.sources[spec.path];
    if (value === null) {
      // An emptied field returns to its source when that source is empty;
      // anything else needs a number.
      if (info && info.status === "empty") {
        set(inputs, spec.path, get(preset.inputs, spec.path) === null ? null : 0);
        changed.delete(spec.path);
        wrapper.setAttribute("data-status", "empty");
        source.replaceChildren(el("span", { class: "field__status", text: calc.status_words.empty + ". " }), info.source);
        reset.hidden = true;
        recompute();
        return;
      }
      source.replaceChildren(el("span", { class: "field__status", text: calc.words.invalid }));
      return;
    }
    if (Number.isNaN(value)) {
      source.replaceChildren(el("span", { class: "field__status", text: calc.words.invalid }));
      return;
    }
    set(inputs, spec.path, value / scale);
    changed.add(spec.path);
    wrapper.setAttribute("data-status", "changed");
    source.replaceChildren(el("span", { class: "field__status", text: calc.status_words.changed + ". " }), sourceLine(spec.path));
    reset.hidden = false;
    recompute();
  });
  input.addEventListener("blur", () => {
    if (changed.has(spec.path)) input.value = display(get(inputs, spec.path), format, scale);
  });
  reset.addEventListener("click", () => {
    set(inputs, spec.path, clone(get(preset.inputs, spec.path)));
    changed.delete(spec.path);
    paint();
    recompute();
    input.focus();
  });

  paint();
  wrapper.appendChild(el("label", { class: "field__label", text: spec.label, attrs: { for: id } }));
  wrapper.appendChild(el("div", { class: "field__row" }, [input, unit ? el("span", { class: "field__unit", text: unit }) : null, reset]));
  wrapper.appendChild(source);
  return wrapper;
}

/* The preset's own source of a field, kept under "Your figure" so the
 * visitor can see what they replaced. */
function sourceLine(path) {
  const cited = preset.sources[path];
  return cited ? cited.source : calc.words.not_cited;
}

function selectField(label, id, options, current, onChange, note) {
  const select = el("select", { class: "field__select", id });
  for (const option of options) {
    const node = el("option", { text: option.label, attrs: { value: option.value } });
    if (String(option.value) === String(current)) node.selected = true;
    select.appendChild(node);
  }
  select.addEventListener("change", () => onChange(select.value));
  return el("div", { class: "field field--wide" }, [
    el("label", { class: "field__label", text: label, attrs: { for: id } }),
    select,
    note ? el("p", { class: "field__source", text: note }) : null,
  ]);
}

function checkField(label, id, checked, onChange) {
  const box = el("input", { id, attrs: { type: "checkbox" } });
  box.checked = checked;
  box.addEventListener("change", () => onChange(box.checked));
  return el("div", { class: "field field--wide" }, [el("label", { class: "field__check", attrs: { for: id } }, [box, label])]);
}

function shipExtras(fieldset) {
  const vessel = calc.vessels[get(preset, "legs.vessel")];
  const head = el("tr", {}, [
    el("th", { text: "Leg", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Knots", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: UNITS.tpd, attrs: { scope: "col" } }),
  ]);
  const body = el("tbody");
  for (const [leg, curve] of [["Laden", inputs.laden_curve], ["Ballast", inputs.ballast_curve]]) {
    for (const [speed, tonnes] of curve) {
      body.appendChild(el("tr", {}, [
        el("th", { text: leg, attrs: { scope: "row" } }),
        figureCell(formatCell(speed, "knots", decimals), "curve.speed"),
        figureCell(formatCell(tonnes, "tpd", decimals), "curve.tpd"),
      ]));
    }
  }
  const fit = fill(calc.words.curve_fit, {
    laden: formatNumber(vessel.power_fit_laden.b, "exponent", decimals),
    ballast: formatNumber(vessel.power_fit_ballast.b, "exponent", decimals),
  });
  fieldset.appendChild(el("div", { class: "field field--wide" }, [
    el("p", { class: "field__label", text: vessel.label }),
    el("p", { class: "field__source", text: vessel.note + ". " + (preset.sources.laden_curve ? preset.sources.laden_curve.source : "") }),
    el("table", { class: "table curve-table" }, [el("caption", { class: "table-caption", text: calc.words.curves }), el("thead", {}, [head]), body]),
    el("p", { class: "field__source", text: fit }),
  ]));
  fieldset.appendChild(checkField(calc.words.scrubber, "field-scrubber", inputs.scrubber, (on) => {
    inputs.scrubber = on;
    changed.add("scrubber");
    recompute();
  }));
  fieldset.appendChild(checkField(calc.words.scrubber_in_eca, "field-scrubber-in-eca", inputs.scrubber_in_eca, (on) => {
    inputs.scrubber_in_eca = on;
    changed.add("scrubber_in_eca");
    recompute();
  }));
}

function routeExtras(fieldset) {
  const options = calc.alternatives[preset.route] || [];
  if (options.length <= 1) return;
  const legs = [["laden", "Laden"], ["ballast", "Ballast"]];
  for (const [leg, word] of legs) {
    const current = options.find((o) => o[leg + "_nm"] === inputs[leg].distance_nm);
    fieldset.appendChild(selectField(
      calc.words.routing + ", " + word.toLowerCase() + " leg",
      "field-routing-" + leg,
      options.map((o) => ({ value: o.routing, label: o.label + ", " + formatNumber(o[leg + "_nm"], "nm", decimals) + " " + UNITS.nm })),
      current ? current.routing : "",
      (routing) => {
        const option = options.find((o) => o.routing === routing);
        inputs[leg].distance_nm = option[leg + "_nm"];
        inputs[leg].eca_nm = option[leg + "_eca_nm"];
        changed.add(leg + ".distance_nm");
        changed.add(leg + ".eca_nm");
        refreshFields([leg + ".distance_nm", leg + ".eca_nm"]);
        recompute();
      },
      leg === "ballast" ? calc.words.routing_note : null,
    ));
  }
}

function marketExtras(fieldset) {
  const contract = inputs.contract;
  const bases = calc.freight_bases.filter((b) => (contract === "trip" ? b.id === "hire_usd_day" : b.id !== "hire_usd_day"));
  if (bases.length > 1) {
    fieldset.appendChild(selectField(calc.words.freight_basis, "field-freight-basis",
      bases.map((b) => ({ value: b.id, label: b.label })), inputs.freight_basis, (basis) => switchBasis(basis)));
  }
  const spec = calc.fields.find((f) => f.path === "freight_value");
  const holder = el("div", { class: "field-holder field--wide" }, [numberField(spec)]);
  live.freightHolder = holder;
  fieldset.appendChild(holder);
  const year = calc.ets_years.find((y) => y.phase_in === inputs.ets.phase_in && y.include_non_co2 === inputs.ets.include_non_co2);
  fieldset.appendChild(selectField(calc.words.ets_year, "field-ets-year",
    calc.ets_years.map((y) => ({ value: y.year, label: String(y.year) })), year ? year.year : "", (value) => {
      const chosen = calc.ets_years.find((y) => String(y.year) === String(value));
      inputs.ets.phase_in = chosen.phase_in;
      inputs.ets.include_non_co2 = chosen.include_non_co2;
      changed.add("ets.phase_in");
      recompute();
    }, calc.words.ets_year_note));
}

/* A change of basis keeps the freight: the dollars a tonne it stands for are
 * written in the new unit, or left empty where that needs a flat rate. */
function switchBasis(basis) {
  let usdT = null;
  if (readiness().ok) usdT = engine.freight_usd_t(inputs);
  inputs.freight_basis = basis;
  if (usdT === null) inputs.freight_value = null;
  else if (basis === "usd_t") inputs.freight_value = usdT;
  else if (basis === "lump_sum") inputs.freight_value = usdT * inputs.cargo_t;
  else if (basis === "ws") inputs.freight_value = inputs.flat_rate_usd_t ? engine.usd_t_to_ws(usdT, inputs.flat_rate_usd_t) : null;
  changed.add("freight_value");
  const spec = calc.fields.find((f) => f.path === "freight_value");
  live.freightHolder.replaceChildren(numberField(spec));
  recompute();
}

function warRates(fieldset) {
  const list = el("ul", { class: "war-rates" });
  for (const rate of calc.war_risk_rates) {
    const values = rate.low === rate.high ? [rate.low] : [rate.low, rate.high];
    const item = el("li", { class: "war-rates__item" }, [
      el("span", { text: rate.area + ", " + formatDay(rate.as_of) + ": " + values.map((v) => formatNumber(v, "percent_2", decimals)).join(" to ") + " percent. " + rate.reported + ". " }),
    ]);
    for (const value of values) {
      const button = el("button", { class: "field__reset", text: fill(calc.words.war_use, { value: formatNumber(value, "percent_2", decimals) }), attrs: { type: "button" } });
      button.addEventListener("click", () => {
        inputs.war_risk.premium_pct = value;
        changed.add("war_risk.premium_pct");
        refreshFields(["war_risk.premium_pct"]);
        recompute();
      });
      item.appendChild(button);
    }
    list.appendChild(item);
  }
  fieldset.appendChild(el("div", { class: "field field--wide" }, [el("p", { class: "field__label", text: calc.words.war_rates }), list]));
}

function advancedExtras(fieldset) {
  fieldset.appendChild(selectField(calc.words.vlsfo_class, "field-vlsfo-class",
    calc.vlsfo_classes.map((c) => ({ value: c.id, label: c.label })), inputs.vlsfo_class, (value) => {
      inputs.vlsfo_class = value;
      changed.add("vlsfo_class");
      recompute();
    }, preset.sources.vlsfo_class ? preset.sources.vlsfo_class.source : null));
  fieldset.appendChild(checkField(calc.words.fueleu, "field-fueleu", inputs.fueleu.include, (on) => {
    inputs.fueleu.include = on;
    changed.add("fueleu.include");
    recompute();
  }));
}

/* Redraw the fields of these paths after something other than their own box
 * changed them (a routing, a dated premium). */
function refreshFields(paths) {
  for (const path of paths) {
    const node = document.querySelector('.field[data-path="' + path + '"]');
    if (!node) continue;
    const spec = calc.fields.find((f) => f.path === path);
    node.replaceWith(numberField(spec));
  }
}

/* ------------------------------------------------------------ outputs --- */

function buildOutputs(column) {
  live.verdict = el("p", { class: "calc-verdict", attrs: { role: "status" } });
  live.notes = el("div", { class: "calc-notes" });
  column.appendChild(live.verdict);
  column.appendChild(live.notes);

  // The freight that earns a target TCE, zero by default.
  const targetId = "field-target-tce";
  const targetInput = el("input", { class: "field__input", id: targetId, attrs: { type: "text", inputmode: "decimal", autocomplete: "off" } });
  targetInput.value = display(target, "usd_day", 1);
  targetInput.addEventListener("input", () => {
    const value = parse(targetInput.value);
    if (value === null || Number.isNaN(value)) return;
    target = value;
    recompute();
  });
  live.breakeven = el("dl", { class: "breakeven__values" });
  column.appendChild(el("div", { class: "breakeven" }, [
    el("div", { class: "field" }, [
      el("label", { class: "field__label", text: calc.words.breakeven_heading, attrs: { for: targetId } }),
      el("div", { class: "field__row" }, [targetInput, el("span", { class: "field__unit", text: UNITS.usd_day })]),
      el("p", { class: "field__source", text: calc.words.breakeven_target_unit }),
    ]),
    live.breakeven,
  ]));

  live.figures = [];
  live.bridgeTitle = el("h2", { class: "block__heading" });
  live.bridgeHolder = el("div");
  live.resultLine = el("p", { class: "result-line" });
  live.leaves = el("p", { class: "source-line leaves-out" });
  live.source = el("p", { class: "source-line" });
  const bridgeFigure = el("figure", { class: "block" }, [live.bridgeTitle, live.bridgeHolder, live.resultLine, live.source]);
  live.figures.push(bridgeFigure);
  column.appendChild(bridgeFigure);
  column.appendChild(live.leaves);

  live.tornadoTitle = el("h2", { class: "block__heading" });
  live.tornadoFrame = el("div", { class: "chart-frame" });
  const tornadoFigure = el("figure", { class: "block" }, [
    live.tornadoTitle,
    live.tornadoFrame,
    el("ul", { class: "chart-legend" }, [
      el("li", { class: "chart-legend__item" }, [el("span", { class: "swatch swatch--outline", attrs: { "aria-hidden": "true" } }), calc.words.tornado_lower]),
      el("li", { class: "chart-legend__item" }, [el("span", { class: "swatch swatch--ink", attrs: { "aria-hidden": "true" } }), calc.words.tornado_higher]),
    ]),
  ]);
  live.figures.push(tornadoFigure);
  column.appendChild(tornadoFigure);

  live.speedTitle = el("h2", { class: "block__heading" });
  live.speedFrame = el("div", { class: "chart-frame" });
  live.speedNote = el("p", { class: "source-line" });
  const speedFigure = el("figure", { class: "block" }, [live.speedTitle, live.speedFrame, el("p", { class: "source-line", text: calc.words.speed_desc }), live.speedNote]);
  live.figures.push(speedFigure);
  column.appendChild(speedFigure);

  onWidthChange(live.tornadoFrame, () => drawTornado());
  onWidthChange(live.speedFrame, () => drawSpeed());
}

function bridgeRows(result) {
  const rows = [];
  const gross = result.revenue.gross_usd + result.revenue.other_usd;
  rows.push({ id: "gross", label: calc.words.gross, kind: "total", family: null, from_usd: 0, to_usd: gross, value_usd: gross, detail: null });
  let running = gross;
  const commission = result.revenue.commission_usd;
  rows.push({ id: "commission", label: calc.words.commission, kind: "deduction", family: null, from_usd: running, to_usd: running - commission, value_usd: -commission, detail: null });
  running -= commission;
  for (const family of ["bunkers", "ports", "canals", "ets", "war_risk", "other", "fueleu"]) {
    const value = result.costs[family];
    if ((family === "other" || family === "fueleu") && !value) continue;
    const zeroWords = zeroReason(family);
    rows.push({
      id: family,
      label: calc.cost_labels[family],
      kind: "cost",
      family: FAMILIES[family],
      from_usd: running,
      to_usd: running - value,
      value_usd: -value,
      detail: null,
      zero: value ? null : zeroWords,
    });
    running -= value;
  }
  rows.push({ id: "result", label: calc.words.result, kind: "total", family: null, from_usd: 0, to_usd: result.result_usd, value_usd: result.result_usd, accent: true, detail: null });
  return rows;
}

/* Why a cost family is zero: left out for want of a figure, or none on this
 * voyage. The words are the artifact's status words. */
function zeroReason(family) {
  const paths = {
    ports: ["costs.port_load_usd", "costs.port_discharge_usd"],
    canals: ["costs.canal_laden_usd", "costs.canal_ballast_usd"],
    war_risk: ["war_risk.premium_pct"],
    ets: [],
  }[family] || [];
  if (paths.some((path) => sourceOf(path).status === "empty")) return calc.status_words.empty;
  if (family === "ets") return calc.words.none_ets;
  return calc.words.none;
}

function recompute() {
  const ready = readiness();
  clear(live.notes);
  for (const figure of live.figures) figure.hidden = !ready.ok;
  if (!ready.ok) {
    live.verdict.textContent = ready.why;
    live.verdict.classList.add("is-blocked");
    live.result = null;
    clear(live.breakeven);
    clear(live.bridgeHolder);
    live.bridgeTitle.textContent = "";
    live.resultLine.textContent = "";
    live.leaves.textContent = leavesOut();
    live.source.textContent = "";
    live.tornadoTitle.textContent = "";
    live.speedTitle.textContent = "";
    clear(live.tornadoFrame);
    clear(live.speedFrame);
    return;
  }
  const result = engine.evaluate(inputs);
  live.result = result;
  const tce = result.tce_usd_day;
  const days = result.days.total;
  const template = inputs.contract === "trip" ? calc.words.verdict_trip : (tce < 0 ? calc.words.verdict_negative : calc.words.verdict);
  live.verdict.classList.remove("is-blocked");
  live.verdict.textContent = fill(template, {
    tce: usdText(inputs.contract === "trip" ? tce : Math.abs(tce), "usd_day"),
    days: formatNumber(days, "days", decimals),
    trip_days: formatNumber(result.days.trip, "days", decimals),
    trip_tce: usdText(inputs.freight_value * (1 - inputs.commission_pct / engine_percent()), "usd_day"),
  });
  if (preset.published && changed.size === 0) {
    const error = (tce / preset.published.tce_usd_day - 1) * engine_percent();
    live.notes.appendChild(el("p", { class: "state-message", text: fill(calc.words.published, {
      published: usdText(preset.published.tce_usd_day, "usd_day"),
      error: formatNumber(Math.abs(error), "error_percent", decimals),
      direction: error >= 0 ? "higher" : "lower",
    }) }));
  }
  live.notes.appendChild(el("p", { class: "state-message", text: calc.words.estimate }));

  drawBreakeven();
  const rows = bridgeRows(result);
  live.bridgeTitle.textContent = fill(calc.words.bridge_title, {
    gross: moneyText(result.revenue.gross_usd + result.revenue.other_usd),
    result: moneyText(result.result_usd),
    costs: moneyText(result.costs.total_usd),
  });
  if (live.bridge) live.bridge.redraw(rows);
  else {
    live.bridge = bridgeTable(rows, decimals, { caption: calc.words.bridge_caption });
    live.bridgeHolder.appendChild(live.bridge.node);
  }
  if (!live.bridgeHolder.contains(live.bridge.node)) live.bridgeHolder.appendChild(live.bridge.node);
  live.resultLine.textContent = fill(calc.words.result_line, {
    tce: usdText(tce, "usd_day"),
    days: formatNumber(days, "days", decimals),
    ballast: formatNumber(result.days.ballast_sea, "days", decimals),
    laden: formatNumber(result.days.laden_sea, "days", decimals),
    port: formatNumber(result.days.port_total, "days", decimals),
  });
  live.leaves.textContent = leavesOut();
  live.source.textContent = fill(calc.words.source, { preset: preset.label, market: preset.market_words });
  drawTornado();
  drawSpeed();
}

/* PERCENT is the engine's own constant, from data/engine.json. */
function engine_percent() {
  return data.engine.constants.PERCENT;
}

function leavesOut() {
  const items = (preset.excluded_items || []).filter((item) => !item.paths.every((path) => changed.has(path)));
  if (!items.length) return calc.words.leaves_out_none;
  return fill(calc.words.leaves_out, { items: listWords(items.map((item) => item.text)) });
}

function drawBreakeven() {
  clear(live.breakeven);
  const needed = engine.freight_for_tce(inputs, target);
  const item = (label, value, format) => el("div", { class: "breakeven__item" }, [
    el("dt", { class: "breakeven__label", text: label }),
    el("dd", { class: "breakeven__value" + (value === null ? " is-missing" : ""), text: value === null ? calc.words.breakeven_ws_missing : formatNumber(value, format, decimals) }),
  ]);
  if (inputs.contract === "trip") {
    live.breakeven.appendChild(item(calc.words.breakeven_hire, needed.hire_usd_day, "usd_day"));
    return;
  }
  live.breakeven.appendChild(item(calc.words.breakeven_usd_t, needed.usd_t, "usd_t"));
  live.breakeven.appendChild(item(calc.words.breakeven_ws, needed.ws, "ws"));
  live.breakeven.appendChild(item(calc.words.breakeven_lump, needed.lump_sum_usd, "usd"));
}

function drawTornado() {
  if (!live.result) return;
  const width = live.tornadoFrame.clientWidth;
  if (!width) return;
  const shocks = engine.sensitivities(inputs);
  const label = new Map(calc.shocks.map((s) => [s.id, s.label]));
  const base = live.result.tce_usd_day;
  const rows = shocks
    .map((s) => ({ ...s, spread: Math.abs(s.high_tce_usd_day - s.low_tce_usd_day) }))
    .sort((a, b) => b.spread - a.spread)
    .map((s) => ({
      label: label.get(s.id),
      low: s.low_tce_usd_day,
      high: s.high_tce_usd_day,
      lowText: formatNumber(s.low_tce_usd_day - base, "usd_day", decimals, { signed: true }),
      highText: formatNumber(s.high_tce_usd_day - base, "usd_day", decimals, { signed: true }),
      tip: [label.get(s.id), calc.words.tornado_lower + ": " + usdText(s.low_tce_usd_day, "usd_day"), calc.words.tornado_higher + ": " + usdText(s.high_tce_usd_day, "usd_day")],
    }));
  const first = rows[0];
  live.tornadoTitle.textContent = fill(calc.words.tornado_title, {
    first: first.label,
    range: usdText(Math.abs(first.high - first.low), "usd_day"),
  });
  const { svg, regions } = tornadoChart({
    width,
    rows,
    base,
    words: { title: live.tornadoTitle.textContent, desc: calc.words.tornado_desc, axis: calc.words.tornado_axis },
  });
  live.tornadoFrame.replaceChildren(svg);
  tooltip(live.tornadoFrame, svg, regions);
}

function drawSpeed() {
  if (!live.result) return;
  const width = live.speedFrame.clientWidth;
  if (!width) return;
  const speeds = inputs.laden_curve.map(([v]) => v);
  const margin = calc.speed_chart.margin_kn;
  const step = calc.speed_chart.step_kn;
  const low = Math.min(...speeds) - margin;
  const high = Math.max(...speeds) + margin;
  const grid = [];
  for (let k = 0; low + k * step <= high + step * Number.EPSILON; k += 1) grid.push(low + k * step);
  const points = engine.tce_by_speed(inputs, grid);
  const best = engine.optimal_speed(inputs, low, high);
  const current = inputs.laden.speed_kn;
  const atTop = best.laden_kn >= high - step * Number.EPSILON;
  const atBottom = best.laden_kn <= low + step * Number.EPSILON;
  const knots = (v) => formatNumber(v, "knots", decimals);
  let template = calc.words.speed_title;
  if (atTop) template = calc.words.speed_title_bound;
  else if (atBottom) template = calc.words.speed_title_low;
  live.speedTitle.textContent = fill(template, { best: knots(best.laden_kn), current: knots(current) });
  live.speedNote.textContent = inputs.contract === "trip" ? calc.words.speed_trip_note : "";
  const ys = points.map((p) => p.tce_usd_day).concat([best.tce_usd_day]);
  const y = niceDomain(ys, GEOMETRY.Y_TICKS, false);
  const x = { low, high, step: niceDomain([low, high], GEOMETRY.X_TICKS, false).step };
  const { svg, regions } = lineChart({
    width,
    series: [{ points: points.map((p) => [p.laden_kn, p.tce_usd_day]) }],
    marks: [
      { x: best.laden_kn, y: best.tce_usd_day, className: "mark-accent-dot", label: fill(calc.words.speed_best, { best: knots(best.laden_kn) }) },
      { x: current, y: live.result.tce_usd_day, className: "mark-printed", label: fill(calc.words.speed_current, { current: knots(current) }), below: true },
    ],
    x,
    y,
    words: { title: live.speedTitle.textContent, desc: calc.words.speed_desc, xAxis: calc.words.speed_axis_x, yAxis: calc.words.speed_axis_y },
    tipFor: (v, index) => [knots(v) + " " + UNITS.knots, usdText(points[index].tce_usd_day, "usd_day") + " a day", formatNumber(points[index].days, "days", decimals) + " " + UNITS.days],
  });
  live.speedFrame.replaceChildren(svg);
  tooltip(live.speedFrame, svg, regions);
}

/* ------------------------------------------------------------ sections --- */

function methodSection(inner) {
  const block = el("div", { class: "block" });
  for (const paragraph of calc.words.method) block.appendChild(el("p", { class: "prose", text: paragraph }));
  inner.appendChild(block);
}

function speedSection(inner) {
  const speed = data.speed;
  inner.appendChild(sentence("p", speed.lead, decimals, "lead block"));
  for (const routeEntry of speed.routes) {
    const head = el("tr", {}, [
      el("th", { text: "Freight", attrs: { scope: "col" } }),
      el("th", { text: "Bunkers", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "VLSFO, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "VLSFO" } }),
      el("th", { class: "col-num", text: "Best laden speed, " + UNITS.knots, attrs: { scope: "col", "data-short": "best speed" } }),
      el("th", { class: "col-num", text: "TCE at the best speed, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE at best" } }),
      el("th", { class: "col-num", text: "TCE at the Baltic's speed, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE at the Baltic's speed" } }),
    ]);
    const body = el("tbody");
    for (const cell of routeEntry.grid) {
      body.appendChild(el("tr", {}, [
        el("th", { attrs: { scope: "row" } }, [cell.freight_words]),
        el("td", { class: "words", text: cell.bunker_words }),
        figureCell(formatCell(cell.vlsfo_usd_t, "usd_t", decimals), "vlsfo_usd_t"),
        figureCell(formatCell(cell.optimal_laden_kn, "knots_2", decimals) + (cell.at_bound ? " " + speed.bound_mark : ""), "optimal_laden_kn"),
        figureCell(formatCell(cell.optimal_tce_usd_day, "usd_day", decimals), "optimal_tce_usd_day"),
        figureCell(formatCell(cell.reference_tce_usd_day, "usd_day", decimals), "reference_tce_usd_day"),
      ]));
    }
    const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
    inner.appendChild(el("div", { class: "block" }, [scrollTable([appendSegments(el("span"), routeEntry.caption, decimals)], table)]));
  }
  inner.appendChild(el("p", { class: "note block", text: speed.note }));
}

function dataSection(inner) {
  const head = el("tr", {}, [
    el("th", { text: "Input", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Value", attrs: { scope: "col", "data-short": "value" } }),
    el("th", { text: "Unit", attrs: { scope: "col", "data-short": "unit" } }),
    el("th", { text: "Status", attrs: { scope: "col", "data-short": "status" } }),
    el("th", { text: "Source or reason", attrs: { scope: "col", "data-short": "source" } }),
  ]);
  const body = el("tbody");
  for (const [path, spec] of Object.entries(calc.input_labels)) {
    const cited = preset.sources[path];
    if (!cited && !changed.has(path)) continue;
    const info = sourceOf(path);
    const raw = get(inputs, path);
    let value;
    if (Array.isArray(raw)) value = el("td", { class: "words", text: raw.map(([v, c]) => formatNumber(v, "knots", decimals) + " kn: " + formatNumber(c, "tpd", decimals)).join(", ") });
    else if (typeof raw === "string") value = el("td", { class: "words", text: raw });
    else if (raw === null || raw === undefined || (info.status === "empty" && !raw)) value = el("td", { class: "num is-missing", text: calc.status_words.empty });
    else value = figureCell(formatCell(raw * spec.scale, path === "freight_value" ? freightFormat() : spec.format, decimals), path);
    const format = path === "freight_value" ? freightFormat() : spec.format;
    body.appendChild(el("tr", { attrs: { "data-status": info.status } }, [
      el("th", { text: spec.label, attrs: { scope: "row" } }),
      value,
      el("td", { class: "nowrap", text: format ? UNITS[format] : "" }),
      el("td", { class: "status status--" + info.status, text: calc.status_words[info.status] || "" }),
      el("td", { class: "words", text: info.status === "changed" ? sourceLine(path) : info.source }),
    ]));
  }
  const table = el("table", { class: "table table--inputs" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([calc.words.data_caption], table)]));
}
