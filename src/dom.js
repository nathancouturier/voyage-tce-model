/* dom.js
 *
 * The few element helpers every view needs: build an element, empty one, set
 * a sentence of segments with each figure in its own span, a disclosure, a
 * scrolling table with its caption, a figure cell, and the loading, failure
 * and empty sentences from format.js. Nothing here knows what a TCE is. The
 * sibling studies' helpers, with this study's segments (a figure carries its
 * own prefix and suffix, "USD " and " million").
 *
 * Numeric literals: one declared count, MOST_NAMED.
 */

import { segmentText, missingFigureText, loadFailureSentences, loadingSentence } from "./format.js";
import { artifactEntry } from "./state.js";

/** Build an element. `options.attrs` skips null and undefined, so a caller can
 *  pass a conditional attribute without a branch. Children may be strings,
 *  nodes, or null. */
export function el(tag, options, children) {
  const node = document.createElement(tag);
  const opts = options || {};
  if (opts.class) node.className = opts.class;
  if (opts.id) node.id = opts.id;
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.attrs) {
    for (const [name, value] of Object.entries(opts.attrs)) {
      if (value === null || value === undefined) continue;
      node.setAttribute(name, String(value));
    }
  }
  for (const child of children || []) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/** Set a sentence the export wrote as segments into `parent`.
 *
 *  Words become text nodes. A number becomes span.fig with data-field naming
 *  where it came from, so a test in the browser can walk every figure on the
 *  page back to a field. A word that came from a field (a date, a route)
 *  becomes span.data-word with the same data-field. A missing number becomes
 *  the segment's own `missing` words, or "no figure", never the field. */
export function appendSegments(parent, segments, decimals) {
  for (const segment of segments || []) {
    const piece = segmentText(segment, decimals);
    if (piece.kind === "text") {
      parent.appendChild(document.createTextNode(piece.text));
    } else if (piece.kind === "number") {
      parent.appendChild(el("span", {
        class: piece.missing ? "fig is-missing" : (segment.accent ? "fig text-accent" : "fig"),
        text: piece.missing ? missingFigureText(segment.missing) : piece.text,
        attrs: { "data-field": piece.field },
      }));
    } else {
      parent.appendChild(el("span", { class: "data-word", text: piece.text, attrs: { "data-field": piece.field } }));
    }
  }
  return parent;
}

/** A paragraph saying what is loading. */
export function loadingMessage(what) {
  return el("p", { class: "state-message", text: loadingSentence(what), attrs: { role: "status" } });
}

/** Paragraphs for every artifact that failed, each with its time and what to
 *  do. */
export function failureMessages(failures) {
  const nodes = [];
  for (const failure of failures) {
    for (const line of loadFailureSentences(failure)) {
      nodes.push(el("p", { class: "state-message", text: line }));
    }
  }
  if (nodes.length) nodes[0].setAttribute("role", "alert");
  return nodes;
}

/** Paragraphs for a view or section that received its files but could not
 *  draw them: which files, what went wrong, and what to do. */
export function renderFailureMessages(names, error) {
  const files = names.map((name) => {
    const entry = artifactEntry(name);
    return entry ? entry.path : name;
  });
  const what = error && error.message ? error.message : String(error);
  const nodes = [
    el("p", { class: "state-message", attrs: { role: "alert" }, text: "The page loaded " + files.join(" and ") + " but could not draw what it holds: " + what + "." }),
    el("p", { class: "state-message", text: "Reload the page: the site was probably updated while this copy was open. Nothing is shown here rather than shown in part." }),
  ];
  return nodes;
}

/** A sentence element of segments: el(tag) with appendSegments. */
export function sentence(tag, segments, decimals, className) {
  return appendSegments(el(tag, { class: className }), segments, decimals);
}

/** A button that shows and hides a region under it, named for what the region
 *  holds. The region is built on first open by `build`, so a closed
 *  alternative costs nothing. Enter and Space work because it is a native
 *  button. */
export function disclosure(label, build) {
  const region = el("div", { class: "disclosure__region", id: uniqueId("alt") });
  region.hidden = true;
  const button = el("button", {
    class: "disclosure__button",
    text: label,
    attrs: { type: "button", "aria-expanded": "false", "aria-controls": region.id },
  });
  let built = false;
  button.addEventListener("click", () => {
    const open = button.getAttribute("aria-expanded") !== "true";
    if (open && !built) {
      region.appendChild(build());
      built = true;
    }
    button.setAttribute("aria-expanded", open ? "true" : "false");
    region.hidden = !open;
  });
  return el("div", { class: "disclosure" }, [button, region]);
}

let uniqueCounter = 0;
/** A document unique id. */
export function uniqueId(prefix) {
  uniqueCounter += 1;
  return prefix + "-" + String(uniqueCounter);
}

/** A wide table under its caption.
 *
 *  The caption is a paragraph ABOVE the scroll box, not a caption element inside
 *  it, where it would take the table's width and be clipped with the columns it
 *  announces. The table names the paragraph with aria-labelledby.
 *
 *  The paragraph ends with the columns that are off screen, measured at every
 *  width and scroll position. While the table overflows, the box takes keyboard
 *  focus so it can be scrolled with the arrow keys, and a control that takes
 *  focus inside it is scrolled fully into view with its focus ring. */
export function scrollTable(captionChildren, table) {
  const id = uniqueId("table-caption");
  // At 600px and below a table of more than STACK_FROM columns is set as one
  // block per row, each cell under its column's name (styles: .table--stack),
  // so no figure is cut by the edge of a scroll box.
  const heads = [...table.querySelectorAll("thead tr:last-child th")].map((th) => th.textContent.trim());
  if (heads.length > STACK_FROM) {
    table.classList.add("table--stack");
    // A table set as blocks loses its table semantics in some browsers, so the
    // roles are written into the markup, as the bridge's are.
    table.setAttribute("role", "table");
    for (const group of table.querySelectorAll("thead, tbody")) group.setAttribute("role", "rowgroup");
    for (const th of table.querySelectorAll("thead th")) th.setAttribute("role", "columnheader");
    for (const tr of table.querySelectorAll("tr")) tr.setAttribute("role", "row");
    for (const tr of table.querySelectorAll("tbody tr")) {
      let column = 0;
      for (const cell of tr.children) {
        if (cell.tagName === "TD") {
          cell.setAttribute("role", "cell");
          if (heads[column]) cell.setAttribute("data-label", heads[column]);
        } else if (cell.tagName === "TH") cell.setAttribute("role", "rowheader");
        column += Number(cell.getAttribute("colspan") || 1);
      }
    }
  }
  const more = el("span", { class: "table-caption__more" });
  const caption = el("p", { class: "table-caption", id }, [...captionChildren, more]);
  table.setAttribute("aria-labelledby", id);
  const scroller = el("div", { class: "table-scroll", attrs: { role: "region", "aria-labelledby": id } }, [table]);

  const update = () => {
    if (scroller.clientWidth === 0) return; // inside a closed section, not laid out
    const overflows = scroller.scrollWidth > scroller.clientWidth;
    if (overflows) scroller.tabIndex = 0;
    else scroller.removeAttribute("tabindex");
    const words = overflows ? offScreenWords(scroller, table) : "";
    if (more.textContent !== words) more.textContent = words;
  };
  scroller.addEventListener("scroll", update, { passive: true });
  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(update);
    observer.observe(scroller);
    observer.observe(table);
  } else {
    window.addEventListener("resize", update, { passive: true });
  }

  const reveal = (target) => {
    if (!target || target === scroller || !scroller.contains(target)) return;
    const style = getComputedStyle(target);
    const ring = (parseFloat(style.outlineWidth) || 0) + (parseFloat(style.outlineOffset) || 0);
    const box = scroller.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    const row = target.closest("tr");
    const first = row ? row.firstElementChild : null;
    const sticky = first && !first.contains(target) && getComputedStyle(first).position === "sticky" ? first.getBoundingClientRect().width : 0;
    const overRight = rect.right + ring - box.right;
    const overLeft = box.left + sticky - (rect.left - ring);
    if (overRight > 0 && overLeft <= 0) scroller.scrollLeft += Math.min(overRight, -overLeft);
    else if (overLeft > 0) scroller.scrollLeft -= overLeft;
  };
  scroller.addEventListener("focusin", (event) => {
    reveal(event.target);
    requestAnimationFrame(() => reveal(event.target));
  });

  return el("div", { class: "table-block" }, [caption, scroller]);
}

/* The sentence naming the columns a scroll box cuts off, or "". */
function offScreenWords(scroller, table) {
  const heads = [...table.querySelectorAll("thead tr:last-child th")].filter((th) => th.getBoundingClientRect().width > 0);
  if (heads.length <= 1) return "";
  const tableLeft = table.getBoundingClientRect().left + scroller.scrollLeft;
  const sticky = getComputedStyle(heads[0]).position === "sticky" ? heads[0].getBoundingClientRect().width : 0;
  const visibleLeft = scroller.scrollLeft + sticky;
  const visibleRight = scroller.scrollLeft + scroller.clientWidth;
  const right = [];
  const left = [];
  heads.slice(1).forEach((th) => {
    // The column's content box: a cell whose words are all on screen is not
    // off screen because its right padding is.
    const rect = th.getBoundingClientRect();
    const style = getComputedStyle(th);
    const start = rect.left + scroller.scrollLeft - tableLeft + (parseFloat(style.paddingLeft) || 0);
    const end = rect.left + scroller.scrollLeft - tableLeft + rect.width - (parseFloat(style.paddingRight) || 0);
    if (end > visibleRight + 1) right.push(shortName(th));
    else if (start < visibleLeft - 1) left.push(shortName(th));
  });
  return columnsSentence(right, "to the right") + columnsSentence(left, "to the left");
}

function shortName(th) {
  // data-short is written as it reads inside a sentence ("Baltic TCE",
  // "Supramax"); only a heading's own text is lowered.
  if (th.dataset.short) return th.dataset.short.trim();
  const name = (th.textContent || "").trim();
  return /^[A-Z][a-z]/.test(name) ? name.charAt(0).toLowerCase() + name.slice(1) : name;
}

/* " The a, b and c columns are to the right." More than a handful are named by
 * the first of them. */
const MOST_NAMED = 4;
/* A table of more columns than this is stacked at 600px and below. */
const STACK_FROM = 3;
function columnsSentence(names, where) {
  if (!names.length) return "";
  if (names.length > MOST_NAMED) return " The columns from " + names[0] + " on are " + where + ".";
  const list = names.length === 1 ? names[0] : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  return " The " + list + (names.length === 1 ? " column is " : " columns are ") + where + ".";
}

/** A table cell holding a figure, or the words for a missing one.
 *
 *    text       the formatted figure, or null when there is none
 *    field      the artifact field the figure came from, in data-field for a
 *               test, and never printed
 *    options    { missing, className }: `missing` is what an empty cell says,
 *               in words, from the artifact; absent, the cell says "no figure"
 *               and the reason belongs in the caption.
 */
export function figureCell(text, field, options) {
  const { missing, className } = typeof options === "string" ? { className: options } : (options || {});
  if (text === null) {
    return el("td", { class: "num is-missing", text: missingFigureText(missing), attrs: { "data-missing": field } });
  }
  return el("td", { class: className ? "num " + className : "num", text, attrs: { "data-field": field } });
}
