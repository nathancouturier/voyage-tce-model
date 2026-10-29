# Methodology

How a voyage is built from the seeds and priced by the engine: each rule, where
it comes from, and where the code applies it. The site's Method views and the
research note say the same in prose; this page is the record the code points to.

## The TCE

TCE = (gross freight + other revenue - commission - voyage costs) / voyage days,
net of commission, over the whole round voyage, the ballast leg included
(Baltic Exchange, Guide to Market Benchmarks v8.8, Appendix 3, page 98).
Voyage costs are bunkers, port charges, canal tolls, EU allowances and the war
risk premiums the owner pays. Operating and capital costs are not voyage costs.
`src/voyage/engine.py`, mirrored in `src/engine.js`.

Freight is entered in dollars a tonne, as a lump sum, as hire a day on a trip
charter, or in Worldscale points: freight a tonne = WS / 100 x flat rate. Flat
rates are licensed by the Worldscale Association and no public source states a
study route's flat rate for 2025 or 2026, so the flat rate is the reader's
input, with no default. Commission is one input, address commission and
brokerage together: 5 percent on the dry routes (Baltic, since 2 January 2018)
and 3.75 percent on the tankers.

## Legs and distances

- The laden leg runs from the load port to the discharge port; the ballast leg
  from the discharge port, the Baltic's TCE delivery port, back to the load port
  (Appendix 3). For a trip time charter (S4A) the owner's TCE counts the ballast
  from the redelivery area back to delivery, as the guide counts a time
  charter's ballast time (section 7.4.3, pages 35 and 36).
- Distances are searoute 1.6.0 over Eurostat's SeaRoute network, computed once by
  `scripts/routes.py` under four routings (the shortest; Suez avoided; Panama
  avoided; both) and one more for TD22's laden leg: both canals and the Sunda
  Strait avoided, so the line goes round the Cape of Good Hope and through the
  Strait of Malacca, as the Baltic's own TD3C calculation routes the same laden
  ship (5,897 nm, July 2017). TD22's ballast leg keeps the network's shortest
  line round the Cape, through the Sunda Strait. Each line starts at the
  network's node nearest its port. Amsterdam is asked from IJmuiden, its node
  being behind the lakes, and the 14 miles of the North Sea Canal are added
  (NGA Pub. 151, page 44); the stretch from the port is added at Port Hedland
  and Jubail, where the node lies 10 nm or more out in open water
  (`src/voyage/sea_routes.py`).
- Miles inside emission control areas are measured on the line against polygons
  built from MARPOL Annex VI Appendix VII and the area regulations, in force on
  the voyage date (`src/voyage/eca.py`).

## Days

- Steaming days = distance x (1 + weather margin) / (24 x speed). The 5 percent
  margin is the guide's for tanker TCEs (Appendix 3, page 99). The guide leaves
  a dry route's allowances to its panellists (section 7.4.2, page 35), so the
  same 5 percent on the dry routes is the study's choice, labelled as such;
  without it the Capesize TCEs read 6 to 11 percent higher.
- Tankers: the port, waiting and canal days of the route's TCE description,
  canal days scaled by the transits a routing makes against the routing the
  description assumes.
- Dry bulk: the laytime of the route's terms in calendar days: Saturdays and
  Sundays excepted terms count five working days in seven, Sundays and holidays
  included terms every day, plus the turn time; loading at the port's own scale
  has no published rate and is left out. The guide's dry terms set no time at a
  canal, so a dry routing through one leaves the transit and any wait out and
  says so.
- Days waiting to transit a listed area and the days of a ship to ship transfer
  are scenario inputs, zero in the base case.

## Speed and fuel

- Tankers sail at the laden and ballast speeds their descriptions name, at which
  the Baltic prices its TCEs (Appendix 3); the 11 knot pairs are the guide's Eco
  speeds. Bulk carriers, whose route terms name no speed, sail at the fastest
  pair the guide prints for the ship: the study's choice, labelled as such.
- Consumption is linear between the published pairs and follows a power law
  fitted to them outside.
- A ship without a scrubber burns MGO inside an emission control area, in a port
  inside one and at berth in an EU port, and VLSFO elsewhere. VLSFO is classed
  by its ISO 8217 grade (RMG 380, a heavy fuel oil for the emission factors).
- The speed that maximises the TCE is searched on a 0.01 knot grid from 1 knot
  below the slowest published speed to 1 knot above the fastest.

## Prices and dates

- Bunkers are priced at the hub nearest the load port among Singapore, Fujairah,
  Rotterdam and Houston, the rule the Baltic applies to its tanker TCEs
  (Appendix 3), except C3: its nearest hub, Rotterdam, lies over 4,000 nm off
  the voyage, so it is priced at Singapore, which its ballast leg passes; the
  guide leaves dry bunker prices to its panellists (section 7.4.2).
- A dated market reads no price from after its date: bunkers from the brokers'
  table of the week or of up to seven days before, a reprinted row dated by its
  first printing; the EU allowance price from the latest monthly average before
  the voyage's month; the dollar rate as the mean of the Federal Reserve's H.10
  days of the voyage's month up to its date.
- The common market, August 2026, is a period average: Ship & Bunker's August
  averages where published and its third quarter averages for the other hub
  prices, with the allowance price and dollar rate of August.
- Float sums use `math.fsum`, exactly rounded, so the committed files rebuild
  byte for byte on every supported Python.

## Carbon

EU allowances = covered emissions x phase in x allowance price x dollars per
euro. Coverage is 100 percent between two EEA ports and within a port of call,
50 percent into or out of the EEA (Directive 2003/87/EC, Article 3ga); the
phase in 40, 70 and 100 percent for 2024, 2025 and 2026 (Article 3gb), with
methane and nitrous oxide from 2026 (Annex I) at warming potentials of 28 and
265. On a trip time charter the charterer provides and pays for the trip's
allowances (BIMCO ETS Allowances Clause 2022) and the owner surrenders them
(Article 3gc); the owner bears the ballast leg's. FuelEU Maritime's penalty is
shown for one voyage's share and kept out of the TCE, since it is assessed on a
ship's year. After June 2025 the allowance price is DEHSt's monthly average of
Germany's auctions, a proxy for the common auction platform's: over the 30
months both cover (January 2023 to June 2025) it sat EUR 0.25 a tonne above it
on average (`src/voyage/sources/ec_eua.py`, `proxy_gap`).

## War risk

An additional premium is a percentage of hull value charged on entering a
listed area, for up to seven days there. Each listed area a voyage enters (the
Gulf west of the Strait of Hormuz; the Red Sea and Gulf of Aden) carries its
premium, its entries and the days inside, the load port's days and any delay
there included. The charter's periods are the days inside over seven, rounded
up, never fewer than its entries; each ballast transit is one period.

Who pays follows the charter. On spot voyage charters the premium for the laden
voyage and the stay in the loading area is usually the charterer's (Platts,
8 December 2025). The Baltic's TCEs leave it out too: Appendix 3 (page 98)
admits additional insurance only as a route's description in Appendix 2 sets it
out, and no tanker TCE description names a war risk premium; at the flat rate
Platts' January pairs imply, the engine reads TD3C a few percent above the
Baltic in the war months, where a premium in the costs would put it far above.
So the engine's payer input defaults to the charterer, and that premium is
shown beside the owner's TCE, not in it; the input moves it into the owner's
costs for a fixture that puts it in the freight. The premium for a ballast
leg's approach to the next loading is the owner's unless a charter makes the
charterer pay it (Gard, 21 March 2026), so it is in the owner's voyage costs.
Hull values are Xclusiv's dated five-year-old values; LR1 and Handy tankers
have none, so their premium is empty.

## Validation

- TD22 and TC20 are assessed as lump sums in dollars, so they are priced
  without a flat rate and set against the Baltic's published TCEs week by week,
  each week with the brokers' bunker table of the week or up to seven days
  before (`src/voyage/anchors.py`).
- Platts printed its Persian Gulf to China benchmark in points and dollars
  together in January 2026 (w53.5 and USD 11.07 a tonne; w93 and USD 19.24),
  which implies USD 20.69 a tonne for its own route, whose ports it does not
  state. TD3C's 2026 weeks are priced at that rate as a check only; it is never
  a calculator default.
- The Baltic's TD3C calculation of July 2017 is reproduced for days and fuel;
  it prints no prices.
- Distances are checked against NGA Pub. 151 for 25 port pairs, to 2 percent
  (`src/voyage/distance_checks.py`).

## Paper

A time charter index and its FFA are gross hire, so a voyage's net TCE is
grossed up by its commission before the basis is taken (section 7.4.3). The FFA
is the strip over the voyage's days from the fixture date, each day at its
month's FFA, on the latest curve that could be traded on that date; where the
publisher printed that curve twice with different values (29 June 2026), the
basis is given on both prints. A route FFA in dollars a tonne is turned into a
TCE by the same engine, with the voyage's own costs and days. The hedge is 5TC
days equal to the voyage's days, or route FFA tonnes equal to its cargo.

## Empty and scenario inputs

A value with no dated public source is empty: it counts as zero, the field says
why, and the result names it among what the TCE leaves out. A scenario input
(days waiting to transit a listed area, a ship to ship transfer's days and cost,
other costs, other revenue) is zero in the base case and set by the reader.
Nothing is filled with an assumption, and no input is tuned to an anchor.
