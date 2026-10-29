#!/usr/bin/env node
// Fail on the CSS the design does without, read from declarations with comments removed.
//
//     node tools/check-styles.mjs              self test, then scan styles/
//
// A literal grep also reads comments, so a stylesheet that explains why it has
// no shadow would fail it. This strips comments first, then checks the
// declarations, and adds the two rules a grep cannot see. Plain node, no
// dependencies. The checker of the sibling studies, with one exception this
// study's brief makes: its one orchestrated moment, the overview's bridge
// building once on first load, is a keyframe animation named bridge-grow, and
// that name is the only animation allowed (ONE_MOMENT below).
//
// BANNED
//   backdrop-filter          glass effects
//   box-shadow               heavy shadows, and the sticky column edge shadow
//   text-transform           all caps labels
//   any gradient             gradient washes, and the fade on a scroll container
//   mask-image               the same fade by another name
//   var(--grain-opacity)     the noise overlay
//   var(--text-dim)          fails contrast in both themes
//   var(--accent-deep)       fails contrast in dark
//   var(--bg-card), var(--bg-tint)   a tinted block is the rounded card's relative
//   font-variant-caps, smcp, c2sc    small capitals are all caps
//   font-variation-settings  overrides font-weight
//   a positive letter-spacing        the display -0.025em is the one value
//   overflow hidden or clip on html, body or :root
//   var(--shadow), var(--shadow-sm), var(--shadow-lg), text-shadow, drop-shadow()
//   a transform in a :hover rule     a hover lift
//   @keyframes and animation         motion answers an action, as a transition,
//                                    except the one moment named in ONE_MOMENT
//
// RULES A GREP CANNOT SEE
//   every rule that names Fraunces or var(--ff-display) in a font or
//   font-family declaration also sets font-weight: its default is Black
//   JetBrains Mono, var(--ff-mono), appears only in rules whose selectors are
//   all in MONO_SELECTORS: table figures and axis ticks

import { readdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// The only selectors allowed to set JetBrains Mono: figures
// in table cells and tick values on axes, nothing else.
const MONO_SELECTORS = new Set([".num", ".tick"]);

// The one orchestrated moment: the overview's bridge, each bar growing from
// its running total in turn on first load. The reduced motion block in
// styles/layout.css cuts it to nothing.
const ONE_MOMENT = "bridge-grow";

const BANNED = [
  { pattern: /backdrop-filter\s*:/i, why: "backdrop-filter, glassmorphism" },
  { pattern: /box-shadow\s*:/i, why: "box-shadow" },
  { pattern: /text-transform\s*:/i, why: "text-transform, all caps" },
  { pattern: /gradient\s*\(/i, why: "a gradient" },
  { pattern: /mask-image\s*:/i, why: "mask-image, a fade" },
  { pattern: /var\(\s*--grain-opacity\s*\)/i, why: "var(--grain-opacity), a noise overlay" },
  { pattern: /var\(\s*--text-dim\s*\)/i, why: "var(--text-dim), fails contrast" },
  { pattern: /var\(\s*--accent-deep\s*\)/i, why: "var(--accent-deep), fails contrast in dark" },
  { pattern: /var\(\s*--bg-card\s*\)/i, why: "var(--bg-card), a tinted block" },
  { pattern: /var\(\s*--bg-tint\s*\)/i, why: "var(--bg-tint), a tinted block" },
  { pattern: /font-variant-caps\s*:/i, why: "font-variant-caps, small capitals" },
  { pattern: /\b(?:smcp|c2sc)\b/i, why: "a small capitals feature" },
  { pattern: /font-variation-settings\s*:/i, why: "font-variation-settings overrides font-weight" },
  { pattern: /var\(\s*--shadow(?:-sm|-lg)?\s*\)/i, why: "a shadow token" },
  { pattern: /text-shadow\s*:/i, why: "text-shadow" },
  { pattern: /drop-shadow\s*\(/i, why: "a drop-shadow filter" },
  {
    pattern: new RegExp("@keyframes\\s+(?!" + ONE_MOMENT + "\\b)|(?:^|[;{\\s])animation(?:-name)?\\s*:(?![^;{}]*\\b" + ONE_MOMENT + "\\b)", "i"),
    why: "an animation; motion only answers an action, as a transition, except the bridge's one moment",
  },
];

/* The roots of the page, where a clip would hide a page that overflows. */
const ROOTS = new Set(["html", "body", ":root"]);

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

function lineOf(source, index) {
  let line = 1;
  for (let k = 0; k < index && k < source.length; k += 1) if (source[k] === "\n") line += 1;
  return line;
}

/** Rules as { selector, body, index }, flattening @media and skipping
 *  @font-face, whose font-weight is a range and whose family is a name. */
function rules(css) {
  const out = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match;
  while ((match = pattern.exec(css)) !== null) {
    const selector = match[1].replace(/^[\s\S]*\{/, "").trim();
    out.push({ selector, body: match[2], index: match.index });
  }
  return out;
}

export function checkCss(relative, source) {
  const findings = [];
  const css = stripComments(source);
  for (const banned of BANNED) {
    const global = new RegExp(banned.pattern.source, banned.pattern.flags.includes("g") ? banned.pattern.flags : banned.pattern.flags + "g");
    let match;
    while ((match = global.exec(css)) !== null) {
      findings.push({ file: relative, line: lineOf(css, match.index), why: banned.why });
    }
  }
  for (const rule of rules(css)) {
    const line = lineOf(css, rule.index);
    const selectors = rule.selector.split(",").map((s) => s.trim());
    if (/@font-face/.test(rule.selector)) continue;
    const spacing = /letter-spacing\s*:\s*([^;]+)/i.exec(rule.body);
    if (spacing && !/^\s*(?:-|0(?:\.0+)?(?:em|px|rem)?\s*$|normal\s*$)/.test(spacing[1])) {
      findings.push({ file: relative, line, why: "a positive letter-spacing, " + spacing[1].trim() });
    }
    const overflow = /overflow(?:-x)?\s*:\s*(?:hidden|clip)/i.test(rule.body);
    if (overflow && selectors.some((s) => ROOTS.has(s))) {
      findings.push({ file: relative, line, why: "overflow hidden or clipped on " + rule.selector + ", which would hide a page that overflows" });
    }
    if (selectors.some((s) => /:hover\b/.test(s)) && /(?:^|;)\s*transform\s*:/i.test(rule.body)) {
      findings.push({ file: relative, line, why: "a transform on hover in " + rule.selector + ", a hover lift" });
    }
    // Every font and font-family declaration in the rule, not only the first.
    const familyValue = [...rule.body.matchAll(/(?:^|;)\s*font(?:-family)?\s*:\s*([^;]+)/gi)].map((m) => m[1]).join(" ; ");
    if (/Fraunces|--ff-display/.test(familyValue) && !/font-weight\s*:/.test(rule.body)) {
      findings.push({ file: relative, line, why: "Fraunces without font-weight in " + rule.selector + ", its default is Black" });
    }
    if (/JetBrains Mono|--ff-mono/.test(familyValue) && !selectors.every((s) => MONO_SELECTORS.has(s))) {
      findings.push({ file: relative, line, why: "JetBrains Mono on " + rule.selector + ", only table figures and axis ticks may use it" });
    }
  }
  return findings;
}

function selfTest() {
  const cases = [
    { name: "a shadow", source: ".card { box-shadow: 0 8px 24px black; }", bad: 1 },
    { name: "an uppercase label", source: ".eyebrow { text-transform: uppercase; }", bad: 1 },
    { name: "a gradient wash", source: "body::before { background-image: linear-gradient(red, blue); }", bad: 1 },
    { name: "glass", source: ".nav { backdrop-filter: blur(12px); }", bad: 1 },
    { name: "the dim token", source: ".caption { color: var(--text-dim); }", bad: 1 },
    { name: "positive tracking", source: ".mono { letter-spacing: 0.02em; }", bad: 1 },
    { name: "body overflow", source: "body { position: relative; overflow-x: hidden; }", bad: 1 },
    { name: "Fraunces without a weight", source: "h1 { font-family: var(--ff-display); }", bad: 1 },
    { name: "mono on a label", source: ".label { font-family: var(--ff-mono); }", bad: 1 },
    { name: "small capitals", source: ".x { font-feature-settings: \"smcp\"; }", bad: 1 },
    { name: "a shadow token", source: ".x { outline: var(--shadow-lg); }", bad: 1 },
    { name: "a drop shadow", source: ".x { filter: drop-shadow(0 1px 2px black); }", bad: 1 },
    { name: "a text shadow", source: ".x { text-shadow: 0 1px black; }", bad: 1 },
    { name: "a root clip", source: ":root { overflow-x: hidden; }", bad: 1 },
    { name: "a body clip", source: "body { overflow-x: clip; }", bad: 1 },
    { name: "mono in a second declaration", source: ".label { font-family: var(--ff-body); font-family: var(--ff-mono); }", bad: 1 },
    { name: "a hover lift", source: ".btn:hover { transform: translateY(-2px); }", bad: 1 },
    { name: "an animation", source: "@keyframes pulse { from { opacity: 0; } } .x { animation: pulse 1s; }", bad: 2 },
    { name: "the one moment passes, another does not", source: "@keyframes bridge-grow { from { transform: scaleX(0); } } .bar { animation: bridge-grow 380ms both; } .y { animation: spin 1s; }", bad: 1 },
    {
      name: "allowed forms",
      source: [
        "/* no box-shadow, no text-transform: uppercase, no linear-gradient(), no var(--text-dim) */",
        "@font-face { font-family: \"Fraunces\"; src: url(\"../vendor/f.woff2\"); font-weight: 100 900; }",
        ".verdict { font-family: var(--ff-display); font-weight: 400; letter-spacing: -0.025em; }",
        ".num { font-family: var(--ff-mono); font-weight: 400; }",
        "@media (max-width: 480px) { .tick { font-family: var(--ff-mono); } }",
        ".section__inner { overflow: hidden; }",
        "--shadow-sm: 0 1px 2px rgba(0,0,0,0.4);",
      ].join("\n"),
      bad: 0,
    },
  ];
  const failures = [];
  for (const test of cases) {
    const found = checkCss("planted.css", test.source);
    const ok = found.length === test.bad;
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": expected " + test.bad + ", got " + JSON.stringify(found.map((f) => f.why))));
    if (!ok) failures.push(test.name);
  }
  return failures;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  console.log("check-styles.mjs");
  console.log("self test: planted banned CSS must be reported, allowed forms must pass");
  if (selfTest().length) {
    console.log("FAIL  the self test failed, so a scan result would mean nothing");
    process.exit(1);
  }
  const dir = path.join(ROOT, "styles");
  const files = existsSync(dir) ? readdirSync(dir).filter((name) => name.endsWith(".css")).sort() : [];
  const findings = [];
  for (const name of files) findings.push(...checkCss("styles/" + name, readFileSync(path.join(dir, name), "utf8")));
  console.log("");
  console.log("scanned " + files.length + " stylesheet(s): " + files.map((f) => "styles/" + f).join(", "));
  if (findings.length) {
    console.log("FAIL  CSS this site does not use");
    for (const f of findings) console.log("      " + f.file + ":" + f.line + "  " + f.why);
    process.exit(1);
  }
  console.log("PASS  no banned property, token, tracking or overflow; Fraunces always weighted; mono only on figures and ticks");
}
