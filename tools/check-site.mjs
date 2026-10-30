#!/usr/bin/env node
// The site in headless Chromium: every view drawn at a wide and a narrow
// width; the Map view, where the site opens, with a route picked from the
// list, from the address and with the keyboard; and the calculator's form,
// what a visitor types and what the page must then show. tools/validate-engine.mjs holds src/engine.js to the Python
// engine; this holds the pages that read it, which no other check reaches.
//
//     python scripts/serve.py --port 8150                 in another shell
//     node tools/check-site.mjs [--base URL] [--browser PATH]
//
// Each check opens a view afresh, acts the way a visitor does (a value typed,
// then the input event; a button clicked; a key pressed) and reads the page.
// The figures the page must show are computed here by the same engine module
// on the artifact's inputs, and written by the page's own format module, so a
// check fails when the form layer loses, mislays or misformats a figure.
// Exit status 1 on any failed check or any console error.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { argValue, launch, openView } from "./browser.mjs";
import * as engine from "../src/engine.js";
import { formatNumber, segmentsText } from "../src/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BASE = argValue(process.argv, "--base") || "http://localhost:8150/voyage-tce-model/";
const read = (name) => JSON.parse(readFileSync(path.join(ROOT, "data", name + ".json"), "utf8"));

const calc = read("calculator");
const overview = read("overview");
const atlas = read("atlas");
engine.configure(read("engine").constants);
const decimals = calc.conventions.decimals;
const VIEWS = ["map", "overview", "calculator", "routes", "detours", "carbon", "paper", "method"];
const WIDTHS = [1440, 320];

const clone = (value) => JSON.parse(JSON.stringify(value));
const presetById = (id) => calc.presets.find((p) => p.id === id);
const latestOf = (route) => calc.presets.filter((p) => p.route === route).reduce((a, b) => (b.date > a.date ? b : a));
const fill = (template, values) => template.replace(/\{(\w+)\}/g, (all, name) => (name in values ? values[name] : all));
const usd = (value, format) => "USD " + formatNumber(value, format, decimals, { context: "prose" });

/** The sentence the calculator must show for these inputs, from the engine. */
function verdictFor(inputs) {
  const result = engine.evaluate(inputs);
  const tce = result.tce_usd_day;
  const template = tce < 0 ? calc.words.verdict_negative : calc.words.verdict;
  return fill(template, { tce: usd(Math.abs(tce), "usd_day"), days: formatNumber(result.days.total, "days", decimals) });
}

/* Snippets run in the page. */
const text = (selector) => "((document.querySelector(" + JSON.stringify(selector) + ") || {}).textContent || '')";
const attr = (selector, name) => "((document.querySelector(" + JSON.stringify(selector) + ") || { getAttribute: () => null }).getAttribute(" + JSON.stringify(name) + "))";

function typeInto(selector, value) {
  return "(() => { const input = document.querySelector(" + JSON.stringify(selector) + ");" +
    " input.value = " + JSON.stringify(value) + ";" +
    " input.dispatchEvent(new Event('input', { bubbles: true }));" +
    " input.dispatchEvent(new Event('change', { bubbles: true })); return true; })()";
}

function choose(selector, value) {
  return "(() => { const select = document.querySelector(" + JSON.stringify(selector) + ");" +
    " select.value = " + JSON.stringify(value) + ";" +
    " select.dispatchEvent(new Event('change', { bubbles: true })); return true; })()";
}

function click(selector) {
  return "(() => { document.querySelector(" + JSON.stringify(selector) + ").click(); return true; })()";
}

const VERDICT = ".calc-verdict";
const featured = presetById(overview.featured);
const defaultPreset = presetById(calc.default_preset);
const c5 = latestOf("C5");
const td3c = latestOf("TD3C");
const tc20 = latestOf("TC20");

const CHECKS = [];

for (const view of VIEWS) {
  for (const width of WIDTHS) {
    CHECKS.push({
      name: "the " + view + " view draws its title and its figures at " + width + " px, with no sideways scroll",
      hash: "#/" + view,
      width,
      async run(page) {
        const title = await page.evaluate(text("#view-title"));
        const figures = await page.evaluate("document.querySelectorAll('#view svg, #view table').length");
        const overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
        return [
          [title.trim().length > 0, "no view title"],
          [figures > 0, "no chart, map or table drawn"],
          [overflow <= 0, "the page scrolls sideways by " + overflow + " px"],
        ];
      },
    });
  }
}

CHECKS.push(
  {
    name: "the overview's TCE is the export's figure, and the browser engine gives the same for the featured voyage",
    hash: "#/overview",
    async run(page) {
      const fact = overview.facts.find((f) => f.id === "tce");
      const shown = await page.evaluate(text("[data-fact=\"tce\"] .fact__figure"));
      const expected = formatNumber(fact.value.value, fact.value.format, decimals, { context: "prose" });
      const browser = engine.evaluate(featured.inputs).tce_usd_day;
      return [
        [shown.trim() === expected, "the overview shows " + shown + ", the artifact holds " + expected],
        [Math.abs(browser - fact.value.value) < 1e-6, "src/engine.js gives " + browser + " for " + featured.id + ", the export " + fact.value.value],
      ];
    },
  },
  {
    name: "the calculator opens on the featured voyage with the engine's TCE",
    hash: "#/calculator",
    async run(page) {
      const shown = await page.evaluate(text(VERDICT));
      const expected = verdictFor(defaultPreset.inputs);
      return [
        [calc.default_preset === overview.featured, "the calculator opens on " + calc.default_preset + ", the overview features " + overview.featured],
        [shown === expected, "the verdict reads \"" + shown + "\", the engine gives \"" + expected + "\""],
      ];
    },
  },
  {
    name: "a freight typed under Market moves the TCE to the engine's figure, and Reset brings the preset back",
    hash: "#/calculator?open=market",
    async run(page) {
      const before = await page.evaluate(text(VERDICT));
      const typed = Math.round(defaultPreset.inputs.freight_value * 1.1);
      await page.evaluate(typeInto("#field-freight_value", typed.toLocaleString("en-US")));
      const after = await page.evaluate(text(VERDICT));
      const status = await page.evaluate(attr(".field[data-path=\"freight_value\"]", "data-status"));
      const inputs = clone(defaultPreset.inputs);
      inputs.freight_value = typed;
      const expected = verdictFor(inputs);
      await page.evaluate(click(".field[data-path=\"freight_value\"] .field__reset"));
      const reset = await page.evaluate(text(VERDICT));
      return [
        [after === expected, "after typing " + typed + " the verdict reads \"" + after + "\", the engine gives \"" + expected + "\""],
        [status === "changed", "the field's status is " + status + ", not changed"],
        [reset === before, "Reset left \"" + reset + "\", not \"" + before + "\""],
      ];
    },
  },
  {
    name: "a Worldscale rate with no public flat rate gives no TCE and says why, until a flat rate is typed",
    hash: "#/calculator?preset=" + td3c.id + "&open=market",
    async run(page) {
      const blocked = await page.evaluate(text(VERDICT));
      const hidden = await page.evaluate("[...document.querySelectorAll('.calc__outputs figure')].every((f) => f.hidden)");
      const status = await page.evaluate(attr(".field[data-path=\"flat_rate_usd_t\"]", "data-status"));
      // A flat rate typed by a visitor; the page holds none.
      const flat = 20;
      await page.evaluate(typeInto("#field-flat_rate_usd_t", String(flat)));
      const priced = await page.evaluate(text(VERDICT));
      const inputs = clone(td3c.inputs);
      inputs.flat_rate_usd_t = flat;
      const expected = verdictFor(inputs);
      return [
        [td3c.inputs.freight_basis === "ws" && !td3c.inputs.flat_rate_usd_t, td3c.id + " is not a Worldscale preset without a flat rate"],
        [blocked === calc.words.ws_missing, "the blocked verdict reads \"" + blocked + "\""],
        [hidden, "a figure is drawn without a TCE to draw"],
        [status === "empty", "the flat rate field's status is " + status + ", not empty"],
        [priced === expected, "with a flat rate of " + flat + " the verdict reads \"" + priced + "\", the engine gives \"" + expected + "\""],
      ];
    },
  },
  {
    name: "a Gulf premium is the charterer's and leaves the owner's TCE alone; paid by the owner, the TCE is the engine's",
    hash: "#/calculator?preset=" + tc20.id + "&open=costs",
    async run(page) {
      const before = await page.evaluate(text(VERDICT));
      // A premium a visitor types, in percent of hull value a period; the page holds none.
      const premium = 7.5;
      await page.evaluate(typeInto("#field-war_risk-areas-gulf-premium_pct", String(premium)));
      const charterer = await page.evaluate(text(VERDICT));
      const line = await page.evaluate(text(".war-periods"));
      await page.evaluate(choose("#field-war-payer", "owner"));
      const owner = await page.evaluate(text(VERDICT));
      const inputs = clone(tc20.inputs);
      inputs.war_risk.areas.gulf.premium_pct = premium;
      inputs.war_risk.payer = "owner";
      const expected = verdictFor(inputs);
      const periods = engine.evaluate(inputs).war_risk.areas.gulf.periods;
      return [
        [tc20.inputs.war_risk.areas.gulf.entries > 0, tc20.id + " does not enter the Gulf"],
        [charterer === before, "with the charterer paying the verdict moved to \"" + charterer + "\""],
        [line.includes(periods === 1 ? calc.words.war_period_one : String(periods)), "the periods line reads \"" + line + "\""],
        [owner === expected, "with the owner paying the verdict reads \"" + owner + "\", the engine gives \"" + expected + "\""],
      ];
    },
  },
  {
    name: "a routing sets its distances, canal days and listed areas; the Red Sea ballast transit is the owner's",
    hash: "#/calculator?preset=" + tc20.id + "&open=route,costs",
    async run(page) {
      // TC20 laden round the Cape, ballast back through Suez and the Red Sea.
      const variant = tc20.routings.find((v) => v.laden === "no_suez" && v.ballast === "direct");
      await page.evaluate(choose("#field-routing-laden", "no_suez"));
      const routed = await page.evaluate(text(VERDICT));
      // A premium a visitor types, in percent of hull value a period; the page holds none.
      const premium = 0.5;
      await page.evaluate(typeInto("#field-war_risk-areas-red_sea-premium_pct", String(premium)));
      const priced = await page.evaluate(text(VERDICT));
      const leaves = await page.evaluate(text(".leaves-out"));
      const inputs = clone(tc20.inputs);
      for (const [path, value] of Object.entries(variant.patch)) {
        const keys = path.split(".");
        keys.slice(0, -1).reduce((node, key) => node[key], inputs)[keys[keys.length - 1]] = clone(value);
      }
      const routedExpected = verdictFor(inputs);
      inputs.war_risk.areas.red_sea.premium_pct = premium;
      const expected = verdictFor(inputs);
      const result = engine.evaluate(inputs);
      return [
        [Boolean(variant), tc20.id + " offers no Cape laden, Suez ballast routing"],
        [routed === routedExpected, "routed round the Cape laden the verdict reads \"" + routed + "\", the engine gives \"" + routedExpected + "\""],
        [priced === expected, "with a Red Sea premium the verdict reads \"" + priced + "\", the engine gives \"" + expected + "\""],
        [result.costs.war_risk > 0 && result.war_risk.areas.red_sea.periods === 0, "the ballast transit is not the owner's alone in the engine"],
        [!leaves.includes("Suez Canal toll on the laden leg"), "the leaves-out line still names the laden Suez toll: " + leaves],
      ];
    },
  },
  {
    name: "a route FFA typed on Paper is priced by the engine against the 5TC (182) strip",
    hash: "#/paper?open=hedge",
    async run(page) {
      const paper = read("paper");
      const row = paper.capesize[0];
      // A route FFA a visitor types; the page holds none.
      const typed = 30;
      await page.evaluate(typeInto("#field-route-ffa", String(typed)));
      const shown = await page.evaluate(text(".route-ffa__result"));
      const net = engine.evaluate({ ...row.inputs, freight_basis: "usd_t", freight_value: typed }).tce_usd_day;
      const gross = net / (1 - row.commission_pct / read("engine").constants.PERCENT);
      const expected = usd(gross, "usd_day");
      return [[shown.includes(expected), "the box reads \"" + shown + "\", the engine's grossed up TCE is " + expected]];
    },
  },
  {
    name: "switching a priced voyage to Worldscale asks for the flat rate first",
    hash: "#/calculator?open=market",
    async run(page) {
      await page.evaluate(choose("#field-freight-basis", "ws"));
      const shown = await page.evaluate(text(VERDICT));
      return [[shown === calc.words.ws_missing, "the verdict reads \"" + shown + "\""]];
    },
  },
  {
    name: "the freight for a target TCE is the engine's, in USD a tonne",
    hash: "#/calculator",
    async run(page) {
      const target = 100000;
      await page.evaluate(typeInto("#field-target-tce", target.toLocaleString("en-US")));
      const shown = await page.evaluate(text(".breakeven__item:first-child .breakeven__value"));
      const expected = formatNumber(engine.freight_for_tce(defaultPreset.inputs, target).usd_t, "usd_t", decimals);
      return [[shown === expected, "for " + target + " a day the page asks " + shown + ", the engine " + expected]];
    },
  },
  {
    name: "a route button opens that route's latest preset and writes it to the address",
    hash: "#/calculator",
    async run(page) {
      await page.evaluate(click("button[data-route=\"" + c5.route + "\"]"));
      await page.waitFor("location.hash.includes(" + JSON.stringify("preset=" + c5.id) + ")");
      const shown = await page.evaluate(text(VERDICT));
      const pressed = await page.evaluate(attr("button[data-route=\"" + c5.route + "\"]", "aria-pressed"));
      const expected = verdictFor(c5.inputs);
      return [
        [shown === expected, "the verdict reads \"" + shown + "\", the engine gives \"" + expected + "\""],
        [pressed === "true", "the route button is not pressed"],
      ];
    },
  },
  {
    name: "a section button opens its section, draws it and writes it to the address",
    hash: "#/overview",
    async run(page) {
      await page.evaluate(click("button[data-section=\"method\"]"));
      await page.waitFor("location.hash.includes('open=method')");
      const expanded = await page.evaluate(attr("button[data-section=\"method\"]", "aria-expanded"));
      const drawn = await page.evaluate("document.querySelector('#' + document.querySelector('button[data-section=\"method\"]').getAttribute('aria-controls') + ' .section__inner').children.length");
      return [
        [expanded === "true", "aria-expanded is " + expanded],
        [drawn > 0, "the open section is empty"],
      ];
    },
  },
  {
    name: "the T key switches the theme and remembers it",
    hash: "#/overview",
    async run(page) {
      const before = await page.evaluate("document.documentElement.dataset.theme");
      await page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 't', bubbles: true })), true");
      const after = await page.evaluate("document.documentElement.dataset.theme");
      const stored = await page.evaluate("localStorage.getItem('nc-theme')");
      return [
        [before === "light" && after === "dark", "the theme went from " + before + " to " + after],
        [stored === after, "localStorage holds " + stored],
      ];
    },
  },
  {
    name: "an address that names no view says so and links to the Map, where the site opens",
    hash: "#/nowhere",
    async run(page) {
      const title = await page.evaluate(text("#view-title"));
      const said = await page.evaluate(text("#view"));
      const link = await page.evaluate("[...document.querySelectorAll('#view a')].some((a) => a.getAttribute('href') === '#/map')");
      return [
        [title.length > 0 && said.includes("nowhere"), "the page does not name the address typed"],
        [link, "no link to the Map"],
      ];
    },
  },
);

/* ------------------------------------------------------------ the Map view --- */

const atlasItem = (id) => atlas.items.find((item) => item.id === id);
const rowsShown = "[...document.querySelectorAll('.atlas-row[data-item]')].map((row) => row.getAttribute('data-item'))";
const focused = "(document.activeElement && (document.activeElement.getAttribute('data-item') || document.activeElement.className)) || ''";

CHECKS.push(
  {
    name: "an empty address opens the Map, with its nav link marked as the page",
    hash: "#/",
    async run(page) {
      const title = await page.evaluate(text("#view-title"));
      const current = await page.evaluate(attr(".site-nav a[href=\"#/map\"]", "aria-current"));
      const rows = await page.evaluate(rowsShown);
      return [
        [title.trim() === atlas.page.title, "the title reads \"" + title.trim() + "\""],
        [current === "page", "the Map link's aria-current is " + current],
        [rows.length === atlas.items.length, rows.length + " rows listed, the artifact holds " + atlas.items.length],
      ];
    },
  },
  {
    name: "the nav takes at most two rows at 320 px",
    hash: "#/map",
    width: 320,
    async run(page) {
      const rows = await page.evaluate("new Set([...document.querySelectorAll('.site-nav a')].map((a) => Math.round(a.getBoundingClientRect().top))).size");
      return [[rows <= 2, "the nav takes " + rows + " rows"]];
    },
  },
);

for (const [id, width] of [["TD3C", 1440], ["TD3C", 320], ["P7", 1440], ["P7", 320]]) {
  CHECKS.push({
    name: "the address #/map?route=" + id + " draws " + id + " and its figures at " + width + " px, with no sideways scroll",
    hash: "#/map?route=" + id + "&open=table,method",
    width,
    async run(page) {
      const heading = await page.evaluate(text(".atlas-panel__title"));
      const current = await page.evaluate("[...document.querySelectorAll('.atlas-route.is-current')].map((g) => g.getAttribute('data-item')).join(',')");
      const tce = await page.evaluate(text(".atlas-fact[data-fact] .atlas-fact__value"));
      const first = atlasItem(id).facts[0];
      const overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
      return [
        [heading.trim() === atlasItem(id).heading, "the detail's heading reads \"" + heading.trim() + "\""],
        [current === id, "the map draws " + (current || "no route") + " as the route picked"],
        [tce.trim() === segmentsText(first.value, atlas.conventions.decimals), "the first fact reads \"" + tce.trim() + "\""],
        [overflow <= 0, "the page scrolls sideways by " + overflow + " px"],
      ];
    },
  });
}

CHECKS.push(
  {
    name: "a row of the list opens its route, writes it to the address and moves focus to its heading; Back to the list returns focus to the row",
    hash: "#/map",
    async run(page) {
      await page.evaluate(click(".atlas-row[data-item=\"TC20\"]"));
      await page.waitFor("location.hash.includes('route=TC20') && document.activeElement && document.activeElement.classList.contains('atlas-panel__title')");
      const opened = await page.evaluate(text(".atlas-panel__title"));
      await page.evaluate(click(".atlas-back"));
      await page.waitFor("!location.hash.includes('route=') && document.querySelector('.atlas-row[data-item=\"TC20\"]')");
      await page.evaluate("new Promise((r) => setTimeout(r, 200))");
      const back = await page.evaluate(focused);
      return [
        [opened.trim() === atlasItem("TC20").heading, "the detail opened on \"" + opened.trim() + "\""],
        [back === "TC20", "focus is on " + (back || "nothing") + ", not on the TC20 row"],
      ];
    },
  },
  {
    name: "Escape closes a route opened from its address, and the address follows",
    hash: "#/map?route=TD3C",
    async run(page) {
      await page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })), true");
      await page.waitFor("!location.hash.includes('route=') && document.querySelector('.atlas-list')");
      const rows = await page.evaluate(rowsShown);
      return [[rows.length === atlas.items.length, rows.length + " rows listed after Escape"]];
    },
  },
  {
    name: "a filter keeps its routes only, is pressed, is written to the address and is said in the status line",
    hash: "#/map",
    async run(page) {
      await page.evaluate(click(".atlas-filters button[data-segment=\"dirty\"]"));
      await page.waitFor("location.hash.includes('segment=dirty')");
      const pressed = await page.evaluate(attr(".atlas-filters button[data-segment=\"dirty\"]", "aria-pressed"));
      const rows = await page.evaluate(rowsShown);
      const expected = atlas.items.filter((item) => item.segment === "dirty").map((item) => item.id);
      const status = await page.evaluate(text("#view-status"));
      const filter = atlas.page.filters.find((f) => f.id === "dirty");
      return [
        [pressed === "true", "the dirty tankers button's aria-pressed is " + pressed],
        [rows.length === expected.length && rows.every((id) => expected.includes(id)), "the list shows " + rows.join(", ")],
        [status.trim() === segmentsText(filter.announce, atlas.conventions.decimals), "the status line reads \"" + status.trim() + "\""],
      ];
    },
  },
  {
    name: "an address naming no route says so, leaves the address and lists every route",
    hash: "#/map?route=NOWHERE",
    async run(page) {
      const message = await page.evaluate(text(".atlas-message"));
      const hidden = await page.evaluate("document.querySelector('.atlas-message').hidden");
      const rows = await page.evaluate(rowsShown);
      const hash = await page.evaluate("location.hash");
      return [
        [!hidden && message.includes("NOWHERE"), "the page does not name the route typed"],
        [!hash.includes("NOWHERE"), "the address still reads " + hash],
        [rows.length === atlas.items.length, rows.length + " rows listed"],
      ];
    },
  },
);

console.log("check-site.mjs, " + BASE);
const browser = await launch(process.argv);
let failed = 0;
try {
  const page = await browser.page();
  for (const check of CHECKS) {
    page.errors.length = 0;
    let results;
    try {
      await openView(page, BASE, { hash: check.hash, width: check.width || 1440, theme: "light" });
      results = await check.run(page);
    } catch (error) {
      results = [[false, error.message]];
    }
    const errors = page.errors.filter((m) => !/chrome-extension:\/\//.test(m) && /^(exception|console error|log error)/.test(m));
    for (const error of errors) results.push([false, error]);
    const problems = results.filter(([ok]) => !ok).map(([, message]) => message);
    console.log((problems.length ? "  FAIL  " : "  ok    ") + check.name);
    for (const problem of problems) console.log("        " + problem);
    if (problems.length) failed += 1;
  }
} finally {
  await browser.close();
}
console.log("");
if (failed) {
  console.log("FAIL  " + failed + " of " + CHECKS.length + " checks");
  process.exit(1);
}
console.log("PASS  " + CHECKS.length + " checks: every view draws at both widths, the Map opens, picks and closes a route, and the calculator shows the engine's figures for what is typed");
