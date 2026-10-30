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
 * Below that the stylesheet sets the map, the line under it, the filters and
 * the list first, and the legend after them; the page keeps the legend with
 * the map, where a screen reader reads it. While the map is too narrow for
 * labels, its heading and the line under it promise none and send the
 * reader to the list; the heading promises a figure a day only while the
 * labels carry one.
 *
 * The line under the map says what the pointer is on, or the route picked:
 * one line in the page, never a box over the lines it describes, and the same
 * line a phone shows. It is not a live region: a choice moves focus to the
 * route's heading instead.
 *
 * The address keeps the choice: #/map?route=TD3C&segment=dirty. Opening a
 * route from the list is a history entry, marked as opened over the list in
 * the entry's own state (window.history.state, which Back and Forward bring
 * back with the entry); moving from one route to another replaces it and
 * keeps the mark, so Back always closes the route in one step: "Back to the
 * list" and Escape go back in history from a marked entry and rewrite any
 * other. A plain click on a row, a fact under the list or a link to another
 * route is taken here, so the route opens with the sections open; a click
 * with a modifier key follows the link's own address, which is written afresh
 * as the pointer or focus arrives. Closing a route, by Back to the list,
 * Escape or the browser's Back (which return to the list's entry, marked when
 * the route was opened over it), leaves the sections as the page has them; an
 * address typed or pasted that names its own sections is taken as it is. The
 * segment is not an entry, and a filter press is announced in the page's
 * status line. A route outside the segment clears the segment, and so does
 * closing a route the segment would not list.
 *
 * Focus: on a choice made in the page, to the route's heading, the map first
 * scrolled into view where it is off the screen and the heading then where it
 * lies below the screen's foot; on the way back, to the route's row, or to
 * the pressed filter where no row can take it. Never on the first load, which
 * ui.js handles. Below 1100px a routing shown from its toggle brings the map
 * into view, and focus stays on the toggle; one pressed by a click on the map
 * itself, which is in view, moves nothing.
 *
 * Every figure is from data/atlas.json and every line from data/map.json.
 * Nothing is computed here but where things go, the length of each row's
 * bar, a share of the highest TCE in the list, and which of the legend's
 * lines the map draws.
 *
 * Numeric literals: none.
 */

import * as router from "./router.js";
import { el, clear, appendSegments, sentence, scrollTable } from "./dom.js";
import { viewHead } from "./figure.js";
import { buildSections, withBuilders } from "./sections.js";
import { openParams } from "./state.js";
import { atlasMap } from "./map.js";
import { segmentText, segmentsText, listWords } from "./format.js";

export const artifacts = Object.freeze(["atlas", "map"]);

const VIEW = "map";
/* The facts read first in a route's detail, with its first fact whatever it is
 * (the study's freight); the others follow its alternatives. */
const HEADLINE_FACTS = new Set(["tce", "round_trip", "days", "distance"]);
const isHeadline = (fact, index) => index === 0 || HEADLINE_FACTS.has(fact.id);
/* The mark a route's history entry carries when it was opened over the list,
 * and the one the list's own entry takes then, so a return to it by Back,
 * Escape or the browser's Back is told from an address typed or pasted. */
const OPENED_OVER_LIST = Object.freeze({ openedOverList: true });
const LIST_UNDER_ROUTE = Object.freeze({ listUnderRoute: true });
const marked = (key) => Boolean(window.history.state && window.history.state[key]);
/* A click the page takes; one with a modifier key opens the link's own
 * address as the browser does, in a new tab or window. */
const plainClick = (event) => !(event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);
/* The routings the map draws for a route: those on a leg that is not the
 * route's own, its base being the route's line already. */
const drawnRoutings = (item) => {
  const own = new Set([item.legs.laden, item.legs.ballast]);
  return item.alternatives.filter((alt) => alt.legs.some((key) => !own.has(key)));
};
let sections = null;
let view = null;
let escapeBound = false;

export function render(root, data, route) {
  // The map of an earlier visit stops listening, so it is not kept alive by the page's listeners.
  if (view && view.map) view.map.stop();
  const atlas = data.atlas;
  const page = atlas.page;
  const decimals = atlas.conventions.decimals;
  const title = viewHead(root, page.title, page.takeaway, decimals);
  const byId = new Map(atlas.items.map((item) => [item.id, item]));

  const frame = el("div", { class: "atlas-frame" });
  const mapHeading = el("h2", { class: "block__heading atlas-map-heading", text: page.map.title });
  const caption = el("p", { class: "atlas-caption" });
  const legend = el("ul", { class: "map-legend atlas-legend" }, page.map.legend.map((item) => el("li", { class: "map-legend__item", attrs: { "data-state": item.state, "data-kind": item.kind } }, [
    el("span", { class: "map-legend__sample map-legend__sample--" + item.kind, attrs: { "aria-hidden": "true" } }),
    item.text,
  ])));
  const labelsNote = sentence("p", page.map.labels, decimals, "note atlas-labels-note");
  const sticky = el("div", { class: "atlas-sticky" }, [mapHeading, frame, caption, legend, labelsNote]);
  const figure = el("figure", { class: "atlas-figure" }, [sticky]);

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
  // the list, then the legend and where the lines and figures come from.
  const source = sentence("p", page.map.source, decimals, "source-line atlas-source");
  const layout = el("div", { class: "atlas" }, [figure, side, source]);
  root.appendChild(layout);

  sections = buildSections(VIEW, withBuilders(page.sections, {
    table: (inner) => inner.appendChild(el("div", { class: "block" }, [routeTable(atlas, decimals)])),
    method: (inner) => inner.appendChild(el("div", { class: "block" }, page.method.map((p) => sentence("p", p, decimals, "prose")))),
  }), decimals, route);
  root.appendChild(sections.node);

  view = {
    atlas, page, decimals, byId, geo: data.map.atlas, filters, filterButtons, body, message, layout, sticky, frame, mapHeading, caption, legend, labelsNote,
    map: null,
    baseTitle: document.title,
    // Back asked of the browser and not yet arrived, so a second press waits for it.
    closing: false,
    // What the map's labels carried at its last drawing with nothing picked: "figures", "codes" or "none".
    labels: "figures",
    hovered: null,
    // Each routing's toggle on the panel shown, by the routing's id: press({ fromMap }).
    toggles: new Map(),
    state: { route: null, segment: "all" },
    // The longest bar is the highest TCE among the rows that carry one.
    top: Math.max(...atlas.items.filter(hasBar).map((item) => item.tce_usd_day)),
  };
  view.map = atlasMap(frame, data.map.land, data.map.atlas, atlas.items, atlas.clusters, page.map, decimals, {
    select: (id) => pick(id),
    // A click on a routing of the route picked presses that routing's toggle, so the button and the map stay in
    // step; the map is in view already, so nothing scrolls and focus stays where it is.
    alternative: (id) => {
      const press = view.toggles.get(id);
      if (press) press({ fromMap: true });
    },
    hover: (id, sharing) => hover(id, sharing),
    labels: (mode) => labelsDrawn(mode),
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
  let next = route;
  const asked = route.params || {};
  // A route closed, by Back to the list, Escape or the browser's Back, which
  // land on the list's own entry, or by an address naming no sections, such as
  // the Map in the navigation: the sections stay as the page has them, and the
  // list's address says so. An address typed or pasted that names its own
  // sections is taken as it is (sections.update below).
  const returned = marked("listUnderRoute") || !asked.open;
  if (sections && view && view.layout.isConnected && view.state.route && !asked.route && returned) {
    const params = openParams(sections.open(), asked);
    if (router.href(VIEW, params) !== router.href(VIEW, asked)) {
      router.replaceState(VIEW, params);
      next = router.current();
    }
  }
  if (sections) sections.update(next);
  if (view && view.layout.isConnected) apply(next.params || {}, { firstLoad: false });
}

/* ------------------------------------------------------------- state --- */

function apply(params, { firstLoad }) {
  const { page, byId } = view;
  const asked = params.route || null;
  const item = asked ? byId.get(asked) || null : null;
  const before = view.state.route;
  // The route closed now, whose row takes focus back.
  const closed = !item && !firstLoad && before ? byId.get(before) : null;
  let segment = page.filters.some((filter) => filter.id === params.segment) ? params.segment : "all";
  // A route outside the segment clears the segment: the route asked for is
  // shown. So does closing one the segment would not list: its row is there
  // to take focus.
  const outside = item || closed;
  if (outside && segment !== "all" && outside.segment !== segment) segment = "all";
  view.state = { route: item ? item.id : null, segment };
  view.closing = false;

  // The address says what the page shows: an unknown route or segment leaves it.
  const wanted = { ...params, route: item ? item.id : null, segment: segment === "all" ? null : segment };
  if (router.href(VIEW, wanted) !== router.href(VIEW, params)) router.replaceState(VIEW, wanted);
  view.message.hidden = !(asked && !item);
  view.message.textContent = asked && !item ? page.list.unknown.replace("%s", asked) : "";

  for (const button of view.filterButtons) button.setAttribute("aria-pressed", button.getAttribute("data-segment") === segment ? "true" : "false");
  view.filters.hidden = Boolean(item);
  view.map.show({ filter: segment, selected: view.state.route, focus: null });
  writeHeading();
  showLegend(item, segment);
  document.title = item ? item.label + ", " + view.baseTitle : view.baseTitle;
  writeCaption();

  if (item) {
    showPanel(item);
    if (!firstLoad && before !== item.id) focusHeading();
  } else {
    showList(segment);
    if (closed) focusRow(closed.id);
  }
  if (asked && !item) announce(view.message.textContent);
}

/* A route chosen in the page, with the rest of the address (the segment and
 * the sections open). From the list it adds a history entry, marked as opened
 * over the list; from one route to another it replaces the entry, which keeps
 * its mark. */
function pick(id) {
  const params = { ...(router.current().params || {}), route: id };
  if (view.state.route) {
    router.replaceState(VIEW, params);
    apply(router.current().params || {}, { firstLoad: false });
    return;
  }
  router.mark(LIST_UNDER_ROUTE);
  router.go(VIEW, params, OPENED_OVER_LIST);
}

/* Back to the list: the browser's own Back from an entry opened over the
 * list, so history does not grow and the list's entry comes back; any other
 * entry, a deep link, is rewritten. */
function back() {
  if (view.closing) return;
  if (marked("openedOverList")) {
    view.closing = true;
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

/* Focus to the heading of the route chosen, with the map in view above it.
 * On a short screen the heading can then lie below the screen's foot, and is
 * scrolled up to it, so what has focus is seen. */
function focusHeading() {
  bringIntoView();
  const heading = view.body.querySelector(".atlas-panel__title");
  if (!heading) return;
  heading.focus({ preventScroll: true });
  if (heading.getBoundingClientRect().bottom > window.innerHeight) heading.scrollIntoView({ block: "end" });
}

/* Focus back to the row of the route closed, or to the pressed filter where
 * no row can take it. */
function focusRow(id) {
  const row = view.body.querySelector('.atlas-row[data-item="' + id + '"]');
  const target = row || view.filterButtons.find((button) => button.getAttribute("aria-pressed") === "true");
  if (target) target.focus({ preventScroll: false });
}

/* Below 1100px the map does not stay on screen, so a routing shown from its
 * toggle down the column would change a map out of sight: the map is brought
 * into view, at once, and focus stays on the toggle. */
function showMap(toggle) {
  if (getComputedStyle(view.sticky).position === "sticky") return;
  const box = view.frame.getBoundingClientRect();
  // Within a pixel, as the page scrolls by whole pixels and the map may not sit on one.
  if (box.top > -1 && box.bottom < window.innerHeight + 1) return;
  view.frame.scrollIntoView({ block: "nearest" });
  toggle.focus({ preventScroll: true });
}

function announce(words) {
  const status = document.querySelector("#view-status");
  if (status) status.textContent = words;
}

function routeHref(id) {
  return router.href(VIEW, { ...(router.current().params || {}), route: id });
}

/* A link into a route, from a row, a fact under the list or another route:
 * a plain click is taken here (pick), so the route opens with the address's
 * segment and sections; the href, written afresh as the pointer or focus
 * arrives, serves a click with a modifier key and a copied link. */
function intoRoute(link, id) {
  link.addEventListener("click", (event) => {
    if (!plainClick(event)) return;
    event.preventDefault();
    pick(id);
  });
  const fresh = () => link.setAttribute("href", routeHref(id));
  link.addEventListener("pointerenter", fresh);
  link.addEventListener("focus", fresh);
  return link;
}

/* ---------------------------------------------------- the line under the map --- */

/* What the map's labels carry decides the key to them, which shows only while
 * they carry figures, and the words over and under the map. */
function labelsDrawn(mode) {
  view.labelsNote.hidden = mode !== "figures";
  // With a route picked the labels are its own; the list's mode is kept for when it closes.
  if (mode !== "route") view.labels = mode;
  writeHeading();
  writeCaption();
}

/* The heading over the map: the route picked, else what the map shows, with
 * a figure a day only while the labels carry one. */
function writeHeading() {
  const { page, byId, mapHeading } = view;
  const item = view.state.route ? byId.get(view.state.route) : null;
  mapHeading.textContent = item ? item.map_title : view.labels === "figures" ? page.map.title : page.map.title_narrow;
}

/* What the pointer is on, else the route picked, else how to start: on a map
 * too narrow for labels or a tap, from the list below it. */
function hover(id, sharing) {
  view.hovered = id ? { id, sharing: sharing || [] } : null;
  for (const row of view.body.querySelectorAll(".atlas-row[data-item]")) row.classList.toggle("is-hover", row.getAttribute("data-item") === id);
  writeCaption();
}

function writeCaption() {
  const { caption, page, decimals, byId } = view;
  clear(caption);
  // Two lines are kept for it where a pointer can change it; on a map too narrow for labels and taps it changes only with a pick.
  caption.classList.toggle("atlas-caption--still", view.labels === "none");
  const shown = view.hovered ? byId.get(view.hovered.id) : view.state.route ? byId.get(view.state.route) : null;
  if (!shown) {
    caption.textContent = view.labels === "none" ? page.map.idle_narrow : page.map.idle;
    return;
  }
  appendSegments(caption, shown.readout, decimals);
  const sharing = view.hovered ? view.hovered.sharing.map((id) => byId.get(id)).filter(Boolean) : [];
  if (sharing.length) {
    caption.appendChild(document.createTextNode(" "));
    caption.appendChild(el("span", { class: "atlas-caption__same", text: page.map.same + listWords(sharing.map((other) => other.label)) }));
  }
}

/* The legend names only the lines the map draws now. With a route picked:
 * its ballast leg, its stretches inside an emission control area, its other
 * routings and the rings where its lines leave across the Pacific, each where
 * data/map.json has one; with none, the other routings and the rings of the
 * routes the segment shows. A sample of another kind follows its state. */
function showLegend(item, segment) {
  const { geo, atlas } = view;
  const has = (keys, what) => keys.some((key) => key && geo.legs[key][what].length);
  let draws;
  if (item) {
    const routings = drawnRoutings(item);
    draws = {
      "picked-ballast": Boolean(item.legs.ballast),
      eca: has([item.legs.laden, item.legs.ballast], "eca"),
      "alternative-picked": routings.length > 0,
      edge: has([item.legs.laden, item.legs.ballast, ...routings.flatMap((alt) => alt.legs)], "edges"),
    };
  } else {
    const shown = atlas.items.filter((entry) => segment === "all" || entry.segment === segment);
    draws = {
      alternative: shown.some((entry) => drawnRoutings(entry).length > 0),
      edge: has(shown.map((entry) => entry.legs.laden), "edges"),
    };
  }
  const state = item ? "route" : "list";
  for (const sample of view.legend.children) {
    const own = sample.getAttribute("data-state") === state || sample.getAttribute("data-state") === "both";
    sample.hidden = !own || draws[sample.getAttribute("data-kind")] === false;
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

/* One link a route: its code, ship and ports, its TCE and days, then, across
 * the row, its note (a date, how S4A's days are counted) and its other
 * routings, one line each with what it changes, after the dotted sample the
 * map draws them with. */
function listRow(item, head) {
  const { decimals } = view;
  const row = el("a", { class: "atlas-row", attrs: { href: routeHref(item.id), "data-item": item.id } }, [
    el("span", { class: "atlas-row__route" }, [
      el("span", { class: "atlas-row__code", text: item.label }),
      el("span", { class: "atlas-row__ports", text: item.ship + ", " + item.ports }),
    ]),
    el("span", { class: "atlas-row__tce" }, [
      el("span", { class: "visually-hidden", text: head.tce + " " }),
      rowFigure(item.row.tce, decimals),
      item.row.qualifier ? el("span", { class: "atlas-row__qualifier", text: item.row.qualifier }) : null,
    ]),
    el("span", { class: "atlas-row__days" }, [
      el("span", { class: "visually-hidden", text: head.days + " " }),
      appendSegments(el("span", { class: "atlas-row__figure" }), item.row.days, decimals),
    ]),
    item.row.note.length ? appendSegments(el("span", { class: "atlas-row__note" }), item.row.note, decimals) : null,
    item.row.alts.length ? el("span", { class: "atlas-row__alts" }, item.row.alts.map((line) => appendSegments(el("span", { class: "atlas-row__alt" }, [
      el("span", { class: "atlas-row__swatch", attrs: { "aria-hidden": "true" } }),
    ]), line, decimals))) : null,
    hasBar(item) ? tceBar(item) : null,
  ]);
  intoRoute(row, item.id);
  row.addEventListener("pointerenter", () => view.map.hover(item.id));
  row.addEventListener("pointerleave", () => view.map.hover(null));
  row.addEventListener("focus", () => view.map.hover(item.id));
  row.addEventListener("blur", () => view.map.hover(null));
  return row;
}

/* A row's figure. The Baltic's qualifier is its prefix, read before it ("just
 * under 197,000"), and set in its own span so a narrow row can carry it on
 * the line above the figure, which never breaks. A figure the week did not
 * print keeps its own words, which carry no prefix. */
function rowFigure(segments, decimals) {
  const cell = el("span", { class: "atlas-row__figure" });
  for (const segment of segments) {
    if (segment && typeof segment === "object" && segment.prefix && !segmentText(segment, decimals).missing) {
      cell.appendChild(el("span", { class: "atlas-row__prefix", text: segment.prefix }));
      appendSegments(cell, [{ ...segment, prefix: "" }], decimals);
    } else {
      appendSegments(cell, [segment], decimals);
    }
  }
  return cell;
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

  // The routes whose line runs with this one, each one step away: a short
  // list under the words that name it, every link a full target on its own
  // line of targets, so a tap never lands on the link beside or below it.
  const same = (item.same_water || []).map((id) => byId.get(id)).filter(Boolean);
  if (same.length) {
    const lead = el("p", { class: "atlas-panel__same", id: "atlas-same-water", text: page.panel.same });
    panel.appendChild(lead);
    panel.appendChild(el("ul", { class: "atlas-same", attrs: { "aria-labelledby": lead.id } }, same.map((other) => el("li", {}, [
      intoRoute(el("a", { class: "text-link", text: other.label, attrs: { href: routeHref(other.id), "data-item": other.id } }), other.id),
    ]))));
  }

  panel.appendChild(factList(item, item.facts.filter(isHeadline), "atlas-facts atlas-facts--head"));
  const drawn = new Set(drawnRoutings(item));
  view.toggles = new Map();
  if (item.alternatives.length) {
    panel.appendChild(el("h3", { class: "atlas-panel__heading", text: page.panel.alternatives }));
    const list = el("ul", { class: "atlas-alts" });
    for (const alt of item.alternatives) {
      // The base, listed first, is the routing priced above on the alternatives' own basis: every change is set against it.
      const entry = el("li", { class: "atlas-alt-entry" + (alt.kind === "base" ? " atlas-alt-entry--base" : ""), attrs: { "data-alt": alt.id } }, [
        el("p", { class: "atlas-alt-entry__name", text: alt.name }),
        appendSegments(el("p", { class: "atlas-alt-entry__text" }), alt.text, decimals),
      ]);
      if (drawn.has(alt)) {
        // A toggle draws the routing at full weight on the map, so it works by
        // keyboard and touch as well as by pointer. Each is named for its
        // routing after the words seen, so a list of them reads apart.
        const toggle = el("button", { class: "atlas-alt-entry__show", attrs: { type: "button", "aria-pressed": "false" } }, [
          page.panel.show,
          el("span", { class: "visually-hidden", text: ", " + (alt.short || alt.name) }),
        ]);
        // Pressed from the column, below 1100px, it brings the map into view;
        // pressed from the map, by a click on the routing, nothing moves.
        const press = ({ fromMap }) => {
          const on = toggle.getAttribute("aria-pressed") !== "true";
          for (const other of list.querySelectorAll(".atlas-alt-entry__show")) other.setAttribute("aria-pressed", "false");
          toggle.setAttribute("aria-pressed", on ? "true" : "false");
          view.map.show({ focus: on ? alt.id : null });
          if (on && !fromMap) showMap(toggle);
        };
        toggle.addEventListener("click", () => press({ fromMap: false }));
        view.toggles.set(alt.id, press);
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
  if (rest.length) {
    // Under their own heading, so a reader moving by headings does not find
    // them among the routings; worded for the route ("Hire and costs" on a trip).
    panel.appendChild(el("h3", { class: "atlas-panel__heading", text: item.more }));
    panel.appendChild(factList(item, rest, "atlas-facts"));
  }
  if (others.length) {
    panel.appendChild(el("h3", { class: "atlas-panel__heading", text: page.panel.links }));
    panel.appendChild(linkList(others, "atlas-links"));
  }
  panel.appendChild(sentence("p", item.source, decimals, "source-line"));
  body.appendChild(panel);
}

function factList(item, facts, className) {
  const { page, decimals } = view;
  const list = el("dl", { class: className });
  for (const fact of facts) {
    list.appendChild(el("div", { class: "atlas-fact", attrs: { "data-fact": fact.id } }, [
      el("dt", { class: "atlas-fact__label", text: fact.label }),
      appendSegments(el("dd", { class: "atlas-fact__value" }), leadOut(fact.value), decimals),
      fact.id === "days" && item.split ? daysBar(item.split, page.panel.split) : null,
      fact.note.length ? appendSegments(el("dd", { class: "atlas-fact__note" }), fact.note, decimals) : null,
    ]));
  }
  return list;
}

/* A figure whose prefix carries words before its unit ("just under USD
 * 197,000") keeps only the unit with the figure, which never breaks: the words
 * may take the line above on a narrow screen, or with the text spaced wider. */
function leadOut(segments) {
  return segments.flatMap((segment) => {
    if (!segment || typeof segment !== "object" || !segment.prefix || !Number.isFinite(segment.value)) return [segment];
    const words = segment.prefix.trimEnd().split(" ");
    if (words.length <= 1) return [segment];
    const unit = words.pop();
    return [words.join(" ") + " ", { ...segment, prefix: unit + " " }];
  });
}

/* A route's links. One to another route of this map moves to it as a
 * same-water link does, replacing the entry, so Back still closes in one step. */
function linkList(links, className) {
  return el("ul", { class: className }, links.map((link) => {
    const anchor = el("a", { class: "text-link", text: link.text, attrs: { href: router.href(link.view, link.params) } });
    if (link.view === VIEW && link.params && link.params.route) intoRoute(anchor, link.params.route);
    return el("li", {}, [anchor]);
  }));
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
    const link = intoRoute(appendSegments(el("a", { class: "atlas-glance__value", attrs: { href: routeHref(fact.item), "data-item": fact.item } }), fact.value, decimals), fact.item);
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
      // Each cell's words in one box, so a phone's stacked table wraps them as a sentence, every word kept.
      ...keys.map((key) => el("td", { class: "num" }, [appendSegments(el("span", { class: "atlas-cell" }), item.table[key], decimals)])),
    ]));
  }
  const table = el("table", { class: "table" }, [el("thead", {}, [head]), rows]);
  return scrollTable([appendSegments(el("span"), atlas.page.table.caption, decimals)], table);
}
