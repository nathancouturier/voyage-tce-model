/* state.js
 *
 * Loads the JSON artifacts, holds them, and holds the little view state the
 * address carries. That is the whole job. It touches no DOM, reads no hash and
 * formats nothing: router.js owns the hash, format.js turns values into text,
 * dom.js builds elements, and each view module renders what it is handed here.
 * The sibling studies' loader, with this study's artifacts.
 *
 * A failure is kept, not thrown away: every failed load is recorded with the
 * path, what went wrong in words, and the time the fetch failed, because an
 * empty view names the missing file and the time of the failed fetch.
 *
 * THE SCHEMA GUARD. Every artifact carries schema_version and its own name
 * (src/voyage/export.py). This page was written against one schema version per
 * artifact, declared below, and refuses any other: an artifact whose version
 * or name it does not know is not drawn, and the page says which file and what
 * to do. That is the backstop for a mixed deploy, when a cache hands an old
 * copy of this module a new artifact or the other way round: a layout read
 * with the wrong expectations can print a wrong number without any error, and
 * a refusal cannot. tools/validate-artifacts.mjs fails on every committed
 * artifact this page would refuse.
 *
 * Numeric literals: SCHEMA_ONE is 1, which tools/check-literals.mjs allows
 * as a count; any other version would have to be declared there.
 */

const SCHEMA_ONE = 1;

/* Every artifact the site reads, by name, with what it holds in words for the
 * failure sentence. Paths are relative to index.html: a leading slash would
 * break the subpath deploy. */
const ARTIFACTS = Object.freeze({
  overview: { path: "data/overview.json", artifact: "overview", schema: SCHEMA_ONE, holds: "the featured voyage, its bridge from freight to TCE, its three facts and every input with its source" },
  calculator: { path: "data/calculator.json", artifact: "calculator", schema: SCHEMA_ONE, holds: "the calculator's presets, every input with its source, the ships and the routings" },
  engine: { path: "data/engine.json", artifact: "engine", schema: SCHEMA_ONE, holds: "the engine's constants: emission factors, warming potentials, FuelEU values and the sensitivity shocks" },
  map: { path: "data/map.json", artifact: "map", schema: SCHEMA_ONE, holds: "the land and every voyage's legs, projected for the maps" },
  routes: { path: "data/routes.json", artifact: "routes", schema: SCHEMA_ONE, holds: "the route library, the voyage costs of every route at one dated market, and the distance checks" },
  detours: { path: "data/detours.json", artifact: "detours", schema: SCHEMA_ONE, holds: "Suez against the Cape for a tanker and a bulk carrier, and the Hormuz scenarios" },
  carbon: { path: "data/carbon.json", artifact: "carbon", schema: SCHEMA_ONE, holds: "the EU ETS cost of three voyages under the phase in, and the time charter split" },
  paper: { path: "data/paper.json", artifact: "paper", schema: SCHEMA_ONE, holds: "physical TCEs against the FFA, the hedges and the basis" },
  speed: { path: "data/speed.json", artifact: "speed", schema: SCHEMA_ONE, holds: "the TCE against speed at low, middle and high freight and bunker prices" },
  method: { path: "data/method.json", artifact: "method", schema: SCHEMA_ONE, holds: "the conventions, the formulas, the validation against published figures and the limitations" },
  manifest: { path: "data/manifest.json", artifact: "manifest", schema: SCHEMA_ONE, holds: "every source with its as of date, its retrieval and its licence" },
});

/** The artifact names this build of the page reads, for a validator. */
export function artifactNames() {
  return Object.keys(ARTIFACTS);
}

/** The registry entry of one artifact, for a validator. */
export function artifactEntry(name) {
  return ARTIFACTS[name];
}

const loaded = new Map();
const failures = new Map();
const pending = new Map();

function failureRecord(name, what, detail) {
  return {
    artifact: name,
    path: ARTIFACTS[name].path,
    holds: ARTIFACTS[name].holds,
    what,
    detail: detail || "",
    at: new Date().toISOString(),
  };
}

/* The URL to fetch: the path with its content hash, from the import map in
 * index.html, which import.meta.resolve applies (src/voyage/versions.py). The
 * path is relative to index.html and this module sits one directory below it.
 * An engine without import.meta.resolve, or without import maps, gets the plain
 * path, which still loads and is still checked by the schema guard. */
export function artifactUrl(path) {
  try {
    if (typeof import.meta.resolve === "function") return import.meta.resolve("../" + path);
  } catch (error) {
    /* fall through to the plain path */
  }
  return path;
}

/* Why this page will not read a parsed artifact, or null when it will. */
export function refusal(name, data) {
  const expected = ARTIFACTS[name];
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return "the file holds no artifact header, so this page cannot tell what it is";
  }
  if (data.artifact !== expected.artifact) {
    return "the file names itself as a different artifact, so it is not the file this page asked for";
  }
  if (data.schema_version !== expected.schema) {
    return "the file declares a schema version this page does not read, so it was written for a different version of the site than the code now running";
  }
  return null;
}

const REFUSAL_REMEDY =
  "Reload the page: the site was probably updated while this copy was open, and a reload fetches the code and the data together. " +
  "Nothing from this file is shown, rather than read with the wrong layout.";

async function fetchArtifact(name) {
  const { path } = ARTIFACTS[name];
  let response;
  try {
    response = await fetch(artifactUrl(path), { cache: "no-cache" });
  } catch (error) {
    throw failureRecord(name, "the request did not complete, so the network or the server is unreachable", String(error && error.message ? error.message : error));
  }
  if (!response.ok) {
    const statusText = response.statusText ? " " + response.statusText : "";
    throw failureRecord(name, "the server answered " + String(response.status) + statusText);
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw failureRecord(name, "the file arrived but is not valid JSON", String(error && error.message ? error.message : error));
  }
  const refused = refusal(name, data);
  if (refused) throw { ...failureRecord(name, refused), remedy: REFUSAL_REMEDY };
  return data;
}

/** Load one artifact, or hand back the copy already held. A second caller
 *  while the first request is still out shares that request. */
export function load(name) {
  if (!Object.prototype.hasOwnProperty.call(ARTIFACTS, name)) {
    return Promise.reject(new Error("state.js knows no artifact called " + name));
  }
  if (loaded.has(name)) return Promise.resolve(loaded.get(name));
  if (pending.has(name)) return pending.get(name);
  const request = fetchArtifact(name)
    .then((data) => {
      loaded.set(name, data);
      failures.delete(name);
      return data;
    })
    .catch((failure) => {
      failures.set(name, failure);
      throw failure;
    })
    .finally(() => pending.delete(name));
  pending.set(name, request);
  return request;
}

/** Load several. Resolves to { ok, data, failures }, reporting every failure
 *  rather than the first, so the page can name each missing file. */
export async function loadAll(names) {
  const results = await Promise.allSettled(names.map((name) => load(name)));
  const data = {};
  const broken = [];
  results.forEach((result, index) => {
    const name = names[index];
    if (result.status === "fulfilled") data[name] = result.value;
    else if (result.reason && result.reason.artifact) broken.push(result.reason);
    else broken.push(failureRecord(name, "the load failed", String(result.reason)));
  });
  return { ok: broken.length === 0, data, failures: broken };
}

/** The artifact, or undefined if it never arrived. */
export function artifact(name) {
  return loaded.get(name);
}

/** Forget a failure so the next load tries again. */
export function forget(name) {
  failures.delete(name);
  loaded.delete(name);
}

/* ------------------------------------------------------ view state --- */

/* Which sections of a view are open. It lives in the address,
 * #/routes?open=method,data, so this is a parser of that parameter and a
 * writer back to it, holding no copy that could drift from the hash. */

/** The open section ids from a route's params, in the order of `known`. */
export function openSections(params, known) {
  const asked = new Set(String((params && params.open) || "").split(",").filter((id) => id !== ""));
  return known.filter((id) => asked.has(id));
}

/** The params for a set of open sections, ready for router.href, kept beside
 *  the view's other params. */
export function openParams(openIds, others) {
  const out = { ...(others || {}) };
  delete out.open;
  if (openIds.length) out.open = openIds.join(",");
  return out;
}
