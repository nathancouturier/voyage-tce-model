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
 * public document), derived (a stated rule on sourced values), chosen (the
 * study's choice among published values, with the reason), left out (a cost
 * the Baltic's TCE leaves out, priced at zero) or empty (no public figure; it
 * counts as zero and the result says it is left out). A field the visitor
 * edits says "Your figure" and gains a Reset button. The
 * outputs are computed here, by src/engine.js, the browser copy of the Python
 * engine (tools/validate-engine.mjs holds the two to 1e-9); the words around
 * them are the artifact's, with {name} filled by the figure computed.
 *
 * ROUTINGS. Where the study computes more than one routing for a leg (P7,
 * TD22, TC20), the Route step offers them. Each pair of leg routings is a
 * variant the export built with the engine's case builder: the inputs a
 * routing sets (distances, ECA miles, canal days, the listed areas entered),
 * their sources, and what the voyage then leaves out. A variant overlays the
 * preset; it is not the visitor's own figure.
 *
 * THE ADDRESS. #/calculator?preset=latest-c3&open=market keeps the preset and
 * the open steps, so a priced voyage can be linked; edits to single fields and
 * routings are not written to the address.
 *
 * Numeric literals: none.
 */

import { el, clear, sentence, appendSegments, scrollTable, figureCell } from "./dom.js";
import { formatNumber, formatCell, formatDay, formatDayShort, listWords, roundedParts, UNITS, MINUS_PROSE } from "./format.js";
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
let variant = null;
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

/** "{tce} a day" as segments, the form the export writes a sentence in, so it
 *  is set as the overview sets its own: each {name} the number segment given
 *  for it, and a unit the words write right after a number kept with it as
 *  its suffix, as the export keeps one. A {name} with no number stays words. */
function segmentsOf(template, numbers) {
  const segments = [];
  let from = 0;
  for (const match of template.matchAll(/\{(\w+)\}/g)) {
    const number = numbers[match[1]];
    if (!number) continue;
    const end = match.index + match[0].length;
    const unit = UNITS[number.format] ? " " + UNITS[number.format] : "";
    const suffix = unit && template.startsWith(unit, end) ? unit : "";
    segments.push(template.slice(from, match.index), { ...number, suffix });
    from = end + suffix.length;
  }
  segments.push(template.slice(from));
  return segments.filter((segment) => segment !== "");
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

/** A source sentence as it follows a status word: its first letter a capital. */
function firstUpper(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function display(value, format, scale) {
  if (value === null || value === undefined) return "";
  return formatNumber(value * (scale || 1), format, decimals, { context: "table" }) || "";
}

/* A path's source: the routing variant's where it sets one, else the preset's.
 * A variant's null means the routing leaves that source out. */
function cited(path) {
  if (variant && Object.prototype.hasOwnProperty.call(variant.sources, path)) return variant.sources[path];
  return preset.sources[path] || null;
}

/* A path's value before the visitor's edits: the variant's where it sets it. */
function baseValue(path) {
  if (variant && Object.prototype.hasOwnProperty.call(variant.patch, path)) return variant.patch[path];
  return get(preset.inputs, path);
}

function sourceOf(path) {
  // A figure the visitor typed keeps its source's words after the status, so they can see what it replaced.
  if (changed.has(path)) return { status: "changed", source: sourceLine(path) };
  const found = cited(path);
  if (found) return found;
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
  variant = null;
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
  // The sensitivities and the speed chart run under both columns.
  const wideRow = el("div", { class: "calc-wide" });
  root.appendChild(wideRow);

  stepSections = buildSections(VIEW, calc.steps.map((step) => ({
    id: step.id,
    name: step.label,
    summary: [step.summary],
    build: (inner) => buildStep(inner, step.id),
  })), decimals, route);
  stepSections.node.classList.add("calc-steps");
  inputsColumn.appendChild(stepSections.node);

  buildOutputs(outputsColumn, wideRow);

  lowerSections = buildSections(VIEW, withBuilders(calc.sections, {
    method: (inner) => methodSection(inner),
    speed: (inner) => speedSection(inner),
    assumptions: (inner) => assumptionsSection(inner),
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
    // A dated week shows its day in the short form, so a row of a phone holds two or three; the
    // full label is its tooltip and description, and its name stays the words it shows.
    const short = shortMarket(p);
    const button = el("button", {
      class: "choice",
      text: short || p.market_label,
      attrs: {
        type: "button",
        "aria-pressed": p.id === preset.id ? "true" : "false",
        "data-preset": p.id,
        title: short ? p.market_label : null,
      },
    });
    button.addEventListener("click", () => choose(p.id));
    marketRow.appendChild(button);
  }
  return el("div", { class: "presets" }, [
    el("div", { class: "choice-group" }, [el("p", { class: "choice-group__label", text: calc.words.route_label }), routeRow]),
    el("div", { class: "choice-group" }, [el("p", { class: "choice-group__label", text: calc.words.market_label }), marketRow]),
  ]);
}

/* A market named by its day alone, or by its day after words that hold no
 * figure (the week to it), in the short form of that day; null for a market
 * named by more than its day (a source and its rate), which keeps its words. */
function shortMarket(p) {
  const day = formatDay(p.date);
  if (!day || !p.market_label.endsWith(day) || /\d/.test(p.market_label.slice(0, -day.length))) return null;
  const short = formatDayShort(p.date);
  return short !== p.market_label ? short : null;
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
  // The result sits above the steps on a narrow screen and its column ends before open steps do on a
  // wide one, out of sight either way while a field is edited, so each open step ends with it.
  const line = el("p", { class: "calc-live" });
  live.stepLines = [...(live.stepLines || []), line];
  inner.appendChild(line);
  drawStepLines();
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
    source.replaceChildren(...(words ? [el("span", { class: "field__status", text: words + ". " })] : []), firstUpper(info.source));
    reset.hidden = !changed.has(spec.path);
  };

  input.addEventListener("input", () => {
    const value = parse(input.value);
    const info = cited(spec.path);
    if (value === null) {
      // An emptied field returns to its source when that source is empty;
      // anything else needs a number.
      if (info && info.status === "empty") {
        set(inputs, spec.path, baseValue(spec.path) === null ? null : 0);
        changed.delete(spec.path);
        wrapper.setAttribute("data-status", "empty");
        source.replaceChildren(el("span", { class: "field__status", text: calc.status_words.empty + ". " }), firstUpper(info.source));
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
    source.replaceChildren(el("span", { class: "field__status", text: calc.status_words.changed + ". " }), firstUpper(sourceLine(spec.path)));
    reset.hidden = false;
    recompute();
  });
  input.addEventListener("blur", () => {
    if (changed.has(spec.path)) input.value = display(get(inputs, spec.path), format, scale);
  });
  reset.addEventListener("click", () => {
    set(inputs, spec.path, clone(baseValue(spec.path)));
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
  const found = cited(path);
  return found ? found.source : calc.words.not_cited;
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
  const variants = preset.routings || [];
  if (variants.length <= 1) return;
  const legs = [["laden", calc.words.routing_laden], ["ballast", calc.words.routing_ballast]];
  for (const [leg, label] of legs) {
    const choices = [];
    for (const v of variants) {
      if (!choices.some((c) => c.value === v[leg])) {
        // Led by the leg's distance, in nautical miles as the study's sentences write them, so a select
        // too narrow for the routing's name still shows it.
        choices.push({ value: v[leg], label: formatNumber(v.patch[leg + ".distance_nm"], "nm", decimals) + " nm, " + v[leg + "_label"] });
      }
    }
    if (choices.length <= 1) continue;
    fieldset.appendChild(selectField(label, "field-routing-" + leg, choices, currentRouting()[leg], (routing) => {
      const wanted = { ...currentRouting(), [leg]: routing };
      applyVariant(variants.find((v) => v.laden === wanted.laden && v.ballast === wanted.ballast));
    }, leg === "ballast" ? calc.words.routing_note : null));
  }
}

/* The pair of leg routings the inputs stand on. */
function currentRouting() {
  if (variant) return { laden: variant.laden, ballast: variant.ballast };
  const own = (preset.routings || []).find((v) => v.is_preset);
  return own ? { laden: own.laden, ballast: own.ballast } : { laden: "", ballast: "" };
}

/* A routing pair sets its inputs, sources and leaves-out list; a figure the
 * visitor typed into one of its paths gives way to the routing's. */
function applyVariant(next) {
  variant = next.is_preset ? null : next;
  const paths = Object.keys(next.patch);
  for (const path of paths) {
    set(inputs, path, clone(next.patch[path]));
    changed.delete(path);
  }
  refreshFields(paths);
  fillWarRates();
  recompute();
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

/* The listed areas this voyage enters, the dated premiums for each with a
 * button that enters one, who pays, and the seven day periods the engine
 * counts. The list follows the routing, so it is redrawn when that changes. */
function warRates(fieldset) {
  live.warRates = el("div", { class: "field field--wide" });
  fieldset.appendChild(live.warRates);
  fillWarRates();
  if (inputs.contract !== "trip") {
    const payer = cited("war_risk.payer");
    fieldset.appendChild(selectField(calc.words.war_payer, "field-war-payer",
      Object.entries(calc.payer_words).map(([value, label]) => ({ value, label })), inputs.war_risk.payer, (value) => {
        inputs.war_risk.payer = value;
        changed.add("war_risk.payer");
        recompute();
      }, payer ? firstUpper(payer.source) : null));
  }
  live.warLine = el("p", { class: "field__source field--wide war-periods" });
  fieldset.appendChild(live.warLine);
}

function enteredAreas() {
  return Object.keys(inputs.war_risk.areas).filter((area) => {
    const spec = inputs.war_risk.areas[area];
    return spec.entries > 0 || spec.ballast_transits > 0;
  });
}

function fillWarRates() {
  if (!live.warRates) return;
  const entered = enteredAreas();
  const list = el("ul", { class: "war-rates" });
  for (const rate of calc.war_risk_rates.filter((r) => entered.includes(r.engine_area))) {
    const values = rate.low === rate.high ? [rate.low] : [rate.low, rate.high];
    const path = "war_risk.areas." + rate.engine_area + ".premium_pct";
    const item = el("li", { class: "war-rates__item" }, [
      el("span", { text: rate.area + ", " + formatDay(rate.as_of) + ": " + values.map((v) => formatNumber(v, "percent_2", decimals)).join(" to ") + " percent. " + rate.reported + ". " }),
    ]);
    for (const value of values) {
      const button = el("button", { class: "field__reset", text: fill(calc.words.war_use, { value: formatNumber(value, "percent_2", decimals) }), attrs: { type: "button" } });
      button.addEventListener("click", () => {
        set(inputs, path, value);
        changed.add(path);
        refreshFields([path]);
        recompute();
      });
      item.appendChild(button);
    }
    list.appendChild(item);
  }
  live.warRates.replaceChildren(
    el("p", { class: "field__label", text: calc.words.war_rates }),
    entered.length ? list : el("p", { class: "field__source", text: calc.words.war_none }),
  );
}

/* The periods each listed area makes and who pays them. A stay is counted in
 * days inside; a passage of the Red Sea is one period a transit. */
function drawWarLine(result) {
  if (!live.warLine) return;
  const parts = [];
  const periodWords = (n) => (n === 1 ? calc.words.war_period_one : fill(calc.words.war_period_many, { n: formatNumber(n, "count", decimals) }));
  let charter = false;
  for (const [area, info] of Object.entries(result.war_risk.areas)) {
    if (info.periods) {
      charter = true;
      parts.push(fill(info.days > 0 ? calc.words.war_area_line : calc.words.war_transit_line, {
        area: calc.war_area_names[area],
        days: formatNumber(info.days, "days", decimals),
        periods: periodWords(info.periods),
        usd: moneyText(info.usd),
      }));
    }
    if (info.ballast_periods) {
      parts.push(fill(calc.words.war_ballast_line, {
        area: calc.war_area_names[area],
        periods: periodWords(info.ballast_periods),
        usd: moneyText(info.ballast_usd),
      }));
    }
  }
  if (!parts.length) {
    live.warLine.textContent = "";
    return;
  }
  if (charter) {
    parts.push(inputs.contract === "trip" || inputs.war_risk.payer === "charterer" ? calc.words.war_paid_charterer : calc.words.war_paid_owner);
  }
  live.warLine.textContent = parts.join(" ");
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

function buildOutputs(column, wide) {
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
    if (Number.isNaN(value)) return;
    // An emptied target is a target of zero: the freight that covers the voyage costs.
    target = value === null ? 0 : value;
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
    (live.tornadoSource = el("p", { class: "source-line" })),
  ]);
  live.figures.push(tornadoFigure);
  wide.appendChild(tornadoFigure);

  live.speedTitle = el("h2", { class: "block__heading" });
  live.speedFrame = el("div", { class: "chart-frame" });
  live.speedSource = el("p", { class: "source-line" });
  const speedFigure = el("figure", { class: "block" }, [
    live.speedTitle,
    live.speedFrame,
    el("ul", { class: "chart-legend" }, [
      el("li", { class: "chart-legend__item" }, [el("span", { class: "swatch swatch--line", attrs: { "aria-hidden": "true" } }), calc.words.speed_published]),
      el("li", { class: "chart-legend__item" }, [el("span", { class: "swatch swatch--line swatch--line-dash", attrs: { "aria-hidden": "true" } }), calc.words.speed_extrapolated]),
    ]),
    el("p", { class: "source-line", text: calc.words.speed_desc }),
    live.speedSource,
  ]);
  live.speedFigure = speedFigure;
  live.figures.push(speedFigure);
  wide.appendChild(speedFigure);
  // On a trip the charterer sets the speed and the owner's hire a day does not move with it.
  live.speedTrip = el("p", { class: "note block", text: calc.words.speed_trip_note });
  wide.appendChild(live.speedTrip);

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
    const zeroWords = zeroReason(family, result);
    // Beside the owner's own premium, the charter's part when the charterer pays it.
    const charterPays = inputs.contract === "trip" || inputs.war_risk.payer === "charterer";
    const charterers = family === "war_risk" && value && charterPays ? result.war_risk.charter_usd : 0;
    rows.push({
      id: family,
      label: calc.cost_labels[family],
      kind: "cost",
      family: FAMILIES[family],
      from_usd: running,
      to_usd: running - value,
      value_usd: -value,
      detail: charterers ? fill(calc.words.war_charterer_also, { usd: moneyText(charterers) }) : null,
      zero: value ? null : zeroWords,
    });
    running -= value;
  }
  rows.push({ id: "result", label: calc.words.result, kind: "total", family: null, from_usd: 0, to_usd: result.result_usd, value_usd: result.result_usd, accent: true, detail: null });
  return rows;
}

/* Why a cost family is zero: left out for want of a figure, or none on this
 * voyage. The words are the artifact's status words. */
function zeroReason(family, result) {
  const paths = {
    ports: ["costs.port_load_usd", "costs.port_discharge_usd"],
    canals: ["costs.canal_laden_usd", "costs.canal_ballast_usd"],
    war_risk: ["war_risk.areas.gulf.premium_pct", "war_risk.areas.red_sea.premium_pct"],
    ets: [],
  }[family] || [];
  // A premium priced but paid by the charterer is the charterer's, not the owner's.
  if (family === "war_risk" && result.war_risk.charter_usd) return fill(calc.words.war_charterer, { usd: moneyText(result.war_risk.charter_usd) });
  if (paths.some((path) => sourceOf(path).status === "left_out")) return calc.status_words.left_out;
  if (paths.some((path) => sourceOf(path).status === "empty")) return calc.status_words.empty;
  if (family === "ets") return calc.words.none_ets;
  return calc.words.none;
}

function recompute() {
  const ready = readiness();
  clear(live.notes);
  for (const figure of live.figures) figure.hidden = !ready.ok;
  const trip = inputs.contract === "trip";
  live.speedFigure.hidden = !ready.ok || trip;
  live.speedTrip.hidden = !trip;
  if (!ready.ok) {
    live.verdict.textContent = ready.why;
    live.verdict.classList.add("is-blocked");
    live.result = null;
    // The freight a voyage needs does not depend on the freight typed, so it is drawn even here.
    drawBreakeven();
    clear(live.bridgeHolder);
    live.bridgeTitle.textContent = "";
    live.resultLine.textContent = "";
    live.leaves.textContent = leavesOut();
    live.source.textContent = "";
    live.tornadoSource.textContent = "";
    live.speedSource.textContent = "";
    live.tornadoTitle.textContent = "";
    live.speedTitle.textContent = "";
    clear(live.tornadoFrame);
    clear(live.speedFrame);
    drawData();
    drawAssumptions();
    drawStepLines();
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
  if (preset.published && changed.size === 0 && !variant) {
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
  // The parts rounded so that they add up to the total shown.
  const [ballastDays, ladenDays, portDays] = roundedParts([result.days.ballast_sea, result.days.laden_sea, result.days.port_total], "days", decimals);
  live.resultLine.replaceChildren();
  appendSegments(live.resultLine, segmentsOf(calc.words.result_line, {
    tce: { value: tce, format: "usd_day", prefix: "USD ", accent: true, field: "result.tce_usd_day" },
    days: { value: days, format: "days", field: "result.days.total" },
    ballast: { value: ballastDays, format: "days", field: "result.days.ballast_sea" },
    laden: { value: ladenDays, format: "days", field: "result.days.laden_sea" },
    port: { value: portDays, format: "days", field: "result.days.port_total" },
  }), decimals);
  live.leaves.textContent = leavesOut();
  live.source.textContent = fill(calc.words.source, { preset: preset.label, market: preset.market_words, eua: preset.eua_words, fx: preset.fx_words })
    + yourFigures();
  live.tornadoSource.textContent = live.source.textContent;
  live.speedSource.textContent = live.source.textContent;
  drawWarLine(result);
  drawTornado();
  drawSpeed();
  drawData();
  drawAssumptions();
  drawStepLines();
}

/* The inputs the visitor changed, named after the preset's sources. */
function yourFigures() {
  const names = [...changed].map((path) => (calc.input_labels[path] ? calc.input_labels[path].label.toLowerCase() : null)).filter(Boolean);
  const routed = variant ? [calc.words.routing_changed] : [];
  const all = [...routed, ...names];
  return all.length ? " " + fill(calc.words.source_changed, { fields: listWords(all) }) : "";
}

/* PERCENT is the engine's own constant, from data/engine.json. */
function engine_percent() {
  return data.engine.constants.PERCENT;
}

/* The result in one line under each open step. */
function drawStepLines() {
  if (!live.stepLines) return;
  const text = live.result ? fill(calc.words.live_line, { tce: usdText(live.result.tce_usd_day, "usd_day") }) : readiness().why;
  for (const line of live.stepLines) line.textContent = text;
}

/* The items of the leaves-out list that still apply: the routing's, less those whose inputs the visitor filled. */
function leftOutItems() {
  const all = variant ? variant.excluded_items : (preset.excluded_items || []);
  return all.filter((item) => !item.paths.every((path) => changed.has(path)));
}

function leavesOut() {
  const items = leftOutItems();
  if (!items.length) return calc.words.leaves_out_none;
  return fill(calc.words.leaves_out, { items: listWords(items.map((item) => item.text)) });
}

function drawAssumptions() {
  if (!live.assumptionsList) return;
  const texts = leftOutItems().map((item) => item.text);
  live.assumptionsList.replaceChildren(...(texts.length ? texts : [calc.words.leaves_out_none]).map((text) => el("li", { text: firstUpper(text) + "." })));
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
      bothText: fill(calc.words.tornado_both, {
        lower: formatNumber(s.low_tce_usd_day - base, "usd_day", decimals, { signed: true }),
        higher: formatNumber(s.high_tce_usd_day - base, "usd_day", decimals, { signed: true }),
      }),
      tip: [label.get(s.id), calc.words.tornado_lower + ": " + usdText(s.low_tce_usd_day, "usd_day") + " a day", calc.words.tornado_higher + ": " + usdText(s.high_tce_usd_day, "usd_day") + " a day"],
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
  // The same figures as a table for a screen reader.
  // A table lays out at its content's width, so the hidden box holds it rather than hiding the table itself.
  const table = el("div", { class: "visually-hidden" }, [el("table", {}, [
    el("caption", { text: live.tornadoTitle.textContent }),
    el("thead", {}, [el("tr", {}, [
      el("th", { text: calc.words.tornado_axis, attrs: { scope: "col" } }),
      el("th", { text: calc.words.tornado_lower, attrs: { scope: "col" } }),
      el("th", { text: calc.words.tornado_higher, attrs: { scope: "col" } }),
    ])]),
    el("tbody", {}, rows.map((row) => el("tr", {}, [
      el("th", { text: row.label, attrs: { scope: "row" } }),
      el("td", { text: usdText(row.low, "usd_day") + " a day" }),
      el("td", { text: usdText(row.high, "usd_day") + " a day" }),
    ]))),
  ])]);
  live.tornadoFrame.replaceChildren(svg, table);
  tooltip(live.tornadoFrame, svg, regions);
}

function drawSpeed() {
  if (!live.result || inputs.contract === "trip") return;
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
  const ys = points.map((p) => p.tce_usd_day).concat([best.tce_usd_day]);
  const y = niceDomain(ys, GEOMETRY.Y_TICKS, false);
  const x = { low, high, step: niceDomain([low, high], GEOMETRY.X_TICKS, false).step };
  // The line solid between the slowest and fastest published speeds, where
  // consumption is read from the pairs, and dashed outside them, where it
  // follows the power law fitted to them: three pieces sharing their end
  // points, at the speeds searched nearest the published ones.
  const line = points.map((p) => [p.laden_kn, p.tce_usd_day]);
  const nearest = (v) => Math.min(Math.max(Math.round((v - low) / step), 0), line.length - 1);
  const slowest = nearest(Math.min(...speeds));
  const fastest = nearest(Math.max(...speeds));
  const { svg, regions } = lineChart({
    width,
    series: [
      { points: line.slice(0, slowest + 1), className: "line--dash" },
      { points: line.slice(slowest, fastest + 1), className: "line--solid" },
      { points: line.slice(fastest), className: "line--dash" },
    ],
    marks: [
      { x: best.laden_kn, y: best.tce_usd_day, className: "mark-accent-dot", label: fill(calc.words.speed_best, { best: knots(best.laden_kn) }) },
      { x: current, y: live.result.tce_usd_day, className: "mark-printed", label: fill(calc.words.speed_current, { current: knots(current) }), below: true },
    ],
    x,
    y,
    words: { title: live.speedTitle.textContent, desc: calc.words.speed_desc, xAxis: calc.words.speed_axis_x, yAxis: calc.words.speed_axis_y },
    tipFor: (v, index) => [knots(v) + " " + UNITS.knots, usdText(points[index].tce_usd_day, "usd_day") + " a day", formatNumber(points[index].days, "days", decimals) + " " + UNITS.days],
  });
  // The best and the priced speed as a table for a screen reader.
  const table = el("div", { class: "visually-hidden" }, [el("table", {}, [
    el("caption", { text: live.speedTitle.textContent }),
    el("tbody", {}, [
      el("tr", {}, [el("th", { text: fill(calc.words.speed_best, { best: knots(best.laden_kn) }), attrs: { scope: "row" } }), el("td", { text: usdText(best.tce_usd_day, "usd_day") + " a day" })]),
      el("tr", {}, [el("th", { text: fill(calc.words.speed_current, { current: knots(current) }), attrs: { scope: "row" } }), el("td", { text: usdText(live.result.tce_usd_day, "usd_day") + " a day" })]),
    ]),
  ])]);
  live.speedFrame.replaceChildren(svg, table);
  tooltip(live.speedFrame, svg, regions);
}

/* ------------------------------------------------------------ sections --- */

function methodSection(inner) {
  const block = el("div", { class: "block" });
  for (const paragraph of calc.words.method) block.appendChild(el("p", { class: "prose", text: paragraph }));
  inner.appendChild(block);
}

/* A best speed at an end of the speeds searched says which end; "" for one
 * inside them. */
function boundMark(cell, speed) {
  if (cell.at_top) return speed.bound_marks.top;
  if (cell.at_bottom) return speed.bound_marks.bottom;
  return "";
}

/* A best speed's cell: the figure right aligned in its column like every
 * other, and its end of the range, where it has one, in a quieter span after
 * it that hangs in the room the column keeps (styles: .col-bound). */
function bestSpeedCell(cell, speed, bound) {
  const figure = formatCell(cell.optimal_laden_kn, "knots_2", decimals);
  const td = figureCell(figure, "optimal_laden_kn", bound);
  const mark = boundMark(cell, speed);
  // The space keeps "15.00 top" two words for a screen reader and a copy of the table.
  if (mark && figure !== null) td.replaceChildren(el("span", {}, [figure, " ", el("span", { class: "bound-mark", text: mark })]));
  return td;
}

function speedSection(inner) {
  const speed = data.speed;
  inner.appendChild(sentence("p", speed.lead, decimals, "lead block"));
  // The room a marked column keeps after its figures: the longest mark and a space, in characters.
  const markChars = Math.max(...Object.values(speed.bound_marks).map((mark) => mark.length)) + 1;
  for (const routeEntry of speed.routes) {
    const bound = routeEntry.grid.some((cell) => boundMark(cell, speed)) ? "col-bound" : "";
    const head = el("tr", {}, [
      el("th", { text: "Freight", attrs: { scope: "col" } }),
      el("th", { text: "Bunkers", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "VLSFO, " + UNITS.usd_t, attrs: { scope: "col", "data-short": "VLSFO" } }),
      el("th", { class: ["col-num", bound].filter(Boolean).join(" "), text: "Best laden speed, " + UNITS.knots, attrs: { scope: "col", "data-short": "best speed" } }),
      el("th", { class: "col-num", text: "TCE at the best speed, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE at best" } }),
      el("th", { class: "col-num", text: "TCE at the priced speed, " + UNITS.usd_day, attrs: { scope: "col", "data-short": "TCE at the priced speed" } }),
    ]);
    const body = el("tbody");
    for (const cell of routeEntry.grid) {
      body.appendChild(el("tr", {}, [
        el("th", { attrs: { scope: "row" } }, [cell.freight_words]),
        el("td", { class: "words", text: cell.bunker_words }),
        figureCell(formatCell(cell.vlsfo_usd_t, "usd_t", decimals), "vlsfo_usd_t"),
        bestSpeedCell(cell, speed, bound),
        figureCell(formatCell(cell.optimal_tce_usd_day, "usd_day", decimals), "optimal_tce_usd_day"),
        figureCell(formatCell(cell.reference_tce_usd_day, "usd_day", decimals), "reference_tce_usd_day"),
      ]));
    }
    const table = el("table", { class: "table" }, [el("thead", {}, [head]), body]);
    table.style.setProperty("--mark-chars", String(markChars));
    inner.appendChild(el("div", { class: "block" }, [scrollTable([appendSegments(el("span"), routeEntry.caption, decimals)], table)]));
  }
  inner.appendChild(el("p", { class: "note block", text: speed.note }));
}

function assumptionsSection(inner) {
  const words = calc.assumptions;
  // What the voyage leaves out as it now stands: the routing's items, less those the visitor has filled.
  live.assumptionsList = el("ul", { class: "plain-list" });
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: words.leaves_out_heading }),
    live.assumptionsList,
  ]));
  drawAssumptions();
  inner.appendChild(el("div", { class: "block" }, [
    el("h3", { class: "block__heading", text: words.statuses_heading }),
    el("ul", { class: "plain-list" }, words.statuses.map(([status, text]) => el("li", {}, [el("span", { class: "field__status", text: calc.status_words[status] + ": " }), text]))),
  ]));
}

/* The Data section shows the inputs as they now stand, so every change redraws it. */
function dataSection(inner) {
  live.dataInner = inner;
  drawData();
}

function drawData() {
  const inner = live.dataInner;
  if (!inner) return;
  clear(inner);
  const head = el("tr", {}, [
    el("th", { text: "Input", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Value", attrs: { scope: "col", "data-short": "value" } }),
    el("th", { text: "Unit", attrs: { scope: "col", "data-short": "unit" } }),
    el("th", { text: "Status", attrs: { scope: "col", "data-short": "status" } }),
    el("th", { text: "Source or reason", attrs: { scope: "col", "data-short": "source" } }),
  ]);
  const body = el("tbody");
  for (const [path, spec] of Object.entries(calc.input_labels)) {
    if (!cited(path) && !changed.has(path)) continue;
    const info = sourceOf(path);
    const raw = get(inputs, path);
    let value;
    if (Array.isArray(raw)) value = el("td", { class: "words", text: raw.map(([v, c]) => formatNumber(v, "knots", decimals) + " kn: " + formatNumber(c, "tpd", decimals) + " " + UNITS.tpd).join(", ") });
    else if (path === "war_risk.payer") value = el("td", { class: "words", text: calc.payer_words[raw] });
    else if (typeof raw === "string") value = el("td", { class: "words", text: raw });
    else if (raw === null || raw === undefined || (info.status === "empty" && !raw)) value = el("td", { class: "num is-missing", text: calc.status_words.empty });
    else value = figureCell(formatCell(raw * spec.scale, path === "freight_value" ? freightFormat() : spec.format, decimals), path);
    const format = path === "freight_value" ? freightFormat() : spec.format;
    body.appendChild(el("tr", { attrs: { "data-status": info.status } }, [
      el("th", { text: spec.label, attrs: { scope: "row" } }),
      value,
      el("td", { class: "nowrap", text: format ? UNITS[format] : "" }),
      el("td", { class: "status status--" + info.status, text: calc.status_words[info.status] || "" }),
      el("td", { class: "words", text: firstUpper(info.status === "changed" ? sourceLine(path) : info.source) }),
    ]));
  }
  const table = el("table", { class: "table table--inputs" }, [el("thead", {}, [head]), body]);
  inner.appendChild(el("div", { class: "block" }, [scrollTable([calc.words.data_caption], table)]));
}
