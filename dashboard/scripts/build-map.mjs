// Builds public/data/map.json: the county shapes, the territory cut lines for both franchises, state lines and the nation outline.
//   node scripts/build-map.mjs        (npm runs it before every build and dev start)
//
// us-atlas is Census cartographic boundary data, already projected to Albers USA with Alaska and Hawaii inset. Everything about a
// territory comes from public/data/counties.json; nothing is typed here.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";

// Chugach (02063) and Copper River (02066) are one area, Valdez-Cordova (02261), in the shapes.
const MERGED = { "02261": "02063" };

export function buildMap(atlas, counties) {
  const path_ = geoPath().digits(0);
  const rowOf = new Map(counties.order.map((c, i) => [c, i]));
  const lookup = (id) => rowOf.get(MERGED[id] ?? id);
  const feats = feature(atlas, atlas.objects.counties).features.filter((f) => lookup(String(f.id)) !== undefined);
  const ids = [];
  const d = [];
  const row = [];
  const stateBoxes = {};
  for (const f of feats) {
    const id = String(f.id);
    ids.push(id);
    d.push(path_(f) ?? "");
    row.push(lookup(id));
    const [[x0, y0], [x1, y1]] = path_.bounds(f);
    const st = counties.state[lookup(id)];
    const b = stateBoxes[st];
    stateBoxes[st] = b ? [Math.min(b[0], x0), Math.min(b[1], y0), Math.max(b[2], x1), Math.max(b[3], y1)] : [x0, y0, x1, y1];
  }
  const cutFor = (key) =>
    path_(
      mesh(atlas, atlas.objects.counties, (a, b) => {
        const ra = lookup(String(a.id));
        const rb = lookup(String(b.id));
        return a !== b && ra !== undefined && rb !== undefined && counties[key].territory[ra] !== counties[key].territory[rb];
      }),
    ) ?? "";
  const [[x0, y0], [x1, y1]] = path_.bounds(feature(atlas, atlas.objects.nation));
  return {
    viewBox: [Math.floor(x0) - 4, Math.floor(y0) - 4, Math.ceil(x1 - x0) + 8, Math.ceil(y1 - y0) + 8],
    ids,
    d,
    row,
    cut: { diabetes: cutFor("diabetes"), oncology: cutFor("oncology") },
    states: path_(mesh(atlas, atlas.objects.states, (a, b) => a !== b)) ?? "",
    nation: path_(feature(atlas, atlas.objects.nation)) ?? "",
    stateBoxes,
  };
}

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const counties = JSON.parse(fs.readFileSync(path.join(root, "public", "data", "counties.json"), "utf-8"));
  const atlas = JSON.parse(fs.readFileSync(path.join(root, "node_modules", "us-atlas", "counties-albers-10m.json"), "utf-8"));
  const map = buildMap(atlas, counties);
  const out = path.join(root, "public", "data", "map.json");
  fs.writeFileSync(out, JSON.stringify(map));
  console.log(`wrote ${path.relative(root, out)}: ${map.ids.length} county shapes, ${(fs.statSync(out).size / 1e6).toFixed(2)} MB`);
}
