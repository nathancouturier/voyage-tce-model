#!/usr/bin/env node
// The site in headless Chromium: every view drawn at a wide and a narrow
// width; the Map view, where the site opens, with a route picked from the
// list, from the address and with the keyboard, its history (Back closes a
// route in one step, from a link to another route and after the browser's
// Back and Forward) with the filter, the focus and the sections open kept
// right, an address typed with its own sections taken as it is, its layout
// on a phone, the browser's own input on it (a finger's tap on a row of the
// list on a phone's first screen opens that route; a row focused or pointed
// at on a phone, or the mouse on a map too narrow for labels, moves nothing
// under it, and nor does the mouse along every line where the line under
// the map names what it is on; the first click on a line after Back to the
// list opens that route, and a click on a half pixel of a screen of two
// device pixels a CSS pixel opens the route the map points at), its list
// and a route's detail (a same-water route's name a target of its own; the
// text spaced as WCAG 1.4.12 allows, nothing cut), and its drawing (the
// route picked painted over the rest, each name by its own place, the
// Pacific's by its ring, every routing named with nothing picked and none
// nearer another line than its own, a click on a routing pressing its
// toggle where the page stands, a routing drawn once and only where it
// leaves its route); and the
// calculator's form,
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
      const heading = await page.evaluate(text(".atlas-map-heading"));
      return [
        [title.trim() === atlas.page.title, "the title reads \"" + title.trim() + "\""],
        [current === "page", "the Map link's aria-current is " + current],
        [rows.length === atlas.items.length, rows.length + " rows listed, the artifact holds " + atlas.items.length],
        // The map carries its figures at this width, as its heading says.
        [heading.trim() === atlas.page.map.title, "the map's heading reads \"" + heading.trim() + "\""],
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
    // Opened as a new document: the page rewrites this address as it reads it.
    direct: true,
    async run(page) {
      await page.waitFor("document.querySelector('.atlas-message') && !document.querySelector('.atlas-message').hidden", 5000);
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

/* --------------------------------------- the Map's history and sections --- */

const escape = "document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })), true";
const panelOf = (id) => "document.querySelector('.atlas-panel[data-item=\"" + id + "\"]')";
const listShown = "document.querySelector('.atlas-list') && !location.hash.includes('route=')";
const sectionsOpen = "[...document.querySelectorAll('.section__button[aria-expanded=\"true\"]')].map((b) => b.getAttribute('data-section')).join(',')";

CHECKS.push(
  {
    name: "closing a route the restored filter would not list clears the filter and gives focus back to its row",
    hash: "#/map",
    async run(page) {
      await page.evaluate(click(".atlas-filters button[data-segment=\"dirty\"]"));
      await page.waitFor("location.hash.includes('segment=dirty')");
      await page.evaluate(click(".atlas-row[data-item=\"TD3C\"]"));
      await page.waitFor(panelOf("TD3C"));
      // TC1 is a clean tanker, its line running with TD3C's.
      await page.evaluate(click(".atlas-same a[data-item=\"TC1\"]"));
      await page.waitFor(panelOf("TC1"));
      await page.evaluate(escape);
      await page.waitFor(listShown);
      await page.evaluate("new Promise((r) => setTimeout(r, 200))");
      const hash = await page.evaluate("location.hash");
      const pressed = await page.evaluate(attr(".atlas-filters button[data-segment=\"all\"]", "aria-pressed"));
      const rows = await page.evaluate(rowsShown);
      const back = await page.evaluate(focused);
      return [
        [!hash.includes("segment="), "the address keeps the filter: " + hash],
        [pressed === "true", "the filter for every route is not pressed"],
        [rows.length === atlas.items.length, rows.length + " rows listed"],
        [back === "TC1", "focus is on " + (back || "nothing") + ", not on the TC1 row"],
      ];
    },
  },
  {
    name: "a link from one route to another replaces its history entry, so Back to the list closes it in one step",
    hash: "#/map",
    async run(page) {
      await page.evaluate(click(".atlas-row[data-item=\"TD34\"]"));
      await page.waitFor(panelOf("TD34"));
      const length = await page.evaluate("history.length");
      await page.evaluate(click(".atlas-links a[href*=\"route=TD3C\"]"));
      await page.waitFor(panelOf("TD3C"));
      const after = await page.evaluate("history.length");
      await page.evaluate(click(".atlas-back"));
      await page.waitFor(listShown);
      // Forward again reaches the route's entry, which Back to the list went back from.
      await page.evaluate("history.forward(), true");
      await page.waitFor(panelOf("TD3C"), 3000).catch(() => {});
      const forward = await page.evaluate("location.hash");
      return [
        [after === length, "the link to TD3C added a history entry (" + length + " to " + after + ")"],
        [forward.includes("route=TD3C"), "Back to the list did not go back from TD3C's entry: Forward reads " + forward],
      ];
    },
  },
  {
    name: "after the browser's Back and Forward, Back to the list still goes back in history",
    hash: "#/map",
    async run(page) {
      await page.evaluate(click(".atlas-row[data-item=\"TD22\"]"));
      await page.waitFor(panelOf("TD22"));
      await page.evaluate("history.back(), true");
      await page.waitFor(listShown);
      await page.evaluate("history.forward(), true");
      await page.waitFor(panelOf("TD22"));
      const length = await page.evaluate("history.length");
      await page.evaluate(click(".atlas-back"));
      await page.waitFor(listShown);
      const after = await page.evaluate("history.length");
      await page.evaluate("history.forward(), true");
      await page.waitFor(panelOf("TD22"), 3000).catch(() => {});
      const forward = await page.evaluate("location.hash");
      return [
        [after === length, "Back to the list changed the history's length from " + length + " to " + after],
        [forward.includes("route=TD22"), "Back to the list rewrote the route's entry: Forward reads " + forward],
      ];
    },
  },
  {
    name: "a section open stays open when a route is picked from a row or a fact under the list, and when the route is closed",
    hash: "#/map?open=table",
    async run(page) {
      await page.evaluate(click(".atlas-row[data-item=\"TD22\"]"));
      await page.waitFor(panelOf("TD22"));
      const picked = await page.evaluate("location.hash");
      // A second section opened on the route, then the route closed.
      await page.evaluate(click("button[data-section=\"method\"]"));
      await page.waitFor("location.hash.includes('method')");
      await page.evaluate(click(".atlas-back"));
      await page.waitFor(listShown);
      await page.evaluate("new Promise((r) => setTimeout(r, 200))");
      const closed = await page.evaluate("location.hash");
      const open = await page.evaluate(sectionsOpen);
      const fact = atlas.page.summary.items[0].item;
      await page.evaluate(click(".atlas-glance__value[data-item=\"" + fact + "\"]"));
      await page.waitFor(panelOf(fact));
      const glance = await page.evaluate("location.hash");
      return [
        [picked.includes("open=table") && picked.includes("route=TD22"), "a row's click led to " + picked],
        [closed.includes("table") && closed.includes("method") && open === "table,method", "closing the route left " + closed + " with " + (open || "nothing") + " open"],
        [glance.includes("table") && glance.includes("method") && glance.includes("route=" + fact), "a fact's click led to " + glance],
      ];
    },
  },
  {
    name: "an address typed while a route is open that names its own sections closes the route and opens those sections",
    hash: "#/map?route=TD22&open=table",
    async run(page) {
      await page.evaluate("(location.hash = '#/map?open=method'), true");
      await page.waitFor(listShown);
      await page.evaluate("new Promise((r) => setTimeout(r, 200))");
      const hash = await page.evaluate("location.hash");
      const open = await page.evaluate(sectionsOpen);
      return [[hash === "#/map?open=method" && open === "method", "the address became " + hash + " with " + (open || "nothing") + " open"]];
    },
  },
  {
    name: "on a short phone screen a route picked from the list shows its heading, and a routing shown from its toggle brings the map into view",
    hash: "#/map",
    width: 320,
    height: 568,
    async run(page) {
      // On screen within a pixel: the page scrolls by whole pixels, and a box may not sit on one.
      const seen = (expression) => "(() => { const b = " + expression + ".getBoundingClientRect(); return b.top > -1 && b.bottom < innerHeight + 1; })()";
      await page.evaluate("document.querySelector('.atlas-row[data-item=\"TC20\"]').focus(), true");
      await page.evaluate(click(".atlas-row[data-item=\"TC20\"]"));
      await page.waitFor("document.activeElement && document.activeElement.classList.contains('atlas-panel__title')");
      const heading = await page.evaluate(seen("document.activeElement"));
      await page.evaluate("document.querySelector('.atlas-alt-entry__show').scrollIntoView({ block: 'center' }), true");
      await page.evaluate(click(".atlas-alt-entry__show"));
      const map = await page.evaluate(seen("document.querySelector('.atlas-frame')"));
      const kept = await page.evaluate("document.activeElement.classList.contains('atlas-alt-entry__show')");
      return [
        [heading, "the route's heading, which has focus, is off the screen"],
        [map, "the map is off the screen after a routing is shown from its toggle"],
        [kept, "focus left the toggle"],
      ];
    },
  },
  {
    name: "on a phone the list follows the map and the line under it, the legend follows the list, and the words round a map too narrow for labels send the reader to the list",
    hash: "#/map",
    width: 390,
    async run(page) {
      const parts = [".atlas-map", ".atlas-caption", ".atlas-filters", ".atlas-row[data-item]", ".atlas-legend"];
      const tops = await page.evaluate("[" + parts.map((s) => "document.querySelector(" + JSON.stringify(s) + ").getBoundingClientRect().top").join(", ") + "]");
      const heading = await page.evaluate(text(".atlas-map-heading"));
      const idle = await page.evaluate(text(".atlas-caption"));
      return [
        [tops.every((top, i) => i === 0 || top > tops[i - 1]), parts.map((s, i) => s + " at " + Math.round(tops[i])).join(", ")],
        [heading.trim() === atlas.page.map.title_narrow, "the heading reads \"" + heading.trim() + "\""],
        [idle.trim() === atlas.page.map.idle_narrow, "the line under the map reads \"" + idle.trim() + "\""],
      ];
    },
  },
);

/* ------------------------------------ the Map under a finger and a mouse --- */

/* These act through the browser's own input, a finger's touch or the mouse's
 * events at a point, not element.click(), which no row's or line's own
 * pointer and focus events precede. */
const frame = "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(true))))";
const routeShown = "((document.querySelector('.atlas-panel') || { getAttribute: () => null }).getAttribute('data-item'))";
const pointedAt = "((document.querySelector('.atlas-route.is-hover') || { getAttribute: () => null }).getAttribute('data-item'))";

/** In the page: the points of a route's line on the screen, each on a whole
 *  pixel and on the line as drawn (what a press there lands on), where no
 *  other route's line comes within `clear` px, so the map can point at no
 *  other route there. Serialised into the page. */
function clearPoints(id, clear) {
  const trace = (path) => {
    const matrix = path.getScreenCTM();
    const length = path.getTotalLength();
    const out = [];
    for (let at = 0; at <= length; at += length / 400) out.push(path.getPointAtLength(at).matrixTransform(matrix));
    return out;
  };
  const lines = [...document.querySelectorAll(".atlas-route:not(.is-hidden) .atlas-route__line")];
  const own = lines.find((path) => path.closest(".atlas-route").getAttribute("data-item") === id);
  const others = lines.filter((path) => path !== own).map(trace);
  return trace(own)
    .map((point) => ({ x: Math.round(point.x), y: Math.round(point.y) }))
    .filter((point) => point.x > 0 && point.y > 0 && point.x < innerWidth && point.y < innerHeight)
    .filter((point) => {
      const hit = document.elementFromPoint(point.x, point.y);
      return Boolean(hit && hit.closest(".atlas-route") && hit.closest(".atlas-route").getAttribute("data-item") === id);
    })
    .filter((point) => others.every((line) => line.every((q) => Math.hypot(q.x - point.x, q.y - point.y) > clear)));
}

/** Moves the mouse to points of a route's line on the map clear of every
 *  other route's (by the band a line takes a pointer in, 14 px, as
 *  src/map.js ATLAS_GEOMETRY.HIT) until the map points at that route, and
 *  returns that point on the screen, or null. */
async function pointAtRoute(page, id) {
  const points = await page.evaluate("(" + clearPoints.toString() + ")(" + JSON.stringify(id) + ", 14)");
  // A few points spread along the line are enough.
  const step = Math.max(1, Math.floor(points.length / 8));
  for (const point of points.filter((p, i) => i % step === 0)) {
    await page.mouseMove(point.x, point.y);
    await page.evaluate(frame);
    if (await page.evaluate(pointedAt) === id) return point;
  }
  return null;
}

/* In the page: each row on the first screen, at the middle of its code's
 * line and at the middle of its part on the screen. */
const firstScreenTaps = "[...document.querySelectorAll('.atlas-row[data-item]')].filter((row) => row.getBoundingClientRect().top < innerHeight).flatMap((row) => {" +
  " const box = row.getBoundingClientRect(); const code = row.querySelector('.atlas-row__code').getBoundingClientRect(); const x = box.left + box.width / 2; const id = row.getAttribute('data-item');" +
  " return [{ id, where: 'first line', x, y: (code.top + code.bottom) / 2 }, { id, where: 'middle', x, y: (box.top + Math.min(box.bottom, innerHeight)) / 2 }]; })" +
  ".filter((tap) => tap.y < innerHeight - 1)";

for (const [width, height] of [[390, 844], [414, 896]]) {
  CHECKS.push({
    name: "on a " + width + " by " + height + " px touch screen a tap on the first line or the middle of each row on the first screen opens that row's route",
    hash: "#/map",
    width,
    height,
    touch: true,
    async run(page) {
      const taps = await page.evaluate(firstScreenTaps);
      const missed = [];
      for (const [index, tap] of taps.entries()) {
        // Each tap on the list as the page first shows it.
        if (index) await openView(page, BASE, { hash: "#/map", width, height, touch: true });
        await page.tap(tap.x, tap.y);
        await page.waitFor(routeShown + " === " + JSON.stringify(tap.id), 3000).catch(() => {});
        const opened = await page.evaluate(routeShown);
        if (opened !== tap.id) missed.push("a tap on the " + tap.where + " of " + tap.id + " at " + Math.round(tap.y) + " px opened " + (opened || "nothing"));
      }
      return [
        [taps.length > 0, "no row on the first screen"],
        [missed.length === 0, missed.join("; ")],
      ];
    },
  });
}

for (const width of [1440, 768]) {
  CHECKS.push({
    name: "at " + width + " px, with focus back on a row after Back to the list, the first click on that route's line on the map opens it again, and the first on another route's line opens that one",
    hash: "#/map",
    width,
    async run(page) {
      const results = [];
      for (const id of ["C5", "TC20"]) {
        if (await page.evaluate(routeShown)) {
          await page.evaluate(click(".atlas-back"));
          await page.waitFor(listShown);
        }
        await page.evaluate(click(".atlas-row[data-item=\"C5\"]"));
        await page.waitFor(panelOf("C5"));
        await page.evaluate(click(".atlas-back"));
        await page.waitFor(listShown + " && document.activeElement && document.activeElement.getAttribute('data-item') === 'C5'");
        await page.evaluate("document.querySelector('.atlas-frame').scrollIntoView({ block: 'nearest' }), true");
        await page.evaluate(frame);
        const at = await pointAtRoute(page, id);
        if (!at) {
          results.push([false, "no point on " + id + "'s line where the map points at it"]);
          continue;
        }
        await page.mouseClick(at.x, at.y);
        await page.waitFor(routeShown + " === " + JSON.stringify(id), 3000).catch(() => {});
        const opened = await page.evaluate(routeShown);
        results.push([opened === id, "the first click on " + id + "'s line opened " + (opened || "nothing")]);
      }
      return results;
    },
  });
}

CHECKS.push({
  name: "at 390 px a row focused or pointed at raises its route on the map and moves neither the line under the map nor the list, and the mouse on a map too narrow for labels leaves them too",
  hash: "#/map",
  width: 390,
  height: 844,
  async run(page) {
    // Where the list and the line under the map stand on the page, and the route the map raises over the others.
    const where = "(() => ({ list: Math.round(document.querySelector('.atlas-row[data-item=\"P7\"]').getBoundingClientRect().top + scrollY), line: document.querySelector('.atlas-caption').textContent }))()";
    const raised = "(() => { const last = document.querySelector('.atlas-routes').lastElementChild; return last && last.classList.contains('is-hover') ? last.getAttribute('data-item') : ''; })()";
    const before = await page.evaluate(where);
    await page.evaluate("document.querySelector('.atlas-row[data-item=\"C5\"]').focus(), true");
    const focused = await page.evaluate(where);
    const focusRaised = await page.evaluate(raised);
    await page.evaluate("document.activeElement.blur(), true");
    // Off every row first, so the mouse enters the row it moves to.
    await page.mouseMove(1, 1);
    const row = await page.evaluate("(() => { document.querySelector('.atlas-row[data-item=\"C5\"]').scrollIntoView({ block: 'center' }); const b = document.querySelector('.atlas-row[data-item=\"P7\"] .atlas-row__code').getBoundingClientRect(); return { x: b.left + b.width / 2, y: (b.top + b.bottom) / 2 }; })()");
    await page.mouseMove(row.x, row.y);
    await page.evaluate(frame);
    const pointed = await page.evaluate(where);
    const pointRaised = await page.evaluate(raised);
    await page.evaluate("window.scrollTo(0, 0), true");
    // The first of these routes with a stretch of line clear of the others on a map this narrow.
    let line = null;
    for (const id of ["C5", "C3", "TD20", "TC20"]) {
      line = line || ((await pointAtRoute(page, id)) && id);
    }
    const onMap = await page.evaluate(where);
    const same = (after) => after.list === before.list && after.line === before.line;
    return [
      [same(focused) && focusRaised === "C5", "with the C5 row focused the map raises " + (focusRaised || "nothing") + ", the list moved from " + before.list + " to " + focused.list + " px and the line reads \"" + focused.line + "\""],
      [same(pointed) && pointRaised === "P7", "with the mouse on the P7 row the map raises " + (pointRaised || "nothing") + ", the list moved from " + before.list + " to " + pointed.list + " px and the line reads \"" + pointed.line + "\""],
      [line !== null && same(onMap), line ? "with the mouse on " + line + "'s line the list moved from " + before.list + " to " + onMap.list + " px and the line reads \"" + onMap.line + "\"" : "no point on a route's line where the map points at it"],
    ];
  },
});

/** In the page: points along every route's line on the map, `along` to a
 *  line, each on it and `off` px either side, within the map and the
 *  screen. Serialised into the page. */
function linePoints(along, off) {
  const map = document.querySelector(".atlas-map").getBoundingClientRect();
  return [...document.querySelectorAll(".atlas-route:not(.is-hidden) .atlas-route__line")].flatMap((path) => {
    const matrix = path.getScreenCTM();
    const length = path.getTotalLength();
    const out = [];
    for (let i = 0; i <= along; i += 1) {
      const a = path.getPointAtLength((length * i) / along).matrixTransform(matrix);
      const b = path.getPointAtLength(Math.min(length, (length * i) / along + 1)).matrixTransform(matrix);
      const span = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      for (const side of [0, off, -off]) out.push({ x: a.x - ((b.y - a.y) / span) * side, y: a.y + ((b.x - a.x) / span) * side });
    }
    return out;
  }).filter((p) => p.x > map.left + 1 && p.y > map.top + 1 && p.x < map.right - 1 && p.y < map.bottom - 1 && p.y > 0 && p.y < innerHeight);
}

for (const [width, height] of [[540, 900], [768, 1024], [1100, 800]]) {
  CHECKS.push({
    name: "at " + width + " px the mouse along every route's line on the map, on it and 3 px either side, moves neither the list nor the legend: the line under the map keeps the room of the longest it can bring",
    hash: "#/map",
    width,
    height,
    async run(page) {
      await page.evaluate("document.querySelector('.atlas-frame').scrollIntoView({ block: 'nearest' }), true");
      await page.evaluate(frame);
      const where = "(() => ({ list: Math.round(document.querySelector('.atlas-row[data-item]').getBoundingClientRect().top + scrollY), legend: Math.round(document.querySelector('.atlas-legend').getBoundingClientRect().top + scrollY) }))()";
      const before = await page.evaluate(where);
      const points = await page.evaluate("(" + linePoints.toString() + ")(50, 3)");
      const moved = [];
      for (const point of points) {
        await page.mouseMove(point.x, point.y);
        const now = await page.evaluate(where);
        if (now.list === before.list && now.legend === before.legend) continue;
        moved.push("at (" + Math.round(point.x) + ", " + Math.round(point.y) + ") the list moved " + (now.list - before.list) + " px and the legend " + (now.legend - before.legend) + " px, the line reading \"" + (await page.evaluate(text(".atlas-caption"))) + "\"");
        if (moved.length === 3) break;
      }
      return [
        [points.length > 0, "no point on the map's lines"],
        [moved.length === 0, moved.join("; ")],
      ];
    },
  });
}

/** In the page: pointer positions across a route's line, from its start to
 *  `to` of its length at `steps` + 1 places, each 4 px either side of it by
 *  half pixels, as a screen of two device pixels a CSS pixel gives them.
 *  Serialised into the page. */
function halfPixels(id, to, steps) {
  const path = document.querySelector(".atlas-route[data-item=\"" + id + "\"] .atlas-route__line");
  const matrix = path.getScreenCTM();
  const length = path.getTotalLength();
  const seen = new Set();
  const out = [];
  for (let i = 0; i <= steps; i += 1) {
    const a = path.getPointAtLength((length * to * i) / steps).matrixTransform(matrix);
    const b = path.getPointAtLength(Math.min(length, (length * to * i) / steps + 0.5)).matrixTransform(matrix);
    const span = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    for (let side = -4; side <= 4; side += 0.5) {
      const x = Math.round((a.x - ((b.y - a.y) / span) * side) * 2) / 2;
      const y = Math.round((a.y + ((b.x - a.x) / span) * side) * 2) / 2;
      if (seen.has(x + "," + y)) continue;
      seen.add(x + "," + y);
      out.push({ x, y });
    }
  }
  return out;
}

CHECKS.push({
  name: "on a screen of two device pixels a CSS pixel, where TD3C and TC20 share water by Ras Tanura, a click opens the route the map points at wherever in its pixel the pointer stands",
  hash: "#/map",
  width: 1440,
  height: 900,
  async run(page) {
    // A click gives whole pixels; the pointer's own events, half pixels on such a screen.
    await page.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false });
    await page.reload();
    await page.waitFor("document.querySelector('.atlas-row[data-item]') && document.fonts.status === 'loaded'");
    await page.evaluate(frame);
    const points = await page.evaluate("(" + halfPixels.toString() + ")('TD3C', 0.06, 6)");
    const missed = [];
    let clicks = 0;
    for (const point of points) {
      await page.mouseMove(point.x, point.y);
      const pointed = await page.evaluate(pointedAt);
      if (!pointed) continue;
      clicks += 1;
      await page.mouseClick(point.x, point.y);
      await page.waitFor(routeShown + " !== null", 3000).catch(() => {});
      const opened = await page.evaluate(routeShown);
      if (opened !== pointed) missed.push("at (" + point.x + ", " + point.y + ") the map points at " + pointed + " and a click opens " + (opened || "nothing"));
      if (opened) {
        await page.evaluate(click(".atlas-back"));
        await page.waitFor(listShown);
        // The list as it first stood, with no row focused and the map where it was.
        await page.evaluate("document.activeElement && document.activeElement.blur(), window.scrollTo(0, 0), true");
      }
      // Off the map, so the next point starts with nothing pointed at.
      await page.mouseMove(1439, 899);
      await page.evaluate(frame);
    }
    return [
      [clicks > 0, "no point by Ras Tanura where the map points at a route"],
      [missed.length === 0, missed.length + " of " + clicks + " clicks: " + missed.slice(0, 3).join("; ")],
    ];
  },
});

/** In the page: each routing named on the map with nothing picked (`whole`,
 *  the artifact's whole_label to its route and routing), the distance in px
 *  from its name's box to its own routing's line as drawn and to the
 *  nearest other line drawn, every route's and every other routing's, read
 *  at points a pixel apart. Serialised into the page. */
function routingNames(whole) {
  const shown = (node) => !node.closest(".is-hidden");
  const cache = new Map();
  const points = (path) => {
    if (!cache.has(path)) {
      const matrix = path.getScreenCTM();
      const length = path.getTotalLength();
      const n = Math.max(1, Math.ceil(length * matrix.a));
      const out = [];
      for (let i = 0; i <= n; i += 1) out.push(path.getPointAtLength((length * i) / n).matrixTransform(matrix));
      cache.set(path, out);
    }
    return cache.get(path);
  };
  const from = (box, paths) => Math.min(...paths.flatMap(points).map((p) => Math.hypot(Math.max(box.left - p.x, 0, p.x - box.right), Math.max(box.top - p.y, 0, p.y - box.bottom))));
  const routes = [...document.querySelectorAll(".atlas-route .atlas-route__line")].filter(shown);
  const routings = [...document.querySelectorAll(".atlas-alt")].filter(shown);
  return [...document.querySelectorAll(".atlas-labels text.atlas-label__alt:not(.halo)")].filter((t) => whole[t.textContent]).map((t) => {
    const [item, alt] = whole[t.textContent];
    const box = t.getBoundingClientRect();
    const own = routings.find((g) => g.getAttribute("data-item") === item && g.getAttribute("data-alt") === alt);
    const others = [...routes, ...routings.filter((g) => g !== own).flatMap((g) => [...g.querySelectorAll("path")])];
    return { name: t.textContent, own: from(box, [...own.querySelectorAll("path")]), other: from(box, others) };
  });
}
const wholeNames = Object.fromEntries(atlas.items.flatMap((item) => item.alternatives.filter((alt) => alt.whole_label).map((alt) => [alt.whole_label, [item.id, alt.id]])));

for (const width of [640, 960, 1140]) {
  CHECKS.push({
    name: "with nothing picked at " + width + " px no routing's name lies nearer another line drawn than its own by more than 3.5 px, the margin by which a click tells two lines apart",
    hash: "#/map",
    width,
    async run(page) {
      const names = await page.evaluate("(" + routingNames.toString() + ")(" + JSON.stringify(wholeNames) + ")");
      // Read at points a pixel apart, so half a pixel more is the reading's own error.
      const astray = names.filter((name) => name.other < name.own - 3.5 - 0.5);
      return [
        [names.length > 0, "no routing named"],
        [astray.length === 0, astray.map((name) => "\"" + name.name + "\" is " + name.own.toFixed(1) + " px from its own line and " + name.other.toFixed(1) + " px from another").join("; ")],
      ];
    },
  });
}

/* ------------------------------------------------- the Map's list and detail --- */

/** The legend's samples the map draws for a route, in the legend's order, from
 *  data/map.json: its ballast leg, its ECA stretches, its routings drawn and
 *  the rings where any of its lines leaves the map. */
function legendFor(item) {
  const own = new Set([item.legs.laden, item.legs.ballast]);
  const routings = item.alternatives.filter((alt) => alt.legs.some((key) => !own.has(key)));
  const legs = [item.legs.laden, item.legs.ballast].filter(Boolean);
  const kinds = new Set(["picked", "other"]);
  if (item.legs.ballast) kinds.add("picked-ballast");
  if (legs.some((key) => geo.legs[key].eca.length)) kinds.add("eca");
  if (routings.length) kinds.add("alternative-picked");
  if ([...legs, ...routings.flatMap((alt) => alt.legs)].some((key) => geo.legs[key].edges.length)) kinds.add("edge");
  return atlas.page.map.legend.filter((sample) => kinds.has(sample.kind)).map((sample) => sample.kind).join(",");
}
const legendShown = "[...document.querySelectorAll('.atlas-legend .map-legend__item')].filter((li) => !li.hidden).map((li) => li.getAttribute('data-kind')).join(',')";
/* The text's own box, not its cell's. */
const textBox = (expression) => "(() => { const range = document.createRange(); range.selectNodeContents(" + expression + "); return range.getBoundingClientRect(); })()";

for (const id of ["TD3C", "QD_RTM_PMX", "C5", "P7"]) {
  CHECKS.push({
    name: "with " + id + " picked its figure is at display size, each toggle is named for its routing, its same-water links are full targets, its freight and costs have a heading, and the legend keys only what the map draws",
    hash: "#/map?route=" + id,
    async run(page) {
      const item = atlasItem(id);
      const size = await page.evaluate("getComputedStyle(document.querySelector('.atlas-facts--head .atlas-fact .atlas-fact__value .fig')).fontSize");
      const display = await page.evaluate("(() => { const probe = document.body.appendChild(document.createElement('span')); probe.className = 'fact__figure'; const size = getComputedStyle(probe).fontSize; probe.remove(); return size; })()");
      const toggles = await page.evaluate("[...document.querySelectorAll('.atlas-alt-entry__show')].map((b) => b.textContent)");
      const links = await page.evaluate("[...document.querySelectorAll('.atlas-same a')].map((a) => a.getBoundingClientRect().height)");
      const heads = await page.evaluate("[...document.querySelectorAll('.atlas-panel h3')].map((h) => h.textContent + ' > ' + (h.nextElementSibling ? h.nextElementSibling.className : ''))");
      const legend = await page.evaluate(legendShown);
      const more = item.more + " > atlas-facts";
      return [
        [size === display, "the figure is " + size + ", the overview's facts " + display],
        [toggles.every((t) => t.startsWith(atlas.page.panel.show)) && new Set(toggles).size === toggles.length, "the toggles read " + JSON.stringify(toggles)],
        [links.every((h) => h >= 44), "a same-water link is " + Math.min(...links) + " px tall"],
        [heads.includes(more), "the headings in the detail are " + JSON.stringify(heads)],
        [legend === legendFor(item), "the legend shows " + legend + ", the map draws " + legendFor(item)],
      ];
    },
  });
}

/* In the page: every point inside a same-water route's own letters that a
 * tap would give to another link, or to none. */
const sameWaterMisses = "(() => { document.querySelector('.atlas-same').scrollIntoView({ block: 'center' }); const out = [];" +
  " for (const a of document.querySelectorAll('.atlas-same a')) { const range = document.createRange(); range.selectNodeContents(a);" +
  " for (const q of range.getClientRects()) for (let x = q.left + 1; x < q.right - 1; x += 2) for (let y = q.top + 1; y < q.bottom - 1; y += 2) {" +
  " const hit = document.elementFromPoint(x, y); const link = hit && hit.closest('a');" +
  " if (link !== a) out.push(a.textContent + ' at ' + Math.round(x) + ',' + Math.round(y) + ' goes to ' + (link ? link.textContent : 'nothing')); } }" +
  " return out.slice(0, 4); })()";

for (const [id, width] of [["TD3C", 320], ["TD34", 320], ["TD34", 375], ["TD34", 1100]]) {
  CHECKS.push({
    name: "with " + id + " picked at " + width + " px a tap anywhere on a same-water route's name opens that route, not the one beside or below it",
    hash: "#/map?route=" + id,
    width,
    async run(page) {
      const misses = await page.evaluate(sameWaterMisses);
      return [[misses.length === 0, misses.join("; ")]];
    },
  });
}

/* The WCAG 1.4.12 spacing a reader's own style may set on any page. */
const SPACED = "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }";
const labelsCut = "(() => { const svg = document.querySelector('.atlas-map'); const s = svg.getBoundingClientRect();" +
  " return [...svg.querySelectorAll('.atlas-labels text:not(.halo)')].filter((t) => { const b = t.getBoundingClientRect();" +
  " return b.left < s.left - 0.5 || b.right > s.right + 0.5 || b.top < s.top - 0.5 || b.bottom > s.bottom + 0.5; }).map((t) => t.textContent); })()";

for (const id of ["TD25", "TD3C"]) {
  CHECKS.push({
    name: "with " + id + " picked at 320 px and the text spaced as WCAG 1.4.12 allows, nothing scrolls sideways and no name on the map runs past it",
    hash: "#/map?route=" + id,
    width: 320,
    async run(page) {
      await page.evaluate("(() => { const style = document.createElement('style'); style.textContent = " + JSON.stringify(SPACED) + "; document.head.appendChild(style); return true; })()");
      await page.evaluate("new Promise((r) => setTimeout(r, 400))");
      const overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
      const cut = await page.evaluate(labelsCut);
      return [
        [overflow <= 0, "the page scrolls sideways by " + overflow + " px"],
        [cut.length === 0, "the map cuts " + cut.join(", ")],
      ];
    },
  });
}

for (const width of [320, 1440]) {
  CHECKS.push({
    name: "at " + width + " px each row's qualifier is read before its figure, the figures line up, each routing is a line after its sample, and the study's heads keep apart",
    hash: "#/map",
    width,
    async run(page) {
      const cells = await page.evaluate("[...document.querySelectorAll('.atlas-row[data-item]')].map((row) => ({ id: row.getAttribute('data-item'), tce: row.querySelector('.atlas-row__tce .atlas-row__figure').textContent, alts: [...row.querySelectorAll('.atlas-row__alt')].map((a) => a.textContent), right: row.querySelector('.atlas-row__tce .fig').getBoundingClientRect().right }))");
      const wrong = cells.filter((cell) => {
        const item = atlasItem(cell.id);
        return cell.tce !== segmentsText(item.row.tce, atlas.conventions.decimals) ||
          JSON.stringify(cell.alts) !== JSON.stringify(item.row.alts.map((line) => segmentsText(line, atlas.conventions.decimals)));
      });
      const rights = cells.map((cell) => cell.right);
      const study = await page.evaluate("(() => { const heads = [...document.querySelectorAll('.atlas-row--head')]; const head = heads[heads.length - 1]; return [" + textBox("head.children[0]") + ", " + textBox("head.children[1]") + "].map((b) => ({ left: b.left, right: b.right })); })()");
      const also = await page.evaluate("document.querySelectorAll('.atlas-row__also').length");
      return [
        [wrong.length === 0, wrong.map((cell) => cell.id + " reads " + JSON.stringify(cell.tce) + " and " + JSON.stringify(cell.alts)).join("; ")],
        [Math.max(...rights) - Math.min(...rights) <= 1, "the figures end between " + Math.min(...rights) + " and " + Math.max(...rights) + " px"],
        [study[0].right <= study[1].left, "the study's first head ends at " + study[0].right + " px, over the next starting at " + study[1].left],
        [also === 0, "a row still carries an \"Also\" line"],
      ];
    },
  });
}

CHECKS.push({
  name: "picking the route with the longest heading does not move the map at 1440 px",
  hash: "#/map",
  async run(page) {
    const longest = atlas.items.reduce((a, b) => (b.map_title.length > a.map_title.length ? b : a));
    const where = "document.querySelector('.atlas-map').getBoundingClientRect().top + scrollY";
    const before = await page.evaluate(where);
    await page.evaluate(click(".atlas-row[data-item=\"" + longest.id + "\"]"));
    await page.waitFor(panelOf(longest.id));
    const after = await page.evaluate(where);
    return [[Math.abs(after - before) < 0.5, "the map moved from " + before + " to " + after + " px when " + longest.id + " was picked"]];
  },
});

/* ---------------------------------------------------- the Map's drawing --- */

/* The line and routing groups the map shows, in the order they are painted
 * (document order inside the svg), each as its route, "alt" for a routing,
 * and its state. */
const painted = "[...document.querySelectorAll('.atlas-map .atlas-route, .atlas-map .atlas-alt')]" +
  ".filter((g) => !g.classList.contains('is-hidden'))" +
  ".map((g) => ({ id: g.getAttribute('data-item'), alt: g.classList.contains('atlas-alt'), current: g.classList.contains('is-current'), focus: g.classList.contains('is-focus') }))";

/** In the page: each port and passage name on the map, with its distance in
 *  screen px from its own point and from the nearest other named point (a
 *  port's dot, or a passage whose name is drawn). Serialised into the page. */
function namesAndPoints(ports, passages) {
  const svg = document.querySelector(".atlas-map");
  const ctm = svg.getScreenCTM();
  const screen = (point) => {
    const at = new DOMPoint(point.x, point.y).matrixTransform(ctm);
    return { x: at.x, y: at.y };
  };
  const names = [...svg.querySelectorAll(".atlas-labels text:not(.halo)")].filter((t) => /atlas-label__(port|passage)/.test(t.getAttribute("class")));
  const dots = [...svg.querySelectorAll(".atlas-marks .map-port-dot")].map((c) => ({ x: Number(c.getAttribute("cx")), y: Number(c.getAttribute("cy")) }));
  const points = [
    ...ports.filter((port) => dots.some((dot) => Math.hypot(dot.x - port.x, dot.y - port.y) < 0.05)),
    ...passages.filter((passage) => names.some((t) => t.textContent === passage.name)),
  ].map((point) => ({ name: point.name, ...screen(point) }));
  const away = (box, point) => Math.hypot(Math.max(box.left - point.x, 0, point.x - box.right), Math.max(box.top - point.y, 0, point.y - box.bottom));
  return names.map((t) => {
    const box = t.getBoundingClientRect();
    const own = points.find((point) => point.name === t.textContent);
    const others = points.filter((point) => point !== own).map((point) => ({ name: point.name, distance: away(box, point) })).sort((a, b) => a.distance - b.distance);
    return { name: t.textContent, own: own ? away(box, own) : null, other: others[0] || null };
  });
}
const geo = read("map").atlas;

CHECKS.push({
  name: "the route picked is painted over every other route, its routings over the rest, and the routing its toggle shows over everything",
  hash: "#/map?route=TD3C",
  async run(page) {
    const before = await page.evaluate(painted);
    const routes = before.filter((g) => !g.alt);
    const last = routes[routes.length - 1] || {};
    const firstOwn = before.findIndex((g) => g.current);
    const lastOther = before.map((g) => g.current).lastIndexOf(false);
    await page.evaluate(click(".atlas-alt-entry__show"));
    const after = await page.evaluate(painted);
    const top = after[after.length - 1] || {};
    return [
      [last.id === "TD3C" && last.current, "the last route painted is " + (last.id || "none") + ", not TD3C"],
      [firstOwn > lastOther, "a route or routing of another route is painted over TD3C's own lines"],
      [top.alt && top.focus && top.id === "TD3C", "the routing shown from its toggle is not painted last"],
    ];
  },
});

for (const [id, width] of [["TC20", 1440], ["TC20", 320], ["TC1", 1440], ["TC1", 320]]) {
  CHECKS.push({
    name: "with " + id + " picked at " + width + " px each port and passage is named nearer its own point than any other, and both ends of its laden leg are named",
    hash: "#/map?route=" + id,
    width,
    async run(page) {
      const names = await page.evaluate("(" + namesAndPoints.toString() + ")(" + JSON.stringify(Object.values(geo.ports)) + ", " + JSON.stringify(geo.passages) + ")");
      const leg = geo.legs[atlasItem(id).legs.laden];
      const ends = [geo.ports[leg.from].name, geo.ports[leg.to].name];
      const misplaced = names.filter((n) => n.own === null || (n.other && n.other.distance <= n.own));
      return [
        [misplaced.length === 0, misplaced.map((n) => "\"" + n.name + "\" is " + (n.own === null ? "drawn with no point of its own" : n.other.distance.toFixed(1) + " px from " + n.other.name + " and " + n.own.toFixed(1) + " px from its own point")).join("; ")],
        [ends.every((end) => names.some((n) => n.name === end)), "the map names " + names.map((n) => n.name).join(", ") + ", not both of " + ends.join(" and ")],
      ];
    },
  });
}

CHECKS.push({
  name: "a click on a dotted routing of the route picked presses that routing's toggle and keeps the route",
  hash: "#/map?route=TC20",
  async run(page) {
    const routing = atlasItem("TC20").alternatives.find((alt) => alt.kind === "routing");
    const toggle = ".atlas-alt-entry[data-alt=\"" + routing.id + "\"] .atlas-alt-entry__show";
    // The middle of the routing's first leg, where it runs apart from the route's own lines.
    const at = await page.evaluate("(() => { const path = document.querySelector('.atlas-alt.is-current[data-alt=" + JSON.stringify(routing.id) + "] path');" +
      " const point = path.getPointAtLength(path.getTotalLength() / 2).matrixTransform(path.getScreenCTM()); return { x: point.x, y: point.y }; })()");
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
      await page.send("Input.dispatchMouseEvent", { type, x: at.x, y: at.y, button: "left", clickCount: 1 });
    }
    await page.waitFor("document.querySelector(" + JSON.stringify(toggle) + ").getAttribute('aria-pressed') === 'true'", 3000).catch(() => {});
    const pressed = await page.evaluate(attr(toggle, "aria-pressed"));
    const shown = await page.evaluate("[...document.querySelectorAll('.atlas-alt.is-focus')].map((g) => g.getAttribute('data-alt')).join(',')");
    const hash = await page.evaluate("location.hash");
    return [
      [pressed === "true", "the toggle of " + routing.id + " is not pressed after a click on its line"],
      [shown === routing.id, "the map shows " + (shown || "no routing") + " at full weight"],
      [hash.includes("route=TC20"), "the click left TC20 for " + hash],
    ];
  },
});

/** In the page: each name of the side where lines leave the map, with its
 *  distance in screen px from the nearest ring and from the nearest passage
 *  the route's lines use (named or not) or port dot. */
function edgeNames(passages, words) {
  const svg = document.querySelector(".atlas-map");
  const ctm = svg.getScreenCTM();
  const screen = (x, y) => new DOMPoint(x, y).matrixTransform(ctm);
  const away = (box, point) => Math.hypot(Math.max(box.left - point.x, 0, point.x - box.right), Math.max(box.top - point.y, 0, point.y - box.bottom));
  const rings = [...svg.querySelectorAll(".atlas-marks .atlas-edge")].map((c) => screen(Number(c.getAttribute("cx")), Number(c.getAttribute("cy"))));
  const dots = [...svg.querySelectorAll(".atlas-marks .map-port-dot")].map((c) => screen(Number(c.getAttribute("cx")), Number(c.getAttribute("cy"))));
  const points = [...passages.map((p) => screen(p.x, p.y)), ...dots];
  return [...svg.querySelectorAll(".atlas-labels text:not(.halo)")].filter((t) => t.textContent === words).map((t) => {
    const box = t.getBoundingClientRect();
    return { ring: Math.min(...rings.map((r) => away(box, r))), other: Math.min(...points.map((q) => away(box, q))) };
  });
}

for (const width of [768, 1100]) {
  CHECKS.push({
    name: "with P7 picked at " + width + " px the Panama Canal is named, and each name for the Pacific lies nearer its ring than any passage or port",
    hash: "#/map?route=P7",
    width,
    async run(page) {
      const passages = atlasItem("P7").passages.map((name) => geo.passages.find((p) => p.name === name)).filter(Boolean);
      const edges = await page.evaluate("(" + edgeNames.toString() + ")(" + JSON.stringify(passages) + ", " + JSON.stringify(atlas.page.map.edge) + ")");
      const names = await page.evaluate("[...document.querySelectorAll('.atlas-labels text:not(.halo)')].map((t) => t.textContent)");
      const astray = edges.filter((edge) => edge.other <= edge.ring);
      return [
        [names.includes("Panama Canal"), "the map names " + names.join(", ")],
        [edges.length > 0 && astray.length === 0, astray.map((edge) => "a Pacific name is " + edge.ring.toFixed(1) + " px from its ring and " + edge.other.toFixed(1) + " px from a passage or port").join("; ") || "no Pacific name"],
      ];
    },
  });
}

for (const width of [768, 1100, 1440]) {
  CHECKS.push({
    name: "with nothing picked at " + width + " px every routing the map names in the artifact is named on it",
    hash: "#/map",
    width,
    async run(page) {
      const named = await page.evaluate("[...document.querySelectorAll('.atlas-labels text.atlas-label__alt:not(.halo)')].map((t) => t.textContent)");
      const expected = atlas.items.flatMap((item) => item.alternatives.filter((alt) => alt.whole_label).map((alt) => alt.whole_label));
      const missing = expected.filter((name) => !named.includes(name));
      return [[missing.length === 0, "the map does not name " + missing.join(", ")]];
    },
  });
}

CHECKS.push({
  name: "below 1100 px a click on a routing on the map presses its toggle where the page stands, focus staying where it was",
  hash: "#/map?route=TC20",
  width: 768,
  async run(page) {
    const routing = atlasItem("TC20").alternatives.find((alt) => alt.kind === "routing");
    const toggle = ".atlas-alt-entry[data-alt=\"" + routing.id + "\"] .atlas-alt-entry__show";
    // The map partly scrolled off the top, as a reader who scrolled down the column a little leaves it.
    await page.evaluate("window.scrollTo(0, document.querySelector('.atlas-frame').getBoundingClientRect().top + scrollY + 40), true");
    const at = await page.evaluate("(() => { const path = document.querySelector('.atlas-alt.is-current[data-alt=" + JSON.stringify(routing.id) + "] path');" +
      " const point = path.getPointAtLength(path.getTotalLength() / 2).matrixTransform(path.getScreenCTM()); return { x: point.x, y: point.y }; })()");
    const before = await page.evaluate("scrollY");
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
      await page.send("Input.dispatchMouseEvent", { type, x: at.x, y: at.y, button: "left", clickCount: 1 });
    }
    await page.waitFor("document.querySelector(" + JSON.stringify(toggle) + ").getAttribute('aria-pressed') === 'true'", 3000).catch(() => {});
    const pressed = await page.evaluate(attr(toggle, "aria-pressed"));
    const after = await page.evaluate("scrollY");
    const active = await page.evaluate("document.activeElement ? document.activeElement.className : ''");
    return [
      [pressed === "true", "the toggle of " + routing.id + " is not pressed after a click on its line"],
      [Math.abs(after - before) < 1, "the page scrolled from " + before + " to " + after + " px"],
      [!String(active).includes("atlas-alt-entry__show"), "focus moved to the toggle"],
    ];
  },
});

CHECKS.push({
  name: "a routing is drawn only where it leaves its route, out and back on one path, and shown from its toggle it is the only routing named",
  hash: "#/map?route=P7",
  async run(page) {
    // P7's three routings round the Cape: both ways, back only and laden only, the last two sharing a leg with P7.
    const item = atlasItem("P7");
    const own = [item.legs.laden, item.legs.ballast].map((key) => geo.legs[key].d);
    const shown = item.alternatives.find((alt) => alt.kind === "routing" && alt.legs.some((key) => own.includes(geo.legs[key].d)));
    await page.evaluate(click(".atlas-alt-entry[data-alt=\"" + shown.id + "\"] .atlas-alt-entry__show"));
    const drawn = await page.evaluate("[...document.querySelectorAll('.atlas-map .atlas-alt.is-current path')].map((p) => p.getAttribute('d'))");
    const named = await page.evaluate("[...document.querySelectorAll('.atlas-labels text[data-alt]:not(.halo)')].map((t) => t.getAttribute('data-alt'))");
    return [
      [!drawn.some((d) => own.includes(d)), "a routing draws a dotted copy of P7's own line"],
      [new Set(drawn).size === 1, "the water round the Cape is drawn on " + new Set(drawn).size + " paths, whose dots fall between each other's"],
      [named.every((id) => id === shown.id), "with " + shown.id + " shown the map names " + named.join(", ")],
    ];
  },
});

console.log("check-site.mjs, " + BASE);
const browser = await launch(process.argv);
let failed = 0;
try {
  const page = await browser.page();
  for (const check of CHECKS) {
    page.errors.length = 0;
    let results;
    try {
      await openView(page, BASE, { hash: check.hash, width: check.width || 1440, height: check.height, theme: "light", direct: check.direct, touch: check.touch });
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
console.log("PASS  " + CHECKS.length + " checks: every view draws at both widths, the Map opens, picks and closes a route and keeps its history, focus and sections right, and the calculator shows the engine's figures for what is typed");
