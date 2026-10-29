/* format.js
 *
 * Turns a value from an artifact into the text a reader sees, and writes the
 * sentences for the three states a figure can be in when it is not there:
 * loading, failed to load, and present but empty. No DOM, so it runs under
 * plain node; tools/validate-artifacts.mjs does exactly that. The sibling
 * studies' formatter with this study's units.
 *
 * WHERE THE DECIMALS COME FROM. Not from here. Each artifact carries
 * conventions.decimals, a map from a format name such as usd_day to a count
 * of places, and every numeric segment names its format. A format the artifact
 * does not declare throws, naming it, rather than falling back to a guess.
 *
 * SIGNS. A negative figure in prose carries U+2212, the minus sign, a true
 * minus rather than a hyphen. A negative figure in a table cell carries the
 * ASCII hyphen minus, so a copied cell pastes into a spreadsheet as a number.
 * A positive figure carries a plus only when the artifact marks the value
 * signed. A value that rounds to zero prints with no sign at all, so the page
 * never says "-0.00".
 *
 * MISSING. null, undefined, NaN and the infinities are missing, never zero.
 * The number formatters return null for them, and the caller decides what the
 * gap says: the artifact's own words for it, never the field's identifier.
 *
 * Numeric literals: the code point of the minus sign, declared in
 * tools/check-literals.mjs. The unit words hold no digits.
 */

const MINUS_SIGN = 0x2212;

/** U+2212, the typographic minus, for prose. */
export const MINUS_PROSE = String.fromCharCode(MINUS_SIGN);
/** U+002D, the hyphen minus, for table cells. */
export const MINUS_TABLE = "-";

/** The unit each format is read in, for a column head or a field. An empty
 *  string is a dimensionless figure: a count, a year, a ratio. */
export const UNITS = Object.freeze({
  usd_day: "USD a day",
  usd: "USD",
  usd_m: "USD million",
  usd_m_0: "USD million",
  usd_t: "USD a tonne",
  usd_bbl: "USD a barrel",
  ws: "Worldscale points",
  days: "days",
  days_2: "days",
  nm: "nautical miles",
  knots: "knots",
  knots_2: "knots",
  t: "tonnes",
  tpd: "tonnes a day",
  percent: "percent",
  percent_0: "percent",
  percent_2: "percent",
  eur_t: "EUR a tonne",
  usd_per_eur: "USD per EUR",
  tco2: "tonnes of CO2",
  share: "",
  exponent: "",
  count: "",
  year: "",
  error_percent: "percent",
  g_mj: "g CO2e per MJ",
  tonne_miles_bn: "billion tonne miles",
  days_4: "days",
  t_2: "tonnes",
  mj: "MJ",
  eur: "EUR",
});

/* A year is written 2026, never 2,026. Every other format groups thousands. */
const UNGROUPED = new Set(["year"]);

/** True for anything the page must show as a gap rather than a number. */
export function isMissing(value) {
  return value === null || value === undefined || typeof value !== "number" || !Number.isFinite(value);
}

/** The number of places the artifact declares for a format, or a thrown
 *  Error naming the format and the formats it does declare. */
export function decimalsFor(format, decimals) {
  if (!decimals || typeof decimals !== "object") {
    throw new Error("format.js was given no decimals table; pass the artifact's conventions.decimals");
  }
  const places = decimals[format];
  if (!Number.isInteger(places) || places < 0) {
    throw new Error(
      "the artifact declares no decimals for the format " + JSON.stringify(format) +
      "; it declares " + Object.keys(decimals).sort().join(", ")
    );
  }
  return places;
}

/** Format one number.
 *
 *    value     the number from the artifact
 *    format    its format name, for example "usd_day"
 *    decimals  the artifact's conventions.decimals
 *    options   { signed: boolean, context: "prose" | "table" }
 *
 *  Returns a string, or null when the value is missing. */
export function formatNumber(value, format, decimals, options) {
  const opts = options || {};
  const places = decimalsFor(format, decimals);
  if (isMissing(value)) return null;
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
    useGrouping: !UNGROUPED.has(format),
  }).format(Math.abs(value));
  const roundsToZero = !/[1-9]/.test(body);
  if (roundsToZero) return body;
  if (value < 0) return (opts.context === "table" ? MINUS_TABLE : MINUS_PROSE) + body;
  if (opts.signed) return "+" + body;
  return body;
}

/** A number and its unit, "466,378 USD a day", or null when missing. */
export function formatQuantity(value, format, decimals, options) {
  const text = formatNumber(value, format, decimals, options);
  if (text === null) return null;
  const unit = Object.prototype.hasOwnProperty.call(UNITS, format) ? UNITS[format] : "";
  return unit ? text + " " + unit : text;
}

/** The text of one sentence segment, as the export writes them:
 *    "words"                                        words, no digit
 *    { text, field }                                words or a date that came
 *                                                   from a field
 *    { value, format, field, prefix?, suffix?, signed? }   a number
 *  Returns { text, kind, field, missing } where kind is "text", "word" or
 *  "number". A number's prefix and suffix ("USD ", " million") are part of
 *  its text, so a figure and its unit never break apart. */
export function segmentText(segment, decimals) {
  if (typeof segment === "string") return { text: segment, kind: "text", field: null, missing: false };
  if (Object.prototype.hasOwnProperty.call(segment, "text")) {
    return { text: segment.text, kind: segment.field ? "word" : "text", field: segment.field || null, missing: false };
  }
  const body = formatNumber(segment.value, segment.format, decimals, {
    signed: segment.signed === true,
    context: "prose",
  });
  if (body === null) return { text: null, kind: "number", field: segment.field, missing: true };
  return { text: (segment.prefix || "") + body + (segment.suffix || ""), kind: "number", field: segment.field, missing: false };
}

/** A whole sentence of segments as plain text, for an SVG title or desc. A
 *  missing number reads as the segment's own `missing` words, or "no figure". */
export function segmentsText(segments, decimals) {
  return (segments || [])
    .map((segment) => {
      const piece = segmentText(segment, decimals);
      return piece.missing ? missingFigureText(segment.missing) : piece.text;
    })
    .join("");
}

/** A figure for a table cell: hyphen minus, sign when asked, or null. */
export function formatCell(value, format, decimals, signed) {
  return formatNumber(value, format, decimals, { signed: signed === true, context: "table" });
}

/* ------------------------------------------------------------- time --- */

/* "2-digit" is Intl's own option vocabulary, a string the API defines, not a
 * figure; tools/check-literals.mjs allows it by exact value. */
const INSTANT_PARTS = Object.freeze({
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

const DAY_PARTS = Object.freeze({ day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const MONTH_PARTS = Object.freeze({ month: "long", year: "numeric", timeZone: "UTC" });
const SHORT_DAY_PARTS = Object.freeze({ day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const ISO_DAY = "YYYY-MM-DD";
const ISO_MONTH = "YYYY-MM";

/** "8 October 2026 at 21:04 UTC", for a fetch time. null for anything that is
 *  not a valid instant. */
export function formatInstant(iso) {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return null;
  const parts = {};
  for (const part of new Intl.DateTimeFormat("en-GB", INSTANT_PARTS).formatToParts(date)) {
    parts[part.type] = part.value;
  }
  return parts.day + " " + parts.month + " " + parts.year + " at " + parts.hour + ":" + parts.minute + " UTC";
}

/** "23 October 2026" for an ISO day, "August 2026" for an ISO month, the
 *  string itself for anything else (a quarter, a year), or null. */
export function formatDay(iso) {
  if (typeof iso !== "string" || iso === "") return null;
  const quarter = /^(?<year>\d{4})-(?<quarter>Q\d)$/.exec(iso);
  if (quarter) return quarter.groups.quarter + " " + quarter.groups.year;
  if (iso.length === ISO_MONTH.length) {
    const month = new Date(iso);
    if (!Number.isNaN(month.getTime())) return new Intl.DateTimeFormat("en-GB", MONTH_PARTS).format(month);
  }
  if (iso.length >= ISO_DAY.length) {
    // A date only ISO string is read as midnight UTC.
    const date = new Date(iso.slice(0, ISO_DAY.length));
    if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat("en-GB", DAY_PARTS).format(date);
  }
  return iso;
}

/** "23 Oct 2026", the same day in the short form a table's first column
 *  takes, so a row of figures is not three lines tall on a phone. */
export function formatDayShort(iso) {
  if (typeof iso !== "string" || iso.length < ISO_DAY.length) return formatDay(iso);
  const date = new Date(iso.slice(0, ISO_DAY.length));
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", SHORT_DAY_PARTS).format(date);
}

/* ------------------------------------------ loading, empty and error --- */

/** "Loading the route library." */
export function loadingSentence(what) {
  return "Loading " + what + ".";
}

/** Two sentences for an artifact that did not load: what happened, then what
 *  to do. `failure` is the record state.js keeps, with its time. */
export function loadFailureSentences(failure) {
  const when = formatInstant(failure.at);
  const happened =
    "The page could not load " + failure.path + ", which holds " + failure.holds +
    ": " + failure.what + (when ? ", at " + when : "") + ".";
  const todo = failure.todo ||
    "Reload the page to try again. If it fails again the file is missing or damaged in this copy of the site, " +
    "and nothing it holds is shown, rather than shown from a guess.";
  return [happened, todo];
}

/** What a cell with no figure says when nothing else can be said about it. */
export const NO_FIGURE = "no figure";

const HAS_UNDERSCORE = /_/;
const IS_ONE_WORD = /^\S+$/;

/** The words for a figure that is missing: the artifact's plain words, or
 *  "no figure" when they are absent or shaped like an identifier. */
export function missingFigureText(words) {
  const name = typeof words === "string" ? words.trim() : "";
  if (!name) return NO_FIGURE;
  if (HAS_UNDERSCORE.test(name) || IS_ONE_WORD.test(name)) return NO_FIGURE;
  return name;
}

/** "a, b and c". */
export function listWords(items) {
  const list = (items || []).filter((item) => item !== "" && item !== null && item !== undefined);
  if (list.length <= 1) return list.join("");
  return list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
}
