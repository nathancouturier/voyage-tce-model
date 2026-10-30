/* sections.js
 *
 * The buttons inside a view that open what sits behind its key chart: Method,
 * Assumptions, Data and the view's own panels. The sibling studies' section
 * component, shared here by every view.
 *
 * OPENING. Each section is an h2 holding a full width native button, so Tab
 * reaches it and Enter and Space operate it with no key handler of ours. The
 * button carries aria-expanded and aria-controls; the body it controls is a
 * region labelled by the button, and while closed it is inert, so nothing
 * inside a closed section takes focus or is read. The open set lives in the
 * address, #/routes?open=method,data, written with router.replaceState so
 * opening a section adds no history entry and does not rebuild the page. A
 * section is built the first time it opens, so a closed one costs nothing.
 *
 * The one motion is the body's height, which prefers-reduced-motion cuts to
 * nothing.
 *
 * Numeric literals: none.
 */

import { el, clear, appendSegments, renderFailureMessages } from "./dom.js";
import * as router from "./router.js";
import * as state from "./state.js";

const WORD_SHOW = "Show";
const WORD_HIDE = "Hide";

/** The view's sections in the artifact's order, each with the builder its
 *  id names: [{ id, name, summary }] and { id: build(inner) }. */
export function withBuilders(sections, builders) {
  return sections.filter((section) => builders[section.id]).map((section) => ({ ...section, build: builders[section.id] }));
}

/** Build the sections of a view into one element.
 *
 *    view       the view's name, for the address
 *    items      [{ id, name, summary (segments), build(inner) }]
 *    decimals   the artifact's conventions.decimals, for the summaries
 *    route      the route the view was rendered for
 *
 *  Returns { node, update(route), open() }: update re-reads the open set from
 *  an address that changed under the view, for example a pasted link; open
 *  gives the ids open on the page now, which a view reads before an update
 *  that should not close them. */
export function buildSections(view, items, decimals, route) {
  const rendered = new Map();
  let params = { ...((route && route.params) || {}) };
  const node = el("div", { class: "sections" });

  const openIds = () => [...rendered.keys()].filter((id) => rendered.get(id).button.getAttribute("aria-expanded") === "true");

  for (const item of items) {
    const buttonId = "section-button-" + view + "-" + item.id;
    const bodyId = "section-body-" + view + "-" + item.id;
    const word = el("span", { class: "section__toggle-word", text: WORD_SHOW, attrs: { "aria-hidden": "true" } });
    const button = el("button", {
      class: "section__button",
      id: buttonId,
      attrs: { type: "button", "aria-expanded": "false", "aria-controls": bodyId, "data-section": item.id },
    }, [
      el("span", { class: "section__name", text: item.name }),
      appendSegments(el("span", { class: "section__summary" }), item.summary, decimals),
      word,
    ]);
    const inner = el("div", { class: "section__inner" });
    const body = el("div", {
      class: "section__body",
      id: bodyId,
      attrs: { role: "region", "aria-labelledby": buttonId, "data-open": "false", inert: "" },
    }, [inner]);
    node.appendChild(el("section", { class: "section", id: "section-" + view + "-" + item.id }, [
      el("h2", { class: "section__heading" }, [button]),
      body,
    ]));
    const entry = { item, button, word, body, inner, filled: false };
    rendered.set(item.id, entry);
    button.addEventListener("click", () => {
      setOpen(entry, button.getAttribute("aria-expanded") !== "true");
      // Sections of another group on the same view keep their place in the
      // address: only this group's ids are rewritten.
      const now = router.current().params || params;
      const mine = new Set(rendered.keys());
      const others = String(now.open || "").split(",").filter((id) => id !== "" && !mine.has(id));
      params = state.openParams([...others, ...openIds()], now);
      router.replaceState(view, params);
    });
  }

  const apply = (next) => {
    params = { ...((next && next.params) || {}) };
    const open = new Set(state.openSections(params, [...rendered.keys()]));
    for (const [id, entry] of rendered) setOpen(entry, open.has(id));
  };
  apply(route);
  return { node, update: apply, open: openIds };
}

function setOpen(entry, open) {
  entry.button.setAttribute("aria-expanded", open ? "true" : "false");
  entry.word.textContent = open ? WORD_HIDE : WORD_SHOW;
  entry.body.setAttribute("data-open", open ? "true" : "false");
  if (open) entry.body.removeAttribute("inert");
  else entry.body.setAttribute("inert", "");
  if (open && !entry.filled) fill(entry);
}

function fill(entry) {
  entry.filled = true;
  clear(entry.inner);
  try {
    entry.item.build(entry.inner);
  } catch (error) {
    // The file arrived and was accepted, but this section cannot draw it: say
    // so in the section, and let a later open try again.
    clear(entry.inner);
    for (const node of renderFailureMessages(entry.item.artifacts || [], error)) entry.inner.appendChild(node);
    entry.filled = false;
  }
}
