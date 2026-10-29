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
 * The laden leg is solid ink, the ballast leg a dashed muted line beside it,
 * and an ECA stretch is drawn over either in the sea green of the 0.10 percent
 * zone. The legend under the map says so in words, so no line depends on its
 * colour.
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
  /* Where a name sits against its baseline, as a share of its size: above
   * the dot, below it, and beside it. */
  ABOVE: 0.25,
  BELOW: 0.85,
  BESIDE: 0.35,
  /* The width of a character of a name, as a share of its size. */
  CHAR_EM: 0.6,
});

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

  const leg = (drawing, kind) => {
    const group = svgEl("g", { class: "map-leg map-leg--" + kind });
    group.appendChild(svgEl("path", { class: "map-leg__line", d: drawing.d, "vector-effect": "non-scaling-stroke" }));
    for (const d of drawing.eca || []) {
      group.appendChild(svgEl("path", { class: "map-leg__eca", d, "vector-effect": "non-scaling-stroke" }));
    }
    return group;
  };
  svg.appendChild(leg(voyage.ballast, "ballast"));
  svg.appendChild(leg(voyage.laden, "laden"));

  const ports = voyage.ports.map((port) => {
    const ring = svgEl("circle", { class: "mark-ring-fill", cx: px(port.x), cy: px(port.y) });
    const dot = svgEl("circle", { class: "map-port-dot", cx: px(port.x), cy: px(port.y) });
    const halo = svgEl("text", { class: "map-port halo", "text-anchor": port.anchor }, port.name);
    const name = svgEl("text", { class: "map-port", "text-anchor": port.anchor }, port.name);
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
  onWidthChange(frame, (renderedWidth) => {
    const k = width / renderedWidth;
    const font = g.PORT_FONT * k;
    const radius = g.PORT_RADIUS * k;
    const gap = g.PORT_GAP * k;
    for (const { port, ring, dot, halo, name } of ports) {
      ring.setAttribute("r", px(radius + GEOMETRY.RING_WIDTH * k));
      dot.setAttribute("r", px(radius));
      let x = port.x;
      let y;
      let anchor = port.anchor;
      if (anchor === "middle") {
        y = port.label_y < port.y ? port.y - radius - gap - font * g.ABOVE : port.y + radius + gap + font * g.BELOW;
      } else {
        x = anchor === "start" ? port.x + radius + gap : port.x - radius - gap;
        y = port.y + font * g.BESIDE;
      }
      // A name that would run past the edge of the box is turned back inside.
      const half = port.name.length * font * g.CHAR_EM * GEOMETRY.HALF;
      if (anchor === "middle" && x + half > x0 + width) anchor = "end";
      else if (anchor === "middle" && x - half < x0) anchor = "start";
      if (anchor === "start" && x + half + half > x0 + width) {
        anchor = "end";
        x = port.x - radius - gap;
      } else if (anchor === "end" && x - half - half < x0) {
        anchor = "start";
        x = port.x + radius + gap;
      }
      if (anchor !== port.anchor && port.anchor === "middle") x = anchor === "end" ? port.x + radius : port.x - radius;
      for (const text of [halo, name]) {
        text.setAttribute("x", px(x));
        text.setAttribute("y", px(y));
        text.setAttribute("font-size", px(font));
        text.setAttribute("text-anchor", anchor);
      }
      halo.setAttribute("stroke-width", px(GEOMETRY.RING_WIDTH * k + GEOMETRY.RING_WIDTH * k * GEOMETRY.HALF));
    }
  });
  return svg;
}
