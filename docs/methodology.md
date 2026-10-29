# Methodology

How a voyage is built from the seeds and priced by the engine: each rule, where
it comes from, and where the code applies it. The site's Method views and the
research note say the same in prose; this page is the record the code points to.

## The TCE

TCE = (gross freight + other revenue - commission - voyage costs) / voyage days,
net of commission, over the whole round voyage, the ballast leg included
(Baltic Exchange, Guide to Market Benchmarks v8.8, Appendix 3, page 98).
Voyage costs are bunkers, port charges, canal tolls, EU allowances and, when the
owner pays it, the war risk premium. Operating and capital costs are not voyage
costs. `src/voyage/engine.py`, mirrored in `src/engine.js`.

## Legs and distances

- The laden leg runs from the load port to the discharge port; the ballast leg
  from the discharge port, the Baltic's TCE delivery port, back to the load port
  (Appendix 3). For a trip time charter (S4A) the owner's TCE counts the ballast
  from the redelivery area back to delivery, as the guide counts a time
  charter's ballast time (section 7.4.3, pages 35 and 36).
- Distances are searoute 1.6.0 over Eurostat's SeaRoute network, computed once by
  `scripts/routes.py` under four routings (the shortest; Suez avoided; Panama
  avoided; both). Each line starts at the network's node nearest its port.
  Amsterdam is asked from IJmuiden, its node being behind the lakes, and the 14
  miles of the North Sea Canal are added (NGA Pub. 151, page 44); the stretch
  from the port is added at Port Hedland and Jubail, where the node lies 10 nm
  or more out in open water (`src/voyage/sea_routes.py`).
- Miles inside emission control areas are measured on the line against polygons
  built from MARPOL Annex VI Appendix VII and the area regulations, in force on
  the voyage date (`src/voyage/eca.py`).

## Days

- Steaming days = distance x (1 + 5 percent weather margin) / (24 x speed)
  (Appendix 3).
- Tankers: the port, waiting and canal days of the route's TCE description.
- Dry bulk: the laytime of the route's terms in calendar days: Saturdays and
  Sundays excepted terms count five working days in seven, Sundays and holidays
  included terms every day, plus the turn time; loading at the port's own scale
  has no published rate and is left out. The guide's dry terms set no time at a
  canal, so a dry routing through one leaves the transit and any wait out and
  says so.

## Speed and fuel

- Tankers sail at the laden and ballast speeds their descriptions name, at which
  the Baltic prices its TCEs (Appendix 3); the 11 knot pairs are the guide's Eco
  speeds. Bulk carriers, whose route terms name no speed, sail at the fastest
  pair the guide prints for the ship: the study's choice, labelled as such.
- Consumption is linear between the published pairs and follows a power law
  fitted to them outside.
- A ship without a scrubber burns MGO inside an emission control area, in a port
  inside one and at berth in an EU port, and VLSFO elsewhere.

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

## Carbon

EU allowances = covered emissions x phase in x allowance price x dollars per
euro. Coverage is 100 percent between two EEA ports and within a port of call,
50 percent into or out of the EEA (Directive 2003/87/EC, Article 3ga); the
phase in 40, 70 and 100 percent for 2024, 2025 and 2026 (Article 3gb), with
methane and nitrous oxide from 2026 (Annex I) at warming potentials of 28 and
265. On a trip time charter the charterer provides and pays for the trip's
allowances (BIMCO ETS Allowances Clause 2022) and the owner surrenders them
(Article 3gc). FuelEU Maritime's penalty is shown for one voyage's share and
kept out of the TCE.

## War risk

An additional premium is a percentage of hull value charged on entering a listed
area for up to seven days there; each further seven days inside, or part of
them, is another period, counted from the days inside the Gulf west of the
Strait of Hormuz, the load port's days and any delay there included; each Red
Sea passage is one period. On spot voyage charters the premium is usually the
charterer's and the Baltic's TCEs leave it out, so the engine's payer input
defaults to the charterer and the premium is shown beside the owner's TCE.

## Paper

A time charter index and its FFA are gross hire, so a voyage's net TCE is
grossed up by its commission before the basis is taken (section 7.4.3). The FFA
is the strip over the voyage's days from the fixture date, each day at its
month's FFA, on the latest curve that could be traded on that date. The hedge is
5TC days equal to the voyage's days, or route FFA tonnes equal to its cargo.

## Empty inputs

A value with no dated public source is empty: it counts as zero, the field says
why, and the result names it among what the TCE leaves out. Nothing is filled
with an assumption, and no input is tuned to an anchor.
