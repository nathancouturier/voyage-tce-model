#!/usr/bin/env node
// Check the data the artifacts are built from: the raw manifest, the seeds,
// the caches and the engine's test cases.
//
//     node tools/validate-data.mjs              self test, then the files
//
// Every number on the site is traced to a document: a seed figure carries the
// raw_key of the document it was copied from (data/seed/*.json), and the raw
// manifest (data/raw/manifest.json) gives that document's URL, retrieval time
// and sha256. This checks that the chain holds without running Python: every
// raw_key a seed cites is in the manifest; every manifest entry has a URL, an
// ISO retrieval instant and a sha256; a file the manifest marks committed is
// on disk with that very hash, and a licensed one is not in the repository;
// the caches parse, run forward in time and hold positive finite prices; the
// engine's test cases are there in number. Plain node, no dependencies.
//
// SELF TEST. A planted unknown raw_key, a hash that does not match and a cache
// running backwards must each be reported.

import { readFileSync, existsSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ISO_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SHA256 = /^[0-9a-f]{64}$/;
/* tools/validate-engine.mjs needs at least this many cases: 200 generated
 * cases plus every anchor. */
const MIN_CASES = 200;

function readJson(relative) {
  const full = path.join(ROOT, relative);
  const bytes = readFileSync(full);
  const text = relative.endsWith(".gz") ? gunzipSync(bytes).toString("utf8") : bytes.toString("utf8");
  return JSON.parse(text);
}

/** Every raw_key cited anywhere in a seed, with where. */
function citedKeys(node, where, out) {
  if (Array.isArray(node)) node.forEach((item, at) => citedKeys(item, where + "[" + at + "]", out));
  else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      if (key === "raw_key" && typeof value === "string") out.push({ key: value, where });
      citedKeys(value, where + "." + key, out);
    }
  }
  return out;
}

export function checkManifest(manifest, committedFiles, readBytes) {
  const problems = [];
  for (const [key, entry] of Object.entries(manifest.files || {})) {
    if (!/^https?:\/\//.test(entry.url || "")) problems.push("raw " + key + ": no URL");
    if (!ISO_INSTANT.test(entry.retrieved_at || "")) problems.push("raw " + key + ": retrieved_at is not an ISO instant");
    if (!SHA256.test(entry.sha256 || "")) problems.push("raw " + key + ": no sha256");
    if (entry.committed) {
      const bytes = readBytes(entry.path);
      if (bytes === null) problems.push("raw " + key + ": marked committed and not on disk at " + entry.path);
      else {
        // The hash is of the bytes as served; a file stored gzipped is hashed
        // after it is unpacked.
        let served = bytes;
        try {
          if (entry.stored === "gzip") served = gunzipSync(bytes);
        } catch {
          served = bytes;
        }
        if (createHash("sha256").update(served).digest("hex") !== entry.sha256) problems.push("raw " + key + ": the bytes at " + entry.path + " do not match the recorded sha256");
      }
    } else if (committedFiles.has(entry.path)) {
      problems.push("raw " + key + ": marked not committable but " + entry.path + " is in the repository");
    }
  }
  return problems;
}

export function checkCitations(seeds, manifest) {
  const problems = [];
  for (const [name, seed] of Object.entries(seeds)) {
    for (const { key, where } of citedKeys(seed, name, [])) {
      if (!(key in (manifest.files || {}))) problems.push(name + " cites " + key + " at " + where + ", which the raw manifest does not hold");
    }
  }
  return problems;
}

/** A CSV with a header row: its rows as objects. */
function csv(text) {
  const [head, ...lines] = text.trim().split("\n");
  const columns = head.split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(columns.map((column, at) => [column, cells[at]]));
  });
}

export function checkSeries(name, rows, dateKey, valueKey, allowEmpty) {
  const problems = [];
  let last = "";
  for (const row of rows) {
    const date = row[dateKey];
    if (!(date > last)) problems.push(name + ": " + date + " does not come after " + last);
    last = date;
    const raw = row[valueKey];
    if ((raw === "" || raw === undefined) && allowEmpty) continue;
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) problems.push(name + ": " + date + " holds " + JSON.stringify(raw) + ", not a positive price");
  }
  return problems;
}

function selfTest(manifest) {
  const failures = [];
  const report = (name, found) => {
    const ok = found.length > 0;
    console.log((ok ? "  ok    " : "  FAIL  ") + name + (ok ? "" : ": nothing was reported"));
    if (!ok) failures.push(name);
  };
  report("an unknown raw_key", checkCitations({ planted: { a: { raw_key: "no_such_document" } } }, manifest));
  const committed = Object.entries(manifest.files).find(([, e]) => e.committed);
  if (committed) {
    const [key, entry] = committed;
    report("a hash that does not match", checkManifest({ files: { [key]: entry } }, new Set(), () => Buffer.from("not the file")));
  }
  report("a cache running backwards", checkSeries("planted", [{ m: "2026-02", v: "1" }, { m: "2026-01", v: "1" }], "m", "v", false));
  report("a price that is not positive", checkSeries("planted", [{ m: "2026-01", v: "-3" }], "m", "v", false));
  return failures;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  console.log("validate-data.mjs");
  const manifest = readJson("data/raw/manifest.json");
  console.log("self test: planted faults must be reported");
  if (selfTest(manifest).length) {
    console.log("FAIL  the self test failed, so a clean result would mean nothing");
    process.exit(1);
  }
  let committedFiles = new Set();
  try {
    committedFiles = new Set(execFileSync("git", ["ls-files", "data/raw"], { cwd: ROOT, encoding: "utf8" }).split("\n").filter(Boolean));
  } catch {
    // Not a git checkout: the committed check reads the disk only.
  }
  const readBytes = (relative) => (existsSync(path.join(ROOT, relative)) ? readFileSync(path.join(ROOT, relative)) : null);
  const problems = [...checkManifest(manifest, committedFiles, readBytes)];

  const seeds = {};
  for (const file of readdirSync(path.join(ROOT, "data", "seed")).sort()) {
    if (file.endsWith(".json")) seeds[file] = readJson("data/seed/" + file);
  }
  problems.push(...checkCitations(seeds, manifest));

  problems.push(...checkSeries("data/cache/eua_monthly.csv", csv(readFileSync(path.join(ROOT, "data/cache/eua_monthly.csv"), "utf8")), "month", "eua_eur_t", false));
  problems.push(...checkSeries("data/cache/usd_per_eur_daily.csv", csv(readFileSync(path.join(ROOT, "data/cache/usd_per_eur_daily.csv"), "utf8")), "date", "usd_per_eur", true));

  const cases = readJson("data/fixtures/engine-cases.json");
  const count = Array.isArray(cases.cases) ? cases.cases.length : 0;
  if (count < MIN_CASES) problems.push("data/fixtures/engine-cases.json holds " + count + " cases, fewer than " + MIN_CASES);

  const geo = readJson("data/seed/sea_routes.geojson.gz");
  if (!geo.features || !geo.features.length) problems.push("data/seed/sea_routes.geojson.gz holds no route line");

  console.log("");
  console.log("checked " + Object.keys(manifest.files).length + " raw document(s), " + Object.keys(seeds).length + " seed(s), 2 cache(s) and " + count + " engine case(s)");
  if (problems.length) {
    console.log("FAIL  data the artifacts cannot be traced to or trusted from");
    for (const problem of problems) console.log("      " + problem);
    process.exit(1);
  }
  console.log("PASS  every cited document is in the manifest, every committed file matches its hash, and the caches hold forward running positive prices");
}
