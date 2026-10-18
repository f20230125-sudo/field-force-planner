import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// The contrast table in DESIGN.md, recomputed from the real CSS, so changing a colour cannot quietly break it.
const css = fs.readFileSync(path.join(process.cwd(), "src", "app", "globals.css"), "utf-8");

function block(selector: RegExp): Record<string, string> {
  const m = css.match(selector);
  expect(m, String(selector)).toBeTruthy();
  const out: Record<string, string> = {};
  for (const [, k, v] of m![1].matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) out[k] = v;
  return out;
}
const light = block(/:root \{\s*color-scheme: light;([\s\S]*?)\n\}/);
const dark = { ...light, ...block(/:root\[data-theme="dark"\] \{([\s\S]*?)\n\}/) };

const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lin = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (h: string) => {
  const [r, g, b] = rgb(h).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const mix = (a: string, b: string, pctA: number) => {
  const A = rgb(a);
  const B = rgb(b);
  return `#${A.map((v, i) => Math.round((v * pctA + B[i] * (100 - pctA)) / 100).toString(16).padStart(2, "0")).join("")}`;
};

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("contrast, %s theme", (_name, t) => {
  it("text on paper and on the raised paper reaches 4.5:1", () => {
    for (const k of ["ink", "ink-2", "ink-3"]) {
      expect(contrast(t[k], t.paper), k).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t[k], t["paper-2"]), k).toBeGreaterThanOrEqual(4.5);
    }
  });
  it("text on the yellow cell, its hover state and the tolerance band reaches 4.5:1", () => {
    const hover = mix(t["cell-rule"], t.cell, 25);
    const tol = mix(t.cell, t.paper, 35);
    expect(contrast(t.ink, t.cell), "ink on a cell").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t["ink-2"], t.cell), "ink-2 on a cell").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.ink, hover), "ink on a hovered cell").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t.ink, tol), "ink on the tolerance band").toBeGreaterThanOrEqual(4.5);
    expect(contrast(t["ink-3"], tol), "ink-3 on the tolerance band").toBeGreaterThanOrEqual(4.5);
  });
  it("the yellow rule and the control edge are visible marks (3:1 on paper)", () => {
    expect(contrast(t["cell-rule"], t.paper)).toBeGreaterThanOrEqual(3);
    expect(contrast(t.mute, t.paper)).toBeGreaterThanOrEqual(3);
  });
  it("the selected toggle (paper on ink) is readable", () => {
    expect(contrast(t.paper, t.ink)).toBeGreaterThanOrEqual(4.5);
  });
  it("the ink cut line is visible against every one of the ten territory tints (3:1)", () => {
    for (let i = 0; i < 10; i++) expect(contrast(t.ink, t[`t${i}`]), `tint ${i}`).toBeGreaterThanOrEqual(3);
  });
  it("the six tints in use are told apart from each other", () => {
    for (let i = 0; i < 6; i++) for (let j = i + 1; j < 6; j++) expect(t[`t${i}`], `${i} vs ${j}`).not.toBe(t[`t${j}`]);
  });
});

describe("the tokens themselves", () => {
  it("share paper, ink and mute with the other three MSD sites", () => {
    expect(light.paper).toBe("#faf8f3");
    expect(light.ink).toBe("#15302c");
    expect(light.mute).toBe("#948e7f");
    expect(dark.paper).toBe("#111817");
  });
  it("use the Excel input-cell yellow as the one accent", () => {
    expect(light.cell).toBe("#f8eba9");
    expect(light["cell-rule"]).toBe("#978429");
    expect(dark.cell).toBe("#463d0e");
    expect(dark["cell-rule"]).toBe("#b19b28");
  });
  it("define no other site's accent", () => {
    expect(css).not.toMatch(/--(berry|teal|ochre|denim)/);
  });
});
