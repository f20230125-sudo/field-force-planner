import { z } from "zod";

// One schema per file in public/data. The page is built from these, so a field that is missing, renamed or the
// wrong type fails the build with the file name, instead of printing "undefined" on the page. Only the server reads
// these; the browser gets the validated result, so nothing here may be imported by a client component except as a type.

export type { Franchise } from "./franchises";

const num = z.number();

const Frn = z.object({
  label: z.string(),
  reps: num,
  territories: num,
  calls: num,
  providers: num,
  targeted: num,
  capacity: num,
  callsPerRepDay: num,
  fieldDays: num,
  cvAligned: num,
  cvBaseline: num,
  cvGrown: num,
  within10: num,
  within25: num,
  baselineWithin25: num,
  baselineMax: num,
  alignedMax: num,
  alignedMin: num,
  splitCounties: num,
  radiusKm: num,
  baselineRadiusKm: num,
  crossingStateShare: num.nullable(),
  topState: z.string(),
  topStateReps: num,
});

export const Headline = z.object({
  registry: z.object({ records: num, individuals: num, deactivated: num, kept: num, matchedToCounty: num, matchRate: num }),
  counties: num,
  population: num,
  adults: num,
  franchises: z.object({ diabetes: Frn, oncology: Frn }),
  validation: z.object({
    diabetes: z.object({ sizeRho: num, intensityRho: num, states: num }),
    oncology: z.object({ sizeRho: num, intensityRho: num, states: num }),
  }),
  checks: z.object({ pass: num, warn: num, fail: num, info: num, total: num }),
  built: z.string(),
});
export type Headline = z.infer<typeof Headline>;

const Segment = z.object({
  segment: z.string(),
  tier: z.string(),
  providers: num,
  share: num,
  targeted: num,
  callsPerYear: num,
  calls: num,
});
const StateRow = z.object({ state: z.string(), name: z.string(), calls: num, reps: num, adults: num, patients: num, repsPer100k: num });
const Sizing1 = z.object({
  label: z.string(),
  patientLabel: z.string(),
  callsPerRepDay: num,
  fieldDays: num,
  capacity: num,
  calls: num,
  reps: num,
  segments: z.array(Segment),
  states: z.array(StateRow),
});
export const Sizing = z.object({ diabetes: Sizing1, oncology: Sizing1 });
export type Sizing = z.infer<typeof Sizing>;
export type SizingFranchise = z.infer<typeof Sizing1>;

const Metrics = z.object({
  territories: num,
  cv: num,
  min_over_mean: num,
  max_over_mean: num,
  within_10pct: num,
  within_25pct: num,
  mean_radius_km: num,
  median_radius_km: num,
  disconnected: num,
  split_counties: num,
  crossing_state_share: num.nullable(),
  bridges: num,
});
const Align1 = z.object({
  reps: num,
  territories: num,
  alpha: num,
  metrics: z.object({ aligned: Metrics, before_local_search: Metrics, baseline: Metrics }),
  regions: z.array(z.object({ counties: num, territories: num })),
  bridges: z.array(z.object({ a: z.string(), b: z.string(), km: num })),
  weights: z.object({ aligned: z.array(num), baseline: z.array(num) }),
  territoryRows: z.array(z.object({ id: z.string(), n: num, weight: num, calls: num, patients: num, counties: num })),
});
export const Alignment = z.object({ diabetes: Align1, oncology: Align1 });
export type Alignment = z.infer<typeof Alignment>;
export type AlignFranchise = z.infer<typeof Align1>;

const CountyF = z.object({
  territory: z.array(num),
  colour: z.array(num),
  share: z.array(num),
  touching: z.array(num),
  patients: z.array(num),
});
export const Counties = z.object({
  order: z.array(z.string()),
  name: z.array(z.string()),
  state: z.array(z.string()),
  pop: z.array(num),
  diabetes: CountyF,
  oncology: CountyF,
});
export type Counties = z.infer<typeof Counties>;

export const Quality = z.array(
  z.object({
    id: z.string(),
    dimension: z.string(),
    name: z.string(),
    result: z.string(),
    rule: z.string(),
    status: z.enum(["pass", "warn", "fail", "info"]),
    note: z.string(),
  }),
);
export type Quality = z.infer<typeof Quality>;

export const Meta = z.object({
  built: z.string(),
  sources: z.array(z.object({ name: z.string(), publisher: z.string(), url: z.string() })),
});
export type Meta = z.infer<typeof Meta>;

export type MapData = {
  viewBox: [number, number, number, number];
  /** One path per county shape, in the order of `ids`. */
  ids: string[];
  d: string[];
  /** Index into Counties.order for each shape, or -1 when the shape has no row (it is drawn in the colour of a sibling). */
  row: number[];
  /** The oncology cut lines are a separate file, fetched on first use (see `parseCut`). */
  cut: { diabetes: string; oncology?: string };
  states: string;
  nation: string;
  /** Bounding box of each state's shapes, for zooming. */
  stateBoxes: Record<string, [number, number, number, number]>;
};

export type Dataset = {
  headline: Headline;
  sizing: Sizing;
  alignment: Alignment;
  counties: Counties;
  quality: Quality;
  meta: Meta;
  workbookKb: number;
};
