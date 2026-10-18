import { describe, expect, it } from "vitest";
import { int, longDate, pct, reps, rho } from "./format";

describe("formatting", () => {
  it("prints counts and reps with separators", () => {
    expect(int(9_852_180)).toBe("9,852,180");
    expect(reps(1309.81)).toBe("1,310");
  });
  it("prints shares and signed correlations with a true minus", () => {
    expect(pct(0.996, 1)).toBe("99.6%");
    expect(rho(0.8642)).toBe("0.86");
    expect(rho(-0.1)).toBe("−0.10");
  });
  it("writes dates in words", () => {
    expect(longDate("2026-10-16")).toBe("16 October 2026");
  });
});
