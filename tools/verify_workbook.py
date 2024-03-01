"""Compare Excel's own results with an independent calculation.

    python tools/verify_workbook.py <probe.json>

tools/excel_probe.ps1 drives Excel through the scenarios in excel/probe_scenarios.json and writes what Excel's formulas
returned. This script recomputes the Sizing, States and Checks cells from data/marts/state_segment.csv and
data/marts/state.csv with plain Python (no shared code with src/ff/workbook.py or src/ff/sizing.py, no spreadsheet
engine) and compares them: text exactly, numbers to 1e-9 relative.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ["Endocrinology", "Primary care physician", "Primary care NP or PA", "Oncology specialist"]
SEG_FRANCHISE = {"Endocrinology": "diabetes", "Primary care physician": "diabetes", "Primary care NP or PA": "diabetes",
                 "Oncology specialist": "oncology"}
TOL = 1e-9


def load():
    with (ROOT / "data" / "marts" / "state_segment.csv").open(encoding="utf-8", newline="") as fh:
        seg = list(csv.DictReader(fh))
    with (ROOT / "data" / "marts" / "state.csv").open(encoding="utf-8", newline="") as fh:
        facts = list(csv.DictReader(fh))
    with (ROOT / "data" / "ref" / "rx_state_area.csv").open(encoding="utf-8", newline="") as fh:
        names = {r["state"]: r["state_name"] for r in csv.DictReader(fh)}
    return seg, facts, names


def expected(sc, seg, facts, names):
    fr = sc["franchise"]
    calls_day, days = sc["capacity"][fr]
    cap = calls_day * days
    plan = sc["plan"]
    work = {}
    prov = {s: 0 for s in SEGMENTS}
    for r in seg:
        if r["franchise"] != fr:
            continue
        p = plan[r["segment"]]
        work[r["state"]] = work.get(r["state"], 0.0) + int(r["hcps"]) * p["share"] * p["calls"]
        prov[r["segment"]] += int(r["hcps"])
    states = sorted(names)
    adults = {s: 0 for s in states}
    pats = {s: 0.0 for s in states}
    for r in facts:
        if r["franchise"] == fr:
            adults[r["state"]] += int(r["adults"])
            pats[r["state"]] += float(r["patients"])
    total_calls = sum(work.values())
    reps = total_calls / cap
    rows = []
    for s in states:
        c = work.get(s, 0.0)
        d = c / cap
        rows.append([s, names[s], c, d, float(adults[s]), pats[s], (d / adults[s] * 100000) if adults[s] else "", d / reps])
    rows.append([None, "United States", total_calls, reps, float(sum(adults.values())), sum(pats.values()),
                 reps / sum(adults.values()) * 100000, sum(r[7] for r in rows)])
    seg_rows = []
    for sname in SEGMENTS:
        p = plan[sname]
        n = prov[sname]
        seg_rows.append([sname, float(n), p["share"], n * p["share"], p["calls"], n * p["share"] * p["calls"]])
    seg_rows.append([None, sum(r[1] for r in seg_rows), None, sum(r[3] for r in seg_rows), None, sum(r[5] for r in seg_rows)])
    head = [reps, total_calls, sum(r[3] for r in seg_rows[:4]), sum(r[1] for r in seg_rows[:4]), float(round(reps)), cap]
    ctrl = {k: sum(int(r["hcps"]) for r in seg if r["franchise"] == k) for k in ("diabetes", "oncology")}
    checks = ["OK",
              "OK" if abs(reps - seg_rows[4][5] / cap) < 1e-6 else "CHECK",
              "OK" if all(0 <= plan[s]["share"] <= 1 for s in SEGMENTS) else "CHECK",
              "OK" if cap > 0 else "CHECK",
              "OK" if sum(prov.values()) == ctrl[fr] else "CHECK",
              "OK"]
    return {"head": head, "segtab": seg_rows, "states": rows, "checks": checks,
            "overall": "ALL OK" if all(c == "OK" for c in checks) else "CHECK"}


def same(a, b) -> bool:
    if a in ("", None) and b in ("", None):
        return True
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=1e-9)


def main(argv):
    probe = json.loads(Path(argv[1]).read_text(encoding="utf-8-sig"))
    seg, facts, names = load()
    bad, n = [], 0
    for res in probe:
        exp = expected(res["inputs"], seg, facts, names)

        def cmp(name, got, want):
            nonlocal n
            n += 1
            if not same(got, want):
                bad.append(f"{res['id']} {name}: Excel {got!r} vs Python {want!r}")
        for i, (g, w) in enumerate(zip(res["head"], exp["head"])):
            cmp(f"Sizing!C{4 + i}", g, w)
        for i, (gr, wr) in enumerate(zip(res["segtab"], exp["segtab"])):
            for j, (g, w) in enumerate(zip(gr, wr)):
                if w is not None or g not in ("", None):
                    cmp(f"Sizing!seg{i}.{j}", g, w) if not (j == 0 and w is None) else None
        for i, (gr, wr) in enumerate(zip(res["states"], exp["states"])):
            for j, (g, w) in enumerate(zip(gr, wr)):
                if w is None:
                    continue
                cmp(f"States!r{i}.c{j}", g, w)
        for i, (g, w) in enumerate(zip(res["checks"], exp["checks"])):
            cmp(f"Checks!{i}", g, w)
        cmp("Checks!overall", res["overall"], exp["overall"])
    if bad:
        print(f"{len(bad)} of {n} cells differ:")
        for b in bad[:25]:
            print("  ", b)
        return 1
    print(f"{len(probe)} scenarios OK: {n} cells match the independent calculation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
