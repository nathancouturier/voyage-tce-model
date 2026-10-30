/* atlas.js
 *
 * The Map view, where the site opens: every route the study prices on one
 * map of the world, the list of them beside it, and, once a route is picked,
 * its figures and the other ways it could sail. The map and the list are two
 * ways to the same choice: a click on a line or a label, a row of the list,
 * or an address naming the route. The detail replaces the list where the list
 * was, so the figures appear where the visitor looked; "Back to the list",
 * the Escape key and the browser's Back button return to it.
 *
 * From 1100px the map, its caption line and its legend stay on screen while
 * the column beside them scrolls (a sticky block in styles/components.css),
 * so a route and its alternatives are seen together with their figures.
 *
 * The line under the map says what the pointer is on, or the route picked:
 * one line in the page, never a box over the lines it describes, and the same
 * line a phone shows. It is not a live region: a choice moves focus to the
 * route's heading instead.
 *
 * The address keeps the choice: #/map?route=TD3C&segment=dirty. Opening a
 * route from the list is a history entry; moving from one route to another
 * replaces it, so Back always closes the route in one step. The segment is
 * not an entry, and a filter press is announced in the page's status line.
 * A route outside the segment clears the segment.
 *
 * Focus: on a choice made in the page, to the route's heading (the map first
 * scrolled into view when it is above the screen); on the way back, to the
 * route's row. Never on the first load, which ui.js handles.
 *
 * Every figure is from data/atlas.json and every line from data/map.json.
 * Nothing is computed here but where things go and the length of each row's
 * bar, a share of the highest TCE in the list.
 *
 * Numeric literals: none.
 */

import * as router from "./router.js";
import { el, clear, appendSegments, sentence, scrollTable } from "./dom.js";
import { viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";
import { atlasMap } from "./map.js";
import { segmentsText, listWords } from "./format.js";

export const artifacts = Object.freeze(["atlas", "map"]);

const VIEW = "map";
/* The facts read first in a route's detail, with its first fact whatever it is
 * (the study's freight); the others follow its alternatives. */
const HEADLINE_FACTS = new Set(["tce", "round_trip", "days", "distance"]);
const isHeadline = (fact, index) => index === 0 || HEADLINE_FACTS.has(fact.id);
let sections = null;
let view = null;
let escapeBound = false;

export function render(root, data, route) {
  const atlas = data.atlas;
  const page = atlas.page;
  const decimals = atlas.conventions.decimals;
  const title = viewHead(root, page.title, page.takeaway, decimals);
  const byId = new Map(atlas.items.map((item) => [item.id, item]));

  const frame = el("div", { class: "atlas-frame" });
  const mapHeading = el("h2", { class: "block__heading atlas-map-heading", text: page.map.title });
  const caption = el("p", { class: "atlas-caption" });
  const legend = el("ul", { class: "map-legend atlas-legend" }, page.map.legend.map((item) => el("li", { class: "map-legend__item", attrs: { "data-state": item.state } }, [
    el("span", { class: "map-legend__sample map-legend__sample--" + item.kind, attrs: { "aria-hidden": "true" } }),
    item.text,
  ])));
  const labelsNote = sentence("p", page.map.labels, decimals, "note atlas-labels-note");
  const figure = el("figure", { class: "atlas-figure" }, [
    el("div", { class: "atlas-sticky" }, [mapHeading, frame, caption, legend, labelsNote]),
  ]);

  const filters = el("div", { class: "choice-row atlas-filters", attrs: { role: "group", "aria-label": page.filter_label } });
  const filterButtons = page.filters.map((filter) => {
    const button = el("button", { class: "choice", text: filter.label, attrs: { type: "button", "aria-pressed": "false", "data-segment": filter.id } });
    button.addEventListener("click", () => setSegment(filter.id));
    filters.appendChild(button);
    return button;
  });
  const message = el("p", { class: "state-message atlas-message", attrs: { hidden: "" } });
  const body = el("div", { class: "atlas-body" });
  const side = el("div", { class: "atlas-side" }, [filters, message, body]);
  // The source follows the column: under 1100px a phone reads the map, then
  // the list, then where the lines and figures come from.
  const source = sentence("p", page.map.source, decimals, "source-line atlas-source");
  const layout = el("div", { class: "atlas" }, [figure, side, source]);
  root.appendChild(layout);

  sections = buildSections(VIEW, withBuilders(page.sections, {
    table: (inner) => inner.appendChild(el("div", { class: "block" }, [routeTable(atlas, decimals)])),
    method: (inner) => inner.appendChild(el("div", { class: "block" }, page.method.map((p) => sentence("p", p, decimals, "prose")))),
  }), decimals, route);
  root.appendChild(sections.node);

  view = {
    atlas, page, decimals, byId, filters, filterButtons, body, message, figure, layout, mapHeading, caption, legend, labelsNote,
    map: null,
    baseTitle: document.title,
    pushed: false,
    hovered: null,
    state: { route: null, segment: "all" },
    // The longest bar is the highest TCE among the rows that carry one.
    top: Math.max(...atlas.items.filter(hasBar).map((item) => item.tce_usd_day)),
  };
  view.map = atlasMap(frame, data.map.land, data.map.atlas, atlas.items, atlas.clusters, page.map, decimals, {
    select: (id) => pick(id),
    hover: (id, sharing) => hover(id, sharing),
    // The key to the labels says what they carry, so it shows only while they carry it.
    labels: (mode) => { labelsNote.hidden = mode !== "figures"; },
  });

  // One listener for the page's life: it acts only while this view is on screen with a route open.
  if (!escapeBound) {
    document.addEventListener("keydown", onEscape);
    escapeBound = true;
  }
  apply(route.params || {}, { firstLoad: true });
  return title;
}

export function update(root, route) {
  if (sections) sections.update(route);
  if (view && view.layout.isConnected) apply(route.params || {}, { firstLoad: false });
}

/* ------------------------------------------------------------- state --- */

function apply(params, { firstLoad }) {
  const { page, byId } = view;
  const asked = params.route || null;
  const item = asked ? byId.get(asked) || null : null;
  let segment = page.filters.some((filter) => filter.id === params.segment) ? params.segment : "all";
  // A route outside the segment clears the segment: the route asked for is shown.
  if (item && segment !== "all" && item.segment !== segment) segment = "all";
  const before = view.state.route;
  view.state = { route: item ? item.id : null, segment };
  if (!item) view.pushed = false;

  // The address says what the page shows: an unknown route or segment leaves it.
  const wanted = { ...params, route: item ? item.id : null, segment: segment === "all" ? null : segment };
  if (router.href(VIEW, wanted) !== router.href(VIEW, params)) router.replaceState(VIEW, wanted);
  view.message.hidden = !(asked && !item);
  view.message.textContent = asked && !item ? page.list.unknown.replace("%s", asked) : "";

  for (const button of view.filterButtons) button.setAttribute("aria-pressed", button.getAttribute("data-segment") === segment ? "true" : "false");
  view.filters.hidden = Boolean(item);
  view.map.show({ filter: segment, selected: view.state.route, focus: null });
  view.mapHeading.textContent = item ? item.map_title : page.map.title;
  view.legend.setAttribute("data-state", item ? "route" : "list");
  document.title = item ? item.label + ", " + view.baseTitle : view.baseTitle;
  writeCaption();

  if (item) {
    showPanel(item);
    if (!firstLoad && before !== item.id) {
      bringIntoView();
      const heading = view.body.querySelector(".atlas-panel__title");
      if (heading) heading.focus({ preventScroll: true });
    }
  } else {
    showList(segment);
    if (!firstLoad && before) {
      const row = view.body.querySelector('.atlas-row[data-item="' + before + '"]');
      if (row) row.focus({ preventScroll: false });
    }
  }
  if (asked && !item) announce(view.message.textContent);
}

/* A route chosen in the page. From the list it is a history entry, as a row's
 * link makes one; from one route to another it replaces the entry. */
function pick(id) {
  const params = { ...(router.current().params || {}), route: id };
  if (view.state.route) {
    router.replaceState(VIEW, params);
    apply(router.current().params || {}, { firstLoad: false });
    return;
  }
  view.pushed = true;
  router.go(VIEW, params);
}

/* Back to the list: the browser's own Back when the route was opened from
 * the page, so history does not grow; the entry rewritten after a deep link. */
function back() {
  if (view.pushed) {
    view.pushed = false;
    window.history.back();
    return;
  }
  const params = { ...(router.current().params || {}) };
  delete params.route;
  router.replaceState(VIEW, params);
  apply(router.current().params || {}, { firstLoad: false });
}

/* Escape closes the route open, from anywhere on the page but a field. */
function onEscape(event) {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  if (!view || !view.layout.isConnected || !view.state.route) return;
  const target = event.target;
  if (target && target.closest && target.closest("input, select, textarea, [contenteditable]")) return;
  event.preventDefault();
  back();
}

function setSegment(id) {
  const params = { ...(router.current().params || {}), segment: id === "all" ? null : id };
  router.replaceState(VIEW, params);
  apply(router.current().params || {}, { firstLoad: false });
  const filter = view.page.filters.find((f) => f.id === id);
  if (filter) announce(segmentsText(filter.announce, view.decimals));
}

/* The map's top on screen after a choice made below it: on a phone the list
 * runs far under the map, and on a wide screen the route's heading is at the
 * top of the column. Instant, never smooth. */
function bringIntoView() {
  const box = view.layout.getBoundingClientRect();
  if (box.top < 0 || box.top > window.innerHeight) view.layout.scrollIntoView({ block: "start" });
}

function announce(words) {
  const status = document.querySelector("#view-status");
  if (status) status.textContent = words;
}

function routeHref(id) {
  return router.href(VIEW, { ...(router.current().params || {}), route: id });
}

/* ---------------------------------------------------- the line under the map --- */

/* What the pointer is on, else the route picked, else how to start. */
function hover(id, sharing) {
  view.hovered = id ? { id, sharing: sharing || [] } : null;
  for (const row of view.body.querySelectorAll(".atlas-row[data-item]")) row.classList.toggle("is-hover", row.getAttribute("data-item") === id);
  writeCaption();
}

function writeCaption() {
  const { caption, page, decimals, byId } = view;
  clear(caption);
  const shown = view.hovered ? byId.get(view.hovered.id) : view.state.route ? byId.get(view.state.route) : null;
  if (!shown) {
    caption.textContent = page.map.idle;
    return;
  }
  appendSegments(caption, shown.readout, decimals);
  const sharing = view.hovered ? view.hovered.sharing.map((id) => byId.get(id)).filter(Boolean) : [];
  if (sharing.length) {
    caption.appendChild(document.createTextNode(" "));
    caption.appendChild(el("span", { class: "atlas-caption__same", text: page.map.same + listWords(sharing.map((other) => other.label)) }));
  }
}

/* -------------------------------------------------------------- list --- */

function hasBar(item) {
  return item.kind === "route" && !item.row.last && Number.isFinite(item.tce_usd_day);
}

function showList(segment) {
  const { atlas, page, decimals, body } = view;
  clear(body);
  const list = el("div", { class: "atlas-list" }, [
    el("h2", { class: "visually-hidden", text: page.list.heading }),
    sentence("p", page.list.caption, decimals, "source-line atlas-list__caption"),
  ]);
  for (const group of page.groups) {
    const rows = atlas.items
      .filter((item) => (item.kind === "study" ? group.id === "study" : item.segment === group.id && item.kind !== "study"))
      .filter((item) => segment === "all" || item.segment === segment)
      // Highest first; a row that is not a TCE like the others (S4A's trip) is pinned last, outside the order.
      .sort((a, b) => Number(a.row.last) - Number(b.row.last) || (b.tce_usd_day || 0) - (a.tce_usd_day || 0));
    if (!rows.length) continue;
    const head = group.id === "study" && page.list.study_head ? page.list.study_head : page.list.head;
    list.appendChild(el("h3", { class: "atlas-group", text: group.name }));
    list.appendChild(el("div", { class: "atlas-row atlas-row--head", attrs: { "aria-hidden": "true" } }, [
      el("span", { class: "atlas-row__route", text: head.route }),
      el("span", { class: "atlas-row__tce", text: head.tce }),
      el("span", { class: "atlas-row__days", text: head.days }),
    ]));
    list.appendChild(el("ul", { class: "atlas-rows" }, rows.map((item) => el("li", {}, [listRow(item, head)]))));
  }
  body.appendChild(list);
  body.appendChild(summaryFacts(page.summary, decimals));
}

function listRow(item, head) {
  const { decimals } = view;
  const row = el("a", { class: "atlas-row", attrs: { href: routeHref(item.id), "data-item": item.id } }, [
    el("span", { class: "atlas-row__route" }, [
      el("span", { class: "atlas-row__code", text: item.label }),
      el("span", { class: "atlas-row__ports", text: item.ship + ", " + item.ports }),
      item.row.note.length ? appendSegments(el("span", { class: "atlas-row__note" }), item.row.note, decimals) : null,
      // The other ways it could sail, after the dotted sample the map draws them with.
      item.row.also ? el("span", { class: "atlas-row__also" }, [
        el("span", { class: "atlas-row__swatch", attrs: { "aria-hidden": "true" } }),
        item.row.also,
      ]) : null,
    ]),
    el("span", { class: "atlas-row__tce" }, [
      el("span", { class: "visually-hidden", text: head.tce + " " }),
      appendSegments(el("span", { class: "atlas-row__figure" }), item.row.tce, decimals),
      item.row.qualifier ? el("span", { class: "atlas-row__qualifier", text: item.row.qualifier }) : null,
    ]),
    el("span", { class: "atlas-row__days" }, [
      el("span", { class: "visually-hidden", text: head.days + " " }),
      appendSegments(el("span", { class: "atlas-row__figure" }), item.row.days, decimals),
    ]),
    hasBar(item) ? tceBar(item) : null,
  ]);
  row.addEventListener("click", () => { view.pushed = true; });
  row.addEventListener("pointerenter", () => view.map.hover(item.id));
  row.addEventListener("pointerleave", () => view.map.hover(null));
  row.addEventListener("focus", () => view.map.hover(item.id));
  row.addEventListener("blur", () => view.map.hover(null));
  return row;
}

/* A thin bar under the row, its TCE as a share of the highest in the list, on
 * one linear scale for every route. The figure is printed beside it, so the
 * bar is hidden from a screen reader. */
function tceBar(item) {
  const share = item.tce_usd_day / view.top;
  const fill = el("span", { class: "atlas-row__bar-fill atlas-row__bar-fill--" + item.basis });
  const rest = el("span", { class: "atlas-row__bar-rest" });
  fill.style.flexGrow = String(share);
  rest.style.flexGrow = String(1 - share);
  return el("span", { class: "atlas-row__bar", attrs: { "aria-hidden": "true" } }, [fill, rest]);
}

/* ------------------------------------------------------------- panel --- */

function showPanel(item) {
  const { page, decimals, body, byId } = view;
  clear(body);
  const backButton = el("button", { class: "atlas-back", text: page.panel.back, attrs: { type: "button" } });
  backButton.addEventListener("click", back);
  const panel = el("div", { class: "atlas-panel", attrs: { "data-item": item.id } }, [
    backButton,
    el("h2", { class: "atlas-panel__title", text: item.heading, attrs: { tabindex: "-1" } }),
    appendSegments(el("p", { class: "atlas-panel__sub" }), item.subhead, decimals),
  ]);

  // The routes whose line runs with this one, each one step away.
  const same = (item.same_water || []).map((id) => byId.get(id)).filter(Boolean);
  if (same.length) {
    const line = el("p", { class: "atlas-panel__same" }, [page.panel.same]);
    same.forEach((other, index) => {
      if (index) line.appendChild(document.createTextNode(index === same.length - 1 ? " and " : ", "));
      const link = el("a", { class: "text-link", text: other.label, attrs: { href: routeHref(other.id), "data-item": other.id } });
      link.addEventListener("click", (event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        pick(other.id);
      });
      line.appendChild(link);
    });
    line.appendChild(document.createTextNode(page.panel.same_after));
    panel.appendChild(line);
  }

  panel.appendChild(factList(item, item.facts.filter(isHeadline)));
  const own = new Set([item.legs.laden, item.legs.ballast]);
  if (item.alternatives.length) {
    panel.appendChild(el("h3", { class: "atlas-panel__heading", text: page.panel.alternatives }));
    const list = el("ul", { class: "atlas-alts" });
    for (const alt of item.alternatives) {
      // The base, listed first, is the routing priced above on the alternatives' own basis: every change is set against it.
      const entry = el("li", { class: "atlas-alt-entry" + (alt.kind === "base" ? " atlas-alt-entry--base" : ""), attrs: { "data-alt": alt.id } }, [
        el("p", { class: "atlas-alt-entry__name", text: alt.name }),
        appendSegments(el("p", { class: "atlas-alt-entry__text" }), alt.text, decimals),
      ]);
      if (alt.legs.some((key) => !own.has(key))) {
        // A toggle draws the routing at full weight on the map, so it works by keyboard and touch as well as by pointer.
        const toggle = el("button", { class: "atlas-alt-entry__show", text: page.panel.show, attrs: { type: "button", "aria-pressed": "false" } });
        toggle.addEventListener("click", () => {
          const on = toggle.getAttribute("aria-pressed") !== "true";
          for (const other of list.querySelectorAll(".atlas-alt-entry__show")) other.setAttribute("aria-pressed", "false");
          toggle.setAttribute("aria-pressed", on ? "true" : "false");
          view.map.show({ focus: on ? alt.id : null });
        });
        entry.appendChild(toggle);
      }
      list.appendChild(entry);
    }
    panel.appendChild(list);
  }
  // The calculator first among the links: the step from reading a route to pricing it.
  const calculator = item.links.filter((link) => link.view === "calculator");
  const others = item.links.filter((link) => link.view !== "calculator");
  if (calculator.length) panel.appendChild(linkList(calculator, "atlas-links atlas-links--first"));
  const rest = item.facts.filter((fact, index) => !isHeadline(fact, index));
  if (rest.length) panel.appendChild(factList(item, rest));
  if (others.length) {
    panel.appendChild(el("h3", { class: "atlas-panel__heading", text: page.panel.links }));
    panel.appendChild(linkList(others, "atlas-links"));
  }
  panel.appendChild(sentence("p", item.source, decimals, "source-line"));
  body.appendChild(panel);
}

function factList(item, facts) {
  const { page, decimals } = view;
  const list = el("dl", { class: "atlas-facts" });
  for (const fact of facts) {
    list.appendChild(el("div", { class: "atlas-fact", attrs: { "data-fact": fact.id } }, [
      el("dt", { class: "atlas-fact__label", text: fact.label }),
      appendSegments(el("dd", { class: "atlas-fact__value" }), fact.value, decimals),
      fact.id === "days" && item.split ? daysBar(item.split, page.panel.split) : null,
      fact.note.length ? appendSegments(el("dd", { class: "atlas-fact__note" }), fact.note, decimals) : null,
    ]));
  }
  return list;
}

function linkList(links, className) {
  return el("ul", { class: className }, links.map((link) => el("li", {}, [
    el("a", { class: "text-link", text: link.text, attrs: { href: router.href(link.view, link.params) } }),
  ])));
}

/* The round voyage as one bar: ballast, laden, port and waiting, in proportion.
 * Its values are in the sentence under it, so the bar is hidden from a screen reader. */
function daysBar(split, words) {
  const bar = el("dd", { class: "atlas-days", attrs: { "aria-hidden": "true" } });
  for (const part of ["ballast", "laden", "port"]) {
    const piece = el("span", { class: "atlas-days__part atlas-days__part--" + part, attrs: { title: words[part] } });
    piece.style.flexGrow = String(split[part]);
    bar.appendChild(piece);
  }
  return bar;
}

/* ----------------------------------------------------------- at a glance --- */

/* Four facts after the list, each a way into its route. */
function summaryFacts(summary, decimals) {
  const list = el("dl", { class: "atlas-glance" });
  for (const fact of summary.items) {
    const link = appendSegments(el("a", { class: "atlas-glance__value", attrs: { href: routeHref(fact.item), "data-item": fact.item } }), fact.value, decimals);
    link.addEventListener("click", () => { view.pushed = true; });
    list.appendChild(el("div", { class: "atlas-glance__fact", attrs: { "data-fact": fact.item } }, [
      el("dt", { class: "atlas-glance__label", text: fact.label }),
      el("dd", { class: "atlas-glance__link" }, [link]),
      appendSegments(el("dd", { class: "atlas-glance__note" }), fact.note, decimals),
    ]));
  }
  return el("section", { class: "atlas-glance-block", attrs: { "aria-labelledby": "atlas-glance-title" } }, [
    el("h2", { class: "atlas-group", id: "atlas-glance-title", text: summary.heading }),
    list,
  ]);
}

/* ------------------------------------------------------------- table --- */

function routeTable(atlas, decimals) {
  const columns = atlas.page.table.columns;
  const keys = ["tce", "days", "laden_nm", "freight", "breakeven", "costs"];
  const head = el("tr", {}, [
    el("th", { text: columns.route, attrs: { scope: "col" } }),
    ...keys.map((key) => el("th", { class: "col-num", text: columns[key], attrs: { scope: "col", "data-short": columns[key] } })),
  ]);
  const rows = el("tbody");
  for (const item of atlas.items.filter((entry) => entry.kind === "route")) {
    rows.appendChild(el("tr", { attrs: { "data-item": item.id } }, [
      el("th", { attrs: { scope: "row" } }, [el("span", { class: "row-code", text: item.label }), el("span", { class: "row-name", text: item.ports })]),
      ...keys.map((key) => appendSegments(el("td", { class: "num" }), item.table[key], decimals)),
    ]));
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), rows]);
  return scrollTable([appendSegments(el("span"), atlas.page.table.caption, decimals)], table);
}
