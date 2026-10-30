/* map.js
 *
 * The map of one voyage. Like src/charts.js, SVG drawn by hand, marks coloured
 * by the role and palette classes in styles/components.css.
 *
 * The drawing is made by Python (src/voyage/routemap.py) as path strings in
 * its own coordinates: the land, and the very lines the distances are measured
 * on, with the stretches inside an emission control area cut out as their own
 * paths. Here it is only put on the page. The svg's viewBox is the voyage's
 * own box, so the map shows the part of the world the voyage sails and scales
 * to the column. Lines keep their screen width at any scale
 * (vector-effect: non-scaling-stroke); the port dots and names are sized again
 * on every width change, so a name stays readable on a phone.
 *
 * PORT NAMES are placed here, at the size they are drawn, because that size in
 * map units changes with the width of the column: beside the dot, then above
 * or below it, then a step further away, the first place where no line of the
 * voyage runs through the name, no other name or dot lies under it and the
 * name stays within the width of the box. The box then grows a band at its top
 * or bottom where a name needs one, so a name next to a port at the edge of
 * the voyage's box stays next to it. A name that finds no clear place takes
 * the first one within the width, where its halo keeps it readable.
 *
 * The laden leg is solid ink, the ballast leg a dashed muted line beside it,
 * and an ECA stretch is drawn over either in the sea green of the 0.10 percent
 * zone. The legend under the map says so in words, so no line depends on its
 * colour. A ballast leg Python marks `beside`, one that sails the laden leg's
 * water back, is moved BALLAST_GAP screen px to its side on every width
 * change, so the two lines stay apart at any size.
 *
 * Numeric literals: MAP_GEOMETRY and ATLAS_GEOMETRY below, declared in
 * tools/check-literals.mjs.
 */

import { svgEl, imageSvg, px, onWidthChange, GEOMETRY } from "./charts.js";
import { clear } from "./dom.js";
import { segmentsText } from "./format.js";

export const MAP_GEOMETRY = Object.freeze({
  /* A port's dot, its ring of the ground, and the gap to its name, in px. */
  PORT_RADIUS: 3.5,
  PORT_GAP: 3,
  /* A port's name in px. */
  PORT_FONT: 12,
  /* A name's reach above and below its baseline, and its baseline beside the
   * dot, as shares of its size. */
  ASCENT: 0.85,
  DESCENT: 0.25,
  BESIDE: 0.35,
  /* The width of a character of a name, as a share of its size. */
  CHAR_EM: 0.6,
  /* A name with no clear place next to its dot moves away from it in steps
   * of this share of its size, at most SHIFTS steps. */
  SHIFT: 0.5,
  SHIFTS: 6,
  /* A ballast leg beside its laden leg: the distance between them, in px. */
  BALLAST_GAP: 3,
});

/** A line moved sideways by `distance`, to its left as drawn: each point
 *  along the mean of the normals of the segments that meet there. */
function offsetLine(points, distance) {
  if (points.length <= 1) return points;
  const normals = [];
  for (let i = 1; i < points.length; i += 1) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    const length = Math.hypot(dx, dy) || 1;
    normals.push({ x: -dy / length, y: dx / length });
  }
  return points.map((point, i) => {
    const before = normals[Math.max(i - 1, 0)];
    const after = normals[Math.min(i, normals.length - 1)];
    const nx = before.x + after.x;
    const ny = before.y + after.y;
    const length = Math.hypot(nx, ny) || 1;
    return { x: point.x + (nx / length) * distance, y: point.y + (ny / length) * distance };
  });
}

/** A path string from lines of points. */
function pathString(lines) {
  return lines.map((line) => line.map((point, i) => (i ? "L" : "M") + px(point.x) + " " + px(point.y)).join("")).join("");
}

/** The lines of a path string as Python writes it: absolute M and L only. */
function pathLines(d) {
  const lines = [];
  for (const match of d.matchAll(/(?<command>[ML])(?<x>-?[\d.]+) (?<y>-?[\d.]+)/g)) {
    if (match.groups.command === "M" || !lines.length) lines.push([]);
    lines[lines.length - 1].push({ x: Number(match.groups.x), y: Number(match.groups.y) });
  }
  return lines;
}

/** The box a name covers with `pad` round it, in map units. */
function nameBox(name, place, font, pad) {
  const g = MAP_GEOMETRY;
  const width = name.length * font * g.CHAR_EM;
  const left = place.anchor === "start" ? place.x : place.anchor === "end" ? place.x - width : place.x - width * GEOMETRY.HALF;
  return { left: left - pad, top: place.y - font * g.ASCENT - pad, right: left + width + pad, bottom: place.y + font * g.DESCENT + pad };
}

function overlaps(a, b) {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Whether the segment from p to q enters the box (Liang and Barsky's clip). */
function crosses(box, p, q) {
  let enter = 0;
  let leave = 1;
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  for (const [toward, room] of [[-dx, p.x - box.left], [dx, box.right - p.x], [-dy, p.y - box.top], [dy, box.bottom - p.y]]) {
    if (toward === 0) {
      if (room < 0) return false;
      continue;
    }
    const t = room / toward;
    if (toward < 0) enter = Math.max(enter, t);
    else leave = Math.min(leave, t);
    if (enter > leave) return false;
  }
  return true;
}

/** The places a port's name may take, nearest first: beside the dot (the
 *  side facing the middle of the map first), centred above and below it,
 *  above and below it starting at the dot, then each a step further away. */
function namePlaces(port, font, radius, gap, inward) {
  const g = MAP_GEOMETRY;
  const right = { anchor: "start", x: port.x + radius + gap, from: port.x - radius };
  const left = { anchor: "end", x: port.x - radius - gap, from: port.x + radius };
  const sides = inward === "end" ? [left, right] : [right, left];
  const beside = port.y + font * g.BESIDE;
  const above = port.y - radius - gap - font * g.DESCENT;
  const below = port.y + radius + gap + font * g.ASCENT;
  const places = [];
  for (let step = 0; step <= g.SHIFTS; step += 1) {
    const shift = step * font * g.SHIFT;
    for (const side of sides) {
      places.push({ anchor: side.anchor, x: side.x, y: beside - shift });
      if (step) places.push({ anchor: side.anchor, x: side.x, y: beside + shift });
    }
    places.push({ anchor: "middle", x: port.x, y: above - shift });
    places.push({ anchor: "middle", x: port.x, y: below + shift });
    for (const side of sides) {
      places.push({ anchor: side.anchor, x: side.from, y: above - shift });
      places.push({ anchor: side.anchor, x: side.from, y: below + shift });
    }
  }
  return places;
}

/** Every port's name placed at this size, one place per port in order, and
 *  the top and bottom of the box that holds the voyage and every name. */
function placeNames(ports, lines, view, font, radius, gap) {
  const middle = view.left + (view.right - view.left) * GEOMETRY.HALF;
  const taken = ports.map((port) => ({ left: port.x - radius - gap, top: port.y - radius - gap, right: port.x + radius + gap, bottom: port.y + radius + gap }));
  const segments = [];
  for (const line of lines) {
    for (let i = 1; i < line.length; i += 1) segments.push([line[i - 1], line[i]]);
  }
  const within = (box) => box.left >= view.left && box.right <= view.right;
  let top = view.top;
  let bottom = view.bottom;
  const places = ports.map((port) => {
    const options = namePlaces(port, font, radius, gap, port.x > middle ? "end" : "start");
    const boxes = options.map((place) => nameBox(port.name, place, font, gap));
    const free = (at) => within(boxes[at]) && !taken.some((box) => overlaps(boxes[at], box));
    let chosen = options.findIndex((place, at) => free(at) && !segments.some(([p, q]) => crosses(boxes[at], p, q)));
    if (chosen < 0) chosen = options.findIndex((place, at) => free(at));
    if (chosen < 0) chosen = 0;
    taken.push(boxes[chosen]);
    top = Math.min(top, boxes[chosen].top);
    bottom = Math.max(bottom, boxes[chosen].bottom);
    return options[chosen];
  });
  return { places, top, bottom };
}

/** The map of one voyage as an image that fills `frame`.
 *
 *    land     the land path, in the map's units
 *    voyage   { view_box, laden: { d, eca }, ballast: { d, eca }, ports }
 *    words    { title, desc } */
export function voyageMap(frame, land, voyage, words) {
  const g = MAP_GEOMETRY;
  const [x0, y0, width, height] = voyage.view_box;
  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "map", viewBox: [x0, y0, width, height].join(" ") });
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.appendChild(svgEl("path", { class: "map-land", d: land }));

  // Each path of a leg with the lines it draws, so a ballast leg drawn beside
  // the laden one can be moved again at each width.
  const leg = (drawing, kind) => {
    const group = svgEl("g", { class: "map-leg map-leg--" + kind });
    const paths = [{ className: "map-leg__line", d: drawing.d }, ...(drawing.eca || []).map((d) => ({ className: "map-leg__eca", d }))]
      .map(({ className, d }) => {
        const node = svgEl("path", { class: className, d, "vector-effect": "non-scaling-stroke" });
        group.appendChild(node);
        return { node, lines: pathLines(d) };
      });
    svg.appendChild(group);
    return paths;
  };
  const ballastPaths = leg(voyage.ballast, "ballast");
  leg(voyage.laden, "laden");

  const ports = voyage.ports.map((port) => {
    const ring = svgEl("circle", { class: "mark-ring-fill", cx: px(port.x), cy: px(port.y) });
    const dot = svgEl("circle", { class: "map-port-dot", cx: px(port.x), cy: px(port.y) });
    const halo = svgEl("text", { class: "map-port halo" }, port.name);
    const name = svgEl("text", { class: "map-port" }, port.name);
    svg.appendChild(ring);
    svg.appendChild(dot);
    return { port, ring, dot, halo, name };
  });
  for (const item of ports) {
    svg.appendChild(item.halo);
    svg.appendChild(item.name);
  }
  frame.appendChild(svg);

  // Dots and names at a screen size: k map units per px at this width.
  const laden = pathLines(voyage.laden.d);
  const view = { left: x0, top: y0, right: x0 + width, bottom: y0 + height };
  onWidthChange(frame, (renderedWidth) => {
    const k = width / renderedWidth;
    let ballast = ballastPaths[0].lines;
    if (voyage.ballast.beside) {
      for (const path of ballastPaths) {
        const moved = path.lines.map((line) => offsetLine(line, g.BALLAST_GAP * k));
        path.node.setAttribute("d", pathString(moved));
        if (path === ballastPaths[0]) ballast = moved;
      }
    }
    const lines = [...laden, ...ballast];
    const font = g.PORT_FONT * k;
    const radius = g.PORT_RADIUS * k;
    const gap = g.PORT_GAP * k;
    const placed = placeNames(ports.map((item) => item.port), lines, view, font, radius, gap);
    svg.setAttribute("viewBox", [x0, placed.top, width, placed.bottom - placed.top].join(" "));
    ports.forEach(({ ring, dot, halo, name }, at) => {
      const place = placed.places[at];
      ring.setAttribute("r", px(radius + GEOMETRY.RING_WIDTH * k));
      dot.setAttribute("r", px(radius));
      for (const text of [halo, name]) {
        text.setAttribute("x", px(place.x));
        text.setAttribute("y", px(place.y));
        text.setAttribute("font-size", px(font));
        text.setAttribute("text-anchor", place.anchor);
      }
      // A style, not an attribute: the stylesheet's .halo width would win over an attribute.
      halo.style.strokeWidth = px(GEOMETRY.RING_WIDTH * k + GEOMETRY.RING_WIDTH * k * GEOMETRY.HALF);
    });
  });
  return svg;
}

/* ============================================================== atlas === */

/* THE ATLAS is the Map view's drawing: every route of the study on one map
 * of the world, as Python placed them (src/voyage/routemap.py,
 * atlas_document). Each leg is a path in the map's units; a leg that crosses
 * the open Pacific is cut where it leaves the map and comes back, and those
 * points carry a small ring. The view box is the atlas window or, with a
 * route picked, the box Python framed for it at the window's own shape, so
 * the frame keeps its height whatever is picked and nothing moves round it.
 *
 * Every size here is in screen px and turned into map units on each width or
 * view change: k map units a px. Lines keep their screen width
 * (non-scaling strokes).
 *
 * THE POINTER. A route is found by its distance from the pointer, in map
 * units, not by what lies on top: corridors overlap (Ras Tanura to Hormuz
 * carries four routes), so a click takes the nearest line within half of HIT
 * px, a tap only a line with no other as near, and labels take their own
 * route. Below CODES_FROM px of map a tap does nothing: the lines are too
 * close for a finger, and the list beside the map does the work. What lies
 * under the pointer is told to the caller (`on.hover`), which writes it in
 * the line under the map: no box floats over the lines it describes.
 *
 * Labels are placed here, at the size they are drawn, by the same box search
 * the voyage map uses for its port names: beside the dot first, then above
 * or below, then a step further away, the first place inside the view where
 * no other label or dot lies. With nothing picked each loading area carries
 * a block, one line a route: its code and, where every block still finds a
 * place with them, its TCE, right aligned, in ink for the Baltic's figure and
 * muted for the engine's estimate; the alternatives each route's line carries
 * are named in muted italic where they fit. With a route picked, its ports,
 * the passages that decide between its routings, and each alternative's name
 * with what it changes are written instead. Every word wears a halo of the
 * ground, set inline in map units.
 *
 * A map narrower than TALL_BELOW px takes a taller frame once a route is
 * picked (Python's view_tall), so a phone frames the route rather than the
 * world.
 *
 * The svg is an image (role img, its title and description from the artifact,
 * swapped when the route changes). Its labels and lines answer a pointer
 * only: the keyboard and a screen reader reach every route through the list
 * beside the map, which holds every figure the map shows. */

export const ATLAS_GEOMETRY = Object.freeze({
  /* The band round a line that takes a pointer, in screen px. */
  HIT: 14,
  /* A label line's height as a share of its size. */
  LEADING: 1.3,
  /* The rendered map width from which a loading area's labels carry the TCE,
   * and from which they are written at all and a tap selects, in px. */
  FIGURES_FROM: 640,
  CODES_FROM: 420,
  /* A port's dot, and the ring where a line leaves the map, in screen px. */
  DOT: 3,
  EDGE_RING: 4,
  /* The gap between a label block's codes and its figures, in characters. */
  COLUMN_GAP: 2,
  /* The map width under which a route picked is framed in the taller box, in px. */
  TALL_BELOW: 600,
});

/** The candidate boxes for a block of `width` and `height` round an anchor
 *  box (a loading area's ports, or a point): beside it on the side facing the
 *  middle of the view first, then the other side, then above and below it,
 *  centred and then flush with either end, each then a step further away. */
function blockPlaces(anchor, width, height, gap, step, steps, inward) {
  const g = GEOMETRY;
  const middleY = (anchor.top + anchor.bottom) * g.HALF - height * g.HALF;
  const middleX = (anchor.left + anchor.right) * g.HALF - width * g.HALF;
  const right = { left: anchor.right + gap, top: middleY };
  const left = { left: anchor.left - gap - width, top: middleY };
  const sides = inward === "end" ? [left, right] : [right, left];
  const lefts = inward === "end" ? [middleX, anchor.right - width, anchor.left] : [middleX, anchor.left, anchor.right - width];
  const places = [];
  for (let s = 0; s <= steps; s += 1) {
    const shift = s * step;
    for (const side of sides) {
      places.push({ left: side.left, top: side.top - shift });
      if (s) places.push({ left: side.left, top: side.top + shift });
    }
    for (const x of lefts) places.push({ left: x, top: anchor.top - gap - height - shift });
    for (const x of lefts) places.push({ left: x, top: anchor.bottom + gap + shift });
  }
  return places.map((p) => ({ left: p.left, top: p.top, right: p.left + width, bottom: p.top + height }));
}

/** Place blocks in order, each in the first candidate inside the view that no
 *  earlier block or obstacle overlaps; a block with no such place is left out
 *  (`box` null), since the list beside the map carries every value. */
function placeBlocks(blocks, obstacles, view, step, steps) {
  const taken = [...obstacles];
  const middle = view.left + (view.right - view.left) * GEOMETRY.HALF;
  const inside = (b) => b.left >= view.left && b.right <= view.right && b.top >= view.top && b.bottom <= view.bottom;
  return blocks.map((block) => {
    const centre = (block.anchor.left + block.anchor.right) * GEOMETRY.HALF;
    const candidates = blockPlaces(block.anchor, block.width, block.height, block.gap, step, steps, centre > middle ? "end" : "start");
    const box = candidates.find((c) => inside(c) && !taken.some((t) => overlaps(c, t))) || null;
    if (box) taken.push(box);
    return { ...block, box };
  });
}

/** The distance from a point to a polyline, in its units. */
function lineDistance(point, lines) {
  let best = Infinity;
  for (const points of lines) {
    for (let i = 1; i < points.length; i += 1) {
      const a = points[i - 1];
      const b = points[i];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const span = dx * dx + dy * dy;
      const t = span ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / span)) : 0;
      best = Math.min(best, Math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy)));
    }
  }
  return best;
}

/** The atlas, drawn into `frame`, and the means to change what it shows.
 *
 *    land     map.json land
 *    geo      map.json atlas: view_box, legs, ports, passages
 *    items    atlas.json items, each { id, label, segment, legs, view,
 *             alternatives, passages, readout, figure, map_title, map_desc }
 *    clusters atlas.json clusters: { ports, x, y, items }
 *    words    { title, desc }: the image's name with nothing picked
 *    on       { select(id), hover(id or null, ids sharing its water),
 *               labels(mode) after each layout: "figures", "codes" or
 *               "none" with nothing picked, "route" with a route picked }
 *
 *  Returns { show({ filter, selected, focus }), hover(id), stop() }. */
export function atlasMap(frame, land, geo, items, clusters, words, decimals, on) {
  const g = ATLAS_GEOMETRY;
  const mg = MAP_GEOMETRY;
  const [, , ww, wh] = geo.view_box;
  const svg = imageSvg({ width: ww, height: wh, title: words.title, desc: words.desc, className: "map atlas-map", viewBox: geo.view_box.join(" ") });
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const titleNode = svg.querySelector("title");
  const descNode = svg.querySelector("desc");
  svg.appendChild(svgEl("path", { class: "map-land", d: land }));

  const layer = (name) => svg.appendChild(svgEl("g", { class: "atlas-" + name }));
  const altLayer = layer("alternatives");
  const routeLayer = layer("routes");
  const markLayer = layer("marks");
  const labelLayer = layer("labels");

  const line = (parent, className, d) => parent.appendChild(svgEl("path", { class: className, d, "vector-effect": "non-scaling-stroke" }));
  const byId = new Map(items.map((item) => [item.id, item]));
  const drawn = items.map((item) => {
    const group = routeLayer.appendChild(svgEl("g", { class: "atlas-route", "data-item": item.id }));
    const laden = geo.legs[item.legs.laden];
    const ballast = item.legs.ballast ? geo.legs[item.legs.ballast] : null;
    // Casings of the ground under the route picked, so its accent and its ECA green stand off the land.
    const ballastCasing = ballast ? line(group, "atlas-route__casing", ballast.d) : null;
    line(group, "atlas-route__casing", laden.d);
    const ballastNode = ballast ? line(group, "atlas-route__ballast", ballast.d) : null;
    line(group, "atlas-route__line", laden.d);
    for (const d of [...laden.eca, ...(ballast ? ballast.eca : [])]) line(group, "atlas-route__eca", d);
    // A routing drawn on legs of the route's own (its base, listed first) is the route's line already.
    const own = new Set([item.legs.laden, item.legs.ballast]);
    const alternatives = (item.alternatives || []).filter((alt) => alt.legs.some((key) => !own.has(key))).map((alt) => {
      const altGroup = altLayer.appendChild(svgEl("g", { class: "atlas-alt", "data-item": item.id, "data-alt": alt.id }));
      for (const key of alt.legs) line(altGroup, "atlas-alt__line", geo.legs[key].d);
      return { alt, group: altGroup };
    });
    return {
      item,
      group,
      ballastNodes: [ballastCasing, ballastNode].filter(Boolean),
      ballastLines: ballast ? pathLines(ballast.d) : null,
      ladenLines: pathLines(laden.d),
      alternatives,
    };
  });
  frame.appendChild(svg);
  const drawnAlt = new Set(drawn.flatMap((d) => d.alternatives.map((a) => a.alt)));

  let state = { filter: "all", selected: null, focus: null };
  let hovered = null;
  let k = ww / Math.max(frame.clientWidth, 1);

  const visible = (item) => state.filter === "all" || item.segment === state.filter;

  const setHover = (id, sharing) => {
    if (hovered === id) return;
    hovered = id;
    for (const d of drawn) d.group.classList.toggle("is-hover", d.item.id === id);
    svg.classList.toggle("is-pointing", Boolean(id));
    if (on.hover) on.hover(id, sharing || []);
  };

  /* The routes under a pointer, nearest first, within half a band of it. */
  const near = (event) => {
    const ctm = svg.getScreenCTM();
    if (!ctm) return [];
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse());
    const reach = g.HIT * GEOMETRY.HALF * k;
    return drawn
      .filter((d) => visible(d.item))
      .map((d) => ({ id: d.item.id, distance: lineDistance(p, d.ladenLines) }))
      .filter((c) => c.distance <= reach)
      .sort((a, b) => a.distance - b.distance);
  };
  const labelled = (event) => {
    const node = event.target.closest ? event.target.closest("[data-item]") : null;
    return node && labelLayer.contains(node) ? node.getAttribute("data-item") : null;
  };
  const tapsAllowed = () => frame.clientWidth >= g.CODES_FROM;

  svg.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") return;
    const label = labelled(event);
    const found = label ? [] : near(event);
    const id = label || (found[0] || {}).id || null;
    setHover(id, found.slice(1).map((c) => c.id));
  });
  svg.addEventListener("pointerleave", () => setHover(null, []));
  svg.addEventListener("click", (event) => {
    const touch = event.pointerType === "touch";
    if (touch && !tapsAllowed()) return;
    let id = labelled(event);
    if (!id) {
      const found = near(event);
      // A finger cannot tell two lines this close apart: a tap between them picks neither.
      const distinct = found.length === 1 || (found.length > 1 && found[1].distance - found[0].distance > g.HIT * GEOMETRY.HALF * k * GEOMETRY.HALF);
      id = found.length && (!touch || distinct) ? found[0].id : null;
    }
    if (id && on.select) on.select(id);
  });

  /* Dots, rings and labels at this size and in this view. */
  const view = () => {
    if (!state.selected) return geo.view_box;
    const item = byId.get(state.selected);
    return frame.clientWidth < g.TALL_BELOW ? item.view_tall : item.view;
  };
  const layout = () => {
    const [vx, vy, vw, vh] = view();
    svg.setAttribute("viewBox", [vx, vy, vw, vh].join(" "));
    k = vw / Math.max(frame.clientWidth, 1);
    const box = { left: vx, top: vy, right: vx + vw, bottom: vy + vh };
    const font = mg.PORT_FONT * k;
    const gap = mg.PORT_GAP * k;
    const dot = g.DOT * k;
    const haloWidth = GEOMETRY.RING_WIDTH * k + GEOMETRY.RING_WIDTH * k * GEOMETRY.HALF;
    const lineHeight = font * g.LEADING;
    const width = frame.clientWidth;
    clear(markLayer);
    clear(labelLayer);

    for (const d of drawn) {
      if (d.ballastLines && d.item.legs.beside) {
        const moved = pathString(d.ballastLines.map((points) => offsetLine(points, mg.BALLAST_GAP * k)));
        for (const node of d.ballastNodes) node.setAttribute("d", moved);
      }
    }

    const selected = state.selected ? byId.get(state.selected) : null;
    let mode = selected ? "route" : "none";
    const obstacles = [];
    const dotAt = (x, y) => {
      markLayer.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(x), cy: px(y), r: px(dot + GEOMETRY.RING_WIDTH * k) }));
      markLayer.appendChild(svgEl("circle", { class: "map-port-dot", cx: px(x), cy: px(y), r: px(dot) }));
      obstacles.push({ left: x - dot - gap, top: y - dot - gap, right: x + dot + gap, bottom: y + dot + gap });
    };
    const ringAt = ([x, y]) => markLayer.appendChild(svgEl("circle", { class: "atlas-edge", cx: px(x), cy: px(y), r: px(g.EDGE_RING * k) }));
    // A block is a small table: each line's first part at its left edge, a
    // second part (a figure) right aligned at its right edge.
    const write = (block, className) => {
      const group = labelLayer.appendChild(svgEl("g", { class: className }));
      block.lines.forEach((ln, row) => {
        const y = block.box.top + lineHeight * row + font * mg.ASCENT;
        ln.parts.forEach((part, column) => {
          const attrs = {
            x: px(column ? block.box.right : block.box.left),
            y: px(y),
            "font-size": px(font),
            "text-anchor": column ? "end" : "start",
            "data-item": ln.item || null,
          };
          const halo = group.appendChild(svgEl("text", { ...attrs, class: "atlas-label halo " + (part.className || "") }, part.text));
          halo.style.strokeWidth = px(haloWidth);
          group.appendChild(svgEl("text", { ...attrs, class: "atlas-label " + (part.className || "") }, part.text));
        });
      });
    };
    // An anchor is a box: a loading area's ports, or a point.
    const at = (x, y) => ({ left: x, top: y, right: x, bottom: y });
    const blockOf = (anchor, lines, gapFrom) => {
      const widest = (column) => Math.max(...lines.map((ln) => (ln.parts[column] ? ln.parts[column].text.length : 0)));
      const chars = widest(0) + (lines.some((ln) => ln.parts.length > 1) ? g.COLUMN_GAP + widest(1) : 0);
      return { anchor, lines, width: chars * font * mg.CHAR_EM, height: lineHeight * lines.length, gap: gapFrom };
    };
    // The biggest blocks choose first; the order is stable among equals. Returns
    // whether every block found a place, and leaves the obstacles as they were
    // when `dry` asks only that.
    const place = (blocks, dry) => {
      const order = blocks.map((block, index) => ({ block, index })).sort((a, b) => b.block.lines.length - a.block.lines.length || a.index - b.index);
      const placed = placeBlocks(order.map((entry) => entry.block), obstacles, box, font * mg.SHIFT, mg.SHIFTS);
      if (!dry) {
        for (const block of placed) {
          if (!block.box) continue;
          write(block, "atlas-block");
          obstacles.push(block.box);
        }
      }
      return placed.every((block) => block.box);
    };

    if (!selected) {
      // Every route shown: a ring where its line leaves the map, a dot at each loading port, a block of labels at each loading area.
      const shown = new Set(items.filter(visible).map((item) => item.id));
      for (const d of drawn) {
        if (shown.has(d.item.id)) for (const point of geo.legs[d.item.legs.laden].edges) ringAt(point);
      }
      for (const cluster of clusters) {
        if (!cluster.items.some((id) => shown.has(id))) continue;
        for (const portId of cluster.ports) dotAt(geo.ports[portId].x, geo.ports[portId].y);
      }
      if (width >= g.CODES_FROM) {
        // Each loading area's block with its figures where every block still finds a place, else codes alone.
        const blocks = (figures) => clusters
          .map((cluster) => {
            const lines = cluster.items.filter((id) => shown.has(id)).map((id) => {
              const item = byId.get(id);
              const parts = [{ text: item.label, className: "atlas-label__code" }];
              if (figures && item.figure) parts.push({ text: segmentsText(item.figure, decimals), className: "atlas-label__figure atlas-label__figure--" + item.basis });
              return { item: id, parts };
            });
            const [x0, y0, x1, y1] = cluster.box;
            return lines.length ? blockOf({ left: x0, top: y0, right: x1, bottom: y1 }, lines, dot + gap) : null;
          })
          .filter(Boolean);
        const withFigures = width >= g.FIGURES_FROM && place(blocks(true), true);
        place(blocks(withFigures));
        mode = withFigures ? "figures" : "codes";
        // The alternatives each route's line carries, named where there is still room.
        place(items
          .filter((item) => shown.has(item.id))
          .flatMap((item) => (item.alternatives || []).filter((alt) => alt.whole_label && alt.label_at && drawnAlt.has(alt)))
          .map((alt) => blockOf(at(alt.label_at[0], alt.label_at[1]), [{ parts: [{ text: alt.whole_label, className: "atlas-label__alt" }] }], gap)));
      }
    } else {
      // The route picked: where its lines leave the map, its ports, its alternatives' names, its passages.
      const keys = [selected.legs.laden, selected.legs.ballast, ...(selected.alternatives || []).flatMap((alt) => alt.legs)].filter(Boolean);
      for (const key of keys) for (const point of geo.legs[key].edges) ringAt(point);
      const portIds = [...new Set(keys.flatMap((key) => [geo.legs[key].from, geo.legs[key].to]))];
      for (const portId of portIds) dotAt(geo.ports[portId].x, geo.ports[portId].y);
      const passages = new Map(geo.passages.map((p) => [p.name, p]));
      // One name a side of the map where its lines leave across the Pacific, at the middle of that side's rings.
      const middle = geo.view_box[0] + geo.view_box[2] * GEOMETRY.HALF;
      const edges = [true, false]
        .map((west) => keys.flatMap((key) => geo.legs[key].edges).filter(([x]) => (x < middle) === west))
        .filter((side) => side.length)
        .map((side) => [side[0][0], side.reduce((sum, [, y]) => sum + y, 0) / side.length]);
      place(portIds.map((portId) => blockOf(at(geo.ports[portId].x, geo.ports[portId].y), [{ parts: [{ text: geo.ports[portId].name, className: "atlas-label__port" }] }], dot + gap)));
      place((selected.alternatives || []).filter((alt) => alt.label_at && drawnAlt.has(alt)).map((alt) => {
        const text = alt.map_label ? segmentsText(alt.map_label, decimals) : alt.short;
        return blockOf(at(alt.label_at[0], alt.label_at[1]), [{ parts: [{ text, className: "atlas-label__alt" }] }], gap);
      }));
      place([
        ...(selected.passages || []).filter((name) => passages.has(name)).map((name) => blockOf(at(passages.get(name).x, passages.get(name).y), [{ parts: [{ text: name, className: "atlas-label__passage" }] }], gap)),
        ...edges.map(([x, y]) => blockOf(at(x, y), [{ parts: [{ text: words.edge, className: "atlas-label__passage" }] }], gap)),
      ]);
    }
    if (on.labels) on.labels(mode);
  };

  const show = (next) => {
    state = { ...state, ...next };
    const selected = state.selected ? byId.get(state.selected) : null;
    titleNode.textContent = selected ? selected.map_title : words.title;
    descNode.textContent = selected ? selected.map_desc : words.desc;
    svg.classList.toggle("has-selection", Boolean(selected));
    for (const d of drawn) {
      const isCurrent = d.item.id === state.selected;
      d.group.classList.toggle("is-current", isCurrent);
      d.group.classList.toggle("is-hidden", !visible(d.item));
      for (const a of d.alternatives) {
        a.group.classList.toggle("is-hidden", !visible(d.item) || Boolean(selected && !isCurrent));
        a.group.classList.toggle("is-current", isCurrent);
        a.group.classList.toggle("is-focus", isCurrent && a.alt.id === state.focus);
      }
    }
    layout();
  };

  const stop = onWidthChange(frame, () => layout());
  show({});
  return { show, stop, hover: setHover };
}
