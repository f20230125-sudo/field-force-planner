"""Reality check: does demand built from public prevalence rank states like observed Medicaid drug spend?

    python -m ff.validate

Two questions per franchise, both as Spearman rank correlations over the states and DC:
  size       state patients (adults x prevalence) against Medicaid spend in the matching therapeutic area
  intensity  prevalence against that spend per Medicaid enrollee
The first is mostly about population (big states have both), so it is expected to be high and proves little; the second
strips size out and is the honest test. Whatever comes out is reported as found.
"""

from __future__ import annotations

import csv
import json

import numpy as np

from . import sizing
from .sources import MARTS, REF


def ranks(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties share the mean rank), 1-based."""
    order = np.argsort(a, kind="mergesort")
    r = np.empty(len(a))
    sa = a[order]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and sa[j + 1] == sa[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b) -> float:
    ra, rb = ranks(np.asarray(a, float)), ranks(np.asarray(b, float))
    return float(np.corrcoef(ra, rb)[0, 1])


def run() -> list[dict]:
    with (REF / "rx_state_area.csv").open(encoding="utf-8", newline="") as fh:
        rx = {r["state"]: r for r in csv.DictReader(fh)}
    out = []
    for key in sizing.load_franchises():
        counties = sizing.load_counties(key)
        pat: dict[str, float] = {}
        adults: dict[str, float] = {}
        for c in counties.values():
            pat[c["state"]] = pat.get(c["state"], 0.0) + c["patients"]
            adults[c["state"]] = adults.get(c["state"], 0.0) + c["adults"]
        col = {"diabetes": "spend_diabetes", "oncology": "spend_oncology"}[key]
        states = sorted(s for s in rx if s in pat and rx[s][col] and rx[s]["enrollment"])
        spend = [float(rx[s][col]) for s in states]
        per_enrollee = [float(rx[s][col]) / float(rx[s]["enrollment"]) for s in states]
        prevalence = [pat[s] / adults[s] for s in states]
        out.append({"franchise": key, "states": len(states),
                    "size_rho": spearman([pat[s] for s in states], spend),
                    "intensity_rho": spearman(prevalence, per_enrollee)})
    return out


def main() -> int:
    res = run()
    (MARTS / "validation.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        print(f"{r['franchise']}: {r['states']} states, size rho {r['size_rho']:.2f}, intensity rho {r['intensity_rho']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
