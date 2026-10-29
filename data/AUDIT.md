# Data audit

Every source the study reads, as probed from the build environment on 29 October 2026: the endpoint, what it
covers, its units, its terms, a sample, and what the study does with it. Every downloaded file is listed in
`data/raw/manifest.json` with its URL, retrieval time (UTC) and sha256. Files whose terms allow redistribution
and that the build needs offline are committed under `data/raw/public/`; large public files are kept out of git
under `data/raw/bulk/`; everything else stays in `data/raw/licensed/`, which git ignores, and only its manifest
entry and the figures the study uses (each with its quote, in `data/seed/`) are committed.
`tests/test_provenance.py` finds every quoted figure in its document wherever the raw file is present.

## Sources the pipeline fetches

| Source | Endpoint | Coverage and units | Terms | Stored |
|---|---|---|---|---|
| Baltic Exchange, Guide to Market Benchmarks v8.8 (September 2026) | `balticexchange.com/.../GMB.pdf` | Route and vessel definitions (Appendix 2), tanker TCE method (Appendix 3), forward assessments (Appendix 5) | Baltic copyright | licensed, figures in `src/voyage/baltic.py` with page numbers |
| Baltic Exchange, TD3C TCE calculation process (July 2017) | `balticexchange.com/.../TD3C-TCE_Calculation_Process_0717.pdf` | The Baltic's worked TD3C TCE: days and tonnes, no prices | Baltic copyright | licensed, figures in `data/seed/anchors.json` |
| NGA World Port Index (Pub. 150) | `msi.nga.mil/api/publications/world-port-index?output=json` | 2,951 ports, decimal degrees | US Government work, public domain | committed (gzipped) |
| NGA Distances Between Ports (Pub. 151), 11th edition, 2001 | `msi.nga.mil/api/publications/download?key=16694076/SFH00000/Pub151bk.pdf&type=view` | Port to port distances, nautical miles | US Government work, public domain | committed |
| searoute 1.6.0 over Eurostat SeaRoute | PyPI `searoute==1.6.0` (Apache 2.0), network EUPL 1.2 | Sea routes for every ordered port pair under four routings | Apache 2.0, EUPL 1.2 | results committed in `data/seed/sea_routes.*` |
| IMO resolutions MEPC.328(76), MEPC.361(79), MEPC.117(52), MEPC.201(62), MEPC.392(82) | `wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/` | ECA coordinates (Appendix VII: 47, 206, 45 and 55 points) and boundary lines | IMO copyright | licensed, polygons in `data/seed/eca.json` |
| European Commission, EU ETS auction reports | `climate.ec.europa.eu/.../auctioning-allowances_en`, `cap_report_YYYYMM_en.pdf` | Monthly average clearing price of general allowances, EUR/t, to June 2025 | CC BY 4.0 | the June 2025 report committed as the parser's fixture; the others in the bulk store |
| DEHSt, German auction monthly averages (via jkm-ttf-arbitrage, commit cf42430b) | `raw.githubusercontent.com/nathancouturier/jkm-ttf-arbitrage/cf42430b.../dehst_eua_german_auction_monthly.csv` | Monthly EUR/t from July 2025, a proxy for the platform average | CC BY-NC-ND 4.0, "Source: EEX, DEHSt" | committed unchanged |
| Federal Reserve Board H.10 | `federalreserve.gov/releases/h10/data/FRB_h10_xml.zip` | Daily USD per EUR (RXI$US_N.B.EU) | Public domain | bulk store; the series from 2023 committed as `data/cache/usd_per_eur_daily.csv` |

Samples: `data/cache/eua_monthly.csv` reads `2026-08,82.31,DEHSt (German auctions, proxy),...`;
`data/cache/usd_per_eur_daily.csv` gives an August 2026 mean of 1.159362 over 21 published days.

## Sources read once and cited

Press, broker and regulator documents were downloaded once, recorded in the manifest (329 files) and are cited
figure by figure in the seeds. None is redistributed.

| Input | Source | Seed |
|---|---|---|
| Bunker prices, August 2026 (common market) | Ship & Bunker monthly sales analyses (Singapore, Fujairah) and port price pages (quarterly averages) | `market.json` |
| Bunker prices, anchor weeks | Star Asia Shipbroking weekly reports (weeks 9, 10, 26, 28, 31, 36, 40, 43 of 2026); Banchero Costa week 27 | `market.json` |
| War risk premiums | Platts and Marsh as reported by Hellenic Shipping News (1 April, 18 and 25 June, 24 July, 5 October 2026) | `market.json` |
| Hull values | Xclusiv Shipbrokers weekly report, 7 September 2026, 5 year old values (read from the rendered tables) | `market.json` |
| Tanker rates and TCEs | Baltic Exchange weekly tanker reports as republished by Hellenic Shipping News, 13 weeks from 12 December 2025 to 23 October 2026 | `anchors.json` |
| Early March 2026 VLCC rates | Platts (via Hellenic Shipping News), Argus, Oilprice.com (via Yahoo Finance) | `anchors.json` |
| Dry rates | Signal Group (via Hellenic Shipping News), Banchero Costa weeks 27 and 43 | `anchors.json` |
| FFA curves | Banchero Costa dry bulk FFA assessments, 6 July and 25 October 2026 | `ffa.json` |
| FFA settlement | EEX contract specifications (release 047a, 23 July 2026); ICE Futures Europe rulebook Section TTT Part II E | `ffa.json` |
| Suez Canal | Suez Canal Authority periodicals 16, 17 and 18 of 2026 (surcharges from 15 July 2026); SCA via Hellenic Shipping News (23 July 2026) | `canals.json` |
| Panama Canal | EIA This Week in Petroleum, 27 September 2023; Hellenic Shipping News, April 2026 | `canals.json` |
| Events | EIA Today in Energy; S&P Global Commodities at Sea, Platts, Marsh, ITF and IBF, Baltic Exchange, as reported | `events.json` |
| Conventions | GMB v8.8; MARPOL Annex VI (MEPC.328(76), MEPC.361(79)); Directive 2003/87/EC as amended by 2023/959; Regulations 2015/757, 2023/2776, 2020/1044, 2023/1805; Directives 2016/802 and 2018/2001; BIMCO ETS Allowances Clause 2022; IMO MEPC.391(81) | `conventions.json` |

## Inputs with no public source (left empty, said so where they appear)

| Input | Why it is empty |
|---|---|
| Worldscale flat rates | Licensed by the Worldscale Association; no dated public source states a 2026 flat rate for a study route. WS anchors are recorded as not reproducible. |
| Port charges per call | No public per call figure for these ships; the Baltic's TCEs use Cory Brothers' estimates, which are not published. |
| Suez toll per ship | Charged on Suez Canal net tonnage, which is not published for the Baltic's standard ships. |
| Panama toll | The Panama Canal Authority's tariff and calculator could not be reached. |
| Bulk carrier port consumption | The guide prints none for bulk carriers. |
| C3 and C5 loading time | The Baltic's terms load at the port's own scale, which is not published. |
| Crew war bonus | 100 percent of basic wage in the Warlike Operations Area; the wage bill has no public source. |
| Ship to ship transfer cost | No dated public figure found. |

## Hosts that refused this environment

Denied by the environment's network policy (not retried): pancanal.com, micanaldepanama.com, dehst.de,
worldscale.co.uk, web.archive.org, archive.org, ecfr.gov, marinecadastre.gov, nauticalcharts.noaa.gov,
reuters.com, tradewindsnews.com, gcaptain.com, splash247.com, lloydslist.com, freightinvestorservices.com,
sgx.com, offshore-energy.biz, engine.online, dan-bunkering.com, porthouston.com, portofamsterdam.com,
pilbaraports.com.au, portnola.com, portofgalveston.com, ssyglobal.com, thedcn.com.au, wikipedia.org,
itfglobal.org, ics.org.uk, unctad.org, core.ac.uk, commons.wmu.se.

Answering scripted requests with HTTP 403 or a browser challenge (not bypassed): balticexchange.com HTML pages
(circulars and roundups; static PDFs are served to an honest user agent), spglobal.com, imf.org, iea.org,
cmegroup.com, and the World Port Index API's download path.

What they would have added: the Panama tariff (a toll default for P7), Worldscale flat rates (WS anchors
reproducible), the Baltic's circulars and route TCE histories directly, DEHSt's own reports, US lightering zone
coordinates (33 CFR 156.300) and port authorities' tariffs (port charge defaults).
