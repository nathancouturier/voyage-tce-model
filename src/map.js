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

/** Whether two path strings are the same line run the opposite ways. */
function reverses(a, b) {
  const one = pathLines(a);
  const other = pathLines(b).reverse().map((points) => [...points].reverse());
  return one.length === other.length &&
    one.every((points, i) => points.length === other[i].length && points.every((p, j) => p.x === other[i][j].x && p.y === other[i][j].y));
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

/** The part of the segment from p to q inside the box, as the shares of its
 *  length where it enters and leaves, or null (Liang and Barsky's clip). */
function clip(box, p, q) {
  let enter = 0;
  let leave = 1;
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  for (const [toward, room] of [[-dx, p.x - box.left], [dx, box.right - p.x], [-dy, p.y - box.top], [dy, box.bottom - p.y]]) {
    if (toward === 0) {
      if (room < 0) return null;
      continue;
    }
    const t = room / toward;
    if (toward < 0) enter = Math.max(enter, t);
    else leave = Math.min(leave, t);
    if (enter > leave) return null;
  }
  return [enter, leave];
}

/** Whether the segment from p to q enters the box. */
function crosses(box, p, q) {
  return clip(box, p, q) !== null;
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
 * points carry a small ring, set in from the edge by its own size so the
 * frame does not cut it. A routing is drawn on the legs it does not share
 * with its route, whose line the rest already is, and a leg sailed back on
 * the same water the same way round as the leg out, so the dots of the two
 * fall together and the line still reads as dotted. The view box is the atlas
 * window or, with a route picked, the box Python framed for it at the
 * window's own shape, so the frame keeps its height whatever is picked and
 * nothing moves round it.
 *
 * Every size here is in screen px and turned into map units on each width or
 * view change: k map units a px. Lines keep their screen width
 * (non-scaling strokes).
 *
 * PAINT ORDER. The routes are painted in the list's order, over the other
 * routings they could take. The route under the pointer is raised to the end
 * of its layer, in ink; with nothing picked every other route is then drawn
 * as the thin muted line of a pick, so the one pointed at stands out. The
 * route picked is painted over every other route, its other routings between
 * it and the rest, and the routing its "Show on the map" toggle shows over
 * everything; a route pointed at while one is picked stays under it. When
 * the pick is cleared the list's order comes back. Only the groups whose
 * order changes are moved, and none while a pointer is pressed on the map: a
 * node taken out of the page between a press and its release loses the
 * click (Chromium fires none), so the order waits for the release and is
 * painted at the next frame, after the click the release brings.
 *
 * THE POINTER. A route is found by its distance from the pointer, in map
 * units, not by what lies on top: corridors overlap (Ras Tanura to Hormuz
 * carries four routes), so a click takes the nearest line within half of HIT
 * px, a tap only a line with no other as near, and labels take their own
 * route. With a route picked its own lines are measured too, its ballast leg
 * and the other routings drawn for it, and they keep the pointer unless
 * another route's line is nearer by a quarter of HIT px; a routing must be
 * nearer than the route's own line by as much, since it shares the route's
 * water. A click on one of those routings, or on its name, is handed to the
 * caller (`on.alternative`), which presses the routing's toggle, so the
 * button and the map stay in step. A tap is told from a click by the type of
 * the pointer that went down, as some browsers send a click with no type of
 * its own. A click is measured where the pointer's own events last put it,
 * to the fraction of a pixel, when that lies within the whole pixel the
 * click gives, so it takes the line the pointer was found on and the line
 * under the map names. Below CODES_FROM px of map a tap does nothing: the
 * lines are too close for a finger, and the list beside the map does the
 * work. What lies under the pointer, with the routes that share its water,
 * is told to the caller (`on.hover`) whenever either changes, and so is a
 * route the caller raises itself (`hover(id)`, a row of the list pointed at
 * or focused), with which of the two it is; the caller decides where the
 * line under the map names it (src/atlas.js): no box floats over the lines
 * it describes. After each drawing the caller is also given the most a
 * pointer can find beside each route (`waters`), for the room it keeps for
 * that line.
 *
 * LABELS are placed here at the size they are drawn, each measured on the
 * page in its own face, weight and size (a hidden text in the svg; widths
 * are kept by text and size once the faces are in, and measured again when a
 * face arrives or a reader's own style spaces the text wider), by a box
 * search like the voyage map's: beside the anchor first, then above or
 * below, then a step further away. A place is taken only inside the view
 * with room for the halo, clear of every dot and ring and of every other
 * label with room kept round it and, for a place's name, nearer its own
 * point than any other named point: a port's dot and, with a route picked,
 * every passage and side of the map its lines use, named or not, so a name
 * never reads as another place's. A routing's name names no place and minds
 * none of them: it may go further from its point and, with a route picked,
 * by any point of its own line, as its point is often where its legs meet,
 * at a cape. It minds the lines it could be read as naming instead: its
 * route's own line (with its ballast leg once picked) and other routings
 * and, with nothing picked, every other route's line and routing shown;
 * with a route picked those are muted and named nowhere. None may lie nearer
 * the name than its own line by more than a quarter of HIT px, the margin by
 * which a click tells two lines apart, so a name never reads as another
 * line's, while one by water its line shares with them still finds a place;
 * a name with no such place is left out, as the column beside the map names
 * it. Among those places the first wins that shares no
 * baseline with a label beside it and that no line crosses; failing that, a
 * place on no shared baseline comes before one no line crosses, so two labels
 * run on as one line only where there is no other room, and a line through a
 * label is left to its halo. The lines are, with nothing picked, every
 * route's laden leg and the other routings drawn and, with a route picked,
 * its own; a corridor several routes sail counts as one line. The block with
 * the fewest places chooses first. A label placed left of its point ends at
 * it.
 *
 * With nothing picked each loading area carries a block, one line a route:
 * its code and, where every block still finds a place with them, its TCE in
 * a column a COLUMN_GAP after the widest code, in ink for the Baltic's figure
 * and muted for the engine's estimate; the alternatives each route's line
 * carries are named in the muted ink where they fit. With a route picked,
 * its ports, the passages that decide between its routings, and each
 * routing's name with its days are written instead, or, while a routing is
 * shown from its toggle, its name alone; a passage, or
 * the side where lines leave the map, with no place that reads as its own is
 * left out, as the column beside the map names it. Every word wears a halo of
 * the ground, set inline in map units.
 *
 * A map narrower than TALL_BELOW px takes a taller frame once a route is
 * picked (Python's view_tall), so a phone frames the route rather than the
 * world.
 *
 * The svg is an image (role img) named by its title alone, a short name: the
 * route's heading with a route picked, else the map's own name (`words.name`,
 * or its title where the artifact gives none); its description says how the
 * lines are drawn. Both come from the artifact and change with the route.
 * Its labels and lines answer a pointer only: the keyboard and a screen
 * reader reach every route through the list beside the map, which holds
 * every figure the map shows. */

export const ATLAS_GEOMETRY = Object.freeze({
  /* The band round a line that takes a pointer, in screen px. */
  HIT: 14,
  /* A label line's height as a share of its size. */
  LEADING: 1.3,
  /* The rendered map width from which a loading area's labels carry the TCE,
   * and from which they are written at all and a tap selects, in px. */
  FIGURES_FROM: 640,
  CODES_FROM: 420,
  /* A port's dot, and the ring where a line leaves the map with the width of
   * its stroke (.atlas-edge in styles/components.css), in screen px. */
  DOT: 3,
  EDGE_RING: 4,
  EDGE_STROKE: 1.5,
  /* The gap between a label block's codes and its figures, as a share of its size. */
  COLUMN_GAP: 1.2,
  /* The room kept clear round a label once placed, across and up or down,
   * and how far across no other label should share one of its baselines (lie
   * within that room up or down of it), as shares of its size: two labels
   * never run on as one line, nor stack as one block. */
  ROOM_ACROSS: 1.2,
  ROOM_DOWN: 0.5,
  BASELINE_REACH: 6,
  /* How many steps of SHIFT a routing's name may move from its point with
   * nothing picked: it names no place, so it may go further than a port's or
   * a passage's name to find water no line crosses. With a route picked it
   * may move along its own line instead, a point every ALONG of its size. */
  ROUTING_SHIFTS: 12,
  ALONG: 3,
  /* The map width under which a route picked is framed in the taller box, in px. */
  TALL_BELOW: 600,
});

/** The candidate boxes for a block of `width` and `height` round an anchor
 *  box (a loading area's ports, or a point): beside it on the side facing the
 *  middle of the view first, then the other side, then above and below it,
 *  centred and then flush with either end, each then a step further away. A
 *  place above or below that would cross a side of the view slides inside
 *  it. Each carries how a single line in it is anchored: from its left, from
 *  its middle, or to its right, so a name left of its point ends at the
 *  point. */
function blockPlaces(anchor, width, height, gap, step, steps, inward, view) {
  const g = GEOMETRY;
  const middleY = (anchor.top + anchor.bottom) * g.HALF - height * g.HALF;
  const right = { left: anchor.right + gap, align: "start" };
  const left = { left: anchor.left - gap - width, align: "end" };
  const sides = inward === "end" ? [left, right] : [right, left];
  const within = (x) => Math.min(Math.max(x, view.left), view.right - width);
  const centred = { left: within((anchor.left + anchor.right) * g.HALF - width * g.HALF), align: "middle" };
  const fromLeft = { left: within(anchor.left), align: "start" };
  const toRight = { left: within(anchor.right - width), align: "end" };
  const across = inward === "end" ? [centred, toRight, fromLeft] : [centred, fromLeft, toRight];
  const places = [];
  for (let s = 0; s <= steps; s += 1) {
    const shift = s * step;
    for (const side of sides) {
      places.push({ ...side, top: middleY - shift });
      if (s) places.push({ ...side, top: middleY + shift });
    }
    for (const x of across) places.push({ ...x, top: anchor.top - gap - height - shift });
    for (const x of across) places.push({ ...x, top: anchor.bottom + gap + shift });
  }
  return places.map((p) => ({ left: p.left, top: p.top, right: p.left + width, bottom: p.top + height, align: p.align }));
}

/** The distance between two boxes, 0 where they meet; a point is a box with no size. */
function boxDistance(a, b) {
  return Math.hypot(Math.max(b.left - a.right, a.left - b.right, 0), Math.max(b.top - a.bottom, a.top - b.bottom, 0));
}

/** A line's segments and the box round them, for the label search. */
function traced(lines) {
  const segments = [];
  const box = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
  for (const points of lines) {
    points.forEach((point, i) => {
      box.left = Math.min(box.left, point.x);
      box.top = Math.min(box.top, point.y);
      box.right = Math.max(box.right, point.x);
      box.bottom = Math.max(box.bottom, point.y);
      if (i) segments.push([points[i - 1], point]);
    });
  }
  return { box, segments };
}

/** The distance from a point to the segment from a to b. */
function segmentDistance(point, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const span = dx * dx + dy * dy;
  const t = span ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / span)) : 0;
  return Math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy));
}

/** Whether any of some traced lines comes within `far` of a point: a line or
 *  a segment whose box lies further off is passed over unmeasured. */
function within(point, lines, far) {
  const off = (box) => point.x < box.left - far || point.x > box.right + far || point.y < box.top - far || point.y > box.bottom + far;
  for (const { box, segments } of lines) {
    if (off(box)) continue;
    for (const [a, b] of segments) {
      if (off({ left: Math.min(a.x, b.x), right: Math.max(a.x, b.x), top: Math.min(a.y, b.y), bottom: Math.max(a.y, b.y) })) continue;
      if (segmentDistance(point, a, b) <= far) return true;
    }
  }
  return false;
}

/** The distance from a box to the nearest of some traced lines, 0 where one
 *  runs through it: a segment that misses the box comes nearest it at one of
 *  its ends or at one of the box's corners. A segment whose own box lies no
 *  nearer than the nearest found is passed over, and the search ends at the
 *  first distance under `under`, where the caller needs to know no more. */
function boxLinesDistance(box, lines, under = 0) {
  const corners = [{ x: box.left, y: box.top }, { x: box.right, y: box.top }, { x: box.left, y: box.bottom }, { x: box.right, y: box.bottom }];
  const fromBox = (point) => Math.hypot(Math.max(box.left - point.x, point.x - box.right, 0), Math.max(box.top - point.y, point.y - box.bottom, 0));
  let best = Infinity;
  for (const line of lines) {
    if (boxDistance(box, line.box) >= best) continue;
    for (const [p, q] of line.segments) {
      const across = Math.max(Math.min(p.x, q.x) - box.right, box.left - Math.max(p.x, q.x), 0);
      const down = Math.max(Math.min(p.y, q.y) - box.bottom, box.top - Math.max(p.y, q.y), 0);
      if (across * across + down * down >= best * best) continue;
      if (crosses(box, p, q)) return 0;
      best = Math.min(best, fromBox(p), fromBox(q));
      for (const corner of corners) best = Math.min(best, segmentDistance(corner, p, q));
      if (best < under) return best;
    }
  }
  return best;
}

/** How many lines run through a box, as a reader counts them: each line by
 *  the middle of its run through the box, from where it enters to where it
 *  leaves, and lines whose runs lie within `apart` of each other (a corridor
 *  several routes sail, either way) as one. */
function crossings(box, lines, apart) {
  const runs = [];
  for (const line of lines) {
    if (!overlaps(line.box, box)) continue;
    let first = null;
    let last = null;
    for (const [p, q] of line.segments) {
      const inside = clip(box, p, q);
      if (!inside) continue;
      const [enter, leave] = inside;
      if (!first) first = { x: p.x + (q.x - p.x) * enter, y: p.y + (q.y - p.y) * enter };
      last = { x: p.x + (q.x - p.x) * leave, y: p.y + (q.y - p.y) * leave };
    }
    if (first) runs.push({ x: (first.x + last.x) * GEOMETRY.HALF, y: (first.y + last.y) * GEOMETRY.HALF });
  }
  const seen = [];
  for (const run of runs) if (!seen.some((other) => Math.hypot(other.x - run.x, other.y - run.y) <= apart)) seen.push(run);
  return seen.length;
}

/** Points every `spacing` along some lines, nearest a point first, each as a
 *  box with no size: where else a routing's name may sit beside its line. */
function alongFrom(point, lines, spacing) {
  const out = [];
  for (const points of lines) {
    for (let i = 1; i < points.length; i += 1) {
      const a = points[i - 1];
      const b = points[i];
      const n = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / spacing);
      for (let j = 0; j < n; j += 1) out.push({ x: a.x + ((b.x - a.x) * j) / n, y: a.y + ((b.y - a.y) * j) / n });
    }
  }
  return out
    .sort((p, q) => Math.hypot(p.x - point.x, p.y - point.y) - Math.hypot(q.x - point.x, q.y - point.y))
    .map((p) => ({ left: p.x, top: p.y, right: p.x, bottom: p.y }));
}

/** Place blocks. A block takes a candidate inside the view that nothing
 *  taken overlaps (dots, rings, and the labels placed before it with `room`
 *  round them) and, if it names a place, that lies nearer its own anchor than
 *  any named point it does not own by more than `slack` (a routing's name
 *  names no place, and so minds only what is taken: beside a port's dot it
 *  still reads as the routing's, and its line may run by a port). A block
 *  that carries lines (`lines`, a routing's name: { own, others }, each a
 *  traced line) takes only a candidate that none of the others lies nearer
 *  than the nearest of its own by more than `margin`, so it reads as its own
 *  line's and not as the route's or another routing's, and a candidate by
 *  water they share passes. Among
 *  those it takes the first place where no row of it lies on the baseline of
 *  a label placed within `reach` across (within `level`) and no line crosses
 *  it; else the place with the fewest rows on such a baseline, and of those
 *  the one the fewest lines cross, so two labels never run on as one line
 *  where there is any other room, and a line through a label, which its halo
 *  keeps readable, is the lesser fault. The block with the fewest places left
 *  chooses first, then the biggest, so a long name by the edge of the map is
 *  not crowded out by a block with room all round it.
 *
 *  A block that names a place with no mark of its own (`names`: a passage,
 *  or the side where lines leave the map) makes it a named point once placed,
 *  and is left out when a name already placed lies nearer that place than its
 *  own. A block with no place is left out (`box` null), since the column
 *  beside the map names and prices everything. Returns the blocks in their
 *  order; `taken`, `rows`, `named` and `names` grow with each block placed. */
function placeBlocks(blocks, { taken, rows, named, names, view, step, steps, lines, apart, room, reach, level, slack, margin }) {
  const middle = view.left + (view.right - view.left) * GEOMETRY.HALF;
  const inside = (b) => b.left >= view.left && b.right <= view.right && b.top >= view.top && b.bottom <= view.bottom;
  // Whether a place lies by the block's own line: no other line nearer it by more than the margin. One within the
  // margin of its own line passes at once, as nothing can lie nearer than that by more.
  const byOwnLine = (place, block) => {
    if (!block.lines) return true;
    const under = boxLinesDistance(place, block.lines.own) - margin;
    return under <= 0 || boxLinesDistance(place, block.lines.others, under) >= under;
  };
  const clear = (place) => !taken.some((t) => overlaps(place, t));
  const shared = (place, block) => block.baselines.filter((dy) => rows.some((row) => Math.abs(row.y - place.top - dy) < level && row.left - reach < place.right && place.left < row.right + reach)).length;
  // The named points a block must lie nearer its own point than, as they stand; one at the block's own place is
  // that place. A routing's name names no place, so it has none: the dots and rings it keeps clear of are taken.
  const rivals = (block) => (block.owns ? named.filter((point) => !block.owns.includes(point.key) && boxDistance(point, block.anchor) > slack) : []);
  const plain = (place, block, others) => {
    const own = boxDistance(place, block.anchor);
    return !others.some((point) => boxDistance(place, point) <= own + slack);
  };
  const entries = blocks.map((block, index) => {
    const places = [block.anchor, ...(block.along || [])].flatMap((anchor) => {
      const centre = (anchor.left + anchor.right) * GEOMETRY.HALF;
      return blockPlaces(anchor, block.width, block.height, block.gap, step, steps, centre > middle ? "end" : "start", view);
    }).filter(inside);
    const others = rivals(block);
    return { block, index, places, left: places.filter((place) => clear(place) && plain(place, block, others)).length };
  });
  const order = [...entries].sort((a, b) => a.left - b.left || b.block.rows.length - a.block.rows.length || a.index - b.index);
  const boxes = new Map();
  for (const entry of order) {
    const { block } = entry;
    const point = block.names;
    let box = null;
    if (!point || !names.some((name) => boxDistance(name.box, point) <= boxDistance(name.box, name.anchor) + slack)) {
      const others = rivals(block);
      let best = null;
      for (const place of entry.places) {
        if (!clear(place) || !plain(place, block, others) || !byOwnLine(place, block)) continue;
        const cost = { rows: shared(place, block), lines: crossings(place, lines, apart) };
        if (!best || cost.rows < best.rows || (cost.rows === best.rows && cost.lines < best.lines)) {
          box = place;
          best = cost;
        }
        if (!cost.rows && !cost.lines) break;
      }
    }
    if (box) {
      taken.push({ left: box.left - room.x, top: box.top - room.y, right: box.right + room.x, bottom: box.bottom + room.y });
      for (const dy of block.baselines) rows.push({ left: box.left, right: box.right, y: box.top + dy });
      if (block.owns) names.push({ box, anchor: block.anchor });
      if (point && !named.some((other) => other.key === point.key)) named.push(point);
    }
    boxes.set(entry, box);
  }
  return entries.map((entry) => ({ ...entry.block, box: boxes.get(entry) }));
}

/** The distance from a point to a polyline, in its units. */
function lineDistance(point, lines) {
  let best = Infinity;
  for (const points of lines) {
    for (let i = 1; i < points.length; i += 1) best = Math.min(best, segmentDistance(point, points[i - 1], points[i]));
  }
  return best;
}

/** Puts `nodes` into `parent` in this order, moving only those out of order:
 *  the longest run of them already in `parent` in this order (the longest
 *  increasing run of their places there now) stays where it is, and each of
 *  the rest goes in before the node that follows it. A node moved is taken
 *  out of the page and put back, which costs a press on it its click. Other
 *  children of `parent` stay where they are, for the caller to move. */
function arrange(parent, nodes) {
  const places = new Map([...parent.children].map((node, at) => [node, at]));
  // For each node, the longest run in order that ends at it, and the node before it in that run.
  const runs = nodes.map(() => ({ length: 0, before: -1 }));
  let end = -1;
  nodes.forEach((node, i) => {
    if (!places.has(node)) return;
    runs[i].length = 1;
    for (let j = 0; j < i; j += 1) {
      if (runs[j].length && places.get(nodes[j]) < places.get(node) && runs[j].length >= runs[i].length) runs[i] = { length: runs[j].length + 1, before: j };
    }
    if (end < 0 || runs[i].length > runs[end].length) end = i;
  });
  const kept = new Set();
  for (let i = end; i >= 0; i = runs[i].before) kept.add(nodes[i]);
  let next = null;
  for (let i = nodes.length - 1; i >= 0; i -= 1) {
    if (!kept.has(nodes[i])) parent.insertBefore(nodes[i], next);
    next = nodes[i];
  }
}

/** The atlas, drawn into `frame`, and the means to change what it shows.
 *
 *    land     map.json land
 *    geo      map.json atlas: view_box, legs, ports, passages
 *    items    atlas.json items, each { id, label, heading, segment, legs,
 *             view, alternatives, passages, readout, figure, map_desc }
 *    clusters atlas.json clusters: { ports, box, items }
 *    words    { title, desc, edge, name }: the image's words with nothing
 *             picked (name, its short name, where the artifact gives one)
 *    on       { select(id), alternative(id of a routing of the route
 *               picked), hover(id or null, ids sharing its water, true
 *               where the caller raised it by hover(id) rather than the
 *               pointer finding it), labels(mode, waters) after each
 *               layout: mode "figures", "codes" or "none" with nothing
 *               picked, "route" with a route picked; waters() the routes a
 *               pointer can find beside each route in this view, as
 *               [id, ids] pairs (see `waters` below) }
 *
 *  Returns { show({ filter, selected, focus }), hover(id), stop() }. */
export function atlasMap(frame, land, geo, items, clusters, words, decimals, on) {
  const g = ATLAS_GEOMETRY;
  const mg = MAP_GEOMETRY;
  const [wx, , ww, wh] = geo.view_box;
  const svg = imageSvg({ width: ww, height: wh, title: words.title, desc: words.desc, className: "map atlas-map", viewBox: geo.view_box.join(" ") });
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const titleNode = svg.querySelector("title");
  const descNode = svg.querySelector("desc");
  // Named by its title alone and described by its description, so a screen
  // reader hears a short name rather than both run together.
  svg.setAttribute("aria-labelledby", titleNode.id);
  svg.setAttribute("aria-describedby", descNode.id);
  svg.appendChild(svgEl("path", { class: "map-land", d: land }));

  // Bottom up: the other routings, the routes, the route picked with its own
  // routings, the dots and rings, the labels.
  const layer = (name) => svg.appendChild(svgEl("g", { class: "atlas-" + name }));
  const altLayer = layer("alternatives");
  const routeLayer = layer("routes");
  const pickedLayer = layer("picked");
  const markLayer = layer("marks");
  const labelLayer = layer("labels");
  // A hidden text where each label is measured in its own class and size.
  const probe = svg
    .appendChild(svgEl("g", { class: "atlas-probe", visibility: "hidden", "aria-hidden": "true" }))
    .appendChild(svgEl("text", { class: "atlas-label" }));

  const line = (parent, className, d) => parent.appendChild(svgEl("path", { class: className, d, "vector-effect": "non-scaling-stroke" }));
  const byId = new Map(items.map((item) => [item.id, item]));
  // A routing sailed both ways runs out and back on the same water. Drawn the
  // way each leg is sailed, the two dotted lines would run opposite ways, each
  // filling the other's gaps, and read as one solid line; so a leg whose exact
  // reverse is also a leg is drawn as whichever of the two sorts first, and
  // every copy of that water carries the same dots.
  const asDrawn = (key) => {
    const leg = geo.legs[key];
    const back = Object.keys(geo.legs).find((other) => other < key && geo.legs[other].from === leg.to && geo.legs[other].to === leg.from && geo.legs[other].routing === leg.routing);
    return back && reverses(geo.legs[back].d, leg.d) ? back : key;
  };
  const traces = new Map();
  const trace = (key) => {
    if (!traces.has(key)) traces.set(key, traced(pathLines(geo.legs[key].d)));
    return traces.get(key);
  };
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
    // A routing's legs that are the route's own (its base, listed first) are
    // the route's line already: a routing draws its other legs, never a
    // dotted copy over the route, and one with no other leg is not drawn.
    const own = new Set([item.legs.laden, item.legs.ballast]);
    const alternatives = (item.alternatives || [])
      .map((alt) => ({ alt, legs: alt.legs.filter((key) => !own.has(key)) }))
      .filter((routing) => routing.legs.length)
      .map(({ alt, legs }) => {
        const altGroup = altLayer.appendChild(svgEl("g", { class: "atlas-alt", "data-item": item.id, "data-alt": alt.id }));
        for (const key of legs) line(altGroup, "atlas-alt__line", geo.legs[asDrawn(key)].d);
        return { alt, legs, group: altGroup, lines: legs.flatMap((key) => pathLines(geo.legs[key].d)) };
      });
    const ballastLines = ballast ? pathLines(ballast.d) : null;
    return {
      item,
      group,
      ballastNodes: [ballastCasing, ballastNode].filter(Boolean),
      ballastLines,
      // The ballast leg where it is drawn: moved beside the laden leg at each width.
      ballastDrawn: ballastLines,
      ladenLines: pathLines(laden.d),
      alternatives,
    };
  });
  frame.appendChild(svg);
  const drawnAlt = new Set(drawn.flatMap((d) => d.alternatives.map((a) => a.alt)));

  let state = { filter: "all", selected: null, focus: null };
  let hovered = null;
  // What the caller was last told is under the pointer, with the routes sharing its water and whether it raised it.
  let told = "";
  // The type of the pointer that last went down on the map.
  let pointer = "";
  // A press on the map not yet released, and whether the paint order waits for its release.
  let pressed = false;
  let unpainted = false;
  let k = ww / Math.max(frame.clientWidth, 1);

  const visible = (item) => state.filter === "all" || item.segment === state.filter;
  const picked = () => (state.selected ? drawn.find((d) => d.item.id === state.selected) || null : null);

  /* Paint order, as the comment above says: the list's order, the route
   * pointed at raised in its layer, the route picked over all of them, each
   * group moved only where its order changes, and none during a press. */
  const paint = () => {
    if (pressed) {
      unpainted = true;
      return;
    }
    unpainted = false;
    const current = picked();
    const raised = drawn.find((d) => d.item.id === hovered && d !== current) || null;
    const rest = drawn.filter((d) => d !== current);
    arrange(altLayer, rest.flatMap((d) => d.alternatives.map((a) => a.group)));
    arrange(routeLayer, [...rest.filter((d) => d !== raised), ...(raised ? [raised] : [])].map((d) => d.group));
    if (!current) return;
    const focus = current.alternatives.find((a) => a.alt.id === state.focus) || null;
    arrange(pickedLayer, [...current.alternatives.filter((a) => a !== focus), current, ...(focus ? [focus] : [])].map((part) => part.group));
  };
  /* A press on the map: from the pointer going down, or from the mouse
   * events a tap brings after the touch's own pointer is up, to the
   * release. A focus that leaves a row of the list as the press begins
   * clears the route it raised, and the order it would paint then waits for
   * the next frame, after the click the release brings in its own task. */
  const press = () => {
    pressed = true;
  };
  const release = () => {
    if (!pressed) return;
    pressed = false;
    if (unpainted) {
      requestAnimationFrame(() => {
        if (unpainted) paint();
      });
    }
  };

  const setHover = (id, sharing, asked) => {
    const others = sharing || [];
    const key = id ? (asked ? "asked " : "") + [id, ...others].join(" ") : "";
    if (key === told) return;
    told = key;
    if (id !== hovered) {
      hovered = id;
      for (const d of drawn) d.group.classList.toggle("is-hover", d.item.id === id);
      for (const ring of markLayer.querySelectorAll(".atlas-edge[data-item]")) ring.classList.toggle("is-hover", ring.getAttribute("data-item") === id);
      svg.classList.toggle("is-pointing", Boolean(id));
      paint();
    }
    if (on.hover) on.hover(id, others, Boolean(id && asked));
  };

  /* Every line within half a band of a pointer, nearest first: each route
   * shown by its laden leg and, with a route picked, that route by its
   * ballast leg as drawn and by each other routing drawn for it. */
  const near = (event) => {
    const ctm = svg.getScreenCTM();
    if (!ctm) return [];
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse());
    const reach = g.HIT * GEOMETRY.HALF * k;
    const found = [];
    for (const d of drawn) {
      if (!visible(d.item)) continue;
      const own = d.item.id === state.selected;
      const lines = own && d.ballastDrawn ? [...d.ladenLines, ...d.ballastDrawn] : d.ladenLines;
      found.push({ id: d.item.id, own, alt: null, distance: lineDistance(p, lines) });
      if (own) for (const a of d.alternatives) found.push({ id: d.item.id, own, alt: a.alt.id, distance: lineDistance(p, a.lines) });
    }
    return found.filter((c) => c.distance <= reach).sort((a, b) => a.distance - b.distance);
  };
  /* What the lines near a pointer point it at, { id, alt } or null: the
   * route picked keeps it unless another route's line is nearer by a quarter
   * of the band, and one of its routings takes it from the route's own line
   * by the same margin. Among routings equally near, the one on show comes
   * first, so a second click puts it away. */
  const aim = (found, touch) => {
    const margin = g.HIT * GEOMETRY.HALF * GEOMETRY.HALF * k;
    const route = found.find((c) => c.own && !c.alt) || null;
    const routings = found.filter((c) => c.alt).sort((a, b) => a.distance - b.distance || Number(b.alt === state.focus) - Number(a.alt === state.focus));
    const routing = routings[0] && (!route || routings[0].distance < route.distance - margin) ? routings[0] : null;
    const mine = routing || route;
    const others = found.filter((c) => !c.own);
    if (others.length && (!mine || others[0].distance < mine.distance - margin)) {
      // A finger cannot tell two lines this close apart: a tap between them picks neither.
      if (touch && others.length > 1 && others[1].distance - others[0].distance <= margin) return null;
      return { id: others[0].id, alt: null };
    }
    return mine ? { id: mine.id, alt: routing ? routing.alt : null } : null;
  };
  const sharingOf = (found, id) => [...new Set(found.map((c) => c.id))].filter((other) => other !== id);
  /* The lines a pointer finds a route by, as `near` takes them: its laden
   * leg and, with the route picked, its ballast leg as drawn and its other
   * routings. */
  const pointable = (d) => [
    trace(d.item.legs.laden),
    ...(d.item.id === state.selected ? [...(d.ballastDrawn ? [traced(d.ballastDrawn)] : []), ...d.alternatives.flatMap((a) => a.legs.map(trace))] : []),
  ];
  /* What the line under the map can name in this view, for the room the
   * caller keeps for it: each route shown, with the most routes a pointer
   * can find beside it. A pointer that finds a route lies within half a band
   * of a point of its lines, and the routes it finds beside it within half a
   * band of the pointer: all of them lie within a band of that point. So at
   * points half a band apart along each line in the view, every route
   * within a band and a quarter (half the spacing more) is taken, a set
   * that holds what any pointer near that point finds. Returns [id, ids]
   * pairs, every route shown at least once (with no ids where no pointer
   * finds another beside it), and no set that another of its own holds. */
  const waters = () => {
    const reach = g.HIT * GEOMETRY.HALF * k;
    const far = reach + reach + reach * GEOMETRY.HALF;
    const [vx, vy, vw, vh] = view();
    // A point of a line further out than this takes no pointer in the view.
    const out = reach + reach * GEOMETRY.HALF;
    const shown = drawn.filter((d) => visible(d.item)).map((d) => ({ id: d.item.id, lines: pointable(d) }));
    const pairs = [];
    for (const route of shown) {
      const sets = [[]];
      for (const { segments } of route.lines) {
        for (const [a, b] of segments) {
          const steps = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / reach));
          for (let i = 0; i <= steps; i += 1) {
            const x = a.x + ((b.x - a.x) * i) / steps;
            const y = a.y + ((b.y - a.y) * i) / steps;
            if (x < vx - out || x > vx + vw + out || y < vy - out || y > vy + vh + out) continue;
            const ids = shown.filter((other) => other !== route && within({ x, y }, other.lines, far)).map((other) => other.id);
            if (!sets.some((set) => ids.every((id) => set.includes(id)))) sets.push(ids);
          }
        }
      }
      for (const set of sets) {
        if (!sets.some((other) => other.length > set.length && set.every((id) => other.includes(id)))) pairs.push([route.id, set]);
      }
    }
    return pairs;
  };
  /* The route a label names, with the routing it names where it names one. */
  const labelled = (event) => {
    const node = event.target.closest ? event.target.closest("[data-item]") : null;
    return node && labelLayer.contains(node) ? { id: node.getAttribute("data-item"), alt: node.getAttribute("data-alt") } : null;
  };
  const tapsAllowed = () => frame.clientWidth >= g.CODES_FROM;
  /* Where a pointer last was on the map, to the fraction of a pixel its
   * events give. A click gives whole pixels only (Chromium), and in water
   * routes share the fraction can decide between them: a click within a
   * pixel of it aims there, so it opens what the line under the map names. */
  let spot = null;
  const track = (event) => {
    spot = { clientX: event.clientX, clientY: event.clientY };
  };

  svg.addEventListener("pointermove", (event) => {
    track(event);
    if (event.pointerType === "touch") return;
    const label = labelled(event);
    if (label) {
      setHover(label.id, []);
      return;
    }
    const found = near(event);
    const target = aim(found, false);
    setHover(target ? target.id : null, target ? sharingOf(found, target.id) : []);
  });
  svg.addEventListener("pointerleave", () => setHover(null, []));
  svg.addEventListener("pointerdown", (event) => {
    pointer = event.pointerType;
    track(event);
    press();
  });
  svg.addEventListener("pointerup", track);
  svg.addEventListener("mousedown", press);
  // Released anywhere, as a press may end off the map or be taken by a scroll, a drag, a menu or another window.
  const releases = ["pointerup", "pointercancel", "mouseup", "contextmenu"];
  for (const type of releases) window.addEventListener(type, release, true);
  window.addEventListener("blur", release);
  svg.addEventListener("click", (event) => {
    const touch = (event.pointerType || pointer) === "touch";
    if (touch && !tapsAllowed()) return;
    const within = spot && Math.abs(spot.clientX - event.clientX) < 1 && Math.abs(spot.clientY - event.clientY) < 1;
    const target = labelled(event) || aim(near(within ? spot : event), touch);
    if (!target) return;
    if (target.alt) {
      if (on.alternative) on.alternative(target.alt);
    } else if (target.id !== state.selected && on.select) {
      on.select(target.id);
    }
  });

  // Each label's width as drawn, kept by text and size once the faces are in;
  // a width taken while a face is loading is the fallback face's. A map whose
  // frame has left the page stops listening (stop, below).
  const widths = new Map();
  let widthsAt = "";
  const forget = () => {
    if (!svg.isConnected) {
      stop();
      return;
    }
    widths.clear();
  };
  if (document.fonts) document.fonts.addEventListener("loadingdone", forget);
  const measure = (text, className, font) => {
    const size = px(font);
    if (size !== widthsAt) {
      widths.clear();
      widthsAt = size;
    }
    const key = className + " " + text;
    if (widths.has(key)) return widths.get(key);
    probe.setAttribute("class", "atlas-label " + className);
    probe.setAttribute("font-size", size);
    probe.textContent = text;
    const width = probe.getComputedTextLength();
    if (!width) return text.length * font * mg.CHAR_EM;
    if (!document.fonts || document.fonts.status === "loaded") widths.set(key, width);
    return width;
  };
  // The face's reach above and below its baseline at this size, which is the
  // height of a label's box whatever its letters.
  const extent = (font) => {
    probe.setAttribute("class", "atlas-label");
    probe.setAttribute("font-size", px(font));
    probe.textContent = words.title;
    const b = probe.getBBox();
    return b.height ? { ascent: -b.y, descent: b.height + b.y } : { ascent: font * mg.ASCENT, descent: font * mg.DESCENT };
  };

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
    const ring = g.EDGE_RING * k;
    const inset = ring + g.EDGE_STROKE * k;
    const haloWidth = GEOMETRY.RING_WIDTH * k + GEOMETRY.RING_WIDTH * k * GEOMETRY.HALF;
    const lineHeight = font * g.LEADING;
    const width = frame.clientWidth;
    const face = extent(font);
    clear(markLayer);
    clear(labelLayer);

    for (const d of drawn) {
      if (d.ballastLines && d.item.legs.beside) {
        d.ballastDrawn = d.ballastLines.map((points) => offsetLine(points, mg.BALLAST_GAP * k));
        const moved = pathString(d.ballastDrawn);
        for (const node of d.ballastNodes) node.setAttribute("d", moved);
      }
    }

    const selected = state.selected ? byId.get(state.selected) : null;
    let mode = selected ? "route" : "none";
    // What a label keeps clear of (dots and rings, then each label placed,
    // and the rows of those labels, whose baselines it should not share); the
    // named points a place's name must be nearest its own of (the ports' dots,
    // then every passage and side of the map a picked route's lines use) and
    // the names placed so far; and the lines it should not cross, each leg
    // once however many routes sail it.
    const taken = [];
    const placedRows = [];
    const named = [];
    const names = [];
    const legs = new Set();
    const lines = [];
    const nameAt = (key, x, y) => named.push({ key, edge: false, left: x, top: y, right: x, bottom: y });
    const dotAt = (x, y) => {
      markLayer.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(x), cy: px(y), r: px(dot + GEOMETRY.RING_WIDTH * k) }));
      markLayer.appendChild(svgEl("circle", { class: "map-port-dot", cx: px(x), cy: px(y), r: px(dot) }));
      taken.push({ left: x - dot - gap, top: y - dot - gap, right: x + dot + gap, bottom: y + dot + gap });
    };
    // The ring sits on the frame's edge, so it is set in by its radius and stroke and shows whole.
    const edgeAt = ([x, y]) => [x - wx < wx + ww - x ? x + inset : x - inset, y];
    const ringAt = ([x, y], item) => {
      markLayer.appendChild(svgEl("circle", { class: "atlas-edge" + (item && item === hovered ? " is-hover" : ""), cx: px(x), cy: px(y), r: px(ring), "data-item": item }));
      taken.push({ left: x - inset, top: y - inset, right: x + inset, bottom: y + inset });
    };
    // A block is a small table: each line's code at its left and, in a column
    // a COLUMN_GAP after the widest code, its figure. Its box is the box its
    // letters cover at the size drawn; `owns` holds the named points it names,
    // and is null for a routing's name, which names no place; `point` is the
    // place it names that has no dot, a passage or a side of the map.
    const blockOf = (anchor, owns, rows, gapFrom, point) => {
      for (const row of rows) for (const part of row.parts) part.width = measure(part.text, part.className, font);
      const widest = (column) => Math.max(0, ...rows.map((row) => (row.parts[column] ? row.parts[column].width : 0)));
      const column = rows.some((row) => row.parts.length > 1) ? widest(0) + font * g.COLUMN_GAP : 0;
      const height = lineHeight * (rows.length - 1) + face.ascent + face.descent;
      const baselines = rows.map((row, index) => face.ascent + lineHeight * index);
      return { anchor, owns, rows, baselines, column, width: column ? column + widest(1) : widest(0), height, gap: gapFrom, names: point || null };
    };
    const write = (block, className) => {
      const group = labelLayer.appendChild(svgEl("g", { class: className }));
      const where = block.box;
      // One column follows the side it was placed on, so a name left of its point ends at it; two start at the left.
      const align = block.column ? "start" : where.align;
      const x = align === "end" ? where.right : align === "middle" ? (where.left + where.right) * GEOMETRY.HALF : where.left;
      block.rows.forEach((row, index) => {
        const y = where.top + face.ascent + lineHeight * index;
        row.parts.forEach((part, column) => {
          const attrs = {
            x: px(column ? where.left + block.column : x),
            y: px(y),
            "font-size": px(font),
            "text-anchor": align,
            "data-item": row.item || null,
            "data-alt": row.alt || null,
          };
          const halo = group.appendChild(svgEl("text", { ...attrs, class: "atlas-label halo " + (part.className || "") }, part.text));
          halo.style.strokeWidth = px(haloWidth);
          group.appendChild(svgEl("text", { ...attrs, class: "atlas-label " + (part.className || "") }, part.text));
        });
      });
    };
    // An anchor is a box: a loading area's ports, or a point.
    const at = (x, y) => ({ left: x, top: y, right: x, bottom: y });
    // The lines a routing's name minds: its own, and the others it could be
    // read as naming, its route's line (with its ballast leg as drawn, once
    // the route is picked) and other routings and, with nothing picked,
    // every other route's line and routing shown.
    const routingLines = (d, a) => ({
      own: a.legs.map(trace),
      others: [
        trace(d.item.legs.laden),
        ...(d.item.id === state.selected && d.ballastDrawn ? [traced(d.ballastDrawn)] : []),
        ...d.alternatives.filter((b) => b !== a).flatMap((b) => b.legs.map(trace)),
        ...(state.selected
          ? []
          : drawn.filter((e) => e !== d && visible(e.item)).flatMap((e) => [trace(e.item.legs.laden), ...e.alternatives.flatMap((b) => b.legs.map(trace))])),
      ],
    });
    // Returns whether every block found a place; `dry` asks only that, and
    // leaves the page and what is taken as they were.
    const place = (blocks, dry, steps = mg.SHIFTS) => {
      const placed = placeBlocks(blocks, {
        taken: dry ? [...taken] : taken,
        rows: dry ? [...placedRows] : placedRows,
        named: dry ? [...named] : named,
        names: dry ? [...names] : names,
        // Inside the view with room for the halo, which the frame would cut.
        view: { left: box.left + haloWidth, top: box.top + haloWidth, right: box.right - haloWidth, bottom: box.bottom - haloWidth },
        step: font * mg.SHIFT,
        steps,
        lines,
        // Lines nearer than half the pointer's band are one line to the eye.
        apart: g.HIT * GEOMETRY.HALF * k,
        room: { x: font * g.ROOM_ACROSS, y: font * g.ROOM_DOWN },
        reach: font * g.BASELINE_REACH,
        level: font * g.ROOM_DOWN,
        slack: k,
        // A quarter of the pointer's band, by which a click tells two lines apart.
        margin: g.HIT * GEOMETRY.HALF * GEOMETRY.HALF * k,
      });
      if (!dry) for (const block of placed) if (block.box) write(block, "atlas-block");
      return placed.every((block) => block.box);
    };

    if (!selected) {
      // Every route shown: a ring where its line leaves the map, a dot at each loading port, a block of labels at each loading area.
      const shown = new Set(items.filter(visible).map((item) => item.id));
      for (const d of drawn) {
        if (!shown.has(d.item.id)) continue;
        for (const point of geo.legs[d.item.legs.laden].edges) ringAt(edgeAt(point), d.item.id);
        for (const key of [d.item.legs.laden, ...d.alternatives.flatMap((a) => a.legs)]) legs.add(key);
      }
      for (const cluster of clusters) {
        if (!cluster.items.some((id) => shown.has(id))) continue;
        for (const portId of cluster.ports) {
          dotAt(geo.ports[portId].x, geo.ports[portId].y);
          nameAt(portId, geo.ports[portId].x, geo.ports[portId].y);
        }
      }
      lines.push(...[...legs].map(trace));
      if (width >= g.CODES_FROM) {
        // Each loading area's block with its figures where every block still finds a place, else codes alone.
        const blocks = (figures) => clusters
          .map((cluster) => {
            const rows = cluster.items.filter((id) => shown.has(id)).map((id) => {
              const item = byId.get(id);
              const parts = [{ text: item.label, className: "atlas-label__code" }];
              if (figures && item.figure) parts.push({ text: segmentsText(item.figure, decimals), className: "atlas-label__figure atlas-label__figure--" + item.basis });
              return { item: id, parts };
            });
            const [x0, y0, x1, y1] = cluster.box;
            return rows.length ? blockOf({ left: x0, top: y0, right: x1, bottom: y1 }, cluster.ports, rows, dot + gap) : null;
          })
          .filter(Boolean);
        const withFigures = width >= g.FIGURES_FROM && place(blocks(true), true);
        place(blocks(withFigures));
        mode = withFigures ? "figures" : "codes";
        // The alternatives each route's line carries, named where there is still room.
        place(drawn
          .filter((d) => shown.has(d.item.id))
          .flatMap((d) => d.alternatives.filter((a) => a.alt.whole_label && a.alt.label_at).map((a) => ({
            ...blockOf(at(a.alt.label_at[0], a.alt.label_at[1]), null, [{ parts: [{ text: a.alt.whole_label, className: "atlas-label__alt" }] }], gap),
            lines: routingLines(d, a),
          }))), false, g.ROUTING_SHIFTS);
      }
    } else {
      // The route picked: where its lines leave the map, its ports, its alternatives' names, its passages.
      const current = picked();
      const keys = [selected.legs.laden, selected.legs.ballast, ...(selected.alternatives || []).flatMap((alt) => alt.legs)].filter(Boolean);
      // Its ballast leg where it is drawn, beside the laden one.
      if (current.ballastDrawn) lines.push(traced(current.ballastDrawn));
      for (const key of [selected.legs.laden, ...current.alternatives.flatMap((a) => a.legs)]) legs.add(key);
      for (const key of keys) for (const point of geo.legs[key].edges) ringAt(edgeAt(point), null);
      const portIds = [...new Set(keys.flatMap((key) => [geo.legs[key].from, geo.legs[key].to]))];
      for (const portId of portIds) {
        dotAt(geo.ports[portId].x, geo.ports[portId].y);
        nameAt(portId, geo.ports[portId].x, geo.ports[portId].y);
      }
      const passages = (selected.passages || []).map((name) => geo.passages.find((p) => p.name === name)).filter(Boolean);
      // One name a side of the map where its lines leave across the Pacific, at the middle of that side's rings.
      const middle = wx + ww * GEOMETRY.HALF;
      const edges = ["west", "east"]
        .map((side) => ({ key: "edge " + side, points: keys.flatMap((key) => geo.legs[key].edges).filter(([x]) => (x < middle) === (side === "west")).map(edgeAt) }))
        .filter((edge) => edge.points.length)
        .map((edge) => ({ key: edge.key, x: edge.points[0][0], y: edge.points.reduce((sum, [, y]) => sum + y, 0) / edge.points.length }));
      lines.push(...[...legs].map(trace));
      place(portIds.map((portId) => blockOf(at(geo.ports[portId].x, geo.ports[portId].y), [portId], [{ parts: [{ text: geo.ports[portId].name, className: "atlas-label__port" }] }], dot + gap)));
      // A routing's name goes by its point, where it shows apart from the
      // route, or failing water no line of the route crosses there, by another
      // point of its own line: its point is often where its legs meet, at a
      // cape, where every place beside it lies across one leg or the other.
      const routingName = (alt) => {
        const text = alt.map_label ? segmentsText(alt.map_label, decimals) : alt.short;
        const block = blockOf(at(alt.label_at[0], alt.label_at[1]), null, [{ item: selected.id, alt: alt.id, parts: [{ text, className: "atlas-label__alt" }] }], gap);
        const own = current.alternatives.find((a) => a.alt === alt);
        block.along = own ? alongFrom({ x: alt.label_at[0], y: alt.label_at[1] }, own.lines, font * g.ALONG) : [];
        block.lines = own ? routingLines(current, own) : null;
        return block;
      };
      // While a routing is shown from its toggle its name alone is written:
      // where routings share water, a name on it could be another's.
      place((selected.alternatives || [])
        .filter((alt) => alt.label_at && drawnAlt.has(alt) && (!state.focus || alt.id === state.focus))
        .map(routingName));
      // Every passage and side of the map its lines use is a place a name could
      // be read as, named or not: each name lies nearer its own than any of
      // them, so the Pacific's name never sits by a canal left unnamed.
      const passagePoints = passages.map((p) => ({ key: p.name, edge: false, ...at(p.x, p.y) }));
      const edgePoints = edges.map((edge) => ({ key: edge.key, edge: true, ...at(edge.x, edge.y) }));
      named.push(...passagePoints, ...edgePoints);
      place([
        ...passages.map((p, i) => blockOf(at(p.x, p.y), [p.name], [{ parts: [{ text: p.name, className: "atlas-label__passage" }] }], gap, passagePoints[i])),
        ...edges.map((edge, i) => blockOf(at(edge.x, edge.y), [edge.key], [{ parts: [{ text: words.edge, className: "atlas-label__passage" }] }], inset + gap, edgePoints[i])),
      ]);
    }
    // The probe keeps no text or label class between drawings, so the svg holds only what it draws.
    probe.textContent = "";
    probe.removeAttribute("class");
    if (on.labels) on.labels(mode, waters);
  };

  const show = (next) => {
    state = { ...state, ...next };
    const selected = state.selected ? byId.get(state.selected) : null;
    titleNode.textContent = selected ? selected.heading : words.name || words.title;
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
    paint();
    layout();
  };

  const unobserve = onWidthChange(frame, () => layout());
  // A text of one fixed size that only the faces and the text's spacing can
  // widen: when a face arrives, or a reader's own style spaces letters or
  // words wider (WCAG 1.4.12), every label is measured and placed again, so
  // none runs past the frame until the next change of width.
  const spacing = probe.parentNode.appendChild(svgEl("text", { class: "atlas-probe__spacing", "font-size": mg.PORT_FONT }, words.title));
  let spaced = spacing.getBBox().width;
  const respace = new ResizeObserver(() => {
    const now = spacing.getBBox().width;
    if (now === spaced || !svg.isConnected) return;
    spaced = now;
    widths.clear();
    layout();
  });
  respace.observe(spacing);
  function stop() {
    unobserve();
    respace.disconnect();
    if (document.fonts) document.fonts.removeEventListener("loadingdone", forget);
    for (const type of releases) window.removeEventListener(type, release, true);
    window.removeEventListener("blur", release);
  }
  show({});
  return { show, stop, hover: (id) => setHover(id, [], true) };
}
