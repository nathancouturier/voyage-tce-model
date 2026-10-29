// The voyage estimate in the browser: the same arithmetic as
// src/voyage/engine.py, line for line, so that tools/validate-engine.mjs can
// hold the two to 1e-9 on every output.
//
// The engine holds no number of its own: every factor (emission factors,
// warming potentials, FuelEU values, hours in a day) comes from the Python
// engine through data/engine.json, passed to configure() before any call.
//
// Units: distances in nautical miles, speeds in knots, time in days, fuel in
// tonnes and tonnes per day, prices in USD per tonne, money in USD unless a key
// says EUR. Objects crossing the data contract keep the Python names (snake_case).

let K = null;

/** Set the constants every function reads (data/engine.json, "constants"). */
export function configure(constants) {
  K = constants;
}

function need() {
  if (K === null) throw new Error("engine.js: configure() was not called with data/engine.json");
  return K;
}

const sum = (values) => values.reduce((total, value) => total + value, 0);

// --------------------------------------------------------------------------
// Speed and consumption
// --------------------------------------------------------------------------

function sortedCurve(curve) {
  return curve.map(([v, c]) => [Number(v), Number(c)]).sort((p, q) => p[0] - q[0] || p[1] - q[1]);
}

/** Least squares fit of ln(consumption) on ln(speed): consumption = a x speed ** b. */
export function power_fit(curve) {
  const pairs = sortedCurve(curve);
  const n = pairs.length;
  const xs = pairs.map(([v]) => Math.log(v));
  const ys = pairs.map(([, c]) => Math.log(c));
  const mean_x = sum(xs) / n;
  const mean_y = sum(ys) / n;
  const sxx = sum(xs.map((x) => (x - mean_x) ** 2));
  const sxy = sum(xs.map((x, i) => (x - mean_x) * (ys[i] - mean_y)));
  const b = sxy / sxx;
  const log_a = mean_y - b * mean_x;
  const ss_tot = sum(ys.map((y) => (y - mean_y) ** 2));
  const ss_res = sum(ys.map((y, i) => (y - (log_a + b * xs[i])) ** 2));
  const r2 = ss_tot === 0 ? 1.0 : 1.0 - ss_res / ss_tot;
  return { a: Math.exp(log_a), b, r2 };
}

/** Fuel per day at a speed: linear between published pairs, the fitted power law outside them. */
export function consumption_tpd(curve, speed_kn) {
  const pairs = sortedCurve(curve);
  const [lo_v, lo_c] = pairs[0];
  const [hi_v, hi_c] = pairs[pairs.length - 1];
  if (speed_kn < lo_v || speed_kn > hi_v) {
    const b = power_fit(pairs).b;
    const [anchor_v, anchor_c] = speed_kn < lo_v ? [lo_v, lo_c] : [hi_v, hi_c];
    return anchor_c * (speed_kn / anchor_v) ** b;
  }
  for (let i = 0; i + 1 < pairs.length; i += 1) {
    const [v0, c0] = pairs[i];
    const [v1, c1] = pairs[i + 1];
    if (v0 <= speed_kn && speed_kn <= v1) {
      if (v1 === v0) return c0;
      return c0 + (c1 - c0) * (speed_kn - v0) / (v1 - v0);
    }
  }
  return hi_c;
}

/** Steaming days with the weather allowance on the distance: d (1 + m) / (24 v). */
export function sea_days(distance_nm, speed_kn, margin) {
  if (distance_nm <= 0) return 0.0;
  return distance_nm * (1.0 + margin) / (speed_kn * need().HOURS_PER_DAY);
}

// --------------------------------------------------------------------------
// Worldscale and freight
// --------------------------------------------------------------------------

export function ws_to_usd_t(ws_points, flat_rate_usd_t) {
  return ws_points / need().PERCENT * flat_rate_usd_t;
}

export function usd_t_to_ws(usd_t, flat_rate_usd_t) {
  return need().PERCENT * usd_t / flat_rate_usd_t;
}

export function freight_usd_t(inputs) {
  const basis = inputs.freight_basis;
  const value = inputs.freight_value;
  if (basis === "usd_t") return value;
  if (basis === "ws") return ws_to_usd_t(value, inputs.flat_rate_usd_t);
  if (basis === "lump_sum") return value / inputs.cargo_t;
  throw new Error("freight_usd_t applies to voyage charters, not " + basis);
}

// --------------------------------------------------------------------------
// The voyage
// --------------------------------------------------------------------------

function grade(in_eca, scrubber, scrubber_in_eca) {
  if (in_eca) return scrubber && scrubber_in_eca ? "hsfo" : "mgo";
  return scrubber ? "hsfo" : "vlsfo";
}

function classOf(gradeName, vlsfo_class) {
  if (gradeName === "hsfo") return "HFO";
  if (gradeName === "mgo") return "MGO";
  return vlsfo_class;
}

export function days(inputs) {
  const margin = inputs.sea_margin;
  const { laden, ballast, port } = inputs;
  const out = {
    ballast_sea: sea_days(ballast.distance_nm, ballast.speed_kn, margin),
    laden_sea: sea_days(laden.distance_nm, laden.speed_kn, margin),
    load: port.load_days,
    discharge: port.discharge_days,
    waiting: port.waiting_days,
    canal: port.canal_days,
    delay: port.delay_days,
    sts: port.sts_days,
  };
  out.port_total = out.load + out.discharge + out.waiting + out.canal + out.delay + out.sts;
  out.sea_total = out.ballast_sea + out.laden_sea;
  out.total = out.sea_total + out.port_total;
  out.trip = out.total - out.ballast_sea;
  return out;
}

function legFuel(leg, curve, margin, inputs) {
  const speed = leg.speed_kn;
  const tpd = consumption_tpd(curve, speed);
  const eca_nm = Math.min(leg.eca_nm, leg.distance_nm);
  const open_nm = leg.distance_nm - eca_nm;
  const out = [];
  for (const [nm, in_eca] of [[open_nm, false], [eca_nm, true]]) {
    const d = sea_days(nm, speed, margin);
    if (d <= 0) continue;
    const g = grade(in_eca, inputs.scrubber, inputs.scrubber_in_eca);
    out.push({ grade: g, tonnes: tpd * d, days: d, ets_share: leg.ets_share });
    if (inputs.mgo_at_sea_tpd > 0) {
      out.push({ grade: "mgo", tonnes: inputs.mgo_at_sea_tpd * d, days: d, ets_share: leg.ets_share });
    }
  }
  return out;
}

const PORT_ACTIVITIES = ["load", "discharge", "waiting", "canal", "delay", "sts"];

export function fuel(inputs) {
  const margin = inputs.sea_margin;
  const port = inputs.port;
  const lots = {
    ballast: legFuel(inputs.ballast, inputs.ballast_curve, margin, inputs),
    laden: legFuel(inputs.laden, inputs.laden_curve, margin, inputs),
  };
  for (const activity of PORT_ACTIVITIES) {
    const d = port[activity + "_days"];
    const tpd = port[activity + "_tpd"];
    if (d <= 0 || tpd <= 0) {
      lots[activity] = [];
      continue;
    }
    const g = grade(port[activity + "_eca"], inputs.scrubber, inputs.scrubber_in_eca);
    lots[activity] = [{ grade: g, tonnes: tpd * d, days: d, ets_share: port[activity + "_ets_share"] }];
  }
  const tonnes = { vlsfo: 0.0, hsfo: 0.0, mgo: 0.0 };
  for (const list of Object.values(lots)) {
    for (const lot of list) tonnes[lot.grade] += lot.tonnes;
  }
  return { lots, tonnes, total_t: tonnes.vlsfo + tonnes.hsfo + tonnes.mgo };
}

const PRICE_KEY = { vlsfo: "vlsfo_usd_t", hsfo: "hsfo_usd_t", mgo: "mgo_usd_t" };

function lotCost(lot, prices) {
  return lot.tonnes * prices[PRICE_KEY[lot.grade]];
}

export function emissions(fuelResult, inputs) {
  const k = need();
  const ets = inputs.ets;
  const vlsfo_class = inputs.vlsfo_class;
  let co2 = 0.0;
  let co2e = 0.0;
  let covered = 0.0;
  for (const list of Object.values(fuelResult.lots)) {
    for (const lot of list) {
      const klass = classOf(lot.grade, vlsfo_class);
      const lot_co2 = lot.tonnes * k.CO2_FACTOR[klass];
      const lot_other = lot.tonnes * (k.CH4_FACTOR[klass] * k.GWP_CH4 + k.N2O_FACTOR[klass] * k.GWP_N2O);
      co2 += lot_co2;
      co2e += lot_co2 + lot_other;
      const counted = lot_co2 + (ets.include_non_co2 ? lot_other : 0.0);
      covered += counted * lot.ets_share;
    }
  }
  return { co2_t: co2, co2e_t: co2e, ets_covered_t: covered };
}

export function ets_cost_usd(covered_t, ets) {
  return covered_t * ets.phase_in * ets.eua_eur_t * ets.usd_per_eur;
}

export function fueleu(fuelResult, inputs) {
  const k = need();
  const vlsfo_class = inputs.vlsfo_class;
  const target = k.FUELEU_REFERENCE_G_MJ * (1.0 - inputs.fueleu.reduction_pct / k.PERCENT);
  let energy = 0.0;
  let weighted = 0.0;
  for (const list of Object.values(fuelResult.lots)) {
    for (const lot of list) {
      const klass = classOf(lot.grade, vlsfo_class);
      const mj = lot.tonnes * k.GRAMS_PER_TONNE * k.FUELEU_LCV_MJ_G[klass] * lot.ets_share;
      const ttw = (
        k.CO2_FACTOR[klass] + k.CH4_FACTOR[klass] * k.FUELEU_GWP_CH4 + k.N2O_FACTOR[klass] * k.FUELEU_GWP_N2O
      ) / k.FUELEU_LCV_MJ_G[klass];
      const intensity = k.FUELEU_WTT_G_MJ[klass] + ttw;
      energy += mj;
      weighted += mj * intensity;
    }
  }
  if (energy === 0) {
    return { energy_mj: 0.0, intensity_g_mj: 0.0, target_g_mj: target, balance_g: 0.0, penalty_eur: 0.0, penalty_usd: 0.0 };
  }
  const intensity = weighted / energy;
  const balance = (target - intensity) * energy;
  let penalty_eur = 0.0;
  if (balance < 0) {
    penalty_eur = -balance / (intensity * k.FUELEU_MJ_PER_T_VLSFO) * k.FUELEU_PENALTY_EUR_PER_T;
  }
  return {
    energy_mj: energy,
    intensity_g_mj: intensity,
    target_g_mj: target,
    balance_g: balance,
    penalty_eur,
    penalty_usd: penalty_eur * inputs.ets.usd_per_eur,
  };
}

/** The additional war risk premium by listed area: days inside, seven day periods, dollars.
 * The charter's periods follow the payer; each ballast transit is one period, the owner's. */
export function war_risk(inputs) {
  const k = need();
  const war = inputs.war_risk;
  const margin = inputs.sea_margin;
  const port = inputs.port;
  const areas = {};
  let charter = 0.0;
  let ballast = 0.0;
  for (const name of k.WAR_RISK_AREAS) {
    const area = war.areas[name];
    const rate = area.premium_pct / k.PERCENT * war.hull_value_usd;
    let inside = 0.0;
    let periods = 0.0;
    if (area.entries > 0) {
      inside = sea_days(area.laden_nm, inputs.laden.speed_kn, margin)
        + sea_days(area.ballast_nm, inputs.ballast.speed_kn, margin)
        + sum(area.port_activities.map((activity) => port[activity + "_days"]));
      periods = Math.max(area.entries, Math.ceil(inside / k.WAR_RISK_PERIOD_DAYS));
    }
    const transits = area.ballast_transits;
    const usd = rate * periods;
    const transit_usd = rate * transits;
    areas[name] = { days: inside, periods, usd, ballast_periods: transits, ballast_usd: transit_usd };
    charter += usd;
    ballast += transit_usd;
  }
  const crew = war.crew_bonus_usd;
  return {
    areas,
    charter_usd: charter + crew,
    ballast_usd: ballast,
    premium_usd: charter + ballast,
    total_usd: charter + ballast + crew,
  };
}

const TRIP_ACTIVITIES = ["laden", "load", "discharge", "waiting", "canal", "delay", "sts"];

/** Every line of the voyage estimate, and the TCE. */
export function evaluate(inputs) {
  const k = need();
  const d = days(inputs);
  const f = fuel(inputs);
  const prices = inputs.prices;
  const trip = inputs.contract === "trip";

  const bunkers_by_activity = {};
  for (const [name, list] of Object.entries(f.lots)) {
    bunkers_by_activity[name] = sum(list.map((lot) => lotCost(lot, prices)));
  }
  const bunkers_by_grade = { vlsfo: 0.0, hsfo: 0.0, mgo: 0.0 };
  for (const list of Object.values(f.lots)) {
    for (const lot of list) bunkers_by_grade[lot.grade] += lotCost(lot, prices);
  }

  const em = emissions(f, inputs);
  const ets_all = ets_cost_usd(em.ets_covered_t, inputs.ets);
  const fe = fueleu(f, inputs);

  const costs = inputs.costs;
  const war = war_risk(inputs);
  const port_usd = costs.port_load_usd + costs.port_discharge_usd;
  const canal_usd = costs.canal_laden_usd + costs.canal_ballast_usd;
  const other_usd = costs.other_usd + costs.sts_usd;
  const fueleu_usd = inputs.fueleu.include ? fe.penalty_usd : 0.0;

  let charterer_costs;
  let lines;
  let gross;
  if (trip) {
    const ballastFuel = { lots: { ballast: f.lots.ballast } };
    const owner_bunkers = bunkers_by_activity.ballast;
    const owner_ets = ets_cost_usd(emissions(ballastFuel, inputs).ets_covered_t, inputs.ets);
    const owner_fueleu = inputs.fueleu.include ? fueleu(ballastFuel, inputs).penalty_usd : 0.0;
    const owner_canal = costs.canal_ballast_usd;
    charterer_costs = sum(TRIP_ACTIVITIES.map((a) => bunkers_by_activity[a]))
      + (ets_all - owner_ets)
      + port_usd
      + costs.canal_laden_usd
      + war.charter_usd
      + other_usd
      + (fueleu_usd - owner_fueleu);
    lines = { bunkers: owner_bunkers, ports: 0.0, canals: owner_canal, ets: owner_ets, war_risk: war.ballast_usd, other: 0.0, fueleu: owner_fueleu };
    gross = inputs.freight_value * d.trip;
  } else {
    const charterer_pays_war = inputs.war_risk.payer === "charterer";
    charterer_costs = charterer_pays_war ? war.charter_usd : 0.0;
    lines = {
      bunkers: sum(Object.values(bunkers_by_activity)),
      ports: port_usd,
      canals: canal_usd,
      ets: ets_all,
      war_risk: war.ballast_usd + (charterer_pays_war ? 0.0 : war.charter_usd),
      other: other_usd,
      fueleu: fueleu_usd,
    };
    gross = freight_usd_t(inputs) * inputs.cargo_t;
  }

  const other_revenue = inputs.other_revenue_usd;
  const commission = (gross + other_revenue) * inputs.commission_pct / k.PERCENT;
  const net_revenue = gross + other_revenue - commission;
  const voyage_costs = sum(Object.values(lines));
  const result = net_revenue - voyage_costs;
  const tce = result / d.total;
  return {
    days: d,
    fuel_t: f.tonnes,
    fuel_total_t: f.total_t,
    bunkers_by_activity_usd: bunkers_by_activity,
    bunkers_by_grade_usd: bunkers_by_grade,
    emissions: em,
    ets_all_usd: ets_all,
    fueleu: fe,
    war_risk: war,
    revenue: { gross_usd: gross, other_usd: other_revenue, commission_usd: commission, net_usd: net_revenue },
    costs: { ...lines, total_usd: voyage_costs },
    charterer_costs_usd: charterer_costs,
    result_usd: result,
    tce_usd_day: tce,
  };
}

// --------------------------------------------------------------------------
// Breakevens and speed
// --------------------------------------------------------------------------

/** The freight at which the voyage earns a target TCE, in the units a desk quotes. */
export function freight_for_tce(inputs, target_tce_usd_day) {
  const k = need();
  const r = evaluate(inputs);
  const keep = 1.0 - inputs.commission_pct / k.PERCENT;
  const needed = (target_tce_usd_day * r.days.total + r.costs.total_usd) / keep - inputs.other_revenue_usd;
  if (inputs.contract === "trip") {
    return { hire_usd_day: needed / r.days.trip, usd_t: null, lump_sum_usd: null, ws: null };
  }
  const usd_t = needed / inputs.cargo_t;
  const flat = inputs.flat_rate_usd_t;
  return { hire_usd_day: null, usd_t, lump_sum_usd: needed, ws: flat ? usd_t_to_ws(usd_t, flat) : null };
}

export function with_speed(inputs, laden_kn, ballast_kn) {
  return {
    ...inputs,
    laden: { ...inputs.laden, speed_kn: laden_kn },
    ballast: { ...inputs.ballast, speed_kn: ballast_kn },
  };
}

export function tce_by_speed(inputs, speeds) {
  const gap = inputs.ballast.speed_kn - inputs.laden.speed_kn;
  return speeds.map((v) => {
    const r = evaluate(with_speed(inputs, v, v + gap));
    return { laden_kn: v, ballast_kn: v + gap, tce_usd_day: r.tce_usd_day, days: r.days.total, bunkers_usd: r.costs.bunkers };
  });
}

/** The laden speed on the constants' grid in [lo, hi] that maximises the TCE, ballast keeping its gap. */
export function optimal_speed(inputs, lo_kn, hi_kn) {
  const step = need().SPEED_STEP_KN;
  const gap = inputs.ballast.speed_kn - inputs.laden.speed_kn;
  const steps = Math.round((hi_kn - lo_kn) / step);
  let best_v = lo_kn;
  let best_t = evaluate(with_speed(inputs, lo_kn, lo_kn + gap)).tce_usd_day;
  for (let k = 1; k <= steps; k += 1) {
    const v = lo_kn + k * step;
    const t = evaluate(with_speed(inputs, v, v + gap)).tce_usd_day;
    if (t > best_t) {
      best_v = v;
      best_t = t;
    }
  }
  return { laden_kn: best_v, ballast_kn: best_v + gap, tce_usd_day: best_t };
}

/** A copy of the inputs with one shock applied (see SHOCKS in engine.py). */
export function shocked(inputs, shock, value) {
  if (shock === "freight") return { ...inputs, freight_value: inputs.freight_value * value };
  if (shock === "bunkers") {
    const prices = {};
    for (const [key, price] of Object.entries(inputs.prices)) prices[key] = price * value;
    return { ...inputs, prices };
  }
  if (shock === "speed") return with_speed(inputs, inputs.laden.speed_kn + value, inputs.ballast.speed_kn + value);
  if (shock === "port_days") {
    return { ...inputs, port: { ...inputs.port, waiting_days: Math.max(0.0, inputs.port.waiting_days + value) } };
  }
  if (shock === "eua") return { ...inputs, ets: { ...inputs.ets, eua_eur_t: inputs.ets.eua_eur_t * value } };
  throw new Error("unknown shock " + shock);
}

export function sensitivities(inputs) {
  const base_tce = evaluate(inputs).tce_usd_day;
  return need().SHOCKS.map(([shock, low, high]) => ({
    id: shock,
    low,
    high,
    low_tce_usd_day: evaluate(shocked(inputs, shock, low)).tce_usd_day,
    high_tce_usd_day: evaluate(shocked(inputs, shock, high)).tce_usd_day,
    base_tce_usd_day: base_tce,
  }));
}

// --------------------------------------------------------------------------
// Paper: FFAs and hedges
// --------------------------------------------------------------------------

/** The paper side of a physical voyage; the TCE is grossed up by its commission against a time charter FFA. */
export function hedge(inputs, physical_tce_usd_day, tc_ffa_usd_day, route_ffa_usd_t) {
  const total_days = days(inputs).total;
  const keep = 1.0 - inputs.commission_pct / need().PERCENT;
  const gross_tce = physical_tce_usd_day / keep;
  let route_tce = null;
  if (route_ffa_usd_t !== null) {
    route_tce = evaluate({ ...inputs, freight_basis: "usd_t", freight_value: route_ffa_usd_t }).tce_usd_day;
  }
  return {
    tc_hedge_days: total_days,
    tc_hedge_days_net: total_days * keep,
    route_hedge_t: inputs.cargo_t,
    route_ffa_tce_usd_day: route_tce,
    physical_tce_gross_usd_day: gross_tce,
    basis_vs_tc_ffa_usd_day: tc_ffa_usd_day === null ? null : gross_tce - tc_ffa_usd_day,
    basis_vs_route_ffa_usd_day: route_tce === null ? null : physical_tce_usd_day - route_tce,
  };
}
