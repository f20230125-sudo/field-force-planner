"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  defaultPlan,
  densityRange,
  ledger,
  maxColourSlot,
  planReps,
  registrySteps,
  samePlan,
  splitStats,
  tickCount,
  topShare,
  type Plan,
} from "@/lib/derive";
import { MapShapes, franchiseKeys, type Dataset, type Franchise, type MapData } from "@/lib/schema";
import { int, longDate, pct, reps, rho } from "@/lib/format";
import { Glyph, ProfileChart, RealityCheck, RepRuler, StateLedger, Waterfall } from "./Charts";
import { Frame, useView } from "./chart";
import { ThemeToggle } from "./ThemeToggle";
import { TerritoryMap } from "./TerritoryMap";

const SECTIONS: { id: string; label: string }[] = [
  { id: "how-many", label: "How many" },
  { id: "call-plan", label: "Call plan" },
  { id: "alignment", label: "Alignment" },
  { id: "limits", label: "Limits" },
  { id: "quality", label: "Quality" },
  { id: "method", label: "Method" },
];

const NAME: Record<Franchise, string> = { diabetes: "Diabetes", oncology: "Oncology" };
const WORD = { diabetes: "diabetes", oncology: "oncology" } as const;

function Section({ id, title, dek, children }: { id: string; title: string; dek?: ReactNode; children: ReactNode }) {
  return (
    <section className="sec" id={id} aria-labelledby={`${id}-h`}>
      <div className="sec-head">
        <h2 id={`${id}-h`}>{title}</h2>
        {dek && <p className="dek">{dek}</p>}
      </div>
      <div className="sec-body">{children}</div>
    </section>
  );
}

function FranchiseSwitch({ value, onChange, label }: { value: Franchise; onChange: (f: Franchise) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {franchiseKeys.map((f) => (
        <button key={f} type="button" aria-pressed={value === f} onClick={() => onChange(f)}>
          {NAME[f]}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- first screen

function Plate({ d, map, franchise, setFranchise }: { d: Dataset; map: MapData | null; franchise: Franchise; setFranchise: (f: Franchise) => void }) {
  const [zoom, setZoom] = useState("US");
  const [view, setView] = useView("chart");
  const [state, setState] = useState("ALL");
  const [page, setPage] = useState(0);
  const a = d.alignment[franchise];
  const m = a.metrics.aligned;
  const stateNames = useMemo(() => Object.fromEntries(d.sizing.diabetes.states.map((s) => [s.state, s.name])), [d.sizing]);
  const sp = splitStats(d.counties, franchise, a.territories);
  const f = d.counties[franchise];

  // territories by the states of the counties whose main territory they are
  const rows = useMemo(() => {
    const byT = new Map<number, Set<string>>();
    f.territory.forEach((t, i) => byT.set(t, (byT.get(t) ?? new Set()).add(d.counties.state[i])));
    return a.territoryRows.map((r) => ({ ...r, states: [...(byT.get(r.n) ?? [])].sort() }));
  }, [a, f, d.counties.state]);
  const shown = state === "ALL" ? rows : rows.filter((r) => r.states.includes(state));
  const pageRows = shown.slice(page * 25, page * 25 + 25);

  const key = (
    <ul className="key" aria-label="How to read the map">
      <li>
        <span className="tints" aria-hidden="true">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <i key={i} style={{ background: `var(--t${i})` }} />
          ))}
        </span>
        <b>Colour only tells neighbours apart.</b> It carries no meaning.
      </li>
      <li>
        <span className="line-sample" aria-hidden="true" />
        <b>The line is where a territory changes.</b>
      </li>
      <li>
        <span className="hatch-sample" aria-hidden="true" />
        <b>{int(sp.counties)} counties are cut between territories</b> and hold {pct(sp.popShare, 1)} of the population. The colour shown is the territory with the largest piece.
      </li>
      <li>
        <span className="as">8</span> <b>A yellow number is an assumption, not a count.</b>
      </li>
      <li>
        {int(sp.visible)} of the {int(sp.territories)} territories are the largest piece of at least one county; the rest sit inside hatched counties and cannot be drawn as shapes here.
      </li>
    </ul>
  );

  return (
    <Frame
      id="map"
      title={`The ${int(a.territories)} ${WORD[franchise]} territories, county by county`}
      sub={`${pct(m.within_25pct, 1)} are within 25% of the target weight, and every one is a single connected piece.`}
      view={view}
      onView={setView}
      controls={
        <div className="ctl" style={{ marginBottom: 8 }}>
          <FranchiseSwitch value={franchise} onChange={setFranchise} label="Franchise shown on the map" />
          <label htmlFor="zoom">Zoom to a state</label>
          <select id="zoom" className="map-select" value={zoom} onChange={(e) => setZoom(e.target.value)}>
            <option value="US">United States</option>
            {Object.keys(stateNames)
              .sort((a, b) => stateNames[a].localeCompare(stateNames[b]))
              .map((s) => (
                <option key={s} value={s}>
                  {stateNames[s]}
                </option>
              ))}
          </select>
        </div>
      }
      source="Source: CMS NPPES registry (October 2026); Census Bureau county shapes (generalised, 1:10 million) and population estimates; CDC PLACES; alignment computed in this project. Zooming shows smoothed county outlines."
      table={
        <div>
          <div className="ctl" style={{ margin: "0 0 10px" }}>
            <label htmlFor="tstate">State</label>
            <select
              id="tstate"
              className="cell"
              style={{ width: "auto", textAlign: "left", background: "var(--paper)", borderBottom: "1px solid var(--mute)" }}
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setPage(0);
              }}
            >
              <option value="ALL">All states</option>
              {Object.keys(stateNames)
                .sort()
                .map((s) => (
                  <option key={s} value={s}>
                    {stateNames[s]}
                  </option>
                ))}
            </select>
            <span>
              {shown.length.toLocaleString("en-US")} territories, 25 a page
            </span>
            <button type="button" className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <button type="button" className="btn" disabled={(page + 1) * 25 >= shown.length} onClick={() => setPage(page + 1)}>
              Next
            </button>
          </div>
          <div>
            <table className="tbl">
              <caption>Each territory by the states of its counties, its weight (1.00 is on target), calls a year and patients</caption>
              <thead>
                <tr>
                  <th scope="col">Territory</th>
                  <th scope="col">States</th>
                  <th scope="col" className="n">Counties</th>
                  <th scope="col" className="n">Weight</th>
                  <th scope="col" className="n">Calls a year</th>
                  <th scope="col" className="n">Patients</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r) => (
                  <tr key={r.id}>
                    <th scope="row" className="id">{r.id}</th>
                    <td>{r.states.join(", ")}</td>
                    <td className="n">{r.counties}</td>
                    <td className="n">{r.weight.toFixed(2)}</td>
                    <td className="n">{int(r.calls)}</td>
                    <td className="n">{int(r.patients)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      }
    >
      <div className="plate">
        <TerritoryMap map={map} counties={d.counties} align={a} franchise={franchise} zoom={zoom} />
        {key}
      </div>
    </Frame>
  );
}

// ---------------------------------------------------------------------------------------------- how many

function HowMany({ d }: { d: Dataset }) {
  const [franchise, setFranchise] = useState<Franchise>("diabetes");
  const s = d.sizing[franchise];
  const ts = topShare(s);
  const dr = densityRange(s);
  const gen = d.sizing.diabetes.segments.filter((x) => x.tier === "generalist").reduce((a, x) => a + x.calls, 0) / d.sizing.diabetes.calls;
  const rowsAll = ledger(s);
  const [all, setAll] = useState(false);
  const [view, setView] = useView("chart");
  const shown = all ? rowsAll : rowsAll.slice(0, 8);
  return (
    <Section
      id="how-many"
      title={`Diabetes needs about ${reps(d.sizing.diabetes.reps)} reps and oncology about ${reps(d.sizing.oncology.reps)}; ${pct(gen, 1)} of diabetes calls go to primary care`}
      dek="One tick is one rep, at the same scale for both. The call plan behind them is assumed and set out in the next section; the provider counts are from the registry."
    >
      <div>
        <p className="stat-line">
          <b>Diabetes:</b> {reps(d.sizing.diabetes.reps)} reps ({d.sizing.diabetes.reps.toFixed(2)}, drawn as {tickCount(d.sizing.diabetes.reps).toLocaleString("en-US")}).
        </p>
        <RepRuler reps={d.sizing.diabetes.reps} label={`${tickCount(d.sizing.diabetes.reps)} ticks, one for each diabetes rep`} />
        <p className="stat-line" style={{ marginTop: 22 }}>
          <b>Oncology:</b> {reps(d.sizing.oncology.reps)} reps ({d.sizing.oncology.reps.toFixed(2)}, drawn as {tickCount(d.sizing.oncology.reps).toLocaleString("en-US")}).
        </p>
        <RepRuler reps={d.sizing.oncology.reps} label={`${tickCount(d.sizing.oncology.reps)} ticks, one for each oncology rep`} />
      </div>
      <div className="pair">
        <Frame
          title="Reps by state"
          sub={`${NAME[franchise]}. One tick is one rep; the last tick is drawn at the height of the fraction.`}
          view={view}
          onView={setView}
          controls={<FranchiseSwitch value={franchise} onChange={setFranchise} label="Franchise in the state ledger" />}
          source="Source: CMS NPPES registry (October 2026), the call plan in the next section, and Census adults."
          table={
            <table className="tbl">
              <caption>Reps, calls and adults by state ({NAME[franchise]})</caption>
              <thead>
                <tr>
                  <th scope="col">State</th>
                  <th scope="col" className="n">Reps</th>
                  <th scope="col" className="n">Calls a year</th>
                  <th scope="col" className="n">Adults</th>
                  <th scope="col" className="n">Reps per 100,000 adults</th>
                </tr>
              </thead>
              <tbody>
                {rowsAll.map((r) => {
                  const st = s.states.find((x) => x.state === r.state)!;
                  return (
                    <tr key={r.state}>
                      <th scope="row">{r.name}</th>
                      <td className="n">{r.reps.toFixed(1)}</td>
                      <td className="n">{int(st.calls)}</td>
                      <td className="n">{int(st.adults)}</td>
                      <td className="n">{r.repsPer100k.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          }
        >
          <StateLedger rows={shown} label={`Reps by state, ${WORD[franchise]}: ${shown.map((r) => `${r.name} ${r.reps.toFixed(0)}`).join(", ")}`} />
          <p style={{ margin: "8px 0 0" }}>
            <button type="button" className="btn" onClick={() => setAll((v) => !v)}>
              {all ? "Show the top eight" : "Show all 51 states"}
            </button>
          </p>
        </Frame>
        <ul className="rlist">
          <li>
            <b>{pct(ts.share, 1)}</b> of {WORD[franchise]} reps are in five states: {ts.names.join(", ")}.
          </li>
          <li>
            Reps per 100,000 adults run from <b>{dr.lo.v.toFixed(2)}</b> ({dr.lo.name}) to <b>{dr.hi.v.toFixed(2)}</b> ({dr.hi.name}).
          </li>
          <li>
            Calls by provider group: {s.segments.map((x) => `${x.segment} ${pct(x.calls / s.calls, 1)}`).join(", ")}.
          </li>
        </ul>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- the call plan

function CallPlan({ d }: { d: Dataset }) {
  const [franchise, setFranchise] = useState<Franchise>("diabetes");
  const s = d.sizing[franchise];
  const stated = useMemo(() => defaultPlan(s), [s]);
  const [plans, setPlans] = useState<Record<Franchise, Plan>>({ diabetes: defaultPlan(d.sizing.diabetes), oncology: defaultPlan(d.sizing.oncology) });
  const plan = plans[franchise];
  const res = planReps(s, plan);
  const base = planReps(s, stated);
  const set = (next: Plan) => setPlans({ ...plans, [franchise]: next });
  const num = (v: string) => (v === "" || Number.isNaN(Number(v)) ? 0 : Math.max(0, Number(v)));
  const changed = !samePlan(plan, stated);
  const diff = res.reps - base.reps;
  return (
    <Section id="call-plan" title="Providers are counted; shares and calls are assumed, and the headcount follows the cells" dek={`The yellow cells are assumptions you can change. The national headcount recomputes here; the map and the alignment come from the stated plan and are not re-run in the browser.`}>
      <div className="ctl">
        <FranchiseSwitch value={franchise} onChange={setFranchise} label="Franchise in the call plan" />
        <span className="stat-line" style={{ margin: 0 }}>{s.label}</span>
      </div>
      <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Call plan worksheet">
        <table className="tbl">
          <caption>Providers are from the registry; the yellow cells are assumptions</caption>
          <thead>
            <tr>
              <th scope="col">Provider group</th>
              <th scope="col" className="n">Providers</th>
              <th scope="col" className="n">Share targeted (%)</th>
              <th scope="col" className="n">Calls per provider a year</th>
              <th scope="col" className="n">Calls a year</th>
            </tr>
          </thead>
          <tbody>
            {s.segments.map((x, i) => (
              <tr key={x.segment}>
                <th scope="row">{x.segment}</th>
                <td className="n">{int(x.providers)}</td>
                <td className="in n">
                  <input
                    className="cell"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    max={100}
                    step={5}
                    aria-label={`${x.segment}: share targeted, percent`}
                    value={Math.round(plan.share[x.segment] * 1000) / 10}
                    onChange={(e) => set({ ...plan, share: { ...plan.share, [x.segment]: Math.min(1, num(e.target.value) / 100) } })}
                  />
                </td>
                <td className="in n">
                  <input
                    className="cell"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={1}
                    aria-label={`${x.segment}: calls per provider a year`}
                    value={plan.calls[x.segment]}
                    onChange={(e) => set({ ...plan, calls: { ...plan.calls, [x.segment]: num(e.target.value) } })}
                  />
                </td>
                <td className="n">{int(res.byGroup[i].calls)}</td>
              </tr>
            ))}
            <tr className="tot">
              <th scope="row">All groups</th>
              <td className="n">{int(s.segments.reduce((a, x) => a + x.providers, 0))}</td>
              <td />
              <td />
              <td className="n">{int(res.calls)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="ctl">
        <label htmlFor="cpd">Calls a rep makes a day</label>
        <input id="cpd" className="cell" type="number" min={1} step={1} value={plan.callsPerDay} onChange={(e) => set({ ...plan, callsPerDay: Math.max(1, num(e.target.value)) })} />
        <label htmlFor="fd">Field days a year</label>
        <input id="fd" className="cell" type="number" min={1} step={5} value={plan.fieldDays} onChange={(e) => set({ ...plan, fieldDays: Math.max(1, num(e.target.value)) })} />
        <span>= {int(plan.callsPerDay * plan.fieldDays)} calls a rep a year</span>
      </div>
      <div>
        <p className="scenario" aria-live="polite">
          Your scenario needs <b>{int(res.reps)} reps</b>.{" "}
          {changed ? (
            <>
              The stated plan needs {int(base.reps)}; yours is {diff < 0 ? "−" : "+"}
              {int(Math.abs(diff))}.
            </>
          ) : (
            <>This is the stated plan.</>
          )}
          <button type="button" className="btn" onClick={() => set(stated)} disabled={!changed}>
            Reset to the stated plan
          </button>
        </p>
        <RepRuler reps={res.reps} animate label={`${tickCount(res.reps)} ticks, one for each rep in your scenario`} />
      </div>
      <p className="limits">
        <b>Workload</b> = providers x share targeted x calls per provider a year. <b>Reps</b> = workload / (calls a day x field days). Public data says who the providers are and where, not what each prescribes, so the share targeted is a flat assumption for a whole group, not a ranking of individual doctors. The call plan is a stated assumption, not any company&apos;s.
      </p>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- alignment

function Alignment({ d }: { d: Dataset }) {
  const [franchise, setFranchise] = useState<Franchise>("diabetes");
  const a = d.alignment[franchise];
  const al = a.metrics.aligned;
  const ba = a.metrics.baseline;
  const h = d.headline.franchises[franchise];
  const [view, setView] = useView("chart");
  const ids = a.territoryRows.map((r) => r.id);
  const aligned = a.territoryRows.map((r) => r.weight);
  return (
    <Section
      id="alignment"
      title={`Cut by weight, ${pct(al.within_25pct, 1)} of territories land within 25% of the target, against ${pct(ba.within_25pct, 1)} when cut by county count`}
      dek="Weight is half a territory's share of calls and half its share of patients, scaled so 1.00 is on target. The comparison cuts the same number of territories with equal numbers of counties, blind to weight: it is a deliberately naive baseline, not any company's alignment."
    >
      <Frame
        title="The weight of every territory, lightest to heaviest"
        sub={`${NAME[franchise]}: ${int(a.territories)} territories.`}
        view={view}
        onView={setView}
        controls={<FranchiseSwitch value={franchise} onChange={setFranchise} label="Franchise in the balance charts" />}
        legend={
          <ul className="legend" aria-label="Legend">
            <li><i />Cut by weight</li>
            <li><i className="ink3" />Cut by county count</li>
            <li><i className="band" />Within 25% of the target (a chosen tolerance)</li>
          </ul>
        }
        source="Source: this project's alignment of the Census 2020 counties. A county heavier than 0.15 of a territory is cut into equal pieces; Alaska and Hawaii are aligned on their own."
        table={
          <table className="tbl">
            <caption>Balance and shape, {WORD[franchise]}</caption>
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col" className="n">Cut by weight</th>
                <th scope="col" className="n">Cut by county count</th>
              </tr>
            </thead>
            <tbody>
              <tr><th scope="row">Spread of weight (coefficient of variation)</th><td className="n">{pct(al.cv, 1)}</td><td className="n">{pct(ba.cv, 0)}</td></tr>
              <tr><th scope="row">Within 10% of the target</th><td className="n">{pct(al.within_10pct, 1)}</td><td className="n">{pct(ba.within_10pct, 1)}</td></tr>
              <tr><th scope="row">Within 25% of the target</th><td className="n">{pct(al.within_25pct, 1)}</td><td className="n">{pct(ba.within_25pct, 1)}</td></tr>
              <tr><th scope="row">Lightest, times the target</th><td className="n">{al.min_over_mean.toFixed(2)}</td><td className="n">{ba.min_over_mean.toFixed(3)}</td></tr>
              <tr><th scope="row">Heaviest, times the target</th><td className="n">{al.max_over_mean.toFixed(2)}</td><td className="n">{ba.max_over_mean.toFixed(1)}</td></tr>
              <tr><th scope="row">Mean territory radius, km</th><td className="n">{al.mean_radius_km.toFixed(0)}</td><td className="n">{ba.mean_radius_km.toFixed(0)}</td></tr>
            </tbody>
          </table>
        }
      >
        <div className="pair even">
          <ProfileChart weights={aligned} ids={ids} tone="ink" title="Cut by weight." facts={`Spread ${pct(al.cv, 1)}; ${pct(al.within_25pct, 1)} within 25%; heaviest ${al.max_over_mean.toFixed(2)} times the target.`} />
          <ProfileChart weights={a.weights.baseline} tone="ink3" title="Cut by county count." facts={`Spread ${pct(ba.cv, 0)}; ${pct(ba.within_25pct, 1)} within 25%; heaviest ${ba.max_over_mean.toFixed(1)} times the target.`} />
        </div>
      </Frame>
      <div className="pair">
        <ul className="rlist">
          <li>
            <b>What balance costs.</b> Spread of weight <b>{pct(al.cv, 1)}</b> against {pct(ba.cv, 0)}; within 10% of the target <b>{pct(al.within_10pct, 1)}</b> against {pct(ba.within_10pct, 1)}.
          </li>
          <li>
            Mean territory radius <b>{al.mean_radius_km.toFixed(0)} km</b> against {ba.mean_radius_km.toFixed(0)} km: balanced territories are drawn around the work, not around the map.
          </li>
          <li>
            Territories that cross a state line: <b>{al.crossing_state_share == null ? "n/a" : pct(al.crossing_state_share, 1)}</b> against {ba.crossing_state_share == null ? "n/a" : pct(ba.crossing_state_share, 1)}.
          </li>
          <li>
            Counties cut between territories: <b>{int(h.splitCounties)}</b> against 0. The same method before its local search (moving border pieces) had a spread of {pct(h.cvGrown, 1)}.
          </li>
        </ul>
        <p className="limits">
          <b>Method in one line.</b> Weighted k-means seeds, region growing that always extends the lightest territory, then moves of border pieces that lower the spread and keep the old territory in one piece. Deterministic and tested for coverage, connection and balance; not proven optimal.
        </p>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- limits

function Limits({ d }: { d: Dataset }) {
  const sp = splitStats(d.counties, "diabetes", d.alignment.diabetes.territories);
  const v = d.headline.validation;
  return (
    <Section id="limits" title="The map is a county-level shortcut, and demand follows size, not spend per enrollee" dek={`The first limit is on the first screen: ${int(sp.counties)} counties are cut inside and hold ${pct(sp.popShare, 1)} of the population.`}>
      <div className="pair">
        <ul className="rlist">
          <li>
            <b>No prescribing data.</b> The CMS Part D prescriber files, which say what each doctor prescribes, are served from data.cms.gov and refuse requests from the UAE. This project knows who the providers are and where, not who prescribes most.
          </li>
          <li>
            <b>Counties, split.</b> Real alignments use ZIP-code or smaller bricks. Here a county heavier than 0.15 of a territory is cut into equal pieces, so the largest cities are only hatched on the map.
          </li>
          <li>
            <b>Heuristic.</b> The alignment is deterministic and tested, not proven optimal. The county-count baseline is a straw man on purpose.
          </li>
          <li>
            <b>Vintages.</b> 2020 Census counties; population July 2021; CDC PLACES 2023 (survey year 2021), with Florida from the 2024 release. Connecticut&apos;s 2022 planning regions are not used because the ZIP crosswalk and adjacency files predate them.
          </li>
          <li>
            <b>Registry.</b> A ZIP code is not a Census ZIP-code area, so PO-box and single-building ZIPs are lost: every county count is a slight undercount ({pct(1 - d.headline.registry.matchRate, 1)} of providers could not be placed).
          </li>
        </ul>
        <div>
          <p className="stat-line">
            <b>Does public prevalence rank states like observed Medicaid spend?</b> By size, yes, which is mostly population. Per enrollee, no. Rank correlations over the {v.diabetes.states} states and DC, against spend from Rx Market Pulse:
          </p>
          <RealityCheck
            rows={[
              { franchise: "Diabetes", size: v.diabetes.sizeRho, intensity: v.diabetes.intensityRho },
              { franchise: "Oncology", size: v.oncology.sizeRho, intensity: v.oncology.intensityRho },
            ]}
          />
          <p className="src">
            Filled square: demand against spend, by state size ({rho(v.diabetes.sizeRho)} diabetes, {rho(v.oncology.sizeRho)} oncology). Outlined square: prevalence against spend per Medicaid enrollee ({rho(v.diabetes.intensityRho)}, {rho(v.oncology.intensityRho)}). Formulary, benefit design and who is enrolled dominate, not how common the disease is.
          </p>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- quality

function Quality({ d }: { d: Dataset }) {
  const c = d.headline.checks;
  const byDim = new Map<string, typeof d.quality>();
  for (const q of d.quality) byDim.set(q.dimension, [...(byDim.get(q.dimension) ?? []), q]);
  const word = { pass: "Pass", warn: "Warn", fail: "Fail", info: "Measured" } as const;
  return (
    <Section id="quality" title={`${c.total} checks: ${c.pass} pass, ${c.warn === 0 && c.fail === 0 ? "none warn or fail" : `${c.warn} warn, ${c.fail} fail`}, ${c.info} are measurements`} dek="Each check says what it measured, the number and the rule it was held to. A measurement has no pass or fail rule; it is there because it changes how to read the data.">
      {[...byDim.entries()].map(([dim, items]) => (
        <div className="qgroup" key={dim}>
          <h3>{dim}</h3>
          <ul className="qlist">
            {items.map((q) => (
              <li key={q.id}>
                <div className="qrow">
                  <span className="st">
                    <Glyph status={q.status} />
                    {word[q.status]}
                  </span>
                  <div>
                    <span className="nm">
                      {q.id}. {q.name}
                    </span>
                    <span className="rs">{q.result}</span>
                    {q.note && (
                      <details>
                        <summary>Why it matters</summary>
                        <p>{q.note}</p>
                      </details>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- method and footer

function Method({ d, repoUrl }: { d: Dataset; repoUrl?: string }) {
  const r = d.headline.registry;
  const dia = d.sizing.diabetes;
  const onc = d.sizing.oncology;
  const fixed = [
    ["Weight is half calls, half patients", "0.5", "fixed in the alignment"],
    ["A territory is on target at weight", "1.00", "fixed in the alignment"],
    ["Within-target tolerance", "25%", "a chosen reading, fixed"],
    ["A county is cut into pieces above", "0.15 of a territory", "fixed in the alignment"],
  ];
  return (
    <Section id="method" title={`From ${int(r.records)} registry records to ${int(d.alignment.diabetes.territories)} territories, and the choices made on the way`}>
      <Waterfall steps={registrySteps(r)} />
      <ol className="method">
        <li><b>Providers.</b> The October 2026 NPPES file is streamed through DuckDB. The {int(r.deactivated)} records with no entity type are deactivated numbers and match the separate deactivation report; {int(r.kept)} individuals are active and in the 50 states and DC.</li>
        <li><b>Specialty.</b> The primary taxonomy code maps to a provider group through a short reference file; every code is checked against the NUCC code set.</li>
        <li><b>Geography.</b> A provider&apos;s ZIP code goes to a Census ZIP-code area and then to the county holding most of its land: {pct(r.matchRate, 1)} of providers reach a county.</li>
        <li><b>Sizing.</b> Providers x share targeted x calls per provider = calls a year; calls / (calls a rep makes in a year) = reps. The same arithmetic runs in Python and in the Excel model, and Excel itself was driven through six scenarios against an independent calculation.</li>
        <li><b>Alignment.</b> Weighted seeds, region growing, then a local search; Alaska and Hawaii on their own.</li>
      </ol>
      <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Every assumption on the page">
        <table className="tbl" style={{ maxWidth: 760 }}>
          <caption>Every assumption on the page. Yellow is assumed, not counted.</caption>
          <thead>
            <tr>
              <th scope="col">Assumption</th>
              <th scope="col" className="n">Value</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {[dia, onc].flatMap((s, k) =>
              s.segments.flatMap((x) => [
                [`${k === 0 ? "Diabetes" : "Oncology"}: ${x.segment.toLowerCase()}, share targeted`, pct(x.share), "change it in the call plan"],
                [`${k === 0 ? "Diabetes" : "Oncology"}: ${x.segment.toLowerCase()}, calls per provider a year`, String(x.callsPerYear), "change it in the call plan"],
              ]),
            )
              .concat([
                ["Diabetes: calls a rep makes a day, field days", `${dia.callsPerRepDay}, ${dia.fieldDays}`, "change it in the call plan"],
                ["Oncology: calls a rep makes a day, field days", `${onc.callsPerRepDay}, ${onc.fieldDays}`, "change it in the call plan"],
                ...fixed,
              ])
              .map(([a, v, s]) => (
                <tr key={a}>
                  <th scope="row">{a}</th>
                  <td className="n"><span className="as">{v}</span></td>
                  <td>{s}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <p className="limits">
        <b>What this is not.</b> Not any company&apos;s sales force, call plan or alignment; not a forecast; not based on what any doctor prescribes. It shows how a sizing and an alignment follow from stated assumptions and public counts, and where the shortcuts are.
      </p>
      <footer className="foot" id="end">
        <div className="foot-grid">
          <div>
            <h2>Sources</h2>
            <ul>
              {d.meta.sources.map((s) => (
                <li key={s.url + s.name}>
                  {s.name}, {s.publisher}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2>Take it further</h2>
            <ul>
              <li>
                <a href="/downloads/Field-Force-Sizing-Model.xlsx" download>
                  Sizing model (Excel, {d.workbookKb} KB)
                </a>
                : pick a franchise, change the call plan, get reps by state. Live formulas, checked in Excel against an independent calculation.
              </li>
              {repoUrl && (
                <li>
                  <a href={repoUrl}>The code and data on GitHub</a>, including the alignment and the scorecard as text.
                </li>
              )}
            </ul>
          </div>
          <div>
            <h2>Built by</h2>
            <p style={{ margin: 0 }}>Mohammad Uzair Khan. Part of a set with Rx Market Pulse, Trial Pipeline Benchmark and Drug Price Watch.</p>
          </div>
        </div>
        <p className="disc">An independent case study built from public data. Not produced or endorsed by MSD or any company named. Built {longDate(d.meta.built)}.</p>
      </footer>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------- the page

export function Report({ data: d, repoUrl }: { data: Dataset; repoUrl?: string }) {
  const [franchise, setFranchise] = useState<Franchise>("diabetes");
  const [map, setMap] = useState<MapData | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/data/map.json")
      .then((res) => res.json())
      .then((j) => live && setMap(MapShapes.parse(j) as MapData))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  const h = d.headline;
  const dia = h.franchises.diabetes;
  const onc = h.franchises.oncology;
  if (maxColourSlot(d.counties) > 5) throw new Error("the data uses a map tint above slot 5; re-tune the reserve tints");
  return (
    <>
      <a className="skip" href="#main">
        Skip to the report
      </a>
      <header className="bar">
        <div className="shell bar-in">
          <a className="brand" href="#top">
            Field Force Planner
          </a>
          <nav aria-label="Sections">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`}>
                {s.label}
              </a>
            ))}
            <a className="dl" href="/downloads/Field-Force-Sizing-Model.xlsx" download>
              Sizing model (Excel, {d.workbookKb} KB)
            </a>
          </nav>
          <details className="sections-menu">
            <summary className="btn">Sections</summary>
            <div className="menu">
              {SECTIONS.map((s) => (
                <a key={s.id} href={`#${s.id}`}>
                  {s.label}
                </a>
              ))}
              <a href="/downloads/Field-Force-Sizing-Model.xlsx" download>
                Sizing model (Excel)
              </a>
            </div>
          </details>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="shell" tabIndex={-1}>
        <div className="hero" id="top">
          <p className="kicker">
            <b>Sales-force sizing and territory alignment for a US pharma launch, from public data.</b> A commercial-analytics case study by Mohammad Uzair Khan.
          </p>
          <h1>
            A diabetes launch needs about {reps(dia.reps)} reps. An oncology launch needs about {reps(onc.reps)}.
          </h1>
          <p className="lede">
            Counted from {(h.registry.kept / 1e6).toFixed(2)} million active providers in the CMS registry, at <span className="as">{dia.callsPerRepDay} calls a day</span> over{" "}
            <span className="as">{dia.fieldDays} field days</span> (diabetes). One territory per rep, all {int(h.counties)} counties.
          </p>
          <Plate d={d} map={map} franchise={franchise} setFranchise={setFranchise} />
        </div>
        <HowMany d={d} />
        <CallPlan d={d} />
        <Alignment d={d} />
        <Limits d={d} />
        <Quality d={d} />
        <Method d={d} repoUrl={repoUrl} />
      </main>
    </>
  );
}
