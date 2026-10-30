# Design

The voyage economics study joins a series of sites that share one design system: the portfolio's tokens,
type scale, light and dark themes and components, as crack-spread-study and jkm-ttf-arbitrage use them. This
document records what the study inherits unchanged, the one thing it adds (its data palette), how each view is
built, and how the site meets the study's own requirements (Part 8).

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
- **Faces.** Fraunces for the view titles (weight 500), the overview's verdict and the calculator's live
  sentence (weight 400), always with a stated weight; Figtree (the openly licensed stand in for the portfolio's
  Satoshi) for every word, weight 400 set on the body because the file's default instance is Light; JetBrains
  Mono for figures in table cells and for what a chart sets in the tick style (axis ticks, the Paper chart's
  basis labels), nothing else. Fonts are the siblings' files, byte for byte, with their sha256 in
  `vendor/README.md`.
- **Figures.** Inside a sentence a figure keeps the sentence's face with tabular lining digits. The three headline
  facts of the overview use proportional figures at display size, set in Figtree 600, never in Fraunces.
  Negative figures in prose use the minus sign the faces carry; in table cells the hyphen minus, so a copied
  value pastes into a spreadsheet.
- **Banned.** All caps and small capitals, eyebrows over headings, positive letter spacing, middle dots joining
  metadata, arrows after links, glassmorphism, gradients, box shadows, tinted cards, grids of identical rounded
  cards, one highlighted word in a headline, emoji. A long dash appears nowhere: no em dash or en dash in any file,
  on the site or in the PDF text (`tools/check-dashes.mjs` for the files, `scripts/note.py` for the PDF).
- **Theme.** `data-theme` on `html`, set before first paint from `localStorage` key `nc-theme` (shared with the
  portfolio on the same origin), the T key and the round toggle button, `theme-color` rewritten. System
  `prefers-color-scheme` is ignored, as the portfolio ignores it.
- **Focus.** The portfolio's rule: a 2px `--accent` outline 4px off the element (2px off a chart). Never removed.
- **Paths.** Every path is relative: the site is served from `/voyage-tce-model/`. `scripts/serve.py` serves the
  repository under that subpath only, and `tools/check-paths.mjs` fails on a leading slash.

## Part 2. The data palette, the one thing this study adds

The siblings draw every series in ink and tell series apart by line style. This study has three kinds of thing
that must be told apart at a glance and that recur on several views, so it names a palette for them. Each hue
was chosen for what it stands for, then the set was checked against this site's own surfaces, `#FBFAF8` light
and `#17181C` dark: the OKLab difference, times 100, between adjacent slots under the Machado, Oliveira and
Fernandes (2009) simulation of protanopia and deuteranopia at full severity, with a target of 8, and in normal
vision, with a floor of 15. Every slot is at least 3:1 against its
surface, so a mark can be read alone; text never wears these colours (labels and figures stay in `--text` and
`--text-muted`, with a swatch beside them).

### Legs and fuel zones (the map)

| Role | Light | Dark | Contrast light / dark | Why this colour |
|---|---|---|---|---|
| Laden leg | `--text` `#17181C` | `--text` `#FBFAF8` | 17.01 / 17.01 | The leg that earns the freight, drawn solid in ink, the strongest mark on the map. |
| Ballast leg | `--text-muted` `#6A6E76` | `--text-muted` `#A6A9B0` | 4.90 / 7.54 | The unpaid repositioning leg: the same route language, quieter, and dashed (8 4) so it never depends on colour. |
| VLSFO, open sea | `#487ec1` | `#5187cb` | 4.00 / 4.80 | The fuel burnt outside emission control areas; the same harbour blue as the bunker cost family, because it is most of that cost. |
| MGO, inside an ECA | `#00a278` | `#0fab81` | 3.13 / 6.05 | The 0.10 percent sulphur zone: a sea green that marks ECA segments on the map, the ECA polygons' 10 percent wash, and MGO in the fuel split. |
| HSFO, behind a scrubber | `#954000` | `#a24c00` | 6.69 / 3.02 | Only when the scrubber input is on; a rust that sits apart from both blues. It never shares a chart with the accent. |

The check, the three fuel slots in this order: light worst adjacent separation 15.3 (deuteranopia), normal
vision 17.9; dark 15.1 and 17.9; all PASS.

Of this set the site draws only the map's part: the laden and ballast legs and, over them, the sea green of the
stretches inside an emission control area, each named in the map's legend. The VLSFO and HSFO slots, their mark
and swatch classes and the ECA wash token stay defined in `styles/tokens.css` and `styles/components.css` for a
fuel split and ECA polygons that no view draws.

### Cost families (the bridge, the Routes chart, the Detours chart, the Carbon chart)

| Family | Light | Dark | Contrast light / dark | Why this colour |
|---|---|---|---|---|
| Bunkers | `#487ec1` | `#5187cb` | 4.00 / 4.80 | Fuel, the largest voyage cost on every route: harbour blue, the calmest hue, so the biggest block is not the loudest. |
| EU ETS allowances | `#006f2f` | `#137837` | 6.07 / 3.18 | Carbon: a deep green, read as environmental without the bright green of a "good" status. |
| War risk premium | `#9c8600` | `#a58f00` | 3.46 / 5.51 | Hazard: an ochre, the warning family without borrowing the status warning yellow; kept apart from the brick accent (an OKLab separation of 23.9 light and 18.2 dark in normal vision, 18.8 and 9.2 at the worst simulated colour vision deficiency, both above the target of 8) so a premium never looks like the result. |
| Canal tolls | `#614fb6` | `#6958c0` | 6.10 / 3.17 | Violet, a hue no other family or the map uses, so a toll in the Suez detour reads as its own thing. |
| Port charges | `#c765ac` | `#cc69b1` | 3.42 / 5.26 | An orchid; ports are empty on every route (no public figure), and when entered they stand apart from fuel and carbon. |

The check, the five families in this order (bunkers, ETS, war risk, canals, ports): light worst adjacent
separation 11.5 (protanopia, war risk beside ETS), normal vision 18.7; dark 11.1 and 18.5; all PASS (target 8,
floor 15 for normal vision). On the site two families stack only on the Routes chart, bunkers then EU
allowances; the bridge gives each family a row of its own with a swatch beside its name, the Detours chart sets
the war risk ochre against ink, and the Carbon chart is all ETS green. Commission, a revenue deduction rather
than a voyage cost, is drawn as an ink outline, the house sign for a negative step, never as a family colour.

### The accent

The brick `--accent` stays the portfolio's "one thing", one mark to a chart: the voyage result in the bridge, its
bar and its figure, on the overview (with the TCE in the sentence under the table) and in the calculator; the
base TCE rule of the calculator's tornado; the best speed on its speed chart, dot and label; on the Map, the
route picked, its laden leg solid and its ballast leg dashed beside it, over a casing of the ground so it stands
off the land (with nothing picked the Map carries no accent). A family colour never stands in for it, and it
never appears beside HSFO. On the Map the accent shares the drawing with the ECA sea green and the muted line of
every other route; the OKLab separations measured in both themes all pass the target of 8 and the floor of 15
for normal vision, the closest being the dark ECA green under deuteranopia:

| Accent against | Normal vision, light / dark | Worst simulated, light / dark |
|---|---|---|
| ECA sea green | 31.5 / 27.5 | 18.5 / 8.9 |
| The muted line | 17.1 / 21.9 | 11.6 / 17.0 |

### How an input shows where it comes from

Every field of the calculator carries one of seven statuses, written under the field before its source or its
reason. The inputs tables of the overview and the calculator carry the same words in a Status column: an empty
input in the muted ink, a visitor's own figure at weight 600, never red. Every field's border is drawn in
`--text-muted` (4.90:1 on the light page, 7.54:1 on the dark), solid, dotted or dashed by its status, so a field
can be found at the 3:1 that form controls need.

| Status, as written | Treatment | Example, as the calculator shows it |
|---|---|---|
| Sourced | the value in `--text`; under the field the status word in `--text` at weight 600, then the document and its date in `--text-muted` | VLSFO price on C3 in the week to 23 October 2026: 940.00 USD a tonne, "Sourced. Star Asia Shipbroking weekly market report, week 43 of 2026, 23 October 2026" |
| Derived | as sourced, with the rule and the figures it rests on | Days loading on P7: 10.24, "Derived. GMB v8.8 page 80: 66,000 t at 10,000 t a day SSHEX, five working days a week, plus 24 hours turn time" |
| Study's choice | the value in a dotted field, the reason in the source line | Laden speed on C3: 14.0 knots, "Study's choice. The fastest of the laden speeds GMB v8.8 page 78 gives for BCI182 (14, 13, 12 and 11 knots), since the C3 terms name no speed" |
| Left out of the TCE | a zero in a dashed field: a cost the Baltic's TCE leaves out too, which the visitor may enter | War risk premium, the Gulf, on TD3C: 0.00 percent of hull value a period, since the Baltic's TD3C TCE description names no war risk premium |
| No public figure | an empty dashed field reading "No public figure" in the muted ink, the reason in the source line; it counts as zero and the "Leaves out" sentence names it | Port charges at loading on TD22: "No public figure. No public per call figure; the Baltic uses Cory Brothers' estimates, which are not published" |
| Scenario input | the figure in `--text-muted`: zero in the base case, for the visitor to set | Days of ship to ship transfer: "Scenario input. A scenario input, zero in the base case: the days of a ship to ship transfer, which have no public figure" |
| Your figure | the value typed; the source line reads "Your figure." before the source it replaced, and a Reset button restores the default | any field the visitor edits |

Assumed values are never shown as sourced: an edited field says "Your figure" before the source it replaced, the
source line under the bridge and the calculator's charts names every figure changed, and an empty or left out
cost stays in the "Leaves out" sentence printed under every TCE until the visitor fills it.

## Part 3. The views

Progressive disclosure, as the siblings: the page opens on one view; the others are reached by the nav, each at
its own hash (`#/map`, `#/overview`, `#/calculator`, `#/routes`, `#/detours`, `#/carbon`, `#/paper`,
`#/method`), and an empty address opens the Map. The Map and every view from Routes on open with a title in
Fraunces, one takeaway sentence and its key chart, whose source line names the documents it reads and the day
they were retrieved; the overview opens on its verdict and the calculator on its presets. Method, assumptions, data and a view's own panels sit behind buttons inside the view,
each an `h2` holding a full width button that opens its section by `grid-template-rows`, the sibling's component.
The open sections are written to the address (`#/routes?open=method,data`), so a view can be linked as it is
read, and a section is built the first time it opens. Nothing is a card.

### 1. Map (`#/map`, default)

- **The question:** what each route earns a day, and what the other ways to sail it would cost. The title says
  so; the takeaway, one sentence of at most about thirty words written by the export, sets the highest of the
  Baltic's TCEs against the lowest, both of the same day.
- **The map** (`src/map.js`, `atlasMap`): every route of the study on one equirectangular map, 110 degrees west to
  155 degrees east, each laden leg a line from its loading port, the other routings the study prices dotted, a
  small ring where a line leaves the map across the Pacific and where it comes back. Each loading area carries a
  block of labels, one line a route: its code and, where every block still finds a place with them, its TCE,
  right aligned, the Baltic's in ink and the engine's estimates in the muted ink, as the key under the map says.
  The other routings are named on open water where there is room. Under 420px of map the labels and taps give way
  to the list beside it.
- **A route picked** (a click on its line or its label, a row of the list, or `#/map?route=TD3C`): the map frames
  it at the window's shape (from Python, `view`; under 600px of map a taller frame, `view_tall`), draws it in the
  accent with its ballast leg dashed beside it and its ECA stretches in sea green, its other routings dotted in
  ink and named with what each changes ("Round the Cape: +31.5 days, TCE 210,173"), every other route a thin muted
  line. Its ports and the passages that decide between its routings are named. The column beside the map gives
  the route's heading, the routes whose line runs with it (one step away each), its TCE, round voyage days (with a
  bar of ballast, laden, port and waiting) and laden miles, its other ways to sail it with a "Show on the map"
  toggle each, the calculator link, then its freight, break-even, costs, war risk and what it leaves out, its
  links and its sources.
- **The list:** one row a route, grouped by basis (dry bulk at the engine's estimate, dirty and clean tankers at
  the Baltic's TCE, the detour study apart under its own column heads), highest TCE first, each row its code, ship
  class and ports, the other ways it could sail after a dotted sample, its TCE with the Baltic's qualifier words
  and its round voyage days, and a thin bar of its TCE on one linear scale for every route. A row that is not a
  TCE like the others (S4A's trip) is pinned last, outside the order, with no bar. Filters (every route, dry bulk,
  dirty tankers, clean tankers) head the list and are written to the address (`segment=`). Four facts follow the
  list, each a link into its route. Behind buttons: every route side by side in a table, and how to read the map.
- **Built from** `data/atlas.json` (the items, their figures, alternatives, frames and words) and the `atlas` block
  of `data/map.json` (the lines, ports and passages), both written by the export (`src/voyage/atlas.py`,
  `src/voyage/routemap.py`, the words in `src/voyage/pages.py`).

### 2. Overview (`#/overview`)

- **The verdict (the view's `h1`, Fraunces 400):** "A VLCC on TD22, Galveston to Ningbo, at the Baltic's
  assessed USD 58.22 million in the week to 23 October 2026, earns an estimated USD 463,639 a day over a 111.1
  day round voyage; freight of USD 17.34 a tonne would only cover the voyage costs priced." Figures from
  `data/overview.json`, written by the export.
- **Three facts** under it, in one row from 768px and stacked below: "TCE, round voyage from Ningbo" (USD a day),
  "Freight that covers the voyage costs priced" (USD a tonne, with the lump sum in its note) and "Bunkers in the
  voyage costs priced" (percent; 100.0 on TD22, whose only other cost, port charges, has no public figure, so its
  note gives the bunker bill, USD 4.51 million, and its share of the freight, 7.7 percent). Each has a note and
  its as-of date in `--text-muted`. Not cards: three label and value pairs separated by space, with a hairline
  above the row.
- **The bridge** (the one orchestrated motion, Part 5): a table, one row per step from gross freight to the
  result: gross freight and other revenue (ink fill), commission (ink outline), bunkers, port charges, canal
  tolls, EU ETS allowances and war risk premium (family colours, a swatch beside each name), the voyage result
  (the accent). A step with no figure keeps its row, says why once, in the figure's place ("Left out: no public
  per call figure", "None on this routing", "None: no EEA port"), with no line under its name repeating it, and
  draws no bar; the calculator's bridge uses the same words. Figures in JetBrains Mono at the right. The heading
  says where the freight goes; the sentence under the table divides the result by the days, "Over 111.1 days
  (54.9 in ballast, 51.2 laden and 5.0 in port and waiting), the result is a TCE of USD 463,639 a day.", the TCE
  in the accent.
- **The map**, beside the bridge from 1100px and under it below. Its title gives each leg's routing and miles:
  "TD22 sails round the Cape of Good Hope, Galveston to Ningbo laden by the Strait of Malacca, 15,231 nautical
  miles, and back in ballast by the Sunda Strait, 15,054; 829 miles of each leg lie inside the North American and
  US Caribbean emission control areas." The laden leg is solid in ink, the ballast leg dashed in muted ink and
  drawn beside it, the ECA stretches over both in sea green, the ports ink dots ringed in `--bg` with their names
  placed by the page at the size it draws them (Part 4). Land from Natural Earth 1:110m and the route lines
  projected by Python into SVG paths.
- **The date and source of every input** follow the bridge and the map, full width under both and in the muted
  source style, so on a phone the figures come first; then the "Leaves out" sentence, full width too: what the
  TCE leaves out, and that it is an estimate, not a forecast.
- **Buttons:** "Method" (the Baltic's round voyage TCE and the engine against the Baltic in 13 weeks),
  "Assumptions" (what the TCE leaves out, the ship's speeds and consumptions, the port days), "Data" (every input
  with its value, its status and its source).
- **Featured voyage:** TD22 in the week to 23 October 2026, set in `src/voyage/export.py`. The Baltic assesses
  TD22 as a lump sum in dollars, so its rate converts without a licensed Worldscale flat rate, and its weekly
  report printed TD22's TCE in all 13 weeks studied, so the engine can be set beside it every week; TC20, the
  other lump sum route, has a printed TCE in 2 of them. The calculator opens on the same voyage.

### 3. Calculator (`#/calculator`)

- **Title and lead:** "Price a voyage", then "Choose a route and a dated market. Every field starts from its
  source or says why it is empty, and every change prices the voyage again with the same engine as the rest of the
  study."
- **Presets:** two rows of `aria-pressed` text buttons. The first holds the 14 routes (C3, C5, P7, S4A, TD3C,
  TD22, TD20, TD25, TC2, TC14, TC1, TC5, TC20, TD34), each opening at its latest dated market; the second the
  dated markets of the route chosen, its anchors among them (TD22's 13 weeks, TC20's 2, three TD3C rates reported
  in dollars a tonne), 30 presets in all; a market button shows its date short ("23 Oct 2026") with the full
  label as its accessible name, so several sit on a row on a phone. A preset fills every field with its value
  and its status (sourced, derived, the study's choice, left out of the TCE or scenario input), or leaves it
  empty with the reason.
- **Inputs in five steps,** each opened by its own button, any number open at once: Ship (the Baltic's ship, its
  published speeds and consumptions with the power law fitted to them, the laden and ballast speeds, MGO burnt at
  sea, a scrubber), Route (the routing of each leg where the study computes more than one, each option leading with
  its distance, then distances, miles inside ECAs, port and canal days), Market
  (freight basis and value, Worldscale flat rate, cargo, bunker prices by grade, the allowance price, dollars per
  euro, the ETS year), Costs (port charges, canal tolls, the dated war risk premiums of the listed areas the
  routing enters, hull value, crew war bonus, ship to ship and other costs, who pays the premium, and the periods
  the engine counts), Advanced (weather margin, commission, other revenue, days and fuel waiting to transit a risk
  area or in a transfer, fuel in port, the VLSFO emission class, FuelEU in or out).
- **Outputs,** redrawn at once on every change: the live sentence in Fraunces 400 ("At these inputs the voyage
  earns USD 463,639 a day over 111.1 days." on the opening voyage); the Baltic's own TCE beside it while a preset
  that has one is unchanged; the freight that earns a target TCE (zero by default, the freight that only covers
  the voyage costs priced) in USD a tonne, Worldscale points and a lump sum, or the hire a day on a trip; the
  bridge; the "Leaves out" sentence.
- **Under both columns:** a tornado of the five shocks (freight and bunker prices 10 percent lower or higher,
  laden and ballast speed 1 knot slower or faster, one day less or more waiting, the EU allowance price 20
  percent lower or higher), the widest first, its title naming the input that moves the TCE most; and the TCE
  against laden speed from one knot below the slowest published speed to one knot above the fastest, in 0.25
  knot steps, solid between the published speed pairs and dashed where consumption is extrapolated, with a legend
  saying so, the best speed marked by the accent dot and the priced speed by an open dot. On a trip charter no
  speed chart is drawn, and a note says why.
- **Buttons:** "Method", "Speed across markets" (the best speed at low, middle and high freight and bunker
  prices, and the textbook result tested), "Assumptions" (what this voyage leaves out, what each status means),
  "Data" (every input as it now stands, with its status and its source).
- **State in the hash:** `#/calculator?preset=latest-c5&open=market` keeps the preset and the open steps, so a
  priced voyage can be linked; edits to single fields and routings are not written to the address.

### 4. Routes (`#/routes`)

- **Takeaway:** "At August 2026 prices bunkers are all of the sourced voyage costs on 7 of the 12 routes and, on
  the 5 that touch the EEA, EU allowances are 12.6 to 17.4 percent of them; a Hormuz war risk premium at the low
  end of the latest dated range, 7.5 to 10.0 percent of hull value (Marsh, 22 July 2026), would cost the
  charterer of a TD3C cargo 6.48 times the voyage's fuel bill, 8.64 times at the top of the range."
- **Chart:** the sourced voyage costs of the 12 routes at the August 2026 market, in dollars a day of the round
  voyage, one bar a route split into bunkers and EU allowances and grouped by segment (dry bulk, dirty tankers,
  clean tankers). Its title: "Sourced voyage costs run from USD 17,330 a day on P7 to USD 38,654 on TD3C; on the 7
  routes that do not touch the EEA they are bunkers alone, since port charges and canal tolls have no public
  figure." Port charges and canal tolls are named, not drawn. Under the chart, a note on the S4A trip charter,
  on the routes priced in other views (TC20 and TD34 in the calculator and on Detours, TC23 on Carbon) and the
  link to the Baltic routes map (https://nathancouturier.github.io/baltic-freight-routes/).
- **Buttons:** "The routes, one by one" (a table: each route's code and name, ship, cargo, commission, laden
  distance by routing with the one priced marked, the share of its miles inside ECAs, port days for loading,
  discharging and waiting, round voyage days, sourced voyage costs a day, EU allowances as a share of them, and
  the bunker hub), "The Gulf loadings with the Hormuz premium" (a second table, apart from the chart because the
  premium would swamp it: hull value, days inside the Gulf, seven day periods, the charterer's premium in dollars
  and a tonne, and the premium over the voyage's bunkers, 5.22 to 6.48 times at 7.5 percent), "Method"
  (distances and routings, miles inside ECAs, the bunker hub rule, the common market),
  "Assumptions" (port charges, canal tolls, speeds, laytime as port days, the S4A trip, and what each TCE leaves
  out), "Data" (the 25 distances checked against NGA Pub. 151, 20 of them within 2 percent, and the downloads).

### 5. Detours (`#/detours`)

- **Takeaway:** "Round the Cape an LR2 from Jubail to Rotterdam sails 31.5 more days and needs USD 128.94 a
  tonne more freight to earn what it earns by Suez before Suez tolls; for a VLCC loading in the Gulf, each further
  seven days inside costs the charterer another USD 43.61 a tonne of premium at 7.5 percent of hull value." From
  `data/detours.json` (`page.takeaway`); the USD 128.94 a tonne is USD 11.61 million on TC20's 90,000 t
  (`suez_tanker.cape_vs_suez`). The break-even toll (USD 7.00 million for the two transits) and the Red Sea
  premium (USD 4.72 a tonne, the charterer's on the laden transit) are in the chart and the TC20 panel.
- **Chart:** every detour on one scale, what a tonne of cargo costs more than on its base: the freight the owner
  needs to earn the base TCE in ink, the charterer's war risk premium at cost in the war risk ochre, stacked where
  a Hormuz case has both. Ten rows in three groups: the LR2 on TC20 against Suez, the Panamax one way from
  Qingdao to Rotterdam against Suez, the VLCC on TD3C against no premium and no waiting; each bar's value is
  written after it, with what lies behind it where that helps (extra days and tonne miles, periods of premium).
  Its title: "Per tonne of cargo, the Cape costs an LR2's owner far more freight than the Red Sea premium costs
  its charterer; for a VLCC loading in the Gulf, each further week inside adds a period of premium and a week of
  lost earnings."
- **Three panels,** each opened by a button, each a lead sentence and a table: "Suez or the Cape, LR2" (TC20 by
  routing: miles, days, extra tonne miles, voyage costs, the charterer's and the owner's premiums, the owner's
  TCE and what each leaves out, with the toll Suez can bear), "Asia to Europe, Panamax" (the freight each routing
  needs to earn the P4 hire net of commission, and the tolls and waiting Suez and Panama can bear, in dollars and
  in days of hire), "Hormuz, VLCC" (war risk and waiting at the TCE of three dated weeks, then the transfer chain
  off Fujairah and TD34). Then "Method" (with the dated events), "Assumptions" and "Data".

### 6. Carbon (`#/carbon`)

- **Takeaway:** "In 2026, with every tonne covered, a Handy tanker between two EEA ports pays USD 28,708 of
  allowances, 19.8 percent of its sourced voyage costs, a Suezmax from West Africa to Rotterdam USD 200,059 for
  half its emissions at sea and all of them at Rotterdam, and a VLCC from the Gulf to China nothing; in 2024 the
  same voyages paid 40 percent of their emissions' allowances, on carbon dioxide alone."
- **Chart:** horizontal bars of the allowances per day of the voyage, three voyages (TC23 between two EEA ports,
  TD20 into the EEA, TD3C outside it) by three years of the phase in, each bar labelled with its year and the
  share surrendered ("2026, 100 percent surrendered") and its value written after it; the VLCC's rows read "None:
  no EEA port". Every bar wears the one ETS green, whatever its year: the year is written on each bar's label, and
  colour encodes the cost family across the site (the same green is the allowances in the bridge and on the
  Routes chart), so a shade a year would give the hue a second meaning. Its title: "Per day of the voyage the
  2026 allowances take USD 4,117 from the intra-EEA Handy tanker's TCE and USD 5,509 from the inbound
  Suezmax's."
- **Time charter allocation:** under BIMCO's ETS Allowances Clause for time charter parties (2022), a two row
  table of the S4A trip's allowances, charterer and owner: the charterer bears USD 66,690 for the trip, the owner
  USD 57,491 for the ballast leg out of the EEA after redelivery. Its caption gives the phase in year and the
  share (2026, 100 percent of covered emissions, methane and nitrous oxide included) and the allowance price (EUR
  82.31 a tonne at 1.1594 dollars per euro).
- **Buttons:** "Method" (coverage, the phase in, the emission factors and the warming potentials, each with its
  text), "FuelEU Maritime" (the penalty one voyage's energy would carry, shown and kept out of the TCE),
  "Assumptions", "Data" (every voyage and year as a table, and the downloads).

### 7. Paper (`#/paper`)

- **Takeaway:** "In the week to 3 July 2026 a C3 cargo at USD 30.11 a tonne earned USD 37,294 a day grossed up
  by its 5 percent commission, between USD 419 and 4,060 above the 5TC FFA over its days on the two prints of the
  29 June curve, and a C5 cargo between USD 10,109 and 14,961 above it." Under the chart, the C5 fixture of 22
  October 2026 against the C5 index, as one comparison: it matched the index that day as the report's narrative
  gives it, and sat USD 0.10 a tonne (about USD 552 a day) under it on the report's table series. The hedge (76.5
  days of 5TC (182) or 170,000 tonnes of C3 FFA for the C3 voyage) is in the Hedge and basis section.
- **How a voyage meets paper:** the voyage TCE, grossed up by its commission because the 5TC is gross hire, is
  set against the 5TC FFA strip over the voyage's days from the fixture date, each day at its month's FFA, on the
  latest curve tradable on that date: 29 June for week 27, a date Banchero Costa printed twice with different
  values (the chart reads the week 27 issue's print, and the hedge table gives the basis on both), and 25 October
  for week 43 (`data/paper.json`, `capesize` rows: `ffa`, `printings`, `basis_range_usd_day`).
- **Chart:** a dot plot on one USD a day axis, one row for each route and anchor week (C3 and C5, weeks to 3 July
  and 23 October 2026): the grossed up TCE (ink dot), the FFA over the voyage's days (open dot), the spot 5TC on
  the fixture date for the 182,000 t ship (muted dot). The rule between the first two is the basis, and its value
  is written above it ("Basis +419" on C3 in July). Its title: "Grossed up by their commission, the C5 voyages
  earn well above the 5TC FFA over their days in both weeks; C3 sat between USD 419 and 4,060 above it in July,
  depending on which print of the 29 June curve is read, and USD 6,799 a day below it in October."
- **Buttons:** "Hedge and basis" (a box that turns a route FFA typed in dollars a tonne into a TCE with the
  browser engine, since no dated public C3 or C5 quote was found; the hedge table, week by week: freight, TCE net
  and grossed up, the FFA months and the days in each, the strip on the print used, the basis on it and on the
  other print, the freight that would earn the FFA, the spot 5TC, the timing basis, the hedge in 5TC (182) days
  and in days that hedge the net earnings; and the C5 fixture against its index), "Tankers" (TD3C paper against
  physical in the second quarter of 2026, in words, since no public TD3C FFA quote in dollars a tonne was found),
  "Method" (how each FFA settles), "Assumptions" (which curve and which spot figure each week takes, the weather
  margin, the bunker hub), "Data" (the FFA curves as printed).

### 8. Method and data (`#/method`)

- **Takeaway:** one claim: with bunker prices first printed in the same week the engine reads 2.6 to 4.5 percent
  above the Baltic's own TCE for TD22 and TC20, the two routes it can price without a licensed flat rate. The
  exceptions and TD3C at the 2026 flat rate Platts' January pairs imply are in the chart's title; the 52 other
  Worldscale anchors and the 20 of 25 distances within 2 percent of NGA Pub. 151 are in Validation.
- **Chart:** the engine against the Baltic in percent, one dot a week: TD22 and TC20, the two lump sum routes,
  then TD3C at the implied flat rate of USD 20.69 a tonne. An ink dot is priced with bunker prices first printed
  that week, an open dot with prices printed up to a week before, a muted dot with older prices a broker
  reprinted; a rule joins each dot to zero.
- **Buttons:** "Conventions" (every market convention the engine applies, from `data/seed/conventions.json`, with
  the passage of the text it follows), "Formulas", "Validation" (every tanker rate and TCE published in the weeks
  studied, reproduced or not and why; the dry weeks against the 5TC; early March 2026; the Baltic's own TD3C
  calculation of 2017; and the distance checks, linked to the Routes view's Data), "Sources" (the provenance
  manifest: each series, its as-of date, its retrieval, its publisher and its licence), "Limitations" (what the
  study cannot do, and the sites that could not be reached and what each would have added), "Downloads" (the CSV
  files and the research note PDF).

## Part 4. Charts

One approach for every chart, the siblings': SVG drawn by hand in `src/charts.js` (the map in `src/map.js`), marks
coloured by classes that read the roles in `tokens.css` and the palette above, so a theme change needs no redraw.
A chart is drawn again at its column's width whenever the width changes, never scaled through a `viewBox`, so the
type inside it stays the size the stylesheet sets (the map alone scales with its `viewBox`, its strokes kept at
their screen width and its dots and names resized at every width); and it is drawn once more if a web font
finishes loading after the first draw, since its words were measured in the face standing in for it.

Every chart sits in a figure with a heading that states its takeaway, an axis title with its unit, a legend in
words with a swatch beside each item (the speed chart labels its two marks instead), a source line naming its
documents and the day they were retrieved, a readout, and a text alternative: `role="img"` with a `title` and a
`desc` from the artifact. Its figures are also in a table: in the view, in one of its panels, or, for the
calculator's two charts, in a table read by screen readers. The bridge is itself a table.

Marks: lines 2px; bars 14px thick, with a 2px gap of the ground between stacked segments, and a step narrower than
4px drawn as a dot, so a small value never vanishes; dots of radius 4 ringed 2px in `--bg`, an open dot being a
ring of ink; gridlines 1px in `--border`; one value axis to a chart; labels selective, with a 3px `--bg` halo
where one crosses a line.

### Readouts

- A mouse opens a row's readout on hover and closes it on leaving the chart.
- A tap (touch or pen) opens a row's readout; a second tap on the same row, or a tap outside the chart, closes it.
- A chart with a readout takes keyboard focus: the arrow keys step through its rows (down or right forward, up or
  left back), and Escape, or leaving the chart, closes the readout.
- A pointer's readout opens below and right of the pointer, 14px off. It turns to the left where it would pass the
  chart's right edge and flips above the pointer near the bottom of the window, and it stays within the chart's
  width and the window. The keyboard's readout sits beside the focused row's marks, right or left of them and
  centred on them as far as the chart's height allows, or under or over them when neither side has room.
- The readout is a box of the ground with a hairline, no shadow and no tint. Everywhere but the speed chart, the
  figures it shows are also in the view's sentences, labels, tables or downloads; the speed chart's readout alone
  gives the TCE at each step of its grid, whose best and priced speeds are labelled and tabled.

### Axes

- Tick values are measured on the page in their real font (JetBrains Mono at the caption size). Each axis steps
  to the next coarser step on the 1, 2, 5, 10 ladder until neighbouring labels stand at least 8px apart, or, on a
  vertical axis, until neighbouring values are a label's height (15px) apart. A label too wide to centre on the
  first or last tick is set inside the chart from it.
- Axis titles are measured the same way and wrap to the plot's width, each line right aligned inside the plot,
  under the tick values; the speed chart's vertical axis title sits above the plot at its left.

### Rows and labels

- Wide, a row's label sits in a column left of its marks, as wide as the longest label needs. Below 600px, or
  where that column would take more than 42 percent of the width, each label sits above its row on a plate of the
  ground, so no gridline or rule runs through it; group headings sit on the same plates.
- A bar's value is written after its own bar in the label's ink, never in the bar's colour, and the plot is as
  wide as every value allows.

### Chart by chart

- **Bar charts** (Routes, Detours, Carbon): segments stack from zero in the artifact's order. A bar's value is
  measured, and where it does not fit after its bar the figure stays there and the rest wraps at its commas onto
  lines under it, the row growing to hold them, so no value passes the chart's edge. The zero rule runs
  only beside the bars, from the first bar of a run of rows to its last, so none of it shows above a heading or
  between two labels set above their bars; narrow, each piece is the height of its own bar, and a row with no bar
  has none.
- **Dot charts** (Paper, Method validation): each row is a hairline with its dots. Dots that would overlap stack
  10px apart above and below the row's line (a span's two dots keep the line where they can), and the row grows
  to fit. An optional span label is written above the span in the tick style, where it covers no dot and stays
  inside the plot: the Paper chart's basis.
- **Tornado** (calculator sensitivities): two bars per input from the base TCE, an accent rule, outlined for the
  input lower and filled for the input higher, so the two read apart without colour, each labelled at its end
  with the change in USD a day. Where both cases move the TCE the same way (P7's speed row at its latest market,
  for one), the two bars share the row as half-height bars, the lower case above, and one label at the far end
  gives both changes in that order, joined by "and"; with no room past the far end it sits on the other side of
  the base rule.
- **Line chart** (calculator, TCE against speed): a 2px ink line over the speed grid, solid between the slowest
  and fastest published speeds and dashed outside them, where consumption follows the fitted power law; the best
  speed an accent dot and the priced speed an open dot, each labelled. A mark's label is placed where no line, label or dot lies
  under it: above the dot (below it for the priced speed), centred, starting at the dot or ending at it, then
  beside it, then each of those a step of 8px further out, inside the plot. One readout per speed of the grid.
- **The bridge** (overview and calculator): a bar in each row's cell, drawn at the cell's size, with a dotted
  connector carrying the running total from row to row; a step narrower than the bar's thickness is a dot, an
  outlined one for the commission, with a clear gap before its figure. The bars are drawn again only when a
  cell's size changes. They are hidden from assistive technology, the table being their text.
- **The map** (overview): the projected land and the very lines the distances are measured on, with the stretches
  inside an ECA cut out as their own paths, scaled to the column with every line keeping its screen width. A
  ballast leg that starts at the discharge port sails the laden leg's water back, so the page draws it a fixed 3
  screen px beside the laden leg (`BALLAST_GAP` in `src/map.js`, `voyage.ballast.beside` from
  `src/voyage/routemap.py`), recomputed at every width so the two lines stay apart on a phone. Port dots and names
  are sized again at every width, and each name is placed at the size drawn: beside the dot, then above or below
  it, then a step further away, the first place where no line runs through it and no other name or dot lies under
  it, the map's box growing a band where a name at its edge needs one. The map has no hover readout: its title and
  legend state each leg's routing, miles and ECA miles in words.
- **The atlas** (Map): lines keep their screen width; the route picked is the one accent mark (Part 2). Labels are
  placed at the size drawn by the voyage map's box search, bounded on all four sides of the view, so the frame
  never grows: a loading area's block is a small table, codes left and figures right aligned in tabular figures,
  and the mode is chosen by fit, not by width: every block tries code and figure, and if any finds no place every
  block drops to codes. The route under a pointer is found by its distance in map units, not by the line on top,
  since corridors overlap (Ras Tanura to Hormuz carries four routes): a click takes the nearest line within 7px, a
  tap only a line with no other as near, and a label its own route; a click with no line near does nothing.
  **Its readout is the declared exception to the rule above:** no box over the lines, but one line under the map
  that says what the pointer is on (the route's code, class, ports, TCE with its basis and days, and the routes
  sharing that water), else the route picked, else how to start; two lines are kept for it so nothing below moves.
  The map is an image (`role="img"`, its title and description swapped with the route picked) that answers a
  pointer only; its keyboard and screen reader equivalent is the list beside it, which holds every figure the map
  shows, and hovering or focusing a row draws that route at full weight and writes its line under the map.

## Part 5. Motion

The whole list: a section opening (its height by `grid-template-rows`, `--t-fast`, 200ms); the theme's colours
(`--t-base`, 380ms); and **one orchestrated moment: the overview's bridge builds once**, the first time the
overview is drawn, each bar growing from its running total in turn, 60ms apart, each over `--t-base` with
`--ease-out`, 800ms in all for its eight rows. It does not replay on a return to the overview; a width change
while it runs carries it on from where it is, and one after it redraws without motion. The calculator's bridge
and charts redraw at once when an input changes, with no motion. The Map changes state at once, and the scroll
that brings the map into view after a choice below it is instant. `prefers-reduced-motion: reduce` turns all of
it off, the bridge's delays included, and `tools/check-styles.mjs` allows no other keyframe animation.

## Part 6. Accessibility and widths

Keyboard order: skip link, site name, nav, theme toggle, the view's title (focus moves there on a route change,
not on the first load), then the view in reading order, each chart with a readout taking focus in its place.
Section buttons are native buttons with `aria-expanded`, and a closed section is `inert`, so nothing inside it
takes focus or is read. Every chart and the map is an SVG with `role="img"`, a `title` and a `desc` built from the
artifact; the bridge's bars are hidden, its table being their text. Nav links, the theme toggle, preset buttons,
fields and checkboxes are at least 44px tall and section buttons 56px; the Reset and dated premium buttons beside
a field are 32px.

On the Map the keyboard reaches every route through the list: each row is a link to the route's address. A choice
made in the page moves focus to the route's heading in the column (the map first brought into view when it is
above the screen); "Back to the list", Escape (anywhere on the page but a field) and the browser's Back return to
the list with focus on the route's row. Opening a route from the list is a history entry and moving from one route
to another replaces it, so Back closes a route in one step. A filter press is said in the page's status line; a
route the address names but the study does not is said above the list, and the address is rewritten without it.
The map's lines and labels are pointer targets far under 44px: the list beside the map is their equivalent
control, a tap selects only a line with no other as near, and under 420px of map a tap does nothing, so the
list does the work on a phone.

The layout works from 320px with no horizontal page scroll. Below 900px the header is two rows: the name and the
toggle, then the nav, wrapping. The overview's bridge and map sit side by side from 1100px and one above the other
below; at 480px and below the nav's links sit closer, so the header takes two rows at 320px with the Map first and
the last link named "Method" (`tools/check-site.mjs` counts the rows). The Map sets its map left and its column
right from 1100px, the map, the line under it and its legend sticky while the column scrolls; below that the
column follows the map and the source line follows the column, and once a route is picked a map under 600px wide
takes a taller frame. The calculator sets
its inputs left and its outputs right from 1100px; below that its outputs come first, so the result is read
before the fields that move it; at every width a line under each open step gives the TCE as it stands.
At 600px and below the bridge rows become two lines (name, then bar and figure), and a table of more than three
columns, or of three when its cells hold sentences, becomes one block per row, each cell under its column's name,
with the table roles written into the markup. Above that a wide table scrolls inside its own box with its first
column sticky, at least 13em wide, and a caption above it naming the columns off screen.

## Part 7. Artifacts

`data/atlas.json` (every route at its latest dated rate, its figures, its other routings and its frames on the
map, for the Map view), `data/overview.json`, `data/calculator.json` (the presets with their inputs, sources and
routings, the vessels, the routes, the fields and their words), `data/speed.json` (the best speed across markets),
`data/routes.json`, `data/detours.json`, `data/carbon.json`, `data/paper.json`, `data/method.json`, `data/map.json`
(projected land, each voyage's legs and ports, and the atlas of every leg the study sails), `data/engine.json` (the engine's constants), `data/manifest.json` (provenance with the as-of date
of each source), `data/downloads/*.csv`. Written by `scripts/export.py` from the seeds, the caches and the engine,
byte for byte the same on every run (`export --check` in the gate, which also checks the content hashes
`index.html` loads them by). No market figure in the page's scripts (`src/*.js`) comes from anywhere but the
artifacts: their only literals are the unit and drawing constants declared in `tools/check-literals.mjs`. And
`tools/validate-artifacts.mjs` formats every figure in their sentences as the page will and checks that every
format they name is declared.

## Part 8. Review against the study's requirements

- **One view per question.** Eight views, each answering one: what each route earns a day and what the other ways
  to sail it cost (Map), what a voyage earns and where the money goes (Overview), what a voyage on any of the calculator's 14 routes earns at inputs the visitor sets (Calculator),
  what each route costs to run
  (Routes), what a longer or riskier way costs (Detours), what the EU ETS adds (Carbon), how a physical fixture
  compares with the FFA (Paper), and how far the engine can be trusted and where each input comes from (Method
  and data).
- **The answer in one minute.** The site opens on the Map: every route on one map with its TCE beside its loading
  port, the other routings named, and the list of routes with their figures beside it; the overview opens on the
  verdict, three dated facts, the bridge and the map; every other view is one click away in the nav.
- **The detail in five minutes.** Every input of a voyage is a field with its status and its source, and a preset
  rebuilds any of the 14 calculator routes at its latest dated market or at an anchor week.
- **Progressive disclosure.** Each view opens on its answer: the overview on its verdict, the calculator on its
  presets and the TCE they price, the others on a title, a takeaway and a key chart. Method, assumptions, data and
  the view's own panels sit behind buttons, and the open ones are kept in the address.
- **Takeaway titles.** Every chart's heading states what the chart shows, written from the figures it draws: by
  the export for the views, by the calculator from the engine's output for its two charts.
- **Units and sources on every chart.** An axis title with its unit, a legend in words or labels on the marks, a
  source line with the day its documents were retrieved, a text alternative, and the figures in a table (Part 4).
- **Assumed inputs labelled.** Every field and every inputs table says Sourced, Derived, Study's choice, Left out
  of the TCE, No public figure, Scenario input or Your figure, with the source or the reason (Part 2), and every
  TCE is followed by what it leaves out.
- **No template defaults.** No card grid, gradients, shadows, all caps labels, highlighted word, middle dots,
  arrows on links or emoji; `tools/check-styles.mjs` fails on the CSS ones and `tools/check-dashes.mjs` on a long
  dash.
- **320px without sideways scroll.** `tools/check-site.mjs` opens every view at 1440 and 320px and fails if the
  page scrolls sideways; wide tables stack at 600px and below or scroll in their own box.
- **AA contrast in both themes.** Text wears `--text` (17.01) or `--text-muted` (4.90 light, 7.54 dark), and accent
  text `--accent` in light (7.96) and `--accent-bright` in dark (5.15); every data mark is at least 3:1 on its
  ground (Part 2), gridlines and connectors being decorative; form fields' borders reach 3:1 on the page in both
  themes.
- **One motion moment.** The overview's bridge builds once; the only other motion is a section opening and the
  theme's colours, and reduced motion turns all of it off.
- **Keyboard and screen reader.** Every control is a native button, link or field; every chart's readout steps
  with the arrow keys; every chart and the map carries a title and a description from its artifact; the focus ring
  is never removed.
- **Palette documented and validated.** Hex values, reasons and contrast in both themes, with the separations the
  check measured (Part 2).
- **Every figure from an artifact.** No market figure in the page's scripts comes from anywhere but the
  artifacts, and the artifacts rebuild byte for byte in the gate (Part 7).
