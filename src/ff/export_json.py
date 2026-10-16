"""Write the JSON files the dashboard reads (dashboard/public/data/*.json).

    python -m ff.export_json

Every number the page, the README and the CV quote comes from headline.json, computed here from the warehouse and the
alignment output; nothing is typed in by hand.
"""

from __future__ import annotations

import csv
import json
from datetime import date

from . import sizing
from .build import connect
from .sources import MARTS, REF, ROOT

OUT = ROOT / "dashboard" / "public" / "data"


def _write(name: str, payload: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _r(x: float | None, d: int = 2):
    return None if x is None else round(float(x), d)


def _read(name: str) -> list[dict]:
    with (MARTS / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def color_territories(county_terr: dict[str, int], edges: list[tuple[str, str]], max_colors: int = 10) -> dict[int, int]:
    """Greedy colouring so neighbouring territories get different colours on the map (most-connected first)."""
    nbrs: dict[int, set[int]] = {}
    for a, b in edges:
        ta, tb = county_terr.get(a), county_terr.get(b)
        if ta is not None and tb is not None and ta != tb:
            nbrs.setdefault(ta, set()).add(tb)
            nbrs.setdefault(tb, set()).add(ta)
    colour: dict[int, int] = {}
    for t in sorted(set(county_terr.values()), key=lambda t: (-len(nbrs.get(t, ())), t)):
        used = {colour[n] for n in nbrs.get(t, ()) if n in colour}
        colour[t] = next((c for c in range(max_colors) if c not in used), max_colors - 1)
    return colour


def export_all() -> dict:
    con = connect(read_only=True)
    frs = sizing.load_franchises()
    rules = sizing.load_rules()
    segs = sizing.load_county_segments()
    al = json.loads((MARTS / "alignment.json").read_text(encoding="utf-8"))
    val = json.loads((MARTS / "validation.json").read_text(encoding="utf-8"))
    edges = [(r["a"], r["b"]) for r in _read("edges.csv")]
    with (REF / "rx_state_area.csv").open(encoding="utf-8", newline="") as fh:
        names = {r["state"]: r["state_name"] for r in csv.DictReader(fh)}

    # ----------------------------------------------------------- sizing
    sizing_out = {}
    for key, fr in frs.items():
        calls = sum(sizing.county_workload(key, segs, rules).values())
        seg_rows = sizing.by_segment(key, segs, rules)
        st = sizing.by_state(key, segs, rules, fr)
        counties = sizing.load_counties(key)
        adults, patients = {}, {}
        for c in counties.values():
            adults[c["state"]] = adults.get(c["state"], 0) + c["adults"]
            patients[c["state"]] = patients.get(c["state"], 0.0) + c["patients"]
        sizing_out[key] = {
            "label": fr.label, "patientLabel": fr.patient_label, "callsPerRepDay": fr.calls_per_rep_day,
            "fieldDays": fr.field_days, "capacity": fr.capacity, "calls": _r(calls, 0), "reps": _r(calls / fr.capacity, 2),
            "segments": [{"segment": r["segment"], "tier": r["tier"], "providers": int(r["providers"]), "share": r["share"],
                          "targeted": _r(r["targeted"], 0), "callsPerYear": r["calls_per_year"], "calls": _r(r["calls"], 0)}
                         for r in seg_rows],
            "states": [{"state": s, "name": names[s], "calls": _r(v["calls"], 0), "reps": _r(v["reps"], 2),
                        "adults": adults[s], "patients": _r(patients[s], 0),
                        "repsPer100k": _r(v["reps"] / adults[s] * 100000, 3)} for s, v in st.items()],
        }
    _write("sizing.json", sizing_out)

    # ----------------------------------------------------------- alignment and the county map
    order = [r["county"] for r in _read("county.csv") if r["franchise"] == "diabetes"]
    info = {r["county"]: r for r in _read("county.csv") if r["franchise"] == "diabetes"}
    counties_out: dict = {"order": order, "name": [info[c]["name"] for c in order], "state": [info[c]["state"] for c in order],
                          "pop": [int(info[c]["pop"]) for c in order]}
    align_out = {}
    for key in frs:
        terr = {r["id"]: r for r in _read(f"alignment_territory_{key}.csv")}
        cty = {r["county"]: r for r in _read(f"alignment_county_{key}.csv")}
        tid = {i: n + 1 for n, i in enumerate(sorted(terr))}  # T0001 -> 1
        county_terr = {c: tid[r["territory"]] for c, r in cty.items()}
        colour = color_territories(county_terr, edges)
        pat = {r["county"]: float(r["patients"]) for r in _read("county.csv") if r["franchise"] == key}
        counties_out[key] = {"territory": [county_terr[c] for c in order], "colour": [colour[county_terr[c]] for c in order],
                             "share": [_r(float(cty[c]["share"]), 2) for c in order],
                             "touching": [int(cty[c]["territories"]) for c in order],
                             "patients": [_r(pat[c], 0) for c in order]}
        a = al[key]
        align_out[key] = {
            "reps": _r(a["reps"], 2), "territories": a["territories"], "alpha": a["alpha"], "metrics": a["metrics"],
            "regions": a["regions"], "bridges": a["bridges"], "weights": a["weights"],
            "territoryRows": [{"id": i, "n": tid[i], "weight": _r(float(r["weight"]), 3), "calls": _r(float(r["calls"]), 0),
                               "patients": _r(float(r["patients"]), 0), "counties": int(r["counties"])}
                              for i, r in sorted(terr.items())],
        }
    _write("counties.json", counties_out)
    _write("alignment.json", align_out)

    # ----------------------------------------------------------- quality and meta
    with (MARTS / "dq_checks.csv").open(encoding="utf-8", newline="") as fh:
        quality = list(csv.DictReader(fh))
    _write("quality.json", quality)
    _write("validation.json", val)
    _write("meta.json", {"built": date.today().isoformat(), "sources": [
        {"name": "NPPES NPI registry, monthly file V2, October 2026", "publisher": "CMS", "url": "https://download.cms.gov/nppes/NPI_Files.html"},
        {"name": "NPPES deactivation report, 12 October 2026", "publisher": "CMS", "url": "https://download.cms.gov/nppes/NPI_Files.html"},
        {"name": "NUCC Health Care Provider Taxonomy, version 25.1", "publisher": "National Uniform Claim Committee", "url": "https://www.nucc.org/"},
        {"name": "ZCTA to county relationship file, 2020; county Gazetteer 2021; county adjacency", "publisher": "US Census Bureau", "url": "https://www.census.gov/geographies/reference-files.html"},
        {"name": "County population estimates by age, vintage 2021", "publisher": "US Census Bureau", "url": "https://www.census.gov/programs-surveys/popest.html"},
        {"name": "PLACES: local data for better health, county data (2023 release; Florida from 2024)", "publisher": "CDC", "url": "https://www.cdc.gov/places"},
        {"name": "State drug spend by therapeutic area, 2025 (reality check)", "publisher": "CMS, via Rx Market Pulse", "url": "https://github.com/f20230125-sudo/rx-market-pulse"},
    ]})

    # ----------------------------------------------------------- headline
    n_all, n_ind, n_blank = con.execute("""select count(*), count(*) filter (where entity_type = '1'),
                                                  count(*) filter (where entity_type is null) from stg_nppes""").fetchone()
    kept = con.execute("select count(*) from dim_hcp").fetchone()[0]
    matched, placed = con.execute("select count(county), count(*) from hcp_geo").fetchone()
    pop, adults_total = con.execute("select sum(pop), sum(adults) from (select distinct county, pop, adults from dim_county)").fetchone()
    checks = {st: sum(1 for c in quality if c["status"] == st) for st in ("pass", "warn", "fail", "info")}
    head = {
        "registry": {"records": n_all, "individuals": n_ind, "deactivated": n_blank, "kept": kept,
                     "matchedToCounty": matched, "matchRate": _r(matched / placed, 4)},
        "counties": 3143, "population": int(pop), "adults": int(adults_total),
        "franchises": {},
        "validation": {v["franchise"]: {"sizeRho": _r(v["size_rho"], 2), "intensityRho": _r(v["intensity_rho"], 2),
                                         "states": v["states"]} for v in val},
        "checks": {**checks, "total": len(quality)},
        "built": date.today().isoformat(),
    }
    for key in frs:
        s, a = sizing_out[key], align_out[key]
        m, b = a["metrics"]["aligned"], a["metrics"]["baseline"]
        head["franchises"][key] = {
            "label": s["label"], "reps": s["reps"], "territories": a["territories"], "calls": s["calls"],
            "providers": sum(x["providers"] for x in s["segments"]),
            "targeted": _r(sum(x["targeted"] for x in s["segments"]), 0),
            "capacity": s["capacity"], "callsPerRepDay": s["callsPerRepDay"], "fieldDays": s["fieldDays"],
            "cvAligned": _r(m["cv"], 4), "cvBaseline": _r(b["cv"], 3),
            "within10": _r(m["within_10pct"], 3), "within25": _r(m["within_25pct"], 3),
            "baselineWithin25": _r(b["within_25pct"], 3), "baselineMax": _r(b["max_over_mean"], 1),
            "alignedMax": _r(m["max_over_mean"], 2), "alignedMin": _r(m["min_over_mean"], 2),
            "splitCounties": m["split_counties"], "radiusKm": _r(m["mean_radius_km"], 0),
            "baselineRadiusKm": _r(b["mean_radius_km"], 0), "crossingStateShare": _r(m["crossing_state_share"], 3),
            "topState": max(s["states"], key=lambda x: x["reps"])["name"],
            "topStateReps": max(x["reps"] for x in s["states"]),
        }
    _write("headline.json", head)
    return head


def main() -> int:
    print(json.dumps(export_all(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
