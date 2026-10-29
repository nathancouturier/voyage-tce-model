"""Baltic Exchange route and vessel definitions, as the study uses them.

Source: Baltic Exchange Information Services Ltd, Guide to Market Benchmarks,
version 8.8, September 2026 (the PDF's creation date is 28 September 2026),
https://www.balticexchange.com/content/dam/balticexchange/consumer/documents/data-services/documentation/ocean-bulk-guides-policies/GMB.pdf
retrieved 2026-10-29. Appendix 2 (pages 76 to 97) specifies every route and
vessel; Appendix 3 (pages 98 to 100) the tanker TCE calculation; Appendix 5
(pages 105 to 112) the forward assessments. Page numbers below are the
guide's printed ones.

The guide is the Baltic's copyright and is not redistributed: the PDF stays in
data/raw/licensed/ and its hash is in data/raw/manifest.json. What is kept
here are the figures the study computes with, each with its page, and route
descriptions paraphrased rather than copied.

Three facts do not come from v8.8 itself, each recorded with its source:

* When each Capesize vessel applies. BCI182 routes were reported alongside the
  BCI180 routes from 2 January 2025 to 24 December 2025, and from 2 January 2026
  the BCI182 is the Baltic Standard Capesize Vessel (Baltic circulars 19/25,
  40/25 and 41/25). The circular pages answer scripted requests with a browser
  challenge, so their text is taken from the verbatim record in this study's
  sibling repository baltic-freight-routes (docs/research/r2-capesize-voyage.md,
  read in a browser on 2026-08-18). v8.8 itself prints the derived value
  C5TC(180) = C5TC(182) - 3,503 on page 77.
* The superseded BCI180 vessel's speeds and consumptions, which v8.8 no longer
  prints: 14 knots laden and 15 knots ballast on 62 t, 12 and 13 knots on 43 t,
  as the study brief states them; the sibling record gives the first pair
  ("14/15kn on 62mt FO 380cst") from the BMTI route guide.
* The tanker commission convention: every tanker route moved to 3.75 percent
  total commission from 2.5 percent under Baltic circular 27/21, as the guide's
  own document history records (version 4.7, February 2023, page 2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

GMB = {
    "title": "Guide to Market Benchmarks",
    "publisher": "Baltic Exchange Information Services Ltd",
    "version": "8.8",
    "date": "September 2026",
    "url": "https://www.balticexchange.com/content/dam/balticexchange/consumer/documents/data-services/"
    "documentation/ocean-bulk-guides-policies/GMB.pdf",
    "raw_key": "baltic_gmb",
    "retrieved": "2026-10-29",
}


@dataclass(frozen=True)
class Vessel:
    """A Baltic standard vessel: its size and its speed and consumption pairs.

    laden and ballast are (knots, tonnes of fuel oil per day) pairs as printed,
    fastest first. port_* are tonnes per day in port by activity where the
    guide prints them (tankers); None where it does not (bulk carriers).
    """

    id: str
    label: str
    segment: str
    dwt_t: float
    page: int
    laden: tuple[tuple[float, float], ...]
    ballast: tuple[tuple[float, float], ...]
    #: the speeds the study prices at: for a tanker the laden and ballast speed
    #: its description names (Appendix 3, page 98, prices the TCE at it); for a
    #: bulk carrier, whose route terms name no speed, the fastest pair printed
    reference_laden_kn: float
    reference_ballast_kn: float
    fuel_at_sea: str = "MFO"
    #: marine gas oil burnt at sea on top of the fuel oil, tonnes per day
    mgo_at_sea_tpd: float = 0.0
    port_load_tpd: float | None = None
    port_discharge_tpd: float | None = None
    port_waiting_tpd: float | None = None
    port_heating_tpd: float | None = None
    scrubber: bool = False
    draft_m: float | None = None
    loa_m: float | None = None
    beam_m: float | None = None
    valid: str = ""
    note: str = ""


VESSELS: Mapping[str, Vessel] = {
    "BCI182": Vessel(
        "BCI182",
        "Baltic Standard Capesize (BCI182)",
        "dry",
        182000,
        78,
        laden=((14, 52), (13, 44), (12, 36), (11, 29)),
        ballast=((14, 44), (13, 36), (12, 29), (11, 23)),
        reference_laden_kn=14,
        reference_ballast_kn=14,
        draft_m=18.2,
        loa_m=292,
        beam_m=45,
        valid="reported from 2 January 2025, the Baltic standard Capesize from 2 January 2026",
        note="182,000 t dwt on 18.2 m SSW draft, TPC 123, 199,500 cbm grain, non-scrubber, MFO, no diesel at sea",
    ),
    "BCI180": Vessel(
        "BCI180",
        "Previous Baltic Capesize (BCI180)",
        "dry",
        180000,
        0,
        laden=((14, 62), (12, 43)),
        ballast=((15, 62), (13, 43)),
        reference_laden_kn=14,
        reference_ballast_kn=15,
        valid="the Baltic standard Capesize until 24 December 2025",
        note="speeds and consumptions as the study brief states them; GMB v8.8 no longer prints this vessel",
    ),
    "BPI82": Vessel(
        "BPI82",
        "Baltic Standard Panamax (BPI82)",
        "dry",
        82500,
        80,
        laden=((13.5, 33), (11.5, 22)),
        ballast=((14, 31), (12.5, 23)),
        reference_laden_kn=13.5,
        reference_ballast_kn=14,
        fuel_at_sea="fuel oil (380 cst)",
        mgo_at_sea_tpd=0.1,
        draft_m=14.43,
        loa_m=229,
        beam_m=32.25,
        note="82,500 t dwt on 14.43 m SSW draft, TPC 70.5, 97,000 cbm grain, non-scrubber, plus 0.1 t MGO at sea",
    ),
    "BSI63": Vessel(
        "BSI63",
        "Baltic Standard Supramax (BSI63)",
        "dry",
        63500,
        82,
        laden=((14, 29), (13, 24), (12, 20), (11, 16.5)),
        ballast=((14, 25), (13, 21), (12, 17), (11, 14)),
        reference_laden_kn=14,
        reference_ballast_kn=14,
        draft_m=13.418,
        loa_m=199.98,
        beam_m=32.24,
        note="63,500 t dwt on 13.418 m SSW, TPC 61.4, 80,500 cbm grain, 4 x 30 t cranes, non-scrubber, MFO, "
        "no MGO at sea",
    ),
    "VLCC300": Vessel(
        "VLCC300",
        "Baltic Standard VLCC (VLCC300)",
        "dirty",
        300000,
        89,
        laden=((13, 57.3), (11, 39.8)),
        ballast=((12, 39.5), (11, 28.5)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=20,
        port_discharge_tpd=110,
        port_waiting_tpd=10,
        note="300,000 t dwt, non-scrubber; 11 knots is the guide's eco speed",
    ),
    "SUEZ160": Vessel(
        "SUEZ160",
        "Baltic Standard Suezmax (SUEZ160)",
        "dirty",
        160000,
        89,
        laden=((13, 38.5), (11, 30)),
        ballast=((12, 28.5), (11, 23.5)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=12,
        port_discharge_tpd=68,
        port_waiting_tpd=10,
        note="160,000 t dwt, non-scrubber; 11 knots is the guide's eco speed",
    ),
    "AFRA115": Vessel(
        "AFRA115",
        "Baltic Standard Aframax (AFRA115)",
        "dirty",
        115000,
        89,
        laden=((13, 35.3), (11, 27.0)),
        ballast=((12, 25.3), (11, 21.0)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=10,
        port_discharge_tpd=55,
        port_waiting_tpd=5,
        port_heating_tpd=8,
        note="115,000 t dwt, non-scrubber; the TD25-TCE description names an AFRA105 the guide never describes "
        "(page 88), so the study prices TD25 on the AFRA115, the only Aframax the guide specifies",
    ),
    "LR2-115": Vessel(
        "LR2-115",
        "Baltic Standard LR2 (LR2-115)",
        "clean",
        115000,
        94,
        laden=((13, 35.3), (11, 27.0)),
        ballast=((12, 25.3), (11, 21.0)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=5,
        port_discharge_tpd=44,
        port_waiting_tpd=6,
        note="115,000 t dwt, non-scrubber",
    ),
    "LR1-75": Vessel(
        "LR1-75",
        "Baltic Standard LR1 (LR1-75)",
        "clean",
        75000,
        95,
        laden=((13, 30.5), (11, 22.5)),
        ballast=((12, 24.5), (11, 20.5)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=5,
        port_discharge_tpd=32,
        port_waiting_tpd=5,
        note="75,000 t dwt, non-scrubber",
    ),
    "MR50": Vessel(
        "MR50",
        "Baltic Standard MR (MR50)",
        "clean",
        50000,
        95,
        laden=((13, 23.3), (11, 18.0)),
        ballast=((12, 17.0), (11, 16.5)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=5,
        port_discharge_tpd=25,
        port_waiting_tpd=5,
        note="50,000 t dwt, non-scrubber",
    ),
    "HANDC37": Vessel(
        "HANDC37",
        "Baltic Standard Clean Handy (HANDC37)",
        "clean",
        37800,
        95,
        laden=((13, 21.3), (11, 14.5)),
        ballast=((12, 16.8), (11, 12.8)),
        reference_laden_kn=13,
        reference_ballast_kn=12,
        port_load_tpd=5,
        port_discharge_tpd=20,
        port_waiting_tpd=5,
        note="37,800 t dwt, non-scrubber",
    ),
}


@dataclass(frozen=True)
class Route:
    """A Baltic route as the study prices it.

    For a voyage route the rate is per tonne of cargo (or Worldscale, or a lump
    sum); for a trip it is hire per day. The TCE basis is the round voyage the
    Baltic states for its tanker TCEs (delivery at the discharge port, ballast
    back to the load port, load, laden passage); for the dry voyage routes,
    which carry no Baltic TCE basis, the study applies the same round voyage
    and says so. For a trip the owner's TCE counts the ballast passage to
    delivery from the redelivery area, as the guide counts the ballast time of
    a time charter's equivalent yield (section 7.4.3, pages 35 and 36).
    """

    code: str
    name: str
    segment: str
    family: str
    contract: str
    unit: str
    vessel: str
    load: str
    discharge: str
    page: int
    description: str
    cargo_t: float | None = None
    commission_pct: float = 0.0
    laydays: str = ""
    #: TCE basis days, from the TCE route description (tankers)
    load_days: float | None = None
    discharge_days: float | None = None
    waiting_days: float | None = None
    canal_days: float | None = None
    tce_page: int | None = None
    tce_basis: str = ""
    #: dry laytime terms, tonnes per day and turn time hours, None where the
    #: guide gives a port scale rather than a rate
    load_rate_tpd: float | None = None
    load_terms: str = ""
    discharge_rate_tpd: float | None = None
    discharge_terms: str = ""
    load_turn_h: float | None = None
    discharge_turn_h: float | None = None
    #: published in USD/t as well (the $ suffix routes), with its page
    also_usd_t: str = ""
    laden_routing: str = "direct"
    ballast_routing: str = "direct"
    trip_days: tuple[float, float] | None = None
    in_basket: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)
    #: the bunker hub when the rule (the hub nearest the load port) picks one
    #: off the voyage, with the reason; empty to follow the rule
    bunker_hub: str = ""
    bunker_hub_why: str = ""


ROUTES: Mapping[str, Route] = {
    "C3": Route(
        "C3",
        "Tubarao to Qingdao",
        "dry",
        "BCI",
        "voyage",
        "USD/t",
        "BCI182",
        "tubarao",
        "qingdao",
        77,
        "170,000 t iron ore, 10 percent more or less in owner's option, free in and out; laydays 20/30 days "
        "from index date; scale load, 30,000 t a day Sundays and holidays included discharge; 6 hours turn "
        "time at load, 24 at discharge; age max 18 years; 5 percent total commission",
        cargo_t=170000,
        commission_pct=5.0,
        laydays="20/30 days from index date",
        load_terms="port scale",
        discharge_rate_tpd=30000,
        discharge_terms="SHINC",
        load_turn_h=6,
        discharge_turn_h=24,
        notes=("The cargo moved to 170,000 t from 2 January 2025 (Baltic circular 44/24).",),
        bunker_hub="singapore",
        bunker_hub_why="the hub nearest Tubarao, Rotterdam, lies over 4,000 nm off the voyage, while the round "
        "voyage leaves Qingdao in ballast and passes about 270 nm from Singapore, the waypoint a ship leaving China "
        "takes for orders (special report on TCE earnings, April 2015, page 2); the guide leaves dry bunker prices "
        "to its panellists (section 7.4.2, page 35)",
    ),
    "C5": Route(
        "C5",
        "West Australia to Qingdao",
        "dry",
        "BCI",
        "voyage",
        "USD/t",
        "BCI182",
        "port_hedland",
        "qingdao",
        77,
        "160,000 t or 170,000 t iron ore, 10 percent more or less in owner's option, free in and out; laydays "
        "12/17 days from index date; scale load, 30,000 t a day Sundays and holidays included discharge; 6 hours "
        "turn time at load, 24 at discharge; age max 15 years; 5 percent total commission",
        cargo_t=170000,
        commission_pct=5.0,
        laydays="12/17 days from index date",
        load_terms="port scale",
        discharge_rate_tpd=30000,
        discharge_terms="SHINC",
        load_turn_h=6,
        discharge_turn_h=24,
        notes=(
            "The guide allows 160,000 t or 170,000 t; the study prices 170,000 t, the C3 cargo, and the "
            "calculator takes either.",
        ),
    ),
    "P7": Route(
        "P7",
        "US Gulf to Qingdao grain",
        "dry",
        "BPI",
        "voyage",
        "USD/t",
        "BPI82",
        "new_orleans",
        "qingdao",
        80,
        "Mississippi river to Qingdao (minimum 13 m arrival draft), 66,000 t heavy grain, sorghum and soya, "
        "10 percent more or less in owner's option, free in and out trimmed; 10,000 t a day Saturdays, Sundays "
        "and holidays excluded loading, 8,000 t a day discharge on the same terms; 24 hours turn time at each "
        "end; loading 10/20 days from index date; age max 15 years; 5 percent total commission",
        cargo_t=66000,
        commission_pct=5.0,
        laydays="loading 10/20 days from index date",
        load_rate_tpd=10000,
        load_terms="SSHEX",
        discharge_rate_tpd=8000,
        discharge_terms="SSHEX",
        load_turn_h=24,
        discharge_turn_h=24,
        notes=("The guide names no canal; the study prices P7 through Panama and shows the Cape as the alternative.",),
    ),
    "S4A_63": Route(
        "S4A_63",
        "US Gulf trip to Skaw-Passero",
        "dry",
        "BSI",
        "trip",
        "USD/day",
        "BSI63",
        "new_orleans",
        "rotterdam",
        81,
        "Delivery US Gulf, laydays 5/10 days from index date, redelivery Skaw-Passero range, duration 25 to 30 "
        "days, basis the Baltic Standard Supramax, 5 percent total commission",
        commission_pct=5.0,
        laydays="5/10 days from index date",
        trip_days=(25, 30),
        in_basket="S11TC 7.5%",
        notes=(
            "A trip time charter: the charterer pays the bunkers, ports and canals of the trip, the owner "
            "earns hire. The study places delivery at New Orleans and redelivery at Rotterdam, inside the "
            "named ranges.",
        ),
    ),
    "P4_82": Route(
        "P4_82",
        "Far East trip to Skaw-Gibraltar",
        "dry",
        "BPI",
        "trip",
        "USD/day",
        "BPI82",
        "qingdao",
        "rotterdam",
        80,
        "Delivery Hong Kong-South Korea including Taiwan, loading 15 to 20 days from the index date, for a 55 to "
        "70 day trip, redelivery Skaw-Gibraltar range (the short description reads Skaw-Passero), basis the Baltic "
        "Standard Panamax, 5 percent total commission",
        commission_pct=5.0,
        laydays="loading 15/20 days from index date",
        trip_days=(55, 70),
        in_basket="P5TC 10%",
        notes=(
            "Used as the hire a Panamax earns from the Far East to Europe in the Asia to Europe detour; the study "
            "places delivery at Qingdao and redelivery at Rotterdam, inside the named ranges.",
        ),
    ),
    "TD3C": Route(
        "TD3C",
        "Middle East Gulf to China",
        "dirty",
        "BDTI",
        "voyage",
        "WS",
        "VLCC300",
        "ras_tanura",
        "ningbo",
        84,
        "270,000 t crude, Ras Tanura to Ningbo; laydays 15/30 days from index date; age max 15 years; "
        "3.75 percent total commission",
        cargo_t=270000,
        commission_pct=3.75,
        laydays="15/30 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=2,
        tce_page=87,
        tce_basis="Baltic VLCC (VLCC300), delivery Ningbo for a round voyage loading Ras Tanura: 2 days load, "
        "2 days discharge, 2 days waiting",
        also_usd_t="TD3C$, page 84",
    ),
    "TD34": Route(
        "TD34",
        "Gulf of Oman to China",
        "dirty",
        "BDTI",
        "voyage",
        "WS",
        "VLCC300",
        "mina_al_fahal",
        "ningbo",
        87,
        "270,000 t crude, Mina Al Fahal to Ningbo; laydays 15/30 days from index date; age max 15 years; "
        "3.75 percent total commission",
        cargo_t=270000,
        commission_pct=3.75,
        laydays="15/30 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=89,
        tce_basis="Baltic VLCC (VLCC300), delivery Ningbo for a round voyage loading Mina Al Fahal: 2 days load, "
        "2 days discharge, 1 day waiting",
        also_usd_t="TD34$, page 87",
        notes=(
            "Added to the guide in version 8.4 (May 2026), its TCE in 8.7 (August 2026) and TD34$ in 8.8 "
            "(September 2026), which also amended the TCE's waiting days.",
        ),
    ),
    "TD22": Route(
        "TD22",
        "US Gulf to China",
        "dirty",
        "BDTI",
        "voyage",
        "USD lump sum",
        "VLCC300",
        "galveston",
        "ningbo",
        86,
        "270,000 t crude, Galveston offshore lightering area to Ningbo; laydays 25/35 days from index date; "
        "double hull, age max 15 years; 3.75 percent total commission; assessed as a lump sum",
        cargo_t=270000,
        commission_pct=3.75,
        laydays="25/35 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=88,
        tce_basis="Baltic VLCC (VLCC300), delivery Ningbo for a round voyage loading Galveston Offshore TSA1: "
        "2 days load, 2 days discharge, 1 day waiting",
        also_usd_t="TD22$, page 86",
        laden_routing="no_canals",
        ballast_routing="no_canals",
        notes=(
            "A laden VLCC fits neither canal, so the laden leg goes round the Cape of Good Hope; the ballast "
            "leg is priced round the Cape as well, with Suez in ballast as the alternative.",
        ),
    ),
    "TD20": Route(
        "TD20",
        "West Africa to UK-Continent",
        "dirty",
        "BDTI",
        "voyage",
        "WS",
        "SUEZ160",
        "bonny",
        "rotterdam",
        86,
        "130,000 t crude, offshore terminal Bonny to Rotterdam; laydays 15 to 20 days from index date; "
        "age max 15 years; 82,000 grt; 3.75 percent total commission",
        cargo_t=130000,
        commission_pct=3.75,
        laydays="15 to 20 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=88,
        tce_basis="Baltic Suezmax (SUEZ160), delivery Rotterdam for a round voyage loading Offshore Bonny: "
        "2 days load, 2 days discharge, 1 day waiting",
        also_usd_t="TD20$, page 86",
    ),
    "TD25": Route(
        "TD25",
        "US Gulf to UK-Continent",
        "dirty",
        "BDTI",
        "voyage",
        "WS",
        "AFRA115",
        "houston",
        "rotterdam",
        86,
        "70,000 t crude, Houston to Rotterdam; laydays 10/20 days from index date; double hull, age max 15 years; "
        "3.75 percent total commission",
        cargo_t=70000,
        commission_pct=3.75,
        laydays="10/20 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=0.5,
        tce_page=88,
        tce_basis="Baltic Aframax (named AFRA105 in the guide), delivery Rotterdam for a round voyage loading "
        "Houston: 2 days load, 2 days discharge, 0.5 days waiting",
        also_usd_t="TD25$, page 86",
        notes=("The TCE description names an AFRA105 that the guide never specifies; the study uses the AFRA115.",),
    ),
    "TC2_37": Route(
        "TC2_37",
        "Continent to US Atlantic coast",
        "clean",
        "BCTI",
        "voyage",
        "WS",
        "MR50",
        "rotterdam",
        "new_york",
        90,
        "37,000 t clean products or unleaded gasoline, Rotterdam to New York; laydays 10/14 days from index date; "
        "age max 15 years; 3.75 percent total commission",
        cargo_t=37000,
        commission_pct=3.75,
        laydays="10/14 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=93,
        tce_basis="MR (MR50), delivery New York for a round voyage loading Rotterdam: 2 days load, 2 days "
        "discharge, 1 day waiting",
        also_usd_t="TC2_37$, page 90",
    ),
    "TC14": Route(
        "TC14",
        "US Gulf to Continent",
        "clean",
        "BCTI",
        "voyage",
        "WS",
        "MR50",
        "houston",
        "amsterdam",
        91,
        "38,000 t clean products, unleaded gasoline or diesel, Houston to Amsterdam; laydays 6/12 days from "
        "index date; age max 15 years; 3.75 percent total commission",
        cargo_t=38000,
        commission_pct=3.75,
        laydays="6/12 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=94,
        tce_basis="MR (MR50), delivery Amsterdam for a round voyage loading Houston: 2 days load, 2 days "
        "discharge, 1 day waiting",
        also_usd_t="TC14$, page 91",
    ),
    "TC1": Route(
        "TC1",
        "Middle East Gulf to Japan (LR2)",
        "clean",
        "BCTI",
        "voyage",
        "WS",
        "LR2-115",
        "ras_tanura",
        "yokohama",
        89,
        "75,000 t clean products, naphtha or condensate, Ras Tanura to Yokohama; laydays 30/35 days from index "
        "date; age max 15 years; 3.75 percent total commission",
        cargo_t=75000,
        commission_pct=3.75,
        laydays="30/35 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=0.5,
        tce_page=93,
        tce_basis="LR2 (LR2-115), delivery Yokohama for a round voyage loading Ras Tanura: 2 days load, 2 days "
        "discharge, 0.5 days waiting",
        also_usd_t="TC1$, page 90",
    ),
    "TC5": Route(
        "TC5",
        "Middle East Gulf to Japan (LR1)",
        "clean",
        "BCTI",
        "voyage",
        "WS",
        "LR1-75",
        "ras_tanura",
        "yokohama",
        90,
        "55,000 t clean products, unleaded gasoline, naphtha or condensate, Ras Tanura to Yokohama; laydays "
        "30/35 days from index date; age max 15 years; 3.75 percent total commission",
        cargo_t=55000,
        commission_pct=3.75,
        laydays="30/35 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=93,
        tce_basis="LR1 (LR1-75), delivery Yokohama for a round voyage loading Ras Tanura: 2 days load, 2 days "
        "discharge, 1 day waiting",
        also_usd_t="TC5$, page 90",
    ),
    "TC20": Route(
        "TC20",
        "Middle East Gulf to UK-Continent (LR2)",
        "clean",
        "BCTI",
        "voyage",
        "USD lump sum",
        "LR2-115",
        "jubail",
        "rotterdam",
        92,
        "90,000 t clean products, middle distillate, Jubail to Rotterdam; laydays 15/20 days from index date; "
        "double hull, age max 15 years; 3.75 percent total commission",
        cargo_t=90000,
        commission_pct=3.75,
        laydays="15/20 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        canal_days=2,
        tce_page=94,
        tce_basis="LR2 (LR2-115), delivery Rotterdam for a round voyage via the Suez Canal loading Jubail: 2 days "
        "load, 2 days discharge, 2 days canal, 1 day waiting",
        also_usd_t="TC20$, page 92",
        notes=("Used for the Suez against Cape detour; the Baltic's TCE basis is via Suez.",),
    ),
    "TC23": Route(
        "TC23",
        "ARA to UK-Continent (Handy)",
        "clean",
        "BCTI",
        "voyage",
        "WS",
        "HANDC37",
        "amsterdam",
        "le_havre",
        93,
        "30,000 t clean products, unleaded gasoline or ultra low sulphur diesel, Amsterdam-Rotterdam-Antwerp to "
        "UK-Continent; laydays 5/10 days from index date; age max 15 years; 3.75 percent total commission",
        cargo_t=30000,
        commission_pct=3.75,
        laydays="5/10 days from index date",
        load_days=2,
        discharge_days=2,
        waiting_days=1,
        tce_page=94,
        tce_basis="Handy (HANDC37), delivery Le Havre for a round trip loading Amsterdam: 2 days loading, 2 days "
        "discharge, 1 day waiting",
        also_usd_t="TC23$, page 93",
        notes=("Used as the voyage between two EEA ports in the carbon analysis.",),
    ),
}

#: The routes the brief names, in the order the site lists them.
STUDY_ROUTES: tuple[str, ...] = (
    "C3",
    "C5",
    "P7",
    "S4A_63",
    "TD3C",
    "TD22",
    "TD20",
    "TD25",
    "TC2_37",
    "TC14",
    "TC1",
    "TC5",
)
#: Routes used by the analyses only.
SUPPORT_ROUTES: tuple[str, ...] = ("TD34", "TC20", "TC23")

#: Appendix 3, page 98 to 99: the tanker TCE weather allowance on steaming time.
TANKER_SEA_MARGIN = 0.05
#: Appendix 2, page 77: C5TC(180) = C5TC(182) - 3,503 USD/day.
C5TC_180_DIFFERENTIAL = 3503.0
#: Appendix 2, page 76: BCI = RoundedSum(C8*0.15, C9*0.125, C10*0.35, C14*0.25, C16*0.125)*0.11026, the
#: weighted basket being the C5TC(182) of page 77; BDI = RoundedSum(C5TC*0.40, P5TC*0.30, S11TC*0.30)*0.10.
BCI_FACTOR = 0.11026
BDI_WEIGHTS = {"C5TC": 0.40, "P5TC": 0.30, "S11TC": 0.30}
BDI_FACTOR = 0.10
#: The day each Capesize vessel became the standard (circulars 19/25 and 41/25).
BCI182_STANDARD_FROM = "2026-01-02"
BCI182_REPORTED_FROM = "2025-01-02"


def vessel_for(route: Route, on_date: str | None = None) -> Vessel:
    """The vessel a route is priced with on a date: the BCI180 for Capesize routes before 2 January 2026."""
    if route.vessel == "BCI182" and on_date is not None and on_date < BCI182_STANDARD_FROM:
        return VESSELS["BCI180"]
    return VESSELS[route.vessel]


def as_records() -> dict[str, Any]:
    """Vessels and routes as plain records, for the seed file and the site."""
    from dataclasses import asdict

    return {
        "source": GMB,
        "tanker_sea_margin": TANKER_SEA_MARGIN,
        "c5tc_180_differential_usd_day": C5TC_180_DIFFERENTIAL,
        "bci182_standard_from": BCI182_STANDARD_FROM,
        "bci182_reported_from": BCI182_REPORTED_FROM,
        "vessels": {key: asdict(vessel) for key, vessel in VESSELS.items()},
        "routes": {key: asdict(route) for key, route in ROUTES.items()},
    }
