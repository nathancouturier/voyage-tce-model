// Python to JavaScript parity: run src/engine.js on every case of
// data/fixtures/engine-cases.json and require every output to agree with the
// Python engine's to 1e-9, relative to the size of the figure (at least 1).
//
//   node tools/validate-engine.mjs [path/to/engine-cases.json]
//
// The cases are written by scripts/gen_fixtures.py from voyage.engine. If the
// two disagree, the JavaScript is fixed to match the Python, never the reverse.
// Exit status 1 on any disagreement.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configure, evaluate, freight_for_tce, hedge, optimal_speed, power_fit, sensitivities } from "../src/engine.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FILE = process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, "data", "fixtures", "engine-cases.json");
const TOLERANCE = 1e-9;
const SHOWN = 50;

function compare(expected, actual, where, problems) {
  if (expected === null) {
    if (actual !== null) problems.push(where + ": expected null, got " + JSON.stringify(actual));
    return;
  }
  if (typeof expected === "number") {
    if (typeof actual !== "number" || !Number.isFinite(actual)) {
      problems.push(where + ": expected " + expected + ", got " + JSON.stringify(actual));
      return;
    }
    const scale = Math.max(1, Math.abs(expected));
    if (Math.abs(expected - actual) > TOLERANCE * scale) problems.push(where + ": expected " + expected + ", got " + actual);
    return;
  }
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || actual.length !== expected.length) {
      problems.push(where + ": expected a list of " + expected.length + ", got " + JSON.stringify(actual));
      return;
    }
    expected.forEach((item, i) => compare(item, actual[i], where + "[" + i + "]", problems));
    return;
  }
  if (typeof expected === "object") {
    if (actual === null || typeof actual !== "object") {
      problems.push(where + ": expected an object, got " + JSON.stringify(actual));
      return;
    }
    const keys = new Set([...Object.keys(expected), ...Object.keys(actual)]);
    for (const key of keys) {
      if (!(key in expected)) problems.push(where + "." + key + ": not in the Python output");
      else if (!(key in actual)) problems.push(where + "." + key + ": missing from the JavaScript output");
      else compare(expected[key], actual[key], where + "." + key, problems);
    }
    return;
  }
  if (expected !== actual) problems.push(where + ": expected " + JSON.stringify(expected) + ", got " + JSON.stringify(actual));
}

const data = JSON.parse(readFileSync(FILE, "utf-8"));
if (data.schema_version !== 1) {
  console.log("FAIL  " + FILE + " has schema_version " + data.schema_version + ", expected 1");
  process.exit(1);
}
configure(data.constants);
const problems = [];
const BREAK_EVEN = 0;
for (const c of data.cases) {
  const inputs = structuredClone(c.inputs);
  const call = c.calls;
  const physical = evaluate(inputs);
  const actual = {
    evaluate: physical,
    breakeven_zero: freight_for_tce(inputs, BREAK_EVEN),
    breakeven_target: freight_for_tce(inputs, call.target_tce_usd_day),
    sensitivities: sensitivities(inputs),
    hedge: hedge(inputs, physical.tce_usd_day, call.tc_ffa_usd_day, call.route_ffa_usd_t),
    power_fit: power_fit(inputs.laden_curve),
  };
  if (call.speed_bounds_kn !== null) actual.optimal = optimal_speed(inputs, call.speed_bounds_kn[0], call.speed_bounds_kn[1]);
  compare(c.output, actual, c.name, problems);
}
if (problems.length) {
  for (const p of problems.slice(0, SHOWN)) console.log("FAIL  " + p);
  console.log("\n" + problems.length + " disagreement(s) over " + data.cases.length + " cases");
  process.exit(1);
}
console.log("ok    " + data.cases.length + " cases agree with the Python engine to " + TOLERANCE + " on every output");
