import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { realDataset } from "@/lib/fixtures";
import { Report } from "./Report";

describe("the page, rendered from the real data", () => {
  const html = renderToStaticMarkup(<Report data={realDataset()} repoUrl="https://github.com/example/repo" />);
  it("opens with the answer in numbers", () => {
    expect(html).toMatch(/A diabetes launch needs about 1,310 reps\. An oncology launch needs about 474\./);
  });
  it("has the six sections in order, each with a heading", () => {
    const ids = ["how-many", "call-plan", "alignment", "limits", "quality", "method"];
    let at = 0;
    for (const id of ids) {
      const i = html.indexOf(`id="${id}"`, at);
      expect(i, id).toBeGreaterThan(at);
      at = i;
      expect(html).toContain(`id="${id}-h"`);
    }
  });
  it("marks assumptions in yellow and says what yellow means", () => {
    expect(html).toContain('class="as"');
    expect(html).toContain("A yellow number is an assumption, not a count.");
  });
  it("admits what the map cannot show", () => {
    expect(html).toContain("865 counties are cut between territories");
    expect(html).toContain("838 of the 1,310 territories");
  });
  it("offers the Excel model and the code", () => {
    expect(html).toContain('href="/downloads/Field-Force-Sizing-Model.xlsx"');
    expect(html).toContain("https://github.com/example/repo");
  });
  it("prints no placeholder or broken number anywhere", () => {
    expect(html).not.toMatch(/undefined|NaN|\[object|Infinity/);
  });
  it("uses no em dash", () => {
    expect(html.includes(String.fromCharCode(0x2014))).toBe(false);
  });
});
