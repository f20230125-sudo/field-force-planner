import type { MapData } from "./schema";

// The map shapes are fetched by the browser, so they are checked here with a few plain tests instead of a schema library
// (which would ship in the page bundle). A file that fails any of them is refused and the map stays on its loading line.

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const box = (v: unknown): v is [number, number, number, number] => Array.isArray(v) && v.length === 4 && v.every(isNum);

export function parseMapData(j: unknown): MapData {
  const m = j as Partial<MapData> | null;
  const ok =
    m != null &&
    box(m.viewBox) &&
    Array.isArray(m.ids) &&
    m.ids.every(isStr) &&
    Array.isArray(m.d) &&
    m.d.length === m.ids.length &&
    m.d.every(isStr) &&
    Array.isArray(m.row) &&
    m.row.length === m.ids.length &&
    m.row.every(isNum) &&
    m.cut != null &&
    isStr(m.cut.diabetes) &&
    isStr(m.states) &&
    isStr(m.nation) &&
    m.stateBoxes != null &&
    Object.values(m.stateBoxes).every(box);
  if (!ok) throw new Error("map.json does not have the expected shape");
  return m as MapData;
}

export function parseCut(j: unknown): string {
  const d = (j as { d?: unknown } | null)?.d;
  if (!isStr(d)) throw new Error("cut-oncology.json does not have the expected shape");
  return d;
}
