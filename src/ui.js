/* ui.js
 *
 * The entry module. It wires the theme, builds the nav from the route table,
 * starts the router, loads what a view needs, and renders the view or a
 * sentence saying why it cannot. The sibling studies' entry module, with this
 * study's seven views.
 *
 * THE ROUTE TABLE IS THE ONLY LIST OF VIEWS. The nav is built from it, the
 * router is told its names, and nothing else in the site names a view. A view
 * is added by adding one entry below and one module; router.js does not
 * change.
 *
 * Numeric literals: none.
 */

import * as router from "./router.js";
import * as state from "./state.js";
import { initTheme } from "./theme.js";
import { el, clear, loadingMessage, failureMessages, renderFailureMessages } from "./dom.js";
import { formatDay } from "./format.js";
import * as overview from "./overview.js";
import * as calculator from "./calculator.js";
import * as routesView from "./routes.js";
import * as detours from "./detours.js";
import * as carbon from "./carbon.js";
import * as paper from "./paper.js";
import * as method from "./method.js";

const SITE_NAME = "Voyage economics and TCE";
const DEFAULT_VIEW = "overview";

/* name: the hash segment. label: the nav text and the document title.
 * module: exports `artifacts`, the state.js names it needs, and
 * render(root, data, route), which returns the element that takes focus. */
const ROUTES = [
  { name: "overview", label: "Overview", loading: "the featured voyage, its bridge from freight to TCE and its map", module: overview },
  { name: "calculator", label: "Calculator", loading: "the calculator's presets, ships and routings", module: calculator },
  { name: "routes", label: "Routes", loading: "the route library and the voyage costs of every route", module: routesView },
  { name: "detours", label: "Detours", loading: "Suez against the Cape, and the Hormuz scenarios", module: detours },
  { name: "carbon", label: "Carbon", loading: "the EU ETS cost of three voyages", module: carbon },
  { name: "paper", label: "Paper", loading: "physical TCEs against the FFA", module: paper },
  { name: "method", label: "Method and data", loading: "the conventions, the validation and every source", module: method },
];

const byName = new Map(ROUTES.map((route) => [route.name, route]));
const viewRoot = document.querySelector("#view");
let renderToken = 0;
let rendering = false;

function buildNav() {
  const list = document.querySelector("#site-nav-list");
  if (!list) return;
  clear(list);
  for (const route of ROUTES) {
    list.appendChild(el("li", {}, [
      el("a", { class: "site-nav__link", text: route.label, attrs: { href: router.href(route.name), "data-view": route.name } }),
    ]));
  }
}

function markCurrent(viewName) {
  for (const link of document.querySelectorAll(".site-nav__link")) {
    if (link.getAttribute("data-view") === viewName) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

function setTitle(label) {
  document.title = label + ", " + SITE_NAME;
}

/* The footer: the author, where the data come from, and the date of the
 * latest input, read from the manifest. A footer that cannot load its
 * manifest keeps the author's line and says nothing it does not know. */
async function buildFooter() {
  const footer = document.querySelector("#site-footer");
  if (!footer) return;
  const result = await state.loadAll(["manifest"]);
  if (!result.ok) return;
  const manifest = result.data.manifest;
  footer.appendChild(el("p", {}, [manifest.footer.sources]));
  footer.appendChild(el("p", {}, [
    manifest.footer.updated_words + " " + formatDay(manifest.footer.latest_input) + ". ",
    el("a", { class: "text-link", text: manifest.footer.method_words, attrs: { href: router.href("method") } }),
    ".",
  ]));
}

/* Move focus to the new view's h1 on a route change, never on first load,
 * where it would scroll past the skip link. */
function focusTitle(target, isFirstLoad) {
  if (isFirstLoad || !target) return;
  target.focus({ preventScroll: false });
}

/* An address that names no view: what happened, which address, what to do,
 * with links only to views that exist. */
function renderUnknown(route, isFirstLoad) {
  markCurrent(null);
  setTitle("No view at this address");
  clear(viewRoot);
  const title = el("h1", { class: "view-title", id: "view-title", text: "There is no view at this address.", attrs: { tabindex: "-1" } });
  const typed = route.view === null || route.view === undefined ? "" : String(route.view);
  const names = ROUTES.map((entry) => entry.label + " at " + router.href(entry.name)).join(", ");
  const said = el("p", { class: "state-message" }, [
    "The address ends in " + route.hash + ", and this study has no view at " + JSON.stringify("#/" + typed) + ". ",
    "The views are: " + names + ".",
  ]);
  const todo = el("p", { class: "state-message" }, [
    "Check the address for a typing mistake, or ",
    el("a", { text: "open the overview", attrs: { href: router.href(DEFAULT_VIEW) } }),
    ".",
  ]);
  viewRoot.appendChild(title);
  viewRoot.appendChild(said);
  viewRoot.appendChild(todo);
  focusTitle(title, isFirstLoad);
}

async function renderRoute(route, previous) {
  const isFirstLoad = previous === null;

  // A plain fragment, for example the skip link without script: keep the view.
  if (route.kind === "fragment") {
    if (previous === null) renderRoute(router.parse("", ROUTES.map((entry) => entry.name), DEFAULT_VIEW), null);
    return;
  }
  if (route.kind === "unknown") {
    renderToken += 1;
    renderUnknown(route, isFirstLoad);
    return;
  }

  const entry = byName.get(route.view);
  // Only the view state changed, for example a section opening: the view
  // handles that itself and the page is not rebuilt.
  if (rendering && previous && previous.kind === "route" && previous.view === route.view) return;
  if (previous && previous.kind === "route" && previous.view === route.view && viewRoot.childElementCount && entry.module.update) {
    entry.module.update(viewRoot, route);
    return;
  }

  renderToken += 1;
  const token = renderToken;
  const status = document.getElementById("view-status");
  if (status) status.textContent = "";
  markCurrent(entry.name);
  setTitle(entry.label);
  clear(viewRoot);
  viewRoot.appendChild(loadingMessage(entry.loading));

  rendering = true;
  const result = await state.loadAll(entry.module.artifacts);
  rendering = false;
  if (token !== renderToken) return; // a later route replaced this one
  const address = router.current();
  const current = address.kind === "route" && address.view === route.view ? address : route;

  clear(viewRoot);
  if (!result.ok) {
    const title = el("h1", { class: "view-title", id: "view-title", text: entry.label + " could not be shown.", attrs: { tabindex: "-1" } });
    viewRoot.appendChild(title);
    for (const node of failureMessages(result.failures)) viewRoot.appendChild(node);
    focusTitle(title, isFirstLoad);
    return;
  }
  let target;
  try {
    target = entry.module.render(viewRoot, result.data, current, { firstLoad: isFirstLoad });
  } catch (error) {
    // A file the page accepted but cannot draw: say which, rather than leave
    // a blank page.
    clear(viewRoot);
    target = el("h1", { class: "view-title", id: "view-title", text: entry.label + " could not be shown.", attrs: { tabindex: "-1" } });
    viewRoot.appendChild(target);
    for (const node of renderFailureMessages(entry.module.artifacts, error)) viewRoot.appendChild(node);
  }
  focusTitle(target, isFirstLoad);
}

/* The skip link moves focus to the view's h1 without changing the address, so
 * the route and any open sections survive. */
function wireSkipLink() {
  const link = document.querySelector("[data-skip]");
  if (!link) return;
  link.addEventListener("click", (ev) => {
    const target = document.querySelector("#view-title");
    if (!target) return;
    ev.preventDefault();
    target.focus();
  });
}

// The inline script in index.html says the page could not start unless this
// attribute is set, so it is set before anything else can fail.
document.documentElement.setAttribute("data-started", "");
initTheme();
buildNav();
wireSkipLink();
buildFooter();
router.start(ROUTES.map((route) => route.name), DEFAULT_VIEW, (route, previous) => {
  renderRoute(route, previous);
});
