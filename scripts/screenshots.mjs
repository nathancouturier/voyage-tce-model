#!/usr/bin/env node
// Full page screenshots of the site, from its subpath, in headless Chromium.
//
//     python scripts/serve.py --port 8150                          in another shell
//     node scripts/screenshots.mjs                                 the README's set, into assets/
//     node scripts/screenshots.mjs --matrix --out <dir>            every view at 1440, 768, 390 and
//                                                                  320 px in both themes
//     node scripts/screenshots.mjs --matrix --open --out <dir>     the same with every section open
//     node scripts/screenshots.mjs --base https://nathancouturier.github.io/voyage-tce-model/
//     node scripts/screenshots.mjs --only overview                 shots whose names start so
//
// One PNG per shot, each the whole page, every pixel of its height, with every
// console error or uncaught exception the page raised printed beside it. The
// theme is set the way a visitor's choice is, through the nc-theme key in
// localStorage, before the page loads. The browser is any Chromium, found by
// tools/browser.mjs; every run uses a fresh profile.
//
// Exit status 1 if any shot fails, the page logged an error, or the page
// scrolls sideways, so a run that photographed a broken page does not look
// like a good one. The sibling studies' script, with this site's views.

import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { argValue, launch, openView } from "../tools/browser.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const argv = process.argv;
const BASE = argValue(argv, "--base") || "http://localhost:8150/voyage-tce-model/";
const OUT = path.resolve(ROOT, argValue(argv, "--out") || "assets");

const WIDTHS = { desktop: 1440, tablet: 768, mobile: 390, narrow: 320 };
const HEIGHTS = { desktop: 900, tablet: 1024, mobile: 844, narrow: 640 };
const THEMES = ["light", "dark"];

/* Every view, and the sections that open behind its buttons. */
const VIEWS = {
  overview: { hash: "#/overview", open: "method,assumptions,data" },
  calculator: { hash: "#/calculator", open: "ship,route,market,costs,advanced,method,speed,data" },
  routes: { hash: "#/routes", open: "method,assumptions,data" },
  detours: { hash: "#/detours", open: "suez,dry,hormuz,method,data" },
  carbon: { hash: "#/carbon", open: "method,fueleu,data" },
  paper: { hash: "#/paper", open: "hedge,tankers,method,data" },
  method: { hash: "#/method", open: "conventions,formulas,validation,sources,limitations,downloads" },
};

/* The README's set. */
const README = [
  { name: "overview-desktop-light", view: "overview", size: "desktop", theme: "light" },
  { name: "overview-desktop-dark", view: "overview", size: "desktop", theme: "dark" },
  { name: "overview-mobile-light", view: "overview", size: "mobile", theme: "light" },
  { name: "calculator-desktop-light", view: "calculator", size: "desktop", theme: "light", hash: "#/calculator?open=market&preset=latest-c5" },
  { name: "routes-desktop-light", view: "routes", size: "desktop", theme: "light" },
  { name: "detours-desktop-dark", view: "detours", size: "desktop", theme: "dark" },
  { name: "carbon-desktop-light", view: "carbon", size: "desktop", theme: "light" },
  { name: "paper-desktop-light", view: "paper", size: "desktop", theme: "light" },
  { name: "method-desktop-dark", view: "method", size: "desktop", theme: "dark" },
];

function matrix(open) {
  const out = [];
  for (const view of Object.keys(VIEWS)) {
    for (const size of Object.keys(WIDTHS)) {
      for (const theme of THEMES) out.push({ name: view + "-" + size + "-" + theme + (open ? "-open" : ""), view, size, theme, open });
    }
  }
  return out;
}

const SHOTS = argv.includes("--matrix") ? matrix(argv.includes("--open")) : README;
const ONLY = (argValue(argv, "--only") || "").split(",").filter(Boolean);

/** Width and height from a PNG's IHDR chunk, to report what was written. */
function pngSize(buffer) {
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

mkdirSync(OUT, { recursive: true });
const browser = await launch(argv);
console.log("screenshots.mjs, " + BASE + " into " + path.relative(ROOT, OUT));
let failed = false;
try {
  const page = await browser.page();
  for (const shot of SHOTS.filter((s) => !ONLY.length || ONLY.some((prefix) => s.name.startsWith(prefix)))) {
    page.errors.length = 0;
    const view = VIEWS[shot.view];
    const separator = view.hash.includes("?") ? "&" : "?";
    const hash = shot.hash || (shot.open ? view.hash + separator + "open=" + view.open : view.hash);
    try {
      await openView(page, BASE, { theme: shot.theme, hash, width: WIDTHS[shot.size], height: HEIGHTS[shot.size] });
      const theme = await page.evaluate("document.documentElement.dataset.theme");
      if (theme !== shot.theme) throw new Error("the page is in " + theme + ", not " + shot.theme);
      const overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
      const { png, height } = await page.screenshotFullPage(WIDTHS[shot.size]);
      const file = path.join(OUT, shot.name + ".png");
      writeFileSync(file, png);
      const size = pngSize(png);
      const errors = page.errors.filter((m) => !/chrome-extension:\/\//.test(m) && /^(exception|console error|log error)/.test(m));
      console.log("  " + path.relative(ROOT, file) + "  " + size.width + " x " + size.height + " px" +
        (size.height !== height ? ", PAGE IS " + height + " px TALL" : "") +
        (overflow > 0 ? ", THE PAGE SCROLLS SIDEWAYS BY " + overflow + " px" : "") +
        ", console errors: " + (errors.length ? errors.length : "none"));
      for (const error of errors) console.log("      " + error);
      if (errors.length || size.height !== height || overflow > 0) failed = true;
    } catch (error) {
      failed = true;
      console.log("  FAIL  " + shot.name + ": " + error.message);
    }
  }
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
