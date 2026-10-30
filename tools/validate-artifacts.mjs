#!/usr/bin/env node
// Check every JSON artifact the page reads against what the page expects.
//
//     node tools/validate-artifacts.mjs              self test, then the files
//
// The page refuses an artifact whose name or schema version it does not know
// (src/state.js), formats every figure with the decimals the artifact
// declares, throwing on a format it does not declare (src/format.js), and its
// view modules read named fields. A file that would be refused, a format that
// would throw, or a field a module reads and does not find is found here
// rather than by a reader. Plain node, no dependencies: it imports the page's
// own state.js and format.js, so the rules checked are the ones the page
// applies. The sibling studies' validator, rewritten for this study's
// artifacts.
//
// FOR EACH ARTIFACT IN src/state.js's REGISTRY
//   1  the file exists, parses, and state.js's refusal() accepts it
//   2  conventions.decimals maps every format to a whole number of places, and
//      conventions.scale holds the percent and million factors
//   3  every field the page's modules read is there (REQUIRED below), and on
//      every element of a list they read field by field (REQUIRED_EACH)
//   4  every "format" anywhere in the file is declared in conventions.decimals
//   5  every sentence (a list holding at least one segment object) is made of
//      the three shapes format.js reads, and every figure in it formats:
//        "words"                                  plain words
//        { text, field }                          a word or a date from a field
//        { value, format, field, prefix?, suffix?, signed?, accent?, missing? }
//   6  no NaN or infinity reached the file
//
// AND FOR data/
//   7  every data/*.json is in the registry, so no file is published unread
//   8  every download a view links exists, and every file in data/downloads is
//      linked from a view
//
// SELF TEST. Before checking the files, the tool plants an undeclared format,
// a missing field, a broken segment and a wrong schema version in copies of
// the real artifacts and asserts each is reported.

import { readdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { artifactNames, artifactEntry, refusal } from "../src/state.js";
import { segmentText, decimalsFor } from "../src/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// The fields the page's modules read, by artifact, as dotted paths.
const REQUIRED = Object.freeze({
  atlas: [
    "page.title", "page.takeaway", "page.filters", "page.filter_label", "page.groups",
    "page.list.caption", "page.list.heading", "page.list.unknown", "page.list.head.route", "page.list.head.tce",
    "page.list.head.days", "page.list.study_head.route", "page.list.study_head.tce", "page.list.study_head.days",
    "page.panel.back", "page.panel.same", "page.panel.same_after", "page.panel.split",
    "page.panel.alternatives", "page.panel.more", "page.panel.links", "page.panel.show", "page.summary.heading",
    "page.summary.items", "page.map.title", "page.map.title_narrow", "page.map.name", "page.map.desc",
    "page.map.legend", "page.map.labels", "page.map.idle", "page.map.idle_narrow", "page.map.same", "page.map.edge",
    "page.map.source", "page.sections", "page.method", "page.table.caption", "page.table.columns",
    "clusters", "items",
  ],
  overview: [
    "verdict", "dates", "facts", "bridge.rows", "bridge.title", "bridge.source", "bridge.caption", "bridge.result_line",
    "leaves_out", "map.key", "map.title", "map.legend", "map.source", "sections", "method.paragraphs", "method.formulas",
    "method.comparison_title", "method.comparison_note", "assumptions.leaves_out", "assumptions.vessel", "assumptions.port",
    "data_caption", "inputs_table", "comparison",
  ],
  calculator: [
    "title", "lead", "default_preset", "steps", "fields", "freight_bases", "ets_years", "vlsfo_classes", "shocks",
    "speed_chart.margin_kn", "speed_chart.step_kn", "target_tce.value", "presets", "vessels", "routes",
    "cost_labels", "war_risk_rates", "route_order", "input_labels", "status_words", "payer_words", "war_area_names",
    "words", "sections", "assumptions.statuses",
  ],
  engine: [
    "constants.HOURS_PER_DAY", "constants.PERCENT", "constants.SHOCKS", "constants.SPEED_STEP_KN",
    "constants.WAR_RISK_PERIOD_DAYS", "constants.WAR_RISK_AREAS",
  ],
  map: ["land", "voyages", "atlas.view_box", "atlas.legs", "atlas.ports", "atlas.passages"],
  routes: [
    "page.title", "page.takeaway", "page.baltic_map", "page.chart.title", "page.chart.axis", "page.chart.desc",
    "page.chart.source", "page.chart.legend", "page.table_caption", "page.hormuz.title", "page.hormuz.lead",
    "page.hormuz.caption", "page.segments", "page.sections", "page.method", "page.assumptions", "page.pub151.caption",
    "page.priced_mark", "page.turn_time_mark", "page.chart.note",
    "page.pub151.published_head", "page.pub151.within_head", "page.downloads", "rows", "pub151.checks", "baltic_map_url",
  ],
  detours: [
    "page.title", "page.takeaway", "page.chart.title", "page.chart.rows", "page.chart.legend", "page.chart.source",
    "page.suez_tanker.lead", "page.suez_dry.lead", "page.hormuz.lead", "page.hormuz.chain", "page.sections", "page.method",
    "page.assumptions", "page.events_heading", "suez_tanker.options", "suez_dry.options", "suez_dry.basis",
    "hormuz.scenarios", "hormuz.levels", "events",
  ],
  carbon: [
    "page.title", "page.takeaway", "page.chart.title", "page.chart.axis", "page.chart.source", "page.chart.none",
    "page.kinds", "page.time_charter.title", "page.time_charter.lead", "page.sections", "page.method", "page.fueleu",
    "page.assumptions",
    "rows", "time_charter.rule", "conventions_rows", "convention_links", "market",
  ],
  paper: [
    "page.title", "page.takeaway", "page.chart.title", "page.chart.legend", "page.chart.source", "page.fixture.lead",
    "page.td3c.lead", "page.sections", "page.method", "page.assumptions", "page.hedge_columns", "page.months_words",
    "page.fixture.table_caption", "page.route_ffa.result", "page.route_ffa.empty",
    "capesize", "c5_fixture", "settlement", "curves",
  ],
  speed: ["lead", "note", "bound_marks.top", "bound_marks.bottom", "routes", "textbook"],
  method: [
    "page.title", "page.takeaway", "page.chart.title", "page.chart.legend", "page.chart.source", "page.sections",
    "page.formulas", "page.limitations", "page.limitations_heading", "page.blocked", "page.blocked_heading",
    "page.downloads", "page.early_march_caption", "page.dry_caption", "page.baltic_2017_caption", "page.baltic_2017_labels",
    "page.baltic_2017_head", "convention_items", "validation.tanker", "validation.dry", "validation.early_march",
    "validation.baltic_2017.published", "validation.baltic_2017.computed",
  ],
  manifest: [
    "series", "caption", "footer.sources", "footer.updated_words", "footer.updated", "footer.latest_words",
    "footer.latest_input", "footer.method_words",
  ],
});

// The fields the page reads from every element of a list, by artifact and the
// list's dotted path: src/atlas.js draws each route's row and detail from these.
const REQUIRED_EACH = Object.freeze({
  atlas: {
    items: [
      "id", "label", "kind", "segment", "basis", "ship", "ports", "heading", "subhead", "readout", "map_title",
      "map_desc", "tce_usd_day", "figure", "view", "view_tall", "passages",
      "legs.laden", "same_water", "facts", "alternatives", "links", "source",
      "row.tce", "row.qualifier", "row.days", "row.note", "row.alts", "row.last",
    ],
  },
});

const SEGMENT_KEYS = new Set(["value", "format", "field", "prefix", "suffix", "signed", "accent", "missing"]);

function get(object, dotted) {
  return dotted.split(".").reduce((node, key) => (node === null || node === undefined ? undefined : node[key]), object);
}

/* A figure segment holds value, format and field and nothing outside
 * SEGMENT_KEYS; a word segment holds exactly text and field. A table row that
 * happens to carry a value and a format is neither. */
function isSegmentObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  const has = (key) => Object.prototype.hasOwnProperty.call(value, key);
  if (has("value") && has("format") && has("field")) return keys.every((key) => SEGMENT_KEYS.has(key));
  return has("text") && has("field") && keys.length === 2;
}

/** Every problem with one parsed artifact, as sentences. */
export function check(name, data) {
  const problems = [];
  const refused = refusal(name, data);
  if (refused) return [name + ": " + refused];
  const decimals = data.conventions && data.conventions.decimals;
  if (!decimals || typeof decimals !== "object") return [name + ": no conventions.decimals"];
  for (const [format, places] of Object.entries(decimals)) {
    if (!Number.isInteger(places) || places < 0) problems.push(name + ": the format " + format + " declares " + JSON.stringify(places) + " places");
  }
  const scale = data.conventions.scale;
  if (!scale || scale.percent !== 100 || scale.million !== 1e6) problems.push(name + ": conventions.scale must hold percent 100 and million 1000000");
  for (const field of REQUIRED[name] || []) {
    if (get(data, field) === undefined) problems.push(name + ": the page reads " + field + ", which is missing");
  }
  for (const [list, fields] of Object.entries(REQUIRED_EACH[name] || {})) {
    const elements = get(data, list);
    if (!Array.isArray(elements)) continue;
    elements.forEach((element, at) => {
      for (const field of fields) {
        if (get(element, field) === undefined) problems.push(name + ": the page reads " + list + "[" + at + "]." + field + ", which is missing");
      }
    });
  }
  const walk = (node, where) => {
    if (typeof node === "number" && !Number.isFinite(node)) problems.push(name + ": a non finite number at " + where);
    if (Array.isArray(node)) {
      const sentence = node.some(isSegmentObject) && node.every((item) => typeof item === "string" || isSegmentObject(item));
      if (sentence) {
        node.forEach((segment, at) => {
          if (typeof segment === "object" && Object.prototype.hasOwnProperty.call(segment, "value")) {
            for (const key of Object.keys(segment)) {
              if (!SEGMENT_KEYS.has(key)) problems.push(name + ": the segment " + where + "[" + at + "] has the unknown key " + key);
            }
            if (typeof segment.field !== "string" || segment.field === "") problems.push(name + ": the segment " + where + "[" + at + "] names no field");
          }
          try {
            const piece = segmentText(segment, decimals);
            if (piece.kind === "number" && piece.missing && !segment.missing) {
              problems.push(name + ": the figure " + where + "[" + at + "] (" + segment.field + ") is missing and says nothing in its place");
            }
          } catch (error) {
            problems.push(name + ": " + where + "[" + at + "]: " + error.message);
          }
        });
      }
      node.forEach((item, at) => walk(item, where + "[" + at + "]"));
      return;
    }
    if (node !== null && typeof node === "object") {
      for (const [key, value] of Object.entries(node)) {
        // A link cut at an opening parenthesis points nowhere: every bracket a link opens, it closes.
        if ((key === "url" || key === "href") && typeof value === "string" && value.split("(").length !== value.split(")").length) {
          problems.push(name + ": the link at " + where + "." + key + " has unbalanced parentheses: " + value);
        }
        if (key === "format" && typeof value === "string") {
          try {
            decimalsFor(value, decimals);
          } catch (error) {
            problems.push(name + ": " + where + ".format: " + error.message);
          }
        }
        walk(value, where ? where + "." + key : key);
      }
    }
  };
  walk(data, "");
  return problems;
}

function selfTest(real) {
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const cases = [
    {
      name: "an undeclared format",
      plant: (d) => { const c = clone(d.overview); c.verdict.push({ value: 1, format: "furlongs", field: "x" }); return ["overview", c]; },
    },
    {
      name: "a missing field",
      plant: (d) => { const c = clone(d.routes); delete c.page.chart; return ["routes", c]; },
    },
    {
      name: "a field missing from one element of a list",
      plant: (d) => { const c = clone(d.atlas); delete c.items[c.items.length - 1].row.alts; return ["atlas", c]; },
    },
    {
      name: "a figure with no field",
      plant: (d) => { const c = clone(d.carbon); c.page.takeaway.push({ value: 2, format: "count", field: "" }); return ["carbon", c]; },
    },
    {
      name: "a wrong schema version",
      plant: (d) => { const c = clone(d.paper); c.schema_version = 2; return ["paper", c]; },
    },
    {
      name: "a missing figure with no words",
      plant: (d) => { const c = clone(d.method); c.page.takeaway.push({ value: null, format: "count", field: "x" }); return ["method", c]; },
    },
  ];
  const failures = [];
  for (const test of cases) {
    const [name, planted] = test.plant(real);
    const found = check(name, planted);
    const ok = found.length > 0;
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": nothing was reported"));
    if (!ok) failures.push(test.name);
  }
  const clean = Object.keys(real).every((name) => check(name, real[name]).length === 0);
  return { failures, clean };
}

/** Every href in the artifacts that points into data/downloads or at the note. */
function linkedDownloads(all) {
  const out = new Set();
  const walk = (node) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      for (const [key, value] of Object.entries(node)) {
        if (key === "file" && typeof value === "string") out.add(value);
        walk(value);
      }
    }
  };
  walk(all);
  return out;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  console.log("validate-artifacts.mjs");
  const problems = [];
  const data = {};
  for (const name of artifactNames()) {
    const file = path.join(ROOT, artifactEntry(name).path);
    if (!existsSync(file)) {
      problems.push(artifactEntry(name).path + " is missing");
      continue;
    }
    try {
      data[name] = JSON.parse(readFileSync(file, "utf8"));
    } catch (error) {
      problems.push(artifactEntry(name).path + " is not valid JSON: " + error.message);
    }
  }
  console.log("self test: planted faults must be reported");
  const { failures } = selfTest(data);
  if (failures.length) {
    console.log("FAIL  the self test failed, so a clean result would mean nothing");
    process.exit(1);
  }
  for (const [name, artifact] of Object.entries(data)) problems.push(...check(name, artifact));

  const registered = new Set(artifactNames().map((name) => path.basename(artifactEntry(name).path)));
  for (const file of readdirSync(path.join(ROOT, "data")).filter((f) => f.endsWith(".json"))) {
    if (!registered.has(file)) problems.push("data/" + file + " is published and the page never reads it");
  }
  const linked = linkedDownloads(data);
  for (const file of linked) {
    if (!existsSync(path.join(ROOT, file))) problems.push(file + " is linked from a view and does not exist");
  }
  const downloads = path.join(ROOT, "data", "downloads");
  for (const file of existsSync(downloads) ? readdirSync(downloads) : []) {
    if (!linked.has("data/downloads/" + file)) problems.push("data/downloads/" + file + " is published and no view links it");
  }

  console.log("");
  console.log("checked " + Object.keys(data).length + " artifact(s) and " + linked.size + " linked download(s)");
  if (problems.length) {
    console.log("FAIL  an artifact the page would refuse, misread or fail to format");
    for (const problem of problems) console.log("      " + problem);
    process.exit(1);
  }
  console.log("PASS  every artifact is accepted, every field the page reads is there, and every figure formats");
}
