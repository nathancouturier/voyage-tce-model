# Design

The voyage economics study joins a series of sites that share one design system: the portfolio's tokens,
type scale, light and dark themes and components, as crack-spread-study and jkm-ttf-arbitrage use them. This
document records what the study inherits unchanged, the one thing it adds (its data palette), and how each
view is built. It was written before the site and reviewed against the study brief (section 9).

## Part 1. Inherited unchanged

- **Tokens.** `styles/tokens.css` holds the portfolio's `:root` and `[data-theme="dark"]` blocks verbatim (the
  copy jkm-ttf-arbitrage carries, with the two comments whose middle dot and em dash became commas), the three
  `@font-face` blocks, the one `--ff-body` override and the named chart roles. Contrast on `--bg`, measured by
  the sibling: `--text` 17.01 in both themes, `--text-muted` 4.90 light and 7.54 dark, `--accent` 7.96 light and
  3.79 dark (a mark only in dark, where accent text is `--accent-bright`, 5.15).
- **Unusable tokens.** `--text-dim` (fails text in both themes), `--accent-deep` (2.14 in dark), `--bg-card` and
  `--bg-tint` (a tinted block is the rounded card's relative), the shadows and the grain: used for nothing.
  `--bg-elev` is the field background of a form input, nothing else. `tools/check-styles.mjs` fails on any rule
  that reads them.
- **Faces.** Fraunces for the view titles and the one verdict sentence, always with a stated weight; Figtree
  (the openly licensed stand in for the portfolio's Satoshi) for every word, weight 400 set on the body because
  the file's default instance is Light; JetBrains Mono for figures in table cells and axis ticks and nothing else.
  Fonts are the siblings' files, byte for byte, with their sha256 in `vendor/README.md`.
- **Figures.** Inside a sentence a figure keeps the sentence's face with tabular lining digits. The three headline
  facts of the overview use proportional figures at display size, set in Figtree 600, never in Fraunces.
  Negative figures in prose use the minus sign the faces carry; in table cells the hyphen minus, so a copied
  value pastes into a spreadsheet.
- **Banned.** All caps and small capitals, eyebrows over headings, positive letter spacing, middle dots joining
  metadata, arrows after links, glassmorphism, gradients, box shadows, tinted cards, grids of identical rounded
  cards, one highlighted word in a headline, emoji. A long dash appears nowhere (the check counts zero U+2013 and
  U+2014 in every file, the site and the PDF text).
- **Theme.** `data-theme` on `html`, set before first paint from `localStorage` key `nc-theme` (shared with the
  portfolio on the same origin), the T key and the round toggle button, `theme-color` rewritten. System
  `prefers-color-scheme` is ignored, as the portfolio ignores it.
- **Focus.** The portfolio's rule: a 2px `--accent` outline 4px off the element. Never removed.
- **Paths.** Every path is relative: the site is served from `/voyage-tce-model/`. `scripts/serve.py` serves the
  repository under that subpath only, and `tools/check-paths.mjs` fails on a leading slash.

## Part 2. The data palette, the one thing this study adds

The siblings draw every series in ink and tell series apart by line style. This study has three kinds of thing
that must be told apart at a glance and that recur on several views, so it names a palette for them. Each hue
was chosen for what it stands for, then the set was validated with the dataviz method's validator
(`validate_palette.js`, OKLab differences under protanopia and deuteranopia, Machado 2009 at full severity)
against this site's own surfaces, `#FBFAF8` light and `#17181C` dark. Every slot is at least 3:1 against its
surface, so a mark can be read alone; text never wears these colours (labels and figures stay in `--text` and
`--text-muted`, with a swatch beside them).

### Legs and fuel zones (the map, the voyage strip, the fuel split)

| Role | Light | Dark | Contrast light / dark | Why this colour |
|---|---|---|---|---|
| Laden leg | `--text` `#17181C` | `--text` `#FBFAF8` | 17.01 / 17.01 | The leg that earns the freight, drawn solid in ink, the strongest mark on the map. |
| Ballast leg | `--text-muted` `#6A6E76` | `--text-muted` `#A6A9B0` | 4.90 / 7.54 | The unpaid repositioning leg: the same route language, quieter, and dashed (8 4) so it never depends on colour. |
| VLSFO, open sea | `#487ec1` | `#5187cb` | 4.00 / 4.80 | The fuel burnt outside emission control areas; the same harbour blue as the bunker cost family, because it is most of that cost. |
| MGO, inside an ECA | `#00a278` | `#0fab81` | 3.13 / 6.05 | The 0.10 percent sulphur zone: a sea green that marks ECA segments on the map, the ECA polygons' 10 percent wash, and MGO in the fuel split. |
| HSFO, behind a scrubber | `#954000` | `#a24c00` | 6.69 / 3.02 | Only when the scrubber input is on; a rust that sits apart from both blues. It never shares a chart with the accent. |

Validator, the three fuel slots in this order: light worst adjacent separation 15.3 (deuteranopia), normal
vision 17.9; dark 15.1 and 17.9; all PASS.

### Cost families (the bridge, the cost structure, the detours)

| Family | Light | Dark | Contrast light / dark | Why this colour |
|---|---|---|---|---|
| Bunkers | `#487ec1` | `#5187cb` | 4.00 / 4.80 | Fuel, the largest voyage cost on every route: harbour blue, the calmest hue, so the biggest block is not the loudest. |
| EU ETS allowances | `#006f2f` | `#137837` | 6.07 / 3.18 | Carbon: a deep green, read as environmental without the bright green of a "good" status. |
| War risk premium | `#9c8600` | `#a58f00` | 3.46 / 5.51 | Hazard: an ochre, the warning family without borrowing the status warning yellow; kept 13 or more apart from the brick accent so a premium never looks like the result. |
| Canal tolls | `#614fb6` | `#6958c0` | 6.10 / 3.17 | Violet, a hue no other family or the map uses, so a toll in the Suez detour reads as its own thing. |
| Port charges | `#c765ac` | `#cc69b1` | 3.42 / 5.26 | An orchid; ports are empty on most routes (no public figure), and when entered they stand apart from fuel and carbon. |

Validator, the five families in this order (the stacking order of the cost structure chart): light worst adjacent
separation 11.5 (protanopia, war risk beside ETS), normal vision 18.7; dark 11.1 and 18.5; all PASS (target 8,
floor 15 for normal vision). Commission, a revenue deduction rather than a voyage cost, is drawn as an ink
outline, the house sign for a negative step, never as a family colour.

### The accent

The brick `--accent` stays the portfolio's "one thing": on the overview it marks the TCE bar of the bridge and
nothing else; on a chart it marks one point (today's speed, the anchor week). A family colour never stands in
for it, and it never appears beside HSFO.

### Sourced, derived, empty: how an input shows where it comes from

| State | Treatment | Example |
|---|---|---|
| Sourced | the value in `--text`, a source line under the field in `--text-muted` with the document and its date, linked to the Method view's source table | Singapore VLSFO 822 USD/t, Ship & Bunker, August 2026 average |
| Derived | the value in `--text`, the rule in the source line, starting "From" | Load days 10.24, from 66,000 t at 10,000 t a day, five working days a week, plus 24 hours |
| Empty | an empty field, its placeholder "No public figure", and the reason in the source line; the result's "Leaves out" list names it | Port charges at Galveston: no public per call figure |
| Changed by the visitor | the field keeps its value, the source line reads "Your figure", and a Reset button restores the default | |

Assumed values are never shown as sourced: a field the visitor edits loses its citation, and an empty one adds a
line to the "Leaves out" sentence printed under every TCE.

## Part 3. The views

Progressive disclosure, as the siblings: the page opens on one view; the others are reached by the nav, each at
its own hash (`#/overview`, `#/calculator`, `#/routes`, `#/detours`, `#/carbon`, `#/paper`, `#/method`). Every
view opens with a title in Fraunces, one takeaway sentence, its key chart and the as-of dates of what it reads.
Method, assumptions and data tables sit behind buttons inside the view ("Method", "Assumptions", "Data"), each
an `h2` holding a full width button that opens its section by `grid-template-rows`, the sibling's component.
Nothing is a card.

### 1. Overview (`#/overview`, default)

- **Takeaway sentence (the verdict, Fraunces 400):** "A VLCC on TD22, US Gulf to China, fixed at the Baltic's
  USD 58.22 million in the week to 23 October 2026, earns about USD {tce} a day after USD {costs} of voyage costs;
  it would need USD {breakeven} a tonne to cover them." Figures from `data/overview.json`, written by the export.
- **Three facts** under it, in one row at 768px and above, stacked below: TCE (USD/day), breakeven freight (USD/t
  and lump sum), bunker share of voyage costs (percent). Each with its as-of date and source in `--text-muted`.
  Not cards: three label and value pairs separated by space only.
- **The bridge** (the one orchestrated motion, Part 5): a table of rows, one per line, gross freight down to the
  result and the TCE: gross freight (ink fill), commission (ink outline), bunkers, ports, canals, ETS, war risk
  (family colours, zero rows shown as a hairline with "none sourced" or "none on this route"), result (ink total),
  days, TCE (accent). Figures in mono at the right.
- **The map:** ballast leg dashed in muted ink, laden leg solid in ink, ECA segments over them in sea green, the
  ports as ink dots ringed in `--bg`, port names placed by the page at the size it draws them, beside, above or
  below the dot where no line runs and no other name lies, the map box growing a band for a name at its edge.
  Land from Natural Earth 110m and the route lines projected by Python into SVG paths.
- **Buttons:** "Method" (the round voyage convention and the engine against the Baltic, week by week),
  "Assumptions" (what the TCE leaves out, the ship's speeds and consumptions, the port days), "Data" (every input
  with its value, its status and its source).
- **Featured voyage choice** (Decision 18): TD22 is the only study route whose latest public rate converts to
  dollars without a licensed flat rate, so it is the one that can be shown end to end.

### 2. Calculator (`#/calculator`)

- **Title and sentence:** "Price a voyage." Live TCE in the sentence beside the bridge.
- **Inputs in five steps,** each opened by its own button, one open at a time on narrow screens: Ship (vessel,
  speeds, consumptions, scrubber), Route (Baltic route, routings for each leg, ballast from, distances, ECA miles,
  canal days), Market (freight basis and value, flat rate, bunker prices by grade, EUA and dollar rate, year of
  the ETS phase-in), Costs (port charges, canal tolls, war risk premium, hull value, periods, crew bonus, other),
  Advanced (sea margin, commission, waiting, delay and ship to ship days, FuelEU in or out, VLSFO class).
- **Outputs:** the bridge (live, bars tween over `--t-fast`, figures swap at once), breakeven freight in USD/t,
  WS (when a flat rate is entered) and lump sum, or hire in USD/day for a trip; the "Leaves out" sentence; a
  tornado of the five shocks (freight and bunkers 10 percent, speed 1 knot, port days 1 day, EUA 20 percent);
  TCE against speed with the best speed marked by the accent dot.
- **Presets:** each study route at its latest dated market, and every reproduced anchor week, as `aria-pressed`
  buttons (a route row, then the dated markets of that route); a preset fills every field with its sourced or
  derived default, or leaves it empty with the reason.
- **State in the hash:** `#/calculator?preset=latest-c5&open=market` so a priced voyage can be linked.

### 3. Routes (`#/routes`)

- **Sentence:** how many routes, and the share of each route's distance inside ECAs.
- **Chart:** the voyage costs of every route at the August 2026 market, in dollars a day of the round voyage,
  split into bunkers and EU allowances and grouped by segment (dry, dirty, clean); port charges and canal tolls
  have no public figure and are named, not drawn.
- **Table:** route code, Baltic name, vessel, cargo, commission, laden and ballast distance, ECA miles, port days,
  bunker hub, and what the TCE leaves out. A link to the Baltic routes map
  (https://nathancouturier.github.io/baltic-freight-routes/) beside the title.
- **Buttons:** "Method" (routings, miles inside ECAs, the bunker hub rule, the common market), "Assumptions"
  (port charges, canal tolls, laytime), "Data" (the 21 distances against Pub. 151, and the downloads); the
  Hormuz premiums by route as a table under the chart.

### 4. Detours (`#/detours`)

- **Sentence:** "Round the Cape an LR2 from the Gulf to Rotterdam takes 31.5 more days and needs USD 10.9 million
  more freight to earn what Suez earns; a Hormuz war risk premium of 7.5 percent of hull value adds USD 45 a tonne
  to a VLCC from Ras Tanura." From `data/detours.json`.
- **Three panels,** each opened by a button: Suez against the Cape (TC20), Asia to Europe dry (Panamax, Suez,
  Panama, the Cape), Hormuz (war risk, waiting, ship to ship transfer, TD34). Each: days and distance as bars,
  the freight to stand still in a table, the break even toll or waiting budget as a sentence.

### 5. Carbon (`#/carbon`)

- **Sentence:** the 2026 ETS cost of the intra-EEA, into-EEA and outside voyages, per tonne and per day.
- **Chart:** grouped bars, three voyages by three years (2024, 2025, 2026 phase-in), in the ETS green, the year
  told by position and a direct label, the 2026 bar the darkest step of the same hue.
- **Time charter allocation:** the S4A trip as a two row table, owner and charterer, under BIMCO ETSA 2022.
- **Buttons:** "Method" (coverage shares, phase-in, GWPs, the emission factors), "FuelEU" (the per voyage share,
  shown, not in the TCE), "Data".

### 6. Paper (`#/paper`)

- **Sentence:** the week 27 C3 and C5 voyages against the July 5TC FFA and the hedge size; under the chart, the
  C5 fixture of 22 October against the C5 index. Buttons: "Hedge and basis", "Tankers", "Method", "Data".
- **Chart:** for each anchor week, a dot plot on one USD/day axis: the physical TCE (ink dot), the FFA for the
  voyage month (open dot), the spot 5TC (muted dot), with the basis and timing basis as labelled spans.
- **Tables:** hedge sizes (5TC days, route FFA tonnes), the freight that would earn the FFA, the TD3C paper
  against physical in Q2 2026.

### 7. Method and data (`#/method`)

- Conventions table (from `data/seed/conventions.json`), formulas, the validation table (every anchor with its
  error and reason), sources with links and as-of dates (the provenance manifest), limitations, the blocked
  hosts, CSV downloads, the research note PDF, and the typefaces sentence.

## Part 4. Charts

One approach for every chart, the siblings': SVG drawn by hand in `src/charts.js`, marks coloured by classes
that read the roles in `tokens.css` and the palette above, so a theme change needs no redraw. Every chart has a
title that states the takeaway, axis titles with units, a source line with the retrieval date, a readout or
tooltip on hover and keyboard focus, and a button under it naming its table ("Every line of the bridge", "Every
route by routing"), which reveals a real `table`. Marks follow the dataviz method: 2px lines, bars at most 24px
thick, a 2px `--bg` gap between touching bars, dots of radius 4 with a 2px `--bg` ring, hairline gridlines in
`--border`, one axis per chart, labels selective. Values a visitor would read are always in a table or a label,
never only in a tooltip.

## Part 5. Motion

The whole list: a section opening (grid rows, `--t-fast`); the calculator's bar geometry when an input changes
(`--t-fast`); the theme colours (`--t-base`); and **one orchestrated moment: the overview's bridge builds once on
first load**, each bar growing from its running total in turn, 60ms apart, `--ease-out`, about a second in all.
It does not replay on a route change. `prefers-reduced-motion: reduce` turns all of it off.

## Part 6. Accessibility and widths

Keyboard order: skip link, site name, nav, theme toggle, the view's title (focus moves there on a route change),
then the view in reading order. Every SVG has `role="img"` with a `title` and a `desc` built from the artifact.
Touch targets 44px. The layout works from 320px with no horizontal page scroll: the calculator's inputs stack
above its outputs below 1024px, the bridge rows become two lines (name, then bar and figure) below 600px, and a
wide table scrolls inside its own box with its first column sticky.

## Part 7. Artifacts

`data/overview.json`, `data/calculator.json` (presets, vessels, routes, legs, markets, sources), `data/routes.json`,
`data/detours.json`, `data/carbon.json`, `data/paper.json`, `data/method.json`, `data/map.json` (projected land,
legs and ports), `data/engine.json` (the engine's constants), `data/manifest.json` (provenance with the as-of
date of each source), `data/downloads/*.csv`. Written by `scripts/export.py` from the seeds, the caches and the
engine, byte for byte the same on every run (`export --check` in the gate). No number in `src/` comes from
anywhere else (`tools/check-literals.mjs`).

## Part 8. Review against the brief

- One minute: the overview shows the TCE, where the money goes (the bridge), the breakeven freight, the map, and
  three dated facts; the detours sentence and the paper sentence are one click away.
- Five minutes: every input of a voyage is a field with its source; a preset rebuilds any study route.
- Template defaults avoided: no card grid, no gradients, no all caps labels, no highlighted word, no middle dots,
  no arrows on links, no emoji. One motion moment.
- Palette documented with hex values, reasons and contrast in both themes (Part 2); validated by script.
- Every chart: takeaway title, axis units, source and as-of line, text alternative. Assumed and empty inputs are
  labelled where they appear.
