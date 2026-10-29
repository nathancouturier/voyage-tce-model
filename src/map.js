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
 * Numeric literals: MAP_GEOMETRY below, declared in tools/check-literals.mjs.
 */

import { svgEl, imageSvg, px, onWidthChange, GEOMETRY } from "./charts.js";

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
      halo.setAttribute("stroke-width", px(GEOMETRY.RING_WIDTH * k + GEOMETRY.RING_WIDTH * k * GEOMETRY.HALF));
    });
  });
  return svg;
}
