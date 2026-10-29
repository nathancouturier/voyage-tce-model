# Data audit

Every source the study reads, as probed from the build environment on 29 October 2026: the endpoint, what it
covers, its units, its terms, a sample, and what the study does with it. `data/raw/manifest.json` lists every
downloaded file with its URL, retrieval time (UTC) and sha256: 365 entries, all retrieved on 29 October 2026.
The repository commits the four files whose terms allow redistribution and that the build needs offline, under
`data/raw/public/`. Another 39 public files, which need not be committed (large, reissued often, or kept only as
the record behind a cited figure), stay out of git in `data/raw/bulk/`. The remaining 322 stay in
`data/raw/licensed/`, which git ignores; the repository commits only their manifest entries and the figures the
study uses, each with its quote, in `data/seed/`. `tests/test_provenance.py` finds every quoted figure in its
document wherever the raw file is present.

## Sources the pipeline fetches

The five adapters in `src/voyage/sources/` (`baltic`, `nga`, `imo`, `ec_eua` and `frb_h10`) fetch 17 of the
manifest's entries; `scripts/routes.py` runs searoute, which downloads nothing.

| Source | Endpoint | Coverage and units | Terms | Stored |
|---|---|---|---|---|
| Baltic Exchange, Guide to Market Benchmarks v8.8 (September 2026) | `https://www.balticexchange.com/content/dam/balticexchange/consumer/documents/data-services/documentation/ocean-bulk-guides-policies/GMB.pdf` | Route and vessel definitions (Appendix 2, printed pages 76 to 97), tanker TCE method (Appendix 3, pages 98 to 100), forward assessments (Appendix 5, pages 105 to 112); knots, tonnes a day, USD/t, WS, USD/day | Baltic copyright: figures cited with page numbers, not redistributed | licensed; figures in `src/voyage/baltic.py` with page numbers, written to `data/seed/baltic.json` |
| Baltic Exchange, TD3C TCE calculation process (July 2017) | `https://www.balticexchange.com/content/dam/balticexchange/consumer/data-services-/historicalcircular_docs/TD3C-TCE_Calculation_Process_0717.pdf` | The Baltic's worked TD3C TCE: nautical miles, days and tonnes of fuel, no prices | Baltic copyright: figures cited, not redistributed | licensed; figures in `data/seed/anchors.json` |
| NGA World Port Index (Pub. 150) | `https://msi.nga.mil/api/publications/world-port-index?output=json` | 2,951 ports; positions in decimal degrees | US Government work, no copyright claimed under Title 17 U.S.C. | committed (gzipped) |
| NGA Distances Between Ports (Pub. 151), 11th edition, 2001 | `https://msi.nga.mil/api/publications/download?key=16694076/SFH00000/Pub151bk.pdf&type=view` | Port to port distances, nautical miles | US Government work, no copyright claimed under Title 17 U.S.C. | committed |
| searoute 1.6.0 over Eurostat SeaRoute | PyPI `searoute==1.6.0`, with the network bundled in it | Sea routes in nautical miles for the 306 ordered pairs of the 18 study ports under four routings, plus one special leg: 1,225 legs | Apache 2.0; network EUPL 1.2 | results committed in `data/seed/sea_routes.*` |
| IMO resolutions MEPC.328(76), MEPC.361(79), MEPC.117(52), MEPC.201(62), MEPC.392(82) | `https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/MEPC.328(76).pdf`, the same path for the others | ECA coordinates in degrees and minutes (Appendix VII: 47, 206, 45 and 55 points), boundary lines and dates in force | IMO document: boundaries and dates cited with resolution and page, not redistributed | licensed; polygons in `data/seed/eca.json` |
| European Commission, EU ETS auction reports | page `https://climate.ec.europa.eu/areas-action/carbon-markets/eu-emissions-trading-system-eu-ets/auctioning-allowances_en`; reports `https://climate.ec.europa.eu/document/download/<id>_en?filename=cap_report_YYYYMM_en.pdf`, six from March 2024 to June 2025 | Monthly average clearing price of general allowances, EUR/t, January 2023 to June 2025 | CC BY 4.0 | the June 2025 report committed as the parser's fixture; the other five in the bulk store |
| DEHSt, German auction monthly averages (via jkm-ttf-arbitrage, whose weekly refresh keeps them current) | `https://raw.githubusercontent.com/nathancouturier/jkm-ttf-arbitrage/main/data/cache/dehst_eua_german_auction_monthly.csv` | Monthly EUR/t, January 2013 to August 2026; the study uses July 2025 onwards, a proxy for the platform average | CC BY-NC-ND 4.0, "Source: EEX, DEHSt" | committed unchanged |
| Federal Reserve Board H.10 | `https://www.federalreserve.gov/releases/h10/data/FRB_h10_xml.zip` | Daily USD per EUR (RXI$US_N.B.EU), from the release package of every series | Public domain | bulk store; the series from 2 January 2023 to 23 October 2026 committed as `data/cache/usd_per_eur_daily.csv` |

Samples, one for each source:

- Guide to Market Benchmarks: "As per Circular 27/21 all tanker routes were changed to standard commission at
  3.75% (from 2.5%)" (document history, page 2; `data/seed/conventions.json`).
- TD3C note of July 2017: 19.8457 laden days burning 1,389.20 t of IFO, and "Dividing the nett income by the
  duration (46.4852)" (`data/seed/anchors.json`).
- World Port Index: WPI 48340 (Ras Tannurah) at 26.6333 N, 50.1667 E, the TD3C, TC1 and TC5 load port
  (`data/seed/sea_routes.json`).
- Pub. 151: page 104 prints Singapore to Qingdao as 2,466 nm; searoute measures 2,478 nm between the positions
  Pub. 151 prints. 20 of the 25 distances checked fall within 2 percent.
- searoute: Ras Tanura to Ningbo, the TD3C leg, 5,849 nm by the shortest route, through the Strait of Hormuz
  and the Strait of Malacca.
- IMO: Appendix VII of MEPC.328(76) lists 47 points for the Pacific coast, 206 for the Atlantic and Gulf of
  Mexico coasts, 45 for Hawaii and 55 for the United States Caribbean Sea area.
- Commission auction reports: `data/cache/eua_monthly.csv` reads `2025-06,72.06,European Commission,cap_report_202506`.
- DEHSt: `data/cache/eua_monthly.csv` reads `2026-08,82.31,"DEHSt (German auctions, proxy)",2026_report_08`.
- H.10: `data/cache/usd_per_eur_daily.csv` gives an August 2026 mean of 1.1594 dollars per euro over 21
  published days (1.159362 in `data/routes.json`); its last row reads `2026-10-23,1.1199,A`.

DEHSt's monthly average of Germany's auctions stands in for the platform average after June 2025. Over the 30
months both cover, January 2023 to June 2025, it sat EUR 0.25 a tonne above the platform's on average, from 1.58
below to 1.67 above (`proxy_gap` in `src/voyage/sources/ec_eua.py`, tested in `tests/test_sources.py`).

## Sources read once and cited

The other 348 manifest entries are documents read once during the research. The seeds (`data/seed/*.json`)
carry 269 `raw_key` references to 92 distinct entries: 90 of those 348, plus the guide and the 2017 TD3C note.
The code (`src/voyage/` and `scripts/`) names 21 entries, 12 of them also cited by a seed and 9 not (the H.10
package, the DEHSt months, the World Port Index, Pub. 151 and the five IMO resolutions that give the ECA
polygons), and builds the keys of the Commission's six auction reports from their dates. Seeds and code together
use 107 entries. The other 258 are documents read during the research and not cited: site searches, indexes and
feeds used to find documents; other reports of figures the study takes from elsewhere (SSY's Capesize indices,
Fearnleys' and Advanced Shipping's weekly reports and Argus on Rotterdam bunker sales, among others); pages checked
for a figure they turned out not to hold (the Commission's maritime ETS and MRV FAQs hold no VLSFO grade
guidance); the Port of Rotterdam's 2026 tariffs; the worked example candidates set out below; and 53 Suez Canal
Authority circulars, periodicals and toll calculator files read to trace its surcharges and rebates. The study
redistributes none of the read-once documents, and read 62 of the 90 it cites as Hellenic Shipping News (HSN)
republished them.

| Input | Source | Seed |
|---|---|---|
| Bunker prices, August 2026 (common market) | Ship & Bunker's August sales analyses (Singapore VLSFO and HSFO, Fujairah VLSFO) and its port price pages' Q3 2026 quarterly averages for the other prices; the same pages' Q4 2025 averages are kept for an anchor date with no weekly table | `market.json` |
| Bunker prices, anchor weeks | Star Asia Shipbroking weekly reports via HSN (week 49 of 2025; weeks 4, 8, 9, 10, 11, 12, 15, 16, 26, 28, 31, 36, 37, 40, 41, 43 of 2026), each dated by its close of business Friday; Banchero Costa week 27; Intermodal week 11 as a cross-check. Star Asia often reprints a week's table unchanged (weeks 8 and 9, 15 and 16, 36 and 37, 40 and 41 are identical in every cell; Houston's row of 20 March recurs on 10 and 17 April): the study prices with the table of the date and records when each row was first printed. HSN's listing shows no Star Asia post for weeks 50 and 51 of 2025 or weeks 13, 27 and 32 of 2026. | `market.json` |
| War risk premiums and who pays them | Platts (8 December 2025; 1 April, 18 June, 5 October 2026), Marsh to Platts (25 June, 24 July 2026), Gard (21 March 2026) and Windward on Saudi linked ships (30 July 2026), all via HSN | `market.json`, `conventions.json` |
| Crew war bonus terms | The joint ITF and JNG statement on the Warlike Operations Area (6 March 2026), via HSN | `market.json`, `events.json` |
| The Hormuz shuttle | The Wall Street Journal via ChosunBiz (21 September 2026), Windward (30 July, 12 October 2026), Kpler (23 September 2026), all via HSN | `market.json` |
| Hull values | Xclusiv Shipbrokers weekly report, 7 September 2026, 5 year old values (read from the rendered tables); Signal Group via HSN (2 March 2026) for the early March VLCC value, a lower bound | `market.json` |
| Tanker rates and TCEs | Baltic Exchange weekly tanker reports via HSN, 13 weeks ending 12 December 2025 to 23 October 2026 | `anchors.json` |
| Persian Gulf to China and early March 2026 VLCC rates | Platts via HSN (17 January, 4 and 19 March 2026), Argus (4 March 2026), Oilprice.com via Yahoo Finance (3 March 2026) | `anchors.json` |
| Dry rates | Signal Group via HSN (week 27, with the BCI and BDI of 3 July 2026 that fix its 5TC's vessel basis; C3 of 4 September; the Panamax assessment of 11 September), Banchero Costa weeks 27 and 43 | `anchors.json` |
| FFA curves | Banchero Costa dry bulk FFA assessments printed at 29 June (week 26, beside 22 June), 6 July (week 27, beside 29 June) and 25 October 2026 (week 43, beside 18 October); Drewry's TD3C FFA as a TCE, via HSN (February 2026) | `ffa.json` |
| A physical C5 fixture | Banchero Costa week 43: Dampier to Qingdao at USD 14.15/wmt on 22 October 2026, loading 5 to 7 November | `ffa.json` |
| FFA settlement | EEX contract specifications (release 047a, 23 July 2026); ICE Futures Europe rulebook Section TTT Part II E | `ffa.json` |
| Suez Canal | Suez Canal Authority periodicals 16, 17 and 18 of 2026 (surcharges from 15 July 2026) and its New Suez Canal page (transit time); Korea JoongAng Daily via HSN (23 July 2026) reporting the Authority's toll for a ship of one million barrels | `canals.json` |
| Panama Canal | EIA This Week in Petroleum, 27 September 2023; Platts via HSN, 16 April 2026 | `canals.json` |
| Events | EIA Today in Energy (1 February 2024, 26 March 2026); Platts (11 March 2026, citing S&P Global Commodities at Sea; 1 April, 25 June, 24 July, 28 October 2026); the ITF and JNG statement (6 March 2026); the Baltic's tanker reports (30 March, 12 October 2026); ENGINE (9 April 2026), Windward (13 July 2026) and Zawya (22 October 2026), all via HSN | `events.json` |
| Conventions | GMB v8.8; MARPOL Annex VI (MEPC.328(76)), MEPC.361(79) and MEPC.391(81); Directive 2003/87/EC as amended by 2023/959; Regulation 2015/757 Annex I as replaced by 2023/2776; Regulations 2020/1044 and 2023/1805; Directives 2016/802 and 2018/2001; BIMCO ETS Allowances Clause 2022; Platts (8 December 2025, 1 April 2026) and Gard (21 March 2026) on war risk | `conventions.json` |

Each source's endpoint, coverage, units, terms and a sample follow. Endpoints are the URLs in the manifest; an
article republished by HSN sits at `https://www.hellenicshippingnews.com/<article>/`, so only its path is given.
Terms are the licence the manifest records: "Copyright of the publisher" stands for its "Copyright of the
publisher; not redistributed, figures cited with link". Each sample is copied from the seed's quote of the
document. The guide and the 2017 TD3C note are in the table above.

| Source | Endpoint | Coverage | Units | Terms | Sample |
|---|---|---|---|---|---|
| Baltic Exchange weekly tanker reports, via HSN | one article a week, from `/vlcc-tanker-market-steadied-last-week/` (15 December 2025) to `/vlcc-tanker-market-giving-up-past-gains/` (26 October 2026) | 13 weeks ending 12 December 2025 to 23 October 2026: TD3C, TD34, TD22, TD20, TD25, TC1, TC2, TC5, TC14 and TC20 as each week prints them | Worldscale points, or a lump sum in USD (TD22, TC20); TCE in USD/day | Copyright of the publisher | TD3C, week ending 12 December 2025: "at WS125.78 which corresponds to a daily round-trip TCE of $122,676" |
| Platts, tanker freight, via HSN | `/vlcc-rates-rebound-in-h1-jan-on-fleet-consolidation-strong-demand/` (17 January 2026), `/persian-gulf-tanker-rates-spike-as-hormuz-traffic-drops-on-iran-conflict/` (4 March), `/vlcc-rates-face-downward-pressure-as-tankers-flee-gulf-crisis/` (19 March) | Persian Gulf to China, 270,000 t, on 12 December 2025 and 2 and 13 January and 2 March 2026; the Platts VLCC index on 27 February and 3 and 16 March 2026 | USD/t and Worldscale points; USD/day | Copyright of the publisher | "rose 73.8% to w93 or $19.24/mt by Jan. 13, up from w53.5 or $11.07/mt on Jan. 2" |
| Argus Media | `https://www.argusmedia.com/en/news-and-insights/latest-market-news/2796228-vlcc-rates-surge-to-over-20pc-of-fob-value` | Basrah medium, Mideast Gulf to China, 3 March 2026 (context only) | USD a barrel | Copyright of the publisher | "Mideast Gulf to China VLCC rate surged to $15.32/bl on 3 March" |
| Oilprice.com, via Yahoo Finance | `https://finance.yahoo.com/news/24-hour-energy-shock-world-160000254.html` | 3 March 2026; the article names no source, so the figure is recorded and not used as an anchor | USD/t | Copyright of the publisher | "with a Gulf-to-China voyage now costing $89 per metric tonne, up 560% since early January" |
| Signal Group, dry freight, via HSN | `https://www.hellenicshippingnews.com/?p=1140060` (8 July 2026), `/capesize-in-focus-c3-at-a-multi-year-high-as-ordering-accelerates/` (10 September 2026), `/panamax-in-focus-pacific-routes-gain-as-the-index-eases-and-china-bound-thermal-coal-flows-weaken/` (18 September 2026) | Assessments of 3 July, 4 September and 11 September 2026 | USD/t (C3, C5, P7); USD/day (5TC averages); index points (BCI, BDI) | Copyright of the publisher | "Average C5TC earnings climbed to $33,678/day" (3 July 2026) |
| Banchero Costa weekly reports, via HSN | `https://www.hellenicshippingnews.com/wp-content/uploads/2026/06/Bancosta-Weekly-2026-26.pdf`, `.../2026/07/Bancosta-Weekly-2026-27-1.pdf`, `.../2026/10/Bancosta-Weekly-2026-43.pdf` | Baltic indices of 3 July and 23 October 2026; FFA assessments of 29 June, 6 July and 25 October 2026, each beside the previous week's; the bunker table of 3 July 2026; a C5 fixture of 22 October 2026 | USD/t (routes, bunkers; the fixture in USD/wmt); USD/day (time charter averages and FFAs) | Copyright of the publisher | "C3 Tubarao - Qingdao usd/t 33.87 30.08" (23 October 2026, beside the week before) |
| Drewry, via HSN | `/us-india-trade-pact-a-game-changer-for-crude-flows-and-vlccs/` | TD3C FFA converted to TCE for Q1 and Q2 2026, published February 2026 | USD/day | Copyright of the publisher | "in 2Q26, they are likely to be around $93,100pd" |
| European Energy Exchange | `https://www.eex.com/fileadmin/EEX/Downloads/Rules/EEX-Contract_Specifications_for_Trade_Registration/20260723_EEX_Contract_Specifications_for_Trade_Registration_047a_EN_FINAL.pdf` | Release 047a, 23 July 2026: Capesize 5TC (180,000 t and 182,000 t baskets), Panamax 5TC, C3 and C5 futures | USD/day, one day a lot; USD/t for C3 and C5 | Copyright of the publisher | "Contract Volume 1 day Pricing In USD per day" |
| ICE Futures Europe | `https://www.ice.com/publicdocs/contractregs/86_SECTION_TTT_Part_II_E.pdf` | Rulebook Section TTT Part II E, freight contracts: the Baltic settled tanker FFAs, and Platts settled TC5 and Arab Gulf to Japan 75,000 t contracts | USD and cents a tonne | Copyright of the publisher | "18. TD3C FFA - Middle East Gulf to China (Baltic) Future" |
| Ship & Bunker | sales analyses `https://shipandbunker.com/news/apac/537117-analysis-singapore-bunker-sales-continue-at-record-pace-despite-hormuz-crisis` and `https://shipandbunker.com/news/emea/764284-fujairah-bunker-sales-more-than-halve-from-last-year`; port price pages `https://shipandbunker.com/prices/<region>/<area>/<port>` for Singapore, Fujairah, Rotterdam and Houston, as they stood on 28 October 2026 | August 2026 averages; quarterly averages for Q4 2025 and Q3 2026 | USD/t | Copyright of the publisher | "Singapore's average VLSFO price in August was $822/mt, according to Ship & Bunker data" |
| Star Asia Shipbroking weekly reports, via HSN | `https://www.hellenicshippingnews.com/wp-content/uploads/<year>/<month>/Market-report-Week-<n>.pdf` (Market-Report from week 26 of 2026), from `.../2025/12/Market-report-Week-49.pdf` to `.../2026/10/Market-Report-Week-43.pdf` | 17 weekly tables, 5 December 2025 to 23 October 2026 | USD/t: VLSFO 0.5%, HSFO 3.5% and MGO 0.1% at Singapore, Hong Kong, Fujairah, Rotterdam and Houston | Copyright of the publisher | Week 43 of 2026: "SINGAPORE $940 $879 $1334" |
| Intermodal weekly report, week 11 of 2026, via HSN | `https://www.hellenicshippingnews.com/wp-content/uploads/2026/03/Intermodal-Report-Week-11-2026.pdf` | Bunker prices of 6 March 2026, page 7; a cross-check only | USD/t: MGO, 380cst and VLSFO at Rotterdam, Houston and Singapore | Copyright of the publisher | MGO at Rotterdam, 1,070.3, from the page's letter spaced text "1,0 7 0.3" |
| Xclusiv Shipbrokers weekly report, via HSN | `https://www.hellenicshippingnews.com/wp-content/uploads/2026/09/xclusiv-2026_09_07.pdf` | 7 September 2026, September 2026 column, 5 year old Japanese built ships (dry, page 5; tankers, page 6) | USD | Copyright of the publisher | VLCC, 5 Year: USD 157,000,000, read from the rendered table; the text layer of these tables is rotated and cannot be quoted |
| Signal Group, VLCC values, via HSN | `/vlcc-second-hand-prices-at-decade-highs/` | 2 March 2026 | USD | Copyright of the publisher | "Today, it is indicated above USD 120 million" |
| Platts, war risk and Hormuz, via HSN | for example `/war-risk-insurance-cost-off-highs-but-still-elevated-in-persian-gulf/` (1 April 2026); the others of 8 December 2025 and 11 March, 18 June (with a BRS research note and European tanker sources), 5 October and 28 October 2026 | War risk premiums from 2024 to 15 June 2026, and a multiple reported on 5 October 2026; Hormuz transits from 28 February to 25 October 2026 | Percent of hull and machinery value per seven day period; ships a day | Copyright of the publisher | "The AWRP had reached around 2.5% of the Hull and Machinery value of ships per seven-day period in the Persian Gulf earlier in March" |
| Marsh, to Platts, via HSN | `/war-cover-available-for-hormuz-trades-but-transit-challenges-remain-insurers/` (25 June 2026), `/middle-east-shipping-insurance-costs-rise-on-hormuz-risks-marsh/` (24 July 2026) | The pre-war level, the level after the June peace deal and the levels of 22 July 2026 | Percent of hull value | Copyright of the publisher | "Premiums for vessels transiting the Bab al-Mandab Strait currently stand at 0.5% of hull value, according to Baker" |
| Gard, via HSN | `/the-middle-east-conflict-frequently-asked-questions/` | 21 March 2026 | None: who pays the premium under VOYWAR 2013 | Copyright of the publisher | "VOYWAR 2013 only addresses the cost of a deviation to avoid a dangerous place, not waiting time" |
| Windward, via HSN | `/two-closed-corridors-hormuz-and-bab-el-mandeb-both-effectively-shut-to-tanker-traffic/` (30 July 2026), `/tanker-attacks-spread-beyond-the-strait-of-hormuz-as-gulf-freight-costs-soar/` (12 October 2026), and the ceasefire report of 13 July 2026 | 8 July to 12 October 2026 | USD a transit; barrels | Copyright of the publisher | "National oil companies are paying tankers $50 million per transit to ship crude to ship-to-ship transfer areas off Fujairah and Oman" |
| Kpler, via HSN | `/saudi-export-rerouting-amid-gulf-of-oman-sts-bottlenecks-amplify-vlcc-intensity-of-meg-flows/` | 23 September 2026 | Days of a shuttle's round voyage in the Gulf of Oman | Copyright of the publisher | "increasing it from an observed 17 days to 21 days" |
| The Wall Street Journal via ChosunBiz, via HSN | `/saudi-revives-hormuz-shuttle-to-sustain-exports-amid-rising-risk-and-costs/` | 21 September 2026 | USD a barrel | Copyright of the publisher | USD 16 to 20 a barrel, "per barrel to compensate crews and owners who accept the risk of transiting the Strait of Hormuz" |
| ITF and JNG joint statement, via HSN | `/joint-itf-jng-statement-designation-of-warlike-operations-area-in-the-strait-of-hormuz/` | 6 March 2026 | Percent of basic wage; days | Copyright of the publisher | "A bonus equal to 100% of basic wage, payable for a minimum of five days" |
| ENGINE and Zawya, via HSN | `/irans-hormuz-closure-deepens-ceasefire-uncertainty/` (9 April 2026), `/maersk-expects-full-return-of-shipping-services-to-suez-canal-by-march-2027/` (22 October 2026) | Dated events only | Dates | Copyright of the publisher | "A.P. Moller-Maersk expects all its shipping services to return to the Suez Canal by March 2027" |
| Suez Canal Authority | `https://www.suezcanal.gov.eg/SCAAPI/api/values/GetUpdatedCircularsAndArticles?circularSPID=485&lang=English&publishingDate=06%2F07%2F2026` (486 and 487 for periodicals 17 and 18); `https://www.suezcanal.gov.eg/English/About/SuezCanal/Pages/NewSuezCanal.aspx` | Surcharges for transits from 15 July 2026; transit and waiting times | Percent of normal transit dues; hours | Copyright of the publisher | "is amended to be 37% of the Suez Canal normal transit dues rather than 25%." |
| Korea JoongAng Daily, via HSN | `/as-red-sea-blockade-threat-grows-korea-weighs-suez-canal-as-crude-import-route-of-last-resort/` | 23 July 2026, citing the Suez Canal Authority; a scale reference only | USD a transit | Copyright of the publisher | "Ships carrying 1 million barrels of crude currently pay roughly $500,000 in tolls to transit the Suez Canal" |
| Platts, Panama Canal, via HSN | `/panama-canal-congestion-worsens-as-lng-carriers-crowd-out-dry-bulk/` | 16 April 2026 | Days of waiting | Copyright of the publisher | 18 to 30 days: "unbooked First Come First Serve waiting times have lengthened materially" |
| US Energy Information Administration | `https://www.eia.gov/petroleum/weekly/archive/2023/230927/includes/analysis_print.php`, `https://www.eia.gov/todayinenergy/detail.php?id=61363`, `https://www.eia.gov/todayinEnergy/detail.php?id=67386` | 27 September 2023, 1 February 2024, 26 March 2026 | USD a transit; dates | US Government work, public domain; kept in the bulk store as the record of the figures cited | "the base toll to transit the canal is about $300,000 for a VLGC to cross the newer, larger Neopanamax locks" |
| IMO resolutions MEPC.328(76), MEPC.361(79) and MEPC.391(81), cited in the conventions | `https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/MEPC.391(81).pdf`, the same path for the others | MARPOL Annex VI regulation 14 as revised in 2021; the Mediterranean ECA; the 2024 LCA guidelines | Percent sulphur by mass; ISO 8217 fuel classes | Copyright of the publisher | "The sulphur content of fuel oil used or carried for use on board a ship shall not exceed 0.50% m/m." |
| EU legal texts, Publications Office of the European Union | `http://publications.europa.eu/resource/celex/<CELEX>` for 32023L0959, 02003L0087-20240301, 32023R2776, 32020R1044, 32023R1805, 32016L0802 and 32018L2001 | Acts as published in the Official Journal; the ETS Directive as consolidated on 1 March 2024 | Tonnes of CO2 a tonne of fuel; global warming potentials; percent of emissions; gCO2e/MJ; EUR | EU legal act; reuse authorised (Commission Decision 2011/833/EU); kept in the bulk store | 3.114 t of CO2 a tonne of HFO, printed with decimal commas: "HFO ISO 8217 Grades RME to RMK 3,114 0,00005 0,00018" |
| BIMCO | `https://www.bimco.org/contractual-affairs/bimco-clauses/current-clauses/etsa_clause/` | ETS Allowances Clause for Time Charter Parties 2022 | None: who provides the allowances | Copyright of the publisher | "Throughout the Charter Party period the Charterers shall provide and pay for the Emission Allowances" |

## Inputs with no public source (left empty, said so where they appear)

Every input whose status is empty in one of the calculator's 30 presets (`presets[].sources` in
`data/calculator.json`), with the reason the site gives, and the items the routes view lists as left out
(`data/routes.json`). An empty input counts as zero, and the result names it among what the voyage leaves out.

| Input | Where | Why it is empty |
|---|---|---|
| Worldscale flat rate | every preset | "Worldscale flat rates are licensed by the Worldscale Association and no dated public source states this route's flat rate for the year". No public source states a study route's flat rate for 2025 or 2026, and the December 2025 anchors need a 2025 rate. Platts printed its Persian Gulf to China benchmark in both points and dollars in January 2026 (w53.5 and USD 11.07 a tonne; w93 and USD 19.24), which implies USD 20.69 a tonne for its own route, whose ports it does not state. The study uses it only to check TD3C's 2026 weeks, never as a calculator default (`implied_flat_rates` in `data/seed/anchors.json`). The other Worldscale anchors are recorded as not reproducible. |
| Port charges at the load and discharge ports | every preset | "no public per call figure; the Baltic uses Cory Brothers' estimates, which are not published" |
| Suez toll, laden and ballast | the TC20 anchors of 9 and 23 October 2026 | Tolls are levied on each ship's Suez Canal net tonnage, in SDR a tonne by band, plus surcharges and less rebates; no public source states that tonnage for the Baltic's standard ships or a toll for them. The detours report the largest toll at which Suez still beats the Cape instead. |
| Panama toll, laden and ballast | P7 | The Panama Canal Authority's tariff and calculator (pancanal.com) could not be reached. The only dated public toll found is the EIA's 2023 base toll for a product tanker in the Panamax locks, which is neither 2026 nor a bulk carrier, so the TCE through Panama is reported before the toll. |
| Time at the Panama Canal | P7 | "the guide's P7 terms set no time at the Panama Canal": the transit and any wait are left out |
| Waiting days | C3, C5, P7, S4A | "no waiting time in the Baltic's dry route terms" |
| Bulk carrier fuel in port (loading, discharging, waiting, delay and transfer) | C3, C5, P7, S4A | "the guide prints no port consumption for bulk carriers" |
| Capesize loading time at the load port's scale | C3, C5 | The Baltic's terms load at the port's own scale, which is not published. The calculator carries only the 6 hours turn time (status derived: "GMB v8.8 page 77: 6 hours turn time only; the loading time itself follows the port's scale, which is not published"), and the routes view lists the loading time at Tubarao and at Port Hedland among what each TCE leaves out. |
| Crew war bonus | every preset | The International Bargaining Forum designated the Strait of Hormuz, the Gulf of Oman and the Persian Gulf a Warlike Operations Area from 6 March 2026, with a bonus equal to 100 percent of basic wage for a minimum of five days; the bonus in dollars needs the crew's wage bill, which has no public source for these ships. |
| Hull value of an LR1 | TC5 | "the table has no LR1 (Panamax tanker) row" in Xclusiv's report of 7 September 2026 |
| Hull value of a Handy tanker (HANDC37, the TC23 ship) | `data/seed/market.json`; TC23 has no calculator preset and appears in the carbon view | "the table has no Handy tanker row" |
| Ship to ship transfer cost and days | every preset, as scenario inputs at zero | No public figure for the transfer itself. The reported costs of the shuttle through the strait (USD 16 to 20 a barrel; USD 50 million a transit) are set beside the export voyage in `hormuz_chain`, not entered as the transfer's cost. |
| A typical split of tanker commission between address commission and brokerage | not a separate input | No public source; the guide states the total, 3.75 percent, which the calculator takes as one input. |

Five inputs are scenario inputs in every preset (status scenario): delay days, ship to ship transfer days, ship
to ship transfer cost, other costs and other revenue. Each is zero in the base case as a scenario, not as a
sourced value, for the visitor to set: "days waiting to transit a listed area, as the Hormuz scenarios set", "the
days of a ship to ship transfer, which have no public figure", "the cost of a ship to ship transfer, which has no
public figure", "any other voyage cost" and "a ballast bonus, demurrage or other voyage revenue". The war risk
premium in the Gulf (TD3C, TC1, TC5 and the TC20 anchors) and in the Red Sea (the TC20 anchors) has a source but
is left out of the TCE (status left_out), as the Baltic leaves it out of its own; a figure entered there counts.

## Worked voyage examples

No fully worked public voyage estimate with prices could be downloaded. The hosts that hold examiners' reports,
course handouts, theses and broker notes with worked voyage estimates refused scripted requests or could not be
reached: ics.org.uk, eclass.unipi.gr, maritime-unipi.gr, commons.wmu.se, core.ac.uk, unctad.org, scribd.com and
poten.com; wikipedia.org, also searched, could not be reached either. Any of them would have given a worked
estimate with prices to reproduce to the dollar.

The candidates that could be downloaded are not such an estimate: E.A. Gibson's weekly tanker reports of 28 August
2015 and 3 August 2018 print rates and TCEs "based on round voyage economics at 'market' speed", not the voyage
itself; a 2015 special report on TCE earnings and speed is conceptual; and a copy of a blog article on GitHub holds
a numeric example with no stated source. All four are in the manifest and none is cited.

The Baltic's TD3C TCE calculation of July 2017 is the one fully worked public example found: it prints days and
tonnes of fuel but no prices, so it checks the engine's days and fuel only.

## Hosts that could not be reached

Refused by the build environment's network policy (not retried), with what each would have added:

- pancanal.com and micanaldepanama.com: the Panama Canal tariff and its toll calculator, for dated Panama tolls
  by vessel class (a toll default for P7).
- worldscale.co.uk: the flat rates, which are licensed in any case; a public statement of a study route's flat
  rate would have made its Worldscale anchors reproducible.
- dehst.de: DEHSt's own monthly auction reports, rather than the sibling study's cache of them.
- ecfr.gov, nauticalcharts.noaa.gov and marinecadastre.gov: the North American ECA coordinates in US regulation,
  read instead from MARPOL Annex VI Appendix VII; ecfr.gov also the Galveston lightering zone (33 CFR 156.300),
  for want of which TD22 loads at the World Port Index's Galveston position.
- web.archive.org and archive.org: archived trade press pages, for more dated freight, bunker and war risk quotes.
- reuters.com, tradewindsnews.com, gcaptain.com and offshore-energy.biz: more dated war risk and freight reports.
- freightinvestorservices.com and sgx.com: tanker FFA levels in dollars a tonne, and more dated dry FFA curves.
- engine.online and dan-bunkering.com: more bunker price reports by port; ENGINE's were read only as HSN
  reposted them.
- porthouston.com, portofgalveston.com, portnola.com, portofamsterdam.com and pilbaraports.com.au: port tariffs,
  toward a port charge default for the study's ports.
- ssyglobal.com: SSY's own freight reports; two of its Capesize index sheets were read as HSN republished them,
  and not cited.
- thedcn.com.au: Australian trade press on the Pilbara iron ore ports.
- itfglobal.org: the ITF's own text of the Warlike Operations Area terms, read instead as HSN republished the
  joint statement.
- ics.org.uk, commons.wmu.se, core.ac.uk, unctad.org and wikipedia.org: worked voyage estimates (above).

Answering scripted requests with HTTP 403 or a browser challenge (not bypassed):

- balticexchange.com HTML pages behind a script challenge: the Baltic's circulars, weekly roundups and route TCE
  histories directly, read instead as republished; the site serves its static PDFs (the guide and the 2017 note)
  to a request that names itself honestly.
- splash247.com and lloydslist.com (HTTP 403, not a network refusal): more dated freight and war risk reports.
- cmegroup.com: freight futures curves and settlement prices.
- spglobal.com: Platts' own reports, read instead as HSN republished them.
- iea.org: the IEA's oil market reports, a second agency beside the EIA for the events behind the Hormuz scenarios.
- imf.org: chokepoint transit counts; the study's counts are S&P Global Commodities at Sea's, as Platts reported
  them.
- msi.nga.mil's file download path for the World Port Index: read instead from the agency's JSON service of the
  same index; Pub. 151 came through the same API's download path.
