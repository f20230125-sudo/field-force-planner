// Builds public/data/map.json (the county shapes, the diabetes cut lines, state lines and the nation outline) and
// public/data/cut-oncology.json (the oncology cut lines, fetched only when a visitor switches to oncology).
//   node scripts/build-map.mjs        (npm runs it before every build and dev start)
//
// us-atlas is Census cartographic boundary data, already projected to Albers USA with Alaska and Hawaii inset. Everything about a
// territory comes from public/data/counties.json; nothing is typed here.
//
// Paths are written with whole-pixel coordinates, the first point absolute and every other point as a step from the last
// ("l1 2-3 4"). That draws the shapes d3-geo's own string output draws at zero decimals (a test compares every point), in
// far fewer bytes.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";

// Chugach (02063) and Copper River (02066) are one area, Valdez-Cordova (02261), in the shapes.
const MERGED = { "02261": "02063" };

/** A d3-geo path context that writes compact SVG path data. */
function stepPath() {
  let out = "";
  let x0 = 0;
  let y0 = 0;
  let stepping = false;
  const num = (n, first) => (n < 0 || first ? `${n}` : ` ${n}`);
  const context = {
    moveTo(x, y) {
      x0 = Math.round(x);
      y0 = Math.round(y);
      out += `M${x0},${y0}`;
      stepping = false;
    },
    lineTo(x, y) {
      const nx = Math.round(x);
      const ny = Math.round(y);
      const dx = nx - x0;
      const dy = ny - y0;
      if (dx === 0 && dy === 0) return;
      out += `${stepping ? num(dx, false) : `l${dx}`}${num(dy, false)}`;
      stepping = true;
      x0 = nx;
      y0 = ny;
    },
    closePath() {
      out += "z";
      stepping = false;
    },
    arc() {},
    rect() {},
  };
  return {
    draw(geometry) {
      out = "";
      stepping = false;
      geoPath(null, context)(geometry);
      return out;
    },
  };
}

export function buildMap(atlas, counties) {
  const measure = geoPath().digits(0);
  const writer = stepPath();
  const draw = (g) => writer.draw(g);
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
    d.push(draw(f));
    row.push(lookup(id));
    const [[x0, y0], [x1, y1]] = measure.bounds(f);
    const st = counties.state[lookup(id)];
    const b = stateBoxes[st];
    stateBoxes[st] = b ? [Math.min(b[0], x0), Math.min(b[1], y0), Math.max(b[2], x1), Math.max(b[3], y1)] : [x0, y0, x1, y1];
  }
  const cutFor = (key) =>
    draw(
      mesh(atlas, atlas.objects.counties, (a, b) => {
        const ra = lookup(String(a.id));
        const rb = lookup(String(b.id));
        return a !== b && ra !== undefined && rb !== undefined && counties[key].territory[ra] !== counties[key].territory[rb];
      }),
    );
  const [[x0, y0], [x1, y1]] = measure.bounds(feature(atlas, atlas.objects.nation));
  return {
    viewBox: [Math.floor(x0) - 4, Math.floor(y0) - 4, Math.ceil(x1 - x0) + 8, Math.ceil(y1 - y0) + 8],
    ids,
    d,
    row,
    cut: { diabetes: cutFor("diabetes"), oncology: cutFor("oncology") },
    states: draw(mesh(atlas, atlas.objects.states, (a, b) => a !== b)),
    nation: draw(feature(atlas, atlas.objects.nation)),
    stateBoxes,
  };
}

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const counties = JSON.parse(fs.readFileSync(path.join(root, "public", "data", "counties.json"), "utf-8"));
  const atlas = JSON.parse(fs.readFileSync(path.join(root, "node_modules", "us-atlas", "counties-albers-10m.json"), "utf-8"));
  const map = buildMap(atlas, counties);
  const { oncology, ...cut } = map.cut;
  const out = path.join(root, "public", "data", "map.json");
  fs.writeFileSync(out, JSON.stringify({ ...map, cut }));
  const outOnc = path.join(root, "public", "data", "cut-oncology.json");
  fs.writeFileSync(outOnc, JSON.stringify({ d: oncology }));
  const kb = (p) => (fs.statSync(p).size / 1e3).toFixed(0);
  console.log(`wrote ${path.relative(root, out)}: ${map.ids.length} county shapes, ${kb(out)} KB; ${path.relative(root, outOnc)}: ${kb(outOnc)} KB`);
}
