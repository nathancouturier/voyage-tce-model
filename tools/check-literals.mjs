#!/usr/bin/env node
// Fail if the frontend holds a number that did not come from a JSON artifact.
//
//     node tools/check-literals.mjs              self test, then scan
//     node tools/check-literals.mjs --verbose    also list every allowed literal
//
// Every number in the browser comes from a JSON artifact; the frontend holds no
// numeric literal except unit constants and the drawing surface's dimensions.
// A grep for digits cannot tell a market value from a list index, or code from
// a comment, so this reads the source with a small JavaScript lexer and applies
// an explicit allowlist. Plain node, no dependencies. The checker of the
// sibling studies, with this site's allowlist.
//
// WHAT IS SCANNED
//   src/*.js, the page's modules (src/voyage is the Python package)
//   index.html: every inline script as JavaScript; the text between tags; and
//   every attribute value except href and src, which are paths and are guarded
//   by tools/check-paths.mjs
//
// WHAT COUNTS AS A LITERAL
//   In code, every numeric token: 23.96, 7, 1e-9, 0x1F, 10n.
//   In a string or template literal, every run of digits that stands alone,
//   because "nets 23.96 $/MMBtu" in a string is as much a hardcoded value as
//   23.96 in code. A leading point (".45") or a unit after the digits ("999px")
//   still stands alone; a run touching a letter, #, backslash, point or another
//   digit on its left does not: "v2", "v2.002" and "#17181C" are versions and a
//   colour. In index.html, quoted strings inside an inline <style> are read too.
//   Comments and regex bodies are not scanned.
//
// THE ALLOWLIST, and nothing else passes
//   1  the values 0 and 1 in code: index arithmetic, a length boundary, a step.
//      Not two of them as each other's operands (1 + 1 is a 2 in disguise),
//      and not where a declared snippet names them (an object's default).
//   2  UNIT_CONSTANTS: a name and its exact value, per file, allowed only in the
//      declaration `const NAME = value`. Changing the value fails, and so does
//      using the same figure anywhere else in the file.
//   3  DECLARED: an exact source snippet containing a literal, per file, with
//      the number of times it may occur and the reason.
//   4  STRING_VOCABULARY: exact string literals that an API defines.
//   5  CITATIONS: in a string, a number directly after "section" or "question".
//   6  HTML_ATTRIBUTES: an attribute name and exact value in index.html.
//   7  LAYOUT_CONSTANTS: a name and its exact value, per file, allowed only as
//      the property `NAME: value` alone on its line, the form of the frozen
//      GEOMETRY block in src/charts.js. A drawing surface decision.
//   8  CONTENT_HASH: in index.html only, a relative path followed by ?v= and
//      twelve lower case hex digits, the form src/voyage/versions.py writes.
//
// SELF TEST. Before scanning, the tool plants values in synthetic files and
// asserts it reports each one, and that the allowed forms pass. If the self
// test fails, the scan result means nothing and the tool exits 1.

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// ------------------------------------------------------------ allowlist ---

// Rule 1. Index arithmetic.
const ALWAYS_ALLOWED_VALUES = new Set([0, 1]);

// Rule 2. Unit constants, by file.
const UNIT_CONSTANTS = {
  // The code points of the characters the page draws but never writes literally.
  "src/format.js": [
    { name: "MINUS_SIGN", value: "0x2212" },
  ],
  "src/theme.js": [
    { name: "SUN", value: "0x2600" },
    { name: "MOON", value: "0x263e" },
    { name: "TEXT_PRESENTATION", value: "0xfe0e" },
  ],
};

// Rule 7. Layout constants, by file, as `NAME: value` in a frozen block, in
// CSS pixels unless the reason says otherwise.
const LAYOUT_CONSTANTS = {
  "src/charts.js": [
    { name: "PAD_TOP", value: "28", why: "room above a plot for the unit title" },
    { name: "PAD_LEFT", value: "64", why: "room for the tick values" },
    { name: "PAD_RIGHT", value: "24", why: "room right of a plot for the last tick value" },
    { name: "AXIS_GAP", value: "16", why: "plot edge to the x tick values" },
    { name: "AXIS_BELOW", value: "24", why: "room under the tick values for the axis title" },
    { name: "TICK_LENGTH", value: "4", why: "an axis tick" },
    { name: "LABEL_GAP", value: "8", why: "a mark to its label" },
    { name: "DOT_RADIUS", value: "4", why: "a printed point" },
    { name: "RING_WIDTH", value: "2", why: "the --bg ring" },
    { name: "HALF", value: "0.5", why: "halving, for centring" },
    { name: "COORD_DECIMALS", value: "2", why: "places in a pixel coordinate" },
    { name: "BAR_THICKNESS", value: "14", why: "a bar in a 30px row" },
    { name: "SMALL_STEP", value: "4", why: "steps narrower than this are dots" },
    { name: "SMALL_RADIUS", value: "2.5", why: "the dot of a small step" },
    { name: "OUTLINE_INSET", value: "0.75", why: "half the 1.5px outline" },
    { name: "SEGMENT_GAP", value: "2", why: "the --bg gap between stacked segments" },
    { name: "Y_TICKS", value: "5", why: "about five tick intervals" },
    { name: "X_TICKS", value: "5", why: "about five tick intervals" },
    { name: "NARROW_WIDTH", value: "600", why: "the width below which a label goes above its bar" },
    { name: "ROW", value: "30", why: "a bar chart's row" },
    { name: "ROW_NARROW", value: "44", why: "a row with its label above the bar" },
    { name: "LABEL_COLUMN", value: "220", why: "the widest label column" },
    { name: "LABEL_SHARE", value: "0.32", why: "the label column's share of a chart's width" },
    { name: "GROUP_HEAD", value: "30", why: "a group heading's row" },
    { name: "VALUE_ROOM", value: "112", why: "room right of the longest bar for its value" },
    { name: "CHAR", value: "7", why: "room per character of a caption sized label" },
    { name: "LINE_HEIGHT", value: "260", why: "a line chart's plot" },
    { name: "LINE_HEIGHT_NARROW", value: "200", why: "the same below NARROW_WIDTH" },
    { name: "TOOLTIP_OFFSET", value: "14", why: "the readout's distance from the pointer" },
  ],
  "src/map.js": [
    { name: "PORT_RADIUS", value: "3.5", why: "a port's dot, in screen px" },
    { name: "PORT_GAP", value: "3", why: "a port's dot to its name" },
    { name: "PORT_FONT", value: "12", why: "a port's name, in screen px" },
    { name: "ABOVE", value: "0.25", why: "a name's baseline above the dot, as a share of its size" },
    { name: "BELOW", value: "0.85", why: "a name's baseline below the dot, as a share of its size" },
    { name: "BESIDE", value: "0.35", why: "a name's baseline beside the dot, as a share of its size" },
    { name: "CHAR_EM", value: "0.6", why: "a character's width as a share of its size" },
  ],
};

// Rule 3. Declared snippets, by file. `count` is exact: a snippet counts once
// per literal inside it.
const DECLARED = {
  "src/charts.js": [
    // The mantissas of decimal notation, a fact about how numbers are
    // written. Four literals: 1, 2, 5 and 10.
    { snippet: "Object.freeze([1, 2, 5, 10])", count: 4, why: "the 1, 2, 5, 10 tick ladder" },
  ],
  "src/dom.js": [
    { snippet: "const MOST_NAMED = 4;", count: 1, why: "columns a table caption names one by one" },
  ],
};

// Rule 4. Strings an API defines.
const STRING_VOCABULARY = new Set([
  "2-digit", // Intl.DateTimeFormat option value for hour and minute
  "-1", // the tabindex value that makes an element focusable by script only
]);

// Rule 5. Citation words that may precede a number inside a string.
const CITATION_BEFORE = /(?:sections?|question)\s+(?:\d+(?:\.\d+)*\s+(?:to|and)\s+)?$/;

// Rule 6. Attribute values in index.html, exact.
const HTML_ATTRIBUTES = [
  { attr: "charset", value: "utf-8", why: "the character encoding" },
  { attr: "content", value: "width=device-width, initial-scale=1", why: "the viewport meta" },
  { attr: "tabindex", value: "-1", why: "focusable by script only" },
];

// Rule 8. A versioned path in the import map, exact form, index.html only.
const CONTENT_HASH = /^\.\/(?:src|data|styles)\/[\w.-]+\?v=[0-9a-f]{12}$/;

// ---------------------------------------------------------------- lexer ---

const REGEX_AFTER_WORDS = new Set(["return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "instanceof", "yield", "await"]);

/** Lex JavaScript into the pieces this check cares about: numeric tokens in
 *  code, and string and template text. Comments and regex bodies are skipped.
 *  Returns { numbers: [{ text, index }], strings: [{ text, index, raw }] }. */
export function lex(source) {
  const numbers = [];
  const strings = [];
  let i = 0;
  const n = source.length;
  let lastSignificant = ""; // the previous token class: "word", "num", "close", "punct"
  let lastWord = "";
  const templateStack = []; // brace depth at which each open template resumes

  let braceDepth = 0;

  const readTemplate = (start) => {
    // i points just after a backtick or a closing brace of ${ }
    let text = "";
    let textStart = i;
    while (i < n) {
      const c = source[i];
      if (c === "\\") { text += source.slice(i, i + 2); i += 2; continue; }
      if (c === "`") { strings.push({ text, index: textStart, raw: text }); i += 1; return "closed"; }
      if (c === "$" && source[i + 1] === "{") {
        strings.push({ text, index: textStart, raw: text });
        i += 2;
        templateStack.push(braceDepth);
        braceDepth += 1;
        return "expression";
      }
      text += c;
      i += 1;
    }
    strings.push({ text, index: textStart, raw: text });
    return "closed";
  };

  while (i < n) {
    const c = source[i];
    const next = source[i + 1];
    if (c === "/" && next === "/") { while (i < n && source[i] !== "\n") i += 1; continue; }
    if (c === "/" && next === "*") { const end = source.indexOf("*/", i + 2); i = end < 0 ? n : end + 2; continue; }
    if (/\s/.test(c)) { i += 1; continue; }
    if (c === "'" || c === '"') {
      const quote = c; const start = i; i += 1; let text = "";
      while (i < n && source[i] !== quote) {
        if (source[i] === "\\") { text += source.slice(i, i + 2); i += 2; continue; }
        if (source[i] === "\n") break;
        text += source[i]; i += 1;
      }
      i += 1;
      strings.push({ text, index: start, raw: text });
      lastSignificant = "close";
      continue;
    }
    if (c === "`") {
      i += 1;
      readTemplate(i);
      lastSignificant = "close";
      continue;
    }
    if (c === "{") { braceDepth += 1; i += 1; lastSignificant = "punct"; continue; }
    if (c === "}") {
      braceDepth -= 1;
      if (templateStack.length && templateStack[templateStack.length - 1] === braceDepth) {
        templateStack.pop();
        i += 1;
        readTemplate(i);
        lastSignificant = "close";
        continue;
      }
      i += 1; lastSignificant = "close"; continue;
    }
    if (c === "/") {
      const regexAllowed = lastSignificant === "" || lastSignificant === "punct" || (lastSignificant === "word" && REGEX_AFTER_WORDS.has(lastWord));
      if (regexAllowed) {
        i += 1; let inClass = false;
        while (i < n) {
          const r = source[i];
          if (r === "\\") { i += 2; continue; }
          if (r === "[") inClass = true;
          else if (r === "]") inClass = false;
          else if (r === "/" && !inClass) break;
          else if (r === "\n") break;
          i += 1;
        }
        i += 1;
        while (i < n && /[a-z]/i.test(source[i])) i += 1;
        lastSignificant = "close";
        continue;
      }
      i += 1; lastSignificant = "punct"; continue;
    }
    const numberMatch = /^(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?)n?/.exec(source.slice(i, i + 64));
    if (numberMatch && (/\d/.test(c) || (c === "." && /\d/.test(next || "")))) {
      numbers.push({ text: numberMatch[0], index: i });
      i += numberMatch[0].length;
      lastSignificant = "num";
      continue;
    }
    const wordMatch = /^[A-Za-z_$][\w$]*/.exec(source.slice(i, i + 256));
    if (wordMatch) {
      lastWord = wordMatch[0];
      lastSignificant = "word";
      i += wordMatch[0].length;
      continue;
    }
    lastSignificant = c === ")" || c === "]" ? "close" : "punct";
    i += 1;
  }
  return { numbers, strings };
}

function lineOf(source, index) {
  let line = 1;
  for (let k = 0; k < index && k < source.length; k += 1) if (source[k] === "\n") line += 1;
  return line;
}

function lineText(source, index) {
  const start = source.lastIndexOf("\n", index - 1) + 1;
  const end = source.indexOf("\n", index);
  return source.slice(start, end < 0 ? source.length : end);
}

/** Digit runs that stand alone inside a piece of text, with their offsets. */
function standaloneNumbers(text) {
  // A run of digits, with a leading point (".45") or a unit after it ("999px")
  // still standing alone; one touching a letter, #, a backslash, a point or a
  // digit on its left ("v2", "#17181C", "v2.002") does not.
  const out = [];
  const pattern = /(?<![\w#\\.])(?:\.(?=\d))?\d+(?:[.,]\d+)*/g;
  let match;
  while ((match = pattern.exec(text)) !== null) out.push({ text: match[0], offset: match.index });
  return out;
}

// ------------------------------------------------------------- checking ---

function numericValue(text) {
  const clean = text.replace(/_/g, "").replace(/n$/, "");
  return Number(clean);
}

/** Check one JavaScript source. Returns { violations, allowed }. */
export function checkScript(relative, source, baseIndex = 0, fullSource = source) {
  const violations = [];
  const allowed = [];
  const { numbers, strings } = lex(source);
  const units = UNIT_CONSTANTS[relative] || [];
  const declared = (DECLARED[relative] || []).map((entry) => ({ ...entry, seen: 0 }));

  for (const token of numbers) {
    const at = baseIndex + token.index;
    const where = { file: relative, line: lineOf(fullSource, at), text: lineText(fullSource, at).trim() };
    const value = numericValue(token.text);
    const lineStart0 = source.lastIndexOf("\n", token.index - 1) + 1;
    const lineEnd0 = source.indexOf("\n", token.index);
    const line0 = source.slice(lineStart0, lineEnd0 < 0 ? source.length : lineEnd0);
    const declaredFirst = declared.find((d) => {
      const pos = line0.indexOf(d.snippet);
      if (pos < 0) return false;
      const col = token.index - lineStart0;
      return col >= pos && col < pos + d.snippet.length;
    });
    if (declaredFirst) {
      declaredFirst.seen += 1;
      allowed.push({ ...where, literal: token.text, rule: "declared: " + declaredFirst.why });
      continue;
    }
    if (ALWAYS_ALLOWED_VALUES.has(value) && /^[01]$/.test(token.text)) {
      const left = source.slice(Math.max(0, token.index - 8), token.index);
      const right = source.slice(token.index + token.text.length, token.index + token.text.length + 8);
      if (/(?:^|[^\w.])[01]\s*[-+*/%]\s*$/.test(left) || /^\s*[-+*/%]\s*[01](?![\w.])/.test(right)) {
        violations.push({ ...where, literal: token.text, kind: "arithmetic built from 0 and 1, a figure in disguise" });
        continue;
      }
      // A 1 as an object's value is a setting, not index arithmetic: it has
      // to be declared. A 0 there means nothing is set and passes.
      if (token.text === "1" && /\w\s*:\s*$/.test(left) && /^\s*[,}\n]/.test(right)) {
        violations.push({ ...where, literal: token.text, kind: "a 1 as an object's value, declare it" });
        continue;
      }
      allowed.push({ ...where, literal: token.text, rule: "index arithmetic" });
      continue;
    }
    const before = source.slice(0, token.index);
    const unit = units.find((u) => new RegExp("(?:export\\s+)?const\\s+" + u.name + "\\s*=\\s*$").test(before.slice(-128)) && u.value === token.text);
    if (unit) {
      allowed.push({ ...where, literal: token.text, rule: "unit constant " + unit.name });
      continue;
    }
    const lineStart = source.lastIndexOf("\n", token.index - 1) + 1;
    const lineEnd = source.indexOf("\n", token.index);
    const localLine = source.slice(lineStart, lineEnd < 0 ? source.length : lineEnd);
    const layout = (LAYOUT_CONSTANTS[relative] || []).find((u) =>
      u.value === token.text &&
      new RegExp("^\\s*" + u.name + "\\s*:\\s*$").test(source.slice(lineStart, token.index)) &&
      /^\s*,?\s*$/.test(source.slice(token.index + token.text.length, lineEnd < 0 ? source.length : lineEnd)));
    if (layout) {
      allowed.push({ ...where, literal: token.text, rule: "layout constant " + layout.name });
      continue;
    }
    const entry = declared.find((d) => {
      const pos = localLine.indexOf(d.snippet);
      if (pos < 0) return false;
      const col = token.index - lineStart;
      return col >= pos && col < pos + d.snippet.length;
    });
    if (entry) {
      entry.seen += 1;
      allowed.push({ ...where, literal: token.text, rule: "declared: " + entry.why });
      continue;
    }
    violations.push({ ...where, literal: token.text, kind: "numeric literal in code" });
  }

  for (const entry of declared) {
    if (entry.seen !== entry.count) {
      violations.push({ file: relative, line: 0, text: entry.snippet, literal: entry.snippet, kind: "declared snippet expected " + entry.count + " time(s), found " + entry.seen + "; update the allowlist deliberately" });
    }
  }

  for (const piece of strings) {
    if (relative === "index.html" && CONTENT_HASH.test(piece.text)) {
      if (/\d/.test(piece.text)) allowed.push({ file: relative, line: lineOf(fullSource, baseIndex + piece.index), literal: JSON.stringify(piece.text), rule: "content hash", text: "" });
      continue;
    }
    if (STRING_VOCABULARY.has(piece.text)) {
      if (/\d/.test(piece.text)) allowed.push({ file: relative, line: lineOf(fullSource, baseIndex + piece.index), literal: JSON.stringify(piece.text), rule: "API vocabulary", text: "" });
      continue;
    }
    for (const hit of standaloneNumbers(piece.text)) {
      const at = baseIndex + piece.index;
      const where = { file: relative, line: lineOf(fullSource, at), text: lineText(fullSource, at).trim() };
      if (CITATION_BEFORE.test(piece.text.slice(0, hit.offset))) {
        allowed.push({ ...where, literal: hit.text, rule: "citation" });
        continue;
      }
      violations.push({ ...where, literal: hit.text, kind: "number inside a string" });
    }
  }
  return { violations, allowed };
}

/** Check index.html: inline scripts, text, attributes. */
export function checkHtml(relative, source) {
  const violations = [];
  const allowed = [];
  // Inline scripts, scanned as JavaScript, then blanked so the text scan below
  // does not read them again.
  let rest = source;
  const scriptPattern = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = scriptPattern.exec(source)) !== null) {
    if (/\bsrc\s*=/.test(match[1])) continue;
    const bodyIndex = match.index + match[0].indexOf(">") + 1;
    const result = checkScript(relative, match[2], bodyIndex, source);
    violations.push(...result.violations);
    allowed.push(...result.allowed);
  }
  rest = rest.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, (m) => m.replace(/[^\n]/g, " "));
  rest = rest.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "));
  // An inline stylesheet's sizes are layout, but a quoted string in it (a
  // generated content: "23.96") reaches the reader, so its digits count.
  const stylePattern = /<style\b[^>]*>([\s\S]*?)<\/style>/gi;
  while ((match = stylePattern.exec(source)) !== null) {
    const bodyIndex = match.index + match[0].indexOf(">") + 1;
    for (const quoted of match[1].matchAll(/"([^"]*)"|'([^']*)'/g)) {
      const value = quoted[1] ?? quoted[2];
      for (const hit of standaloneNumbers(value)) {
        const at = bodyIndex + quoted.index;
        violations.push({ file: relative, line: lineOf(source, at), text: lineText(source, at).trim(), literal: hit.text, kind: "number in a style string" });
      }
    }
  }
  rest = rest.replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, (m) => m.replace(/[^\n]/g, " "));
  // Character references such as &#x263E; are an encoding, not a figure.
  rest = rest.replace(/&#x?[0-9a-fA-F]+;/g, (m) => " ".repeat(m.length));

  // Attributes.
  // Opening tags carry attributes; closing tags and the doctype only bound text.
  rest = rest.replace(/<\/[a-zA-Z][\w-]*\s*>|<![^>]*>/g, (m) => "<" + " ".repeat(m.length - 2) + ">");
  const tagPattern = /<([a-zA-Z][\w-]*)((?:\s+[^\s=>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*\/?>/g;
  const tagRanges = [];
  while ((match = tagPattern.exec(rest)) !== null) {
    tagRanges.push([match.index, match.index + match[0].length]);
    const attrPattern = /([^\s=>]+)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    let attr;
    const attrsText = match[2];
    const attrsStart = match.index + match[0].indexOf(attrsText);
    while ((attr = attrPattern.exec(attrsText)) !== null) {
      const name = attr[1].toLowerCase();
      const value = attr[3] ?? attr[4] ?? attr[5] ?? "";
      if (name === "href" || name === "src") continue;
      const hits = standaloneNumbers(value);
      if (!hits.length) continue;
      const at = attrsStart + attr.index;
      const where = { file: relative, line: lineOf(source, at), text: lineText(source, at).trim() };
      const declared = HTML_ATTRIBUTES.find((d) => d.attr === name && d.value === value);
      if (declared) {
        allowed.push({ ...where, literal: name + '="' + value + '"', rule: "attribute: " + declared.why });
        continue;
      }
      for (const hit of hits) violations.push({ ...where, literal: hit.text, kind: "number in the attribute " + name });
    }
  }
  // Text between tags.
  let cursor = 0;
  for (const [start, end] of tagRanges) {
    const text = rest.slice(cursor, start);
    for (const hit of standaloneNumbers(text)) {
      const at = cursor + hit.offset;
      violations.push({ file: relative, line: lineOf(source, at), text: lineText(source, at).trim(), literal: hit.text, kind: "number in page text" });
    }
    cursor = end;
  }
  const tail = rest.slice(cursor);
  for (const hit of standaloneNumbers(tail)) {
    const at = cursor + hit.offset;
    violations.push({ file: relative, line: lineOf(source, at), text: lineText(source, at).trim(), literal: hit.text, kind: "number in page text" });
  }
  return { violations, allowed };
}

// ------------------------------------------------------------ self test ---

function selfTest() {
  // Each engine and charts case carries the real file's declared snippets at
  // their declared counts, so only the planted value can be reported.
  // The engine's snippets hold one literal each and appear `count` times; the
  // tick ladder holds three and appears once, as in the real files.
  const ENGINE = "";
  const CHARTS = (DECLARED["src/charts.js"] || []).map((entry) => entry.snippet + ";\n").join("");
  const cases = [
    { name: "a market value in code", file: "src/planted.js", kind: "js", source: "const spread = 1.01;\n", expect: ["1.01"] },
    { name: "a market value in a string", file: "src/planted.js", kind: "js", source: 'el("p", { text: "Asia pays 1.01 over TTF" });\n', expect: ["1.01"] },
    { name: "a market value in a template expression", file: "src/planted.js", kind: "js", source: "const s = `nets ${value + 23} and ${`${23.96}`}`;\n", expect: ["23", "23.96"] },
    { name: "a market value in template text", file: "src/planted.js", kind: "js", source: "const s = `nets 23.96 ${unit}`;\n", expect: ["23.96"] },
    { name: "a literal that is not 0 or 1", file: "src/planted.js", kind: "js", source: "const month = iso.slice(0, 7);\n", expect: ["7"] },
    { name: "a negative market value", file: "src/planted.js", kind: "js", source: "const regas = -1.18;\n", expect: ["1.18"] },
    { name: "a figure built from ones", file: "src/planted.js", kind: "js", source: "const n = (1 + 1) * (1 + 1 + 1);\n", expect: ["1", "1", "1", "1", "1"] },
    { name: "a value with a leading point in words", file: "src/planted.js", kind: "js", source: 'const s = "boil-off takes .45 a day";\n', expect: [".45"] },
    { name: "a value with a unit in a string", file: "src/planted.js", kind: "js", source: 'node.style.width = "999px";\n', expect: ["999"] },
    { name: "a 1 as an object's value", file: "src/planted.js", kind: "js", source: "const opts = { share: 1, open: 0 };\n", expect: ["1"] },
    { name: "a value in an inline style string", file: "index.html", kind: "html", source: '<style>.x::after { content: "23.96"; width: 12px; }</style>\n', expect: ["23.96"] },
    { name: "a declared snippet moved", file: "src/dom.js", kind: "js", source: "const MOST_NAMED = 5;\n", expect: ["5", "const MOST_NAMED = 4;"] },
    { name: "a unit constant with a moved value", file: "src/format.js", kind: "js", source: "const MINUS_SIGN = 0x2213;\n", expect: ["0x2213"] },
    { name: "a unit constant used outside its declaration", file: "src/format.js", kind: "js", source: "const MINUS_SIGN = 0x2212;\nconst x = 0x2212;\n", expect: ["0x2212"] },
    { name: "a layout constant with a moved value", file: "src/charts.js", kind: "js", source: CHARTS + "const GEOMETRY = Object.freeze({\n  PAD_TOP: 29,\n});\n", expect: ["29"] },
    { name: "a layout constant's figure used elsewhere", file: "src/charts.js", kind: "js", source: CHARTS + "const GEOMETRY = Object.freeze({\n  PAD_TOP: 28,\n});\nconst h = 28;\n", expect: ["28"] },
    { name: "a value in page text", file: "index.html", kind: "html", source: "<p>TCE 466,378 USD a day</p>\n", expect: ["466,378"] },
    { name: "a value in an inline script", file: "index.html", kind: "html", source: "<script>var nb = 23.96;</script>\n", expect: ["23.96"] },
    { name: "a value in a data attribute", file: "index.html", kind: "html", source: '<span data-value="23.96">x</span>\n', expect: ["23.96"] },
    { name: "a value hidden in the import map", file: "index.html", kind: "html", source: '<script type="importmap">{"imports": {"./src/ui.js": "./src/ui.js?v=23.96", "./data/overview.json": "./data/overview.json?v=123456789012 91"}}</script>\n', expect: ["23.96", "123456789012", "91"] },
    {
      name: "allowed forms",
      file: "src/planted.js",
      kind: "js",
      source: [
        "// 23.96 in a comment reaches no reader",
        "/* nor 1.01 in a block comment */",
        "const last = list[list.length - 1];",
        "for (let i = 0; i < n; i += 1) {}",
        'const ink = "#17181C"; const face = "figtree.v2.002";',
        'const opts = { hour: "2-digit" }; const focusable = { tabindex: "-1" };',
        "const zero = /[1-9]/.test(body);",
      ].join("\n"),
      expect: [],
    },
    {
      name: "allowed html",
      file: "index.html",
      kind: "html",
      source: '<script type="importmap">{"imports": {"./src/ui.js": "./src/ui.js?v=123456789012", "./data/overview.json": "./data/overview.json?v=0a1b2c3d4e5f"}}</script>\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<h1 tabindex="-1">x</h1><link href="vendor/figtree/figtree.v2.002.latin.woff2"><span>&#x263E;&#xFE0E;</span><!-- 23.96 -->\n',
      expect: [],
    },
  ];
  const failures = [];
  for (const test of cases) {
    const result = test.kind === "js" ? checkScript(test.file, test.source) : checkHtml(test.file, test.source);
    const found = result.violations.map((v) => v.literal).sort();
    const expected = [...test.expect].sort();
    const ok = found.length === expected.length && found.every((value, index) => value === expected[index]);
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": expected " + JSON.stringify(expected) + ", reported " + JSON.stringify(found)));
    if (!ok) failures.push(test.name);
  }
  return failures;
}

// ----------------------------------------------------------------- main ---

/* The page's modules: the top level of src/, which is what index.html loads.
 * src/voyage is the Python package and never reaches the browser. src/engine.js
 * is held to the Python engine by tools/validate-engine.mjs instead: its
 * literals are the arithmetic of the formulas (0.0, 1.0), checked to 1e-9
 * against the Python source of truth on every committed case. */
function listScripts(directory) {
  const folder = path.join(ROOT, directory);
  if (!existsSync(folder)) return [];
  return readdirSync(folder)
    .filter((name) => name.endsWith(".js") && statSync(path.join(folder, name)).isFile())
    .map((name) => directory + "/" + name)
    .sort();
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const verbose = process.argv.includes("--verbose");
  console.log("check-literals.mjs");
  console.log("self test: planted market values must be reported, allowed forms must pass");
  const testFailures = selfTest();
  if (testFailures.length) {
    console.log("FAIL  the self test failed, so a scan result would mean nothing");
    process.exit(1);
  }

  const files = listScripts("src").filter((file) => file !== "src/engine.js");
  const violations = [];
  const allowed = [];
  for (const relative of files) {
    const result = checkScript(relative, readFileSync(path.join(ROOT, relative), "utf8"));
    violations.push(...result.violations);
    allowed.push(...result.allowed);
  }
  const htmlPath = path.join(ROOT, "index.html");
  let scanned = files.length;
  if (existsSync(htmlPath)) {
    const result = checkHtml("index.html", readFileSync(htmlPath, "utf8"));
    violations.push(...result.violations);
    allowed.push(...result.allowed);
    scanned += 1;
  }

  console.log("");
  console.log("scanned " + scanned + " file(s)");
  const byRule = new Map();
  for (const a of allowed) byRule.set(a.rule, (byRule.get(a.rule) || 0) + 1);
  console.log("allowed: " + ([...byRule.entries()].map(([rule, count]) => count + " " + rule).join(", ") || "none"));
  if (verbose) for (const a of allowed) console.log("  " + a.file + ":" + a.line + "  " + a.literal + "  " + a.rule);

  if (violations.length) {
    console.log("");
    console.log("FAIL  a number in the frontend that no artifact supplied");
    for (const v of violations) console.log("      " + v.file + ":" + v.line + "  " + v.literal + "  " + v.kind + "  | " + v.text.slice(0, 100));
    console.log("");
    console.log(violations.length + " literal(s). Read the figure from a JSON artifact, or, if it is a unit constant, a layout dimension or index arithmetic, add it to the commented allowlist at the top of this file with its reason.");
    process.exit(1);
  }
  console.log("PASS  no numeric literal outside the allowlist in src/ or index.html");
}
