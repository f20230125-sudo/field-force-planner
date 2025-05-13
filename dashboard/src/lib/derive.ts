import type { AlignFranchise, Counties, Franchise, SizingFranchise } from "./schema";

// Pure functions that turn the validated data into what the page draws. No React in here, so they can be tested.

// ---------------------------------------------------------------------------------------------- the call plan

export type Plan = { share: Record<string, number>; calls: Record<string, number>; callsPerDay: number; fieldDays: number };

/** The plan the alignment was built on: read from the data, never typed. */
export function defaultPlan(f: SizingFranchise): Plan {
  return {
    share: Object.fromEntries(f.segments.map((s) => [s.segment, s.share])),
    calls: Object.fromEntries(f.segments.map((s) => [s.segment, s.callsPerYear])),
    callsPerDay: f.callsPerRepDay,
    fieldDays: f.fieldDays,
  };
}

/** workload = providers x share targeted x calls per provider a year; reps = workload / (calls a day x field days). */
export function planReps(f: SizingFranchise, p: Plan): { calls: number; reps: number; targeted: number; byGroup: { segment: string; calls: number }[] } {
  const byGroup = f.segments.map((s) => ({ segment: s.segment, calls: s.providers * (p.share[s.segment] ?? 0) * (p.calls[s.segment] ?? 0) }));
  const calls = byGroup.reduce((a, g) => a + g.calls, 0);
  const targeted = f.segments.reduce((a, s) => a + s.providers * (p.share[s.segment] ?? 0), 0);
  const cap = p.callsPerDay * p.fieldDays;
  return { calls, reps: cap > 0 ? calls / cap : 0, targeted, byGroup };
}

export function samePlan(a: Plan, b: Plan): boolean {
  return a.callsPerDay === b.callsPerDay && a.fieldDays === b.fieldDays && JSON.stringify(a.share) === JSON.stringify(b.share) && JSON.stringify(a.calls) === JSON.stringify(b.calls);
}

// ---------------------------------------------------------------------------------------------- the rep ruler and ledger

/** One tick is one rep, whole ticks only: 1,309.81 is drawn as 1,310. */
export const tickCount = (reps: number) => Math.max(0, Math.round(reps));

export type LedgerRow = { state: string; name: string; reps: number; whole: number; fraction: number; repsPer100k: number };

/** States by reps, each as whole ticks and a last tick at the height of its fraction. */
export function ledger(f: SizingFranchise): LedgerRow[] {
  return [...f.states]
    .sort((a, b) => b.reps - a.reps)
    .map((s) => ({ state: s.state, name: s.name, reps: s.reps, whole: Math.floor(s.reps), fraction: s.reps - Math.floor(s.reps), repsPer100k: s.repsPer100k }));
}

/** The share of all reps in the five states with the most. */
export function topShare(f: SizingFranchise, n = 5): { share: number; names: string[] } {
  const sorted = [...f.states].sort((a, b) => b.reps - a.reps);
  const total = f.states.reduce((a, s) => a + s.reps, 0);
  return { share: sorted.slice(0, n).reduce((a, s) => a + s.reps, 0) / total, names: sorted.slice(0, n).map((s) => s.name) };
}

export function densityRange(f: SizingFranchise): { lo: { name: string; v: number }; hi: { name: string; v: number } } {
  const s = [...f.states].sort((a, b) => a.repsPer100k - b.repsPer100k);
  return { lo: { name: s[0].name, v: s[0].repsPer100k }, hi: { name: s[s.length - 1].name, v: s[s.length - 1].repsPer100k } };
}

/** The tier that carries the most calls and its share. */
export function biggestGroup(f: SizingFranchise): { segment: string; share: number } {
  const total = f.segments.reduce((a, s) => a + s.calls, 0);
  const top = [...f.segments].sort((a, b) => b.calls - a.calls)[0];
  return { segment: top.segment, share: top.calls / total };
}

// ---------------------------------------------------------------------------------------------- the map

export type SplitStats = { counties: number; popShare: number; visible: number; territories: number };

/** Counties cut between territories, their share of the population, and how many territories show as shapes. */
export function splitStats(c: Counties, key: Franchise, territories: number): SplitStats {
  const f = c[key];
  const total = c.pop.reduce((a, b) => a + b, 0);
  let n = 0;
  let pop = 0;
  for (let i = 0; i < f.touching.length; i++) {
    if (f.touching[i] > 1) {
      n++;
      pop += c.pop[i];
    }
  }
  return { counties: n, popShare: pop / total, visible: new Set(f.territory).size, territories };
}

/** The highest tint slot the data uses. The design guarantees six distinguishable tints; a seventh would need re-tuning. */
export function maxColourSlot(c: Counties): number {
  return Math.max(...c.diabetes.colour, ...c.oncology.colour);
}

export type Readout = { title: string; text: string };

/** The words for a county: its territory, weight and calls, or, for a cut county, how many territories share it. */
export function readout(c: Counties, a: AlignFranchise, key: Franchise, row: number, merged: boolean): Readout {
  const f = c[key];
  const t = a.territoryRows.find((r) => r.n === f.territory[row]);
  const title = `${c.name[row]}, ${c.state[row]}`;
  const cut = f.touching[row] > 1;
  const territory = t ? `${t.id}. Weight ${t.weight.toFixed(2)}, ${t.counties} ${t.counties === 1 ? "county" : "counties"}, ${Math.round(t.calls).toLocaleString("en-US")} calls a year, ${Math.round(t.patients).toLocaleString("en-US")} patients.` : "";
  const text = cut ? `Cut into ${f.touching[row]} territories. The largest holds ${Math.round(f.share[row] * 100)}% of the county. ${territory}` : territory;
  return { title, text: merged ? `${text} This shape covers two counties in the population file.` : text };
}

// ---------------------------------------------------------------------------------------------- the ranked profile

/** Weights sorted lightest to heaviest, with how many reach past the top of the axis and the heaviest. */
export function profile(weights: number[], top = 2): { sorted: number[]; over: number; heaviest: number } {
  const sorted = [...weights].sort((a, b) => a - b);
  return { sorted, over: sorted.filter((w) => w > top).length, heaviest: sorted[sorted.length - 1] };
}

// ---------------------------------------------------------------------------------------------- the reconciliation

export type Step = { label: string; value: number };

export function registrySteps(r: { records: number; individuals: number; kept: number; matchedToCounty: number }): Step[] {
  return [
    { label: "Records in the monthly file", value: r.records },
    { label: "Individuals (not organisations or deactivated numbers)", value: r.individuals },
    { label: "Active, in the 50 states and DC", value: r.kept },
    { label: "Placed in a county", value: r.matchedToCounty },
  ];
}
