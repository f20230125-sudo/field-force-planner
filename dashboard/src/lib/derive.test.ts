import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { biggestGroup, defaultPlan, densityRange, ledger, maxColourSlot, planReps, profile, readout, registrySteps, samePlan, splitStats, tickCount, topShare } from "./derive";
import { realDataset } from "./fixtures";
import { buildMap } from "../../scripts/build-map.mjs";

const d = realDataset();

describe("the call plan", () => {
  it("the stated plan gives the headcount the data holds (so the page and the alignment agree)", () => {
    for (const k of ["diabetes", "oncology"] as const) {
      const r = planReps(d.sizing[k], defaultPlan(d.sizing[k]));
      expect(r.reps).toBeCloseTo(d.sizing[k].reps, 1);
      expect(r.calls).toBeCloseTo(d.sizing[k].calls, -1);
    }
  });
  it("doubling the calls a rep makes a day halves the reps", () => {
    const f = d.sizing.diabetes;
    const p = defaultPlan(f);
    expect(planReps(f, { ...p, callsPerDay: p.callsPerDay * 2 }).reps).toBeCloseTo(planReps(f, p).reps / 2, 6);
  });
  it("targeting nobody needs no reps, and a zero capacity is not a division by zero", () => {
    const f = d.sizing.oncology;
    const p = defaultPlan(f);
    expect(planReps(f, { ...p, share: Object.fromEntries(Object.keys(p.share).map((k) => [k, 0])) }).reps).toBe(0);
    expect(planReps(f, { ...p, callsPerDay: 0 }).reps).toBe(0);
  });
  it("recognises the stated plan", () => {
    const p = defaultPlan(d.sizing.diabetes);
    expect(samePlan(p, { ...p })).toBe(true);
    expect(samePlan(p, { ...p, fieldDays: p.fieldDays + 1 })).toBe(false);
  });
});

describe("rulers and ledger", () => {
  it("draw whole ticks: 1,309.81 is 1,310", () => {
    expect(tickCount(1309.81)).toBe(1310);
    expect(tickCount(473.57)).toBe(474);
    expect(tickCount(-3)).toBe(0);
  });
  it("order states by reps and split each into whole ticks and a fraction", () => {
    const rows = ledger(d.sizing.diabetes);
    expect(rows).toHaveLength(51);
    expect(rows[0].state).toBe("CA");
    expect(rows[0].whole + rows[0].fraction).toBeCloseTo(rows[0].reps, 10);
    expect(rows.reduce((a, r) => a + r.reps, 0)).toBeCloseTo(d.sizing.diabetes.reps, 0);
  });
  it("the five biggest states hold 36% of diabetes reps", () => {
    expect(topShare(d.sizing.diabetes).share).toBeCloseTo(0.363, 2);
    expect(densityRange(d.sizing.diabetes).hi.name).toBe("District of Columbia");
  });
  it("primary care carries nearly all diabetes calls", () => {
    const g = d.sizing.diabetes.segments.filter((s) => s.tier === "generalist").reduce((a, s) => a + s.calls, 0) / d.sizing.diabetes.calls;
    expect(g).toBeGreaterThan(0.9);
    expect(biggestGroup(d.sizing.diabetes).share).toBeGreaterThan(0.4);
  });
});

describe("the map data", () => {
  it("the data uses six map tints, the number the design guarantees to be distinguishable", () => {
    expect(maxColourSlot(d.counties)).toBeLessThanOrEqual(5);
  });
  it("865 diabetes counties are cut and hold 82.6% of the population; 838 territories show as shapes", () => {
    const s = splitStats(d.counties, "diabetes", d.alignment.diabetes.territories);
    expect(s.counties).toBe(865);
    expect(s.popShare).toBeCloseTo(0.8265, 3);
    expect(s.visible).toBe(838);
    expect(s.territories).toBe(1310);
  });
  it("neighbouring counties of one territory share a colour and the territory ids match the rows", () => {
    for (const k of ["diabetes", "oncology"] as const) {
      const byT = new Map<number, number>();
      d.counties[k].territory.forEach((t, i) => {
        const c = d.counties[k].colour[i];
        expect(byT.get(t) ?? c).toBe(c);
        byT.set(t, c);
      });
      const ids = new Set(d.alignment[k].territoryRows.map((r) => r.n));
      expect([...byT.keys()].every((t) => ids.has(t))).toBe(true);
    }
  });
  it("reads a county in words, and says when a county is cut", () => {
    const i = d.counties.name.indexOf("Los Angeles County");
    const r = readout(d.counties, d.alignment.diabetes, "diabetes", i, false);
    expect(r.title).toBe("Los Angeles County, CA");
    expect(r.text).toMatch(/^Cut into \d+ territories\. The largest holds \d+% of the county\./);
    const whole = d.counties.diabetes.touching.findIndex((t, j) => t === 1 && j > 10);
    expect(readout(d.counties, d.alignment.diabetes, "diabetes", whole, false).text).toMatch(/^T\d{4}\. Weight \d\.\d\d, \d+ (county|counties), [\d,]+ calls a year, [\d,]+ patients\./);
  });
});

describe("the reconciliation", () => {
  it("falls from records to individuals to kept to placed", () => {
    const s = registrySteps(d.headline.registry);
    expect(s.map((x) => x.value)).toEqual([...s.map((x) => x.value)].sort((a, b) => b - a));
    expect(s[0].value).toBe(9_852_180);
  });
  it("profile cuts weights past the axis and counts them", () => {
    const p = profile([0.5, 1, 3, 10]);
    expect(p.over).toBe(2);
    expect(p.heaviest).toBe(10);
    expect(p.sorted).toEqual([0.5, 1, 3, 10]);
  });
});

describe("the generated map", () => {
  const atlas = JSON.parse(fs.readFileSync(path.join(process.cwd(), "node_modules", "us-atlas", "counties-albers-10m.json"), "utf-8"));
  const map = buildMap(atlas, d.counties);
  it("draws every county but the two merged ones as one shape each, and drops the territories outside the data", () => {
    expect(map.ids).toHaveLength(3142); // 3,141 matched codes plus Valdez-Cordova, which stands for two
    expect(map.ids).toContain("02261");
    expect(map.ids.some((id: string) => id.startsWith("72"))).toBe(false); // Puerto Rico
    expect(new Set(map.ids).size).toBe(map.ids.length);
  });
  it("gives every shape a data row and every state a box to zoom to", () => {
    expect(map.row.every((r: number) => r >= 0 && r < d.counties.order.length)).toBe(true);
    expect(Object.keys(map.stateBoxes)).toHaveLength(51);
  });
  it("has a cut line for each franchise, and more of it for the finer alignment", () => {
    expect(map.cut.diabetes.length).toBeGreaterThan(map.cut.oncology.length);
    expect(map.states.length).toBeGreaterThan(1000);
  });
});
