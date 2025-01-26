"""Data-quality scorecard.

    python -m ff.dq

Runs every check against the warehouse and the alignment output, then writes
    data/marts/dq_checks.csv           one row per check (also read by the dashboard)
    docs/data-quality-scorecard.md     the same, readable

Each check says what it measured, the number, and the rule it was held to. A check that fails its rule is not hidden:
the report leads with it. "info" means a measurement worth knowing that has no pass/fail rule.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass

import duckdb

from . import sizing
from .build import connect
from .sources import MARTS, REF, ROOT

DOCS = ROOT / "docs"


@dataclass
class Check:
    id: str
    dimension: str
    name: str
    result: str
    rule: str
    status: str  # pass | warn | fail | info
    note: str


def _one(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()


def _pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


def run(con: duckdb.DuckDBPyConnection) -> list[Check]:
    checks: list[Check] = []
    add = checks.append

    # ------------------------------------------------------------ the provider registry
    n_all, n_ind, n_org, n_blank = _one(con, """
        select count(*), count(*) filter (where entity_type = '1'), count(*) filter (where entity_type = '2'),
               count(*) filter (where entity_type is null) from stg_nppes""")
    add(Check("C01", "Completeness", "Every registry record is an individual, an organisation or a deactivated number",
              f"{n_all:,} records = {n_ind:,} individuals + {n_org:,} organisations + {n_blank:,} with no entity type",
              "the three add up", "pass" if n_ind + n_org + n_blank == n_all else "fail",
              "A deactivated NPI stays in the file with every field blank except the number."))
    dups = _one(con, "select count(*) - count(distinct npi) from stg_nppes")[0]
    bad_npi = _one(con, "select count(*) from stg_nppes where not regexp_matches(npi, '^[0-9]{10}$')")[0]
    add(Check("C02", "Uniqueness", "Each NPI appears once and has ten digits", f"{dups:,} duplicates, {bad_npi:,} malformed",
              "0 and 0", "pass" if dups == 0 and bad_npi == 0 else "fail", ""))
    n_report = _one(con, "select count(*) from stg_deactivated")[0]
    blank_in_report = _one(con, "select count(*) from stg_nppes n join stg_deactivated d using (npi) where n.entity_type is null")[0]
    add(Check("C03", "Consistency", "Deactivated numbers in the monthly file match the separate deactivation report",
              f"{blank_in_report:,} of {n_blank:,} blank records are on the report ({n_report:,} listed)",
              "all of them, and the report lists at most 10 more", "pass" if blank_in_report == n_blank and n_report - n_blank <= 10 else "fail",
              "Two files from the same agency, built on different days; agreement to within one number is the expectation."))
    on_report = _one(con, "select count(*) from stg_nppes n join stg_deactivated d using (npi) where n.entity_type = '1'")[0]
    add(Check("C04", "Consistency", "Individuals still listed as active that the deactivation report lists",
              f"{on_report:,}", "excluded from the provider table", "info",
              "Removed from every count here, so a number cannot be both."))
    kept, us_ind = _one(con, """select (select count(*) from dim_hcp), count(*) filter (where country = 'US') from stg_nppes
                                where entity_type = '1'""")
    add(Check("C05", "Scope", "Individuals kept: active, in the 50 states and DC", f"{kept:,} of {n_ind:,} ({_pct(kept / n_ind)})",
              "report", "info", "Outside this scope: foreign addresses, territories (Puerto Rico, Guam, ...), deactivated."))
    flagged = _one(con, """select count(*) filter (where sw1 = 'Y' or sw2 = 'Y' or sw3 = 'Y' or sw4 = 'Y' or sw5 = 'Y'
                                  or sw6 = 'Y' or sw7 = 'Y' or sw8 = 'Y' or sw9 = 'Y' or sw10 = 'Y' or sw11 = 'Y' or sw12 = 'Y'
                                  or sw13 = 'Y' or sw14 = 'Y' or sw15 = 'Y') * 1.0 / count(*)
                           from stg_nppes where entity_type = '1'""")[0]
    add(Check("C06", "Validity", "Individuals with a primary taxonomy flagged", _pct(flagged, 2), "at least 99%",
              "pass" if flagged >= 0.99 else "warn", "Where none is flagged the first listed taxonomy is used."))
    codes = {r["taxonomy_code"] for r in csv.DictReader((REF / "segments.csv").open(encoding="utf-8"))}
    in_nucc = {c for (c,) in con.execute("select code from stg_nucc").fetchall()}
    missing = sorted(codes - in_nucc)
    add(Check("C07", "Validity", "Every taxonomy code used for a segment exists in the NUCC code set",
              f"{len(codes) - len(missing)} of {len(codes)}" + (f"; missing {missing}" if missing else ""), "all",
              "pass" if not missing else "fail", "Codes are NUCC 25.1."))

    # ------------------------------------------------------------ geography
    total, with_zip, matched = _one(con, "select count(*), count(zip5), count(county) from hcp_geo")
    add(Check("C08", "Validity", "Providers whose ZIP code is a readable five digits", _pct(with_zip / total, 2), "at least 99%",
              "pass" if with_zip / total >= 0.99 else "warn", ""))
    add(Check("C09", "Completeness", "Providers whose ZIP code reached a county", f"{matched:,} of {total:,} ({_pct(matched / total, 2)})",
              "at least 97%", "pass" if matched / total >= 0.97 else "warn",
              "A ZIP code is not a Census ZCTA: PO-box and single-building ZIPs have no area. Unmatched providers are "
              "left out of county counts, so every county figure is a slight undercount."))
    mism, ok = _one(con, "select count(*) filter (where hcp_state <> county_state), count(*) from hcp_geo where county is not null")
    add(Check("C10", "Consistency", "Provider's state agrees with the state of the county their ZIP maps to",
              f"{mism:,} of {ok:,} differ ({_pct(mism / ok, 3)})", "under 1%", "pass" if mism / ok < 0.01 else "warn",
              "A ZIP near a state line can map to the neighbouring state's county; the county wins."))
    clear = _one(con, """select sum(case when m.share_in_county >= 0.8 then 1 else 0 end) * 1.0 / count(*)
                         from hcp_geo g join map_zip_county m on m.zcta = g.zip5 where g.county is not null""")[0]
    add(Check("C11", "Consistency", "Providers in a ZIP area where one county holds at least 80% of the land", _pct(clear), "report",
              "info", "Where a ZIP area spans counties the provider goes to the county with most of its land. That is "
                      "right for most and wrong for some; city centres are better served by the dominant county than "
                      "the rural remainder, which is why land share is a fair rule here."))
    n_county, n_pop = _one(con, "select (select count(distinct county) from dim_county), (select count(*) from stg_popest)")
    add(Check("C12", "Completeness", "Counties kept after joining the Gazetteer, population and prevalence sources",
              f"{n_county:,} of {n_pop:,} in the population file", "all", "pass" if n_county == n_pop else "fail",
              "An earlier run used the 2023 Gazetteer, in which Connecticut has planning regions instead of counties, "
              "and silently lost 8 counties. The 2021 Gazetteer and the 2023 PLACES release use the old counties."))
    imp, nn = _one(con, "select count(*) filter (where prevalence_imputed), count(*) from dim_county where franchise = 'diabetes'")
    add(Check("C13", "Completeness", "Counties with no CDC PLACES estimate (given their state's median)",
              f"{imp} of {nn} ({_pct(imp / nn)})", "under 3%", "pass" if imp / nn < 0.03 else "warn",
              "The first run of this check found 67 counties, all of Florida: the 2023 PLACES release has no Florida "
              "data (the state did not release its 2021 survey). Florida now takes its 2022 estimates from the 2024 "
              "release. Any county still missing would get its state's median and be flagged in the county table."))
    share = _one(con, """select coalesce(sum(patients) filter (where prevalence_imputed), 0) / sum(patients)
                         from dim_county where franchise = 'diabetes'""")[0]
    add(Check("C14", "Completeness", "Share of diabetes patients that sit in imputed counties", _pct(share, 2), "under 3%",
              "pass" if share < 0.03 else "warn", ""))
    sym = _one(con, """select count(*) from stg_adjacency a left join stg_adjacency b on b.county = a.neighbour and b.neighbour = a.county
                       where b.county is null""")[0]
    add(Check("C15", "Consistency", "County adjacency is symmetric (if A touches B, B touches A)", f"{sym:,} one-way pairs", "0",
              "pass" if sym == 0 else "fail", ""))
    iso = _one(con, """select count(*) from (select distinct county from dim_county) d
                       where county not in (select a from mart_edges) and county not in (select b from mart_edges)""")[0]
    add(Check("C16", "Consistency", "Counties that touch no other county (islands)", f"{iso}", "report", "info",
              "Joined to the nearest mainland county by distance if within 300 km; Alaska and Hawaii are aligned separately."))

    # ------------------------------------------------------------ sizing and alignment
    fr, rules, segs = sizing.load_franchises(), sizing.load_rules(), sizing.load_county_segments()
    al = json.loads((MARTS / "alignment.json").read_text(encoding="utf-8"))
    ties, worst = [], 0.0
    for key, f in fr.items():
        by_county = sum(sizing.county_workload(key, segs, rules).values())
        by_state = sum(v["calls"] for v in sizing.by_state(key, segs, rules, f).values())
        by_seg = sum(r["calls"] for r in sizing.by_segment(key, segs, rules))
        worst = max(worst, abs(by_county - by_state), abs(by_county - by_seg))
        ties.append(f"{key} {by_county:,.0f}")
    add(Check("C17", "Reconciliation", "Workload adds up the same by county, by state and by segment", "; ".join(ties) + " calls a year",
              "equal to the call", "pass" if worst < 1e-6 else "fail", ""))
    cnt = _one(con, "select count(*) from fact_hcp_county")[0]
    seg_sum = _one(con, "select sum(hcps) from fact_hcp_county")[0]
    seg_all = _one(con, "select count(*) from hcp_segment where county is not null")[0]
    add(Check("C18", "Reconciliation", "Providers by county and segment add up to providers placed in a segment",
              f"{seg_sum:,} vs {seg_all:,}", "equal", "pass" if seg_sum == seg_all else "fail", ""))
    for key, a in al.items():
        m = a["metrics"]["aligned"]
        base = a["metrics"]["baseline"]
        add(Check(f"C19{'ab'[list(al).index(key)]}", "Alignment", f"{key.capitalize()}: territories are connected, none empty, count equals reps",
                  f"{a['territories']} territories, {m['disconnected']} disconnected, reps {a['reps']:.1f}", "0 disconnected; count = round(reps)",
                  "pass" if m["disconnected"] == 0 and a["territories"] == round(a["reps"]) else "fail", ""))
        add(Check(f"C20{'ab'[list(al).index(key)]}", "Alignment", f"{key.capitalize()}: territory workload within 25% of the target",
                  f"{_pct(m['within_25pct'])} of territories (within 10%: {_pct(m['within_10pct'])}); baseline {_pct(base['within_25pct'])}",
                  "at least 95%", "pass" if m["within_25pct"] >= 0.95 else "warn",
                  "The baseline cuts the same number of territories with equal numbers of counties, blind to workload."))
        add(Check(f"C21{'ab'[list(al).index(key)]}", "Alignment", f"{key.capitalize()}: counties split between territories",
                  f"{m['split_counties']:,} of {n_county:,}", "report", "info",
                  "A county worth more than 0.15 territories is cut into equal pieces (ZIP-level bricks would do this properly)."))
    val = json.loads((MARTS / "validation.json").read_text(encoding="utf-8"))
    add(Check("C22", "Validation", "Prevalence-based demand against observed Medicaid drug spend, by state",
              "; ".join(f"{v['franchise']}: size rho {v['size_rho']:.2f}, spend per enrollee rho {v['intensity_rho']:.2f}" for v in val),
              "report", "info",
              "Demand follows population (high rho) but prevalence does not explain Medicaid spend per enrollee (rho near 0): "
              "formulary, benefit design and who is enrolled dominate. Territory weights therefore balance workload first."))
    return checks


def write(checks: list[Check]) -> None:
    MARTS.mkdir(parents=True, exist_ok=True)
    with open(MARTS / "dq_checks.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(checks[0])), lineterminator="\n")
        w.writeheader()
        for c in checks:
            w.writerow(asdict(c))
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("pass", "warn", "fail", "info")}
    lines = ["# Data-quality scorecard", "",
             f"{len(checks)} checks run against the warehouse and the alignment. {counts['pass']} pass, {counts['warn']} warn, "
             f"{counts['fail']} fail, {counts['info']} are measurements with no rule.", "",
             "Regenerate with `python -m ff.dq`. Failures and warnings come first.", ""]
    order = {"fail": 0, "warn": 1, "pass": 2, "info": 3}
    for c in sorted(checks, key=lambda c: (order[c.status], c.id)):
        lines += [f"## {c.id} {c.name}", "", f"- **Status:** {c.status}", f"- **Result:** {c.result}", f"- **Rule:** {c.rule}"]
        if c.note:
            lines.append(f"- **Note:** {c.note}")
        lines.append("")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data-quality-scorecard.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    con = connect(read_only=True)
    checks = run(con)
    write(checks)
    for c in checks:
        print(f"{c.id} {c.status:<5} {c.name}: {c.result}")
    return 1 if any(c.status == "fail" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
