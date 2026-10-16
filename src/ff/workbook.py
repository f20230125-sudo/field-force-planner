"""Field Force Sizing Model: an Excel workbook that turns a call plan into headcount, state by state.

    python -m ff.workbook            # writes excel/Field-Force-Sizing-Model.xlsx

Pick a franchise (diabetes sold to primary care and endocrinology, or oncology sold to oncologists), set what a rep can do
in a day and how often each kind of provider is called, and the workbook returns calls needed, reps needed, territories,
and the same by state. Every result is a live formula (SUMIFS over the Data sheet, INDEX/MATCH into the inputs); no
result is pasted in. The Data sheet holds one row per state, franchise and segment: how many providers the registry
lists there.

    workload (calls a year) = providers x share targeted x calls per provider per year
    reps needed             = workload / (calls per rep per day x field days)

The same arithmetic runs in src/ff/sizing.py; tools/verify_workbook.py drives Excel itself through six scenarios and
compares every cell with an independent calculation from data/marts/state_segment.csv.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import xlsxwriter

from . import sizing
from .sources import MARTS, REF, ROOT

OUT = ROOT / "excel" / "Field-Force-Sizing-Model.xlsx"
PROBE = ROOT / "excel" / "probe_scenarios.json"

INK = "#1F2A33"
ACCENT = "#6D4C9F"
SLATE = "#5B6672"
RULE = "#D9DEE3"
INPUT_FILL = "#FFF6D6"
INPUT_FONT = "#1D4ED8"

FIRST, LAST = 6, 56  # state rows on the States sheet (51)
TOTAL = 57


def load_state_names() -> dict[str, str]:
    with (REF / "rx_state_area.csv").open(encoding="utf-8", newline="") as fh:
        return {r["state"]: r["state_name"] for r in csv.DictReader(fh)}


def load_state_segment() -> list[dict]:
    with (MARTS / "state_segment.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["hcps"] = int(r["hcps"])
    return rows


def load_state() -> list[dict]:
    with (MARTS / "state.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["adults"], r["patients"] = int(r["adults"]), float(r["patients"])
    return rows


def segment_table(rules) -> list[dict]:
    """The four segments in a fixed order with their default call plan."""
    seen, out = set(), []
    for (fr, seg), r in rules.items():
        if (fr, seg) not in seen:
            seen.add((fr, seg))
            out.append({"franchise": fr, "segment": seg, "tier": r.tier, "calls": r.calls_per_year, "share": r.targeted_share})
    return out


def probe_scenarios(segs: list[dict]) -> list[dict]:
    """Six input sets for the probe: defaults for each franchise, then changes that exercise every input."""
    base = {s["segment"]: {"calls": s["calls"], "share": s["share"]} for s in segs}

    def mk(i, franchise, cap_d=None, cap_o=None, **chg):
        plan = {k: dict(v) for k, v in base.items()}
        for seg, (c, sh) in chg.items():
            seg = seg.replace("_", " ")
            plan[seg] = {"calls": c, "share": sh}
        return {"id": f"S{i}", "franchise": franchise, "capacity": {"diabetes": cap_d or [8, 190], "oncology": cap_o or [4, 190]},
                "plan": plan}
    return [
        mk(1, "diabetes"),
        mk(2, "oncology"),
        mk(3, "diabetes", cap_d=[10, 200], Primary_care_physician=(12, 0.40), Primary_care_NP_or_PA=(6, 0.10)),
        mk(4, "oncology", cap_o=[3, 170], Oncology_specialist=(18, 0.80)),
        mk(5, "diabetes", cap_d=[6, 200], Endocrinology=(36, 0.60)),
        mk(6, "oncology", Oncology_specialist=(12, 0.50)),
    ]


def build(path: Path = OUT) -> Path:
    franchises = sizing.load_franchises()
    rules = sizing.load_rules()
    segs = segment_table(rules)
    data = load_state_segment()
    state_facts = load_state()
    names = load_state_names()
    states = sorted(names)
    assert len(states) == 51
    scenarios = probe_scenarios(segs)
    PROBE.parent.mkdir(parents=True, exist_ok=True)
    PROBE.write_text(json.dumps(scenarios, indent=1), encoding="utf-8")
    ctrl = {k: sum(r["hcps"] for r in data if r["franchise"] == k) for k in franchises}

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path))
    wb.set_calc_mode("auto")
    wb.set_properties({"title": "Field Force Sizing Model", "author": "Mohammad Uzair Khan",
                       "comments": "Providers from the CMS NPPES registry (October 2026 file); no prescribing data."})
    base = {"font_name": "Calibri", "font_size": 10, "font_color": INK}
    f = lambda **kw: wb.add_format({**base, **kw})
    title = f(font_size=18, bold=True)
    sub = f(font_color=SLATE, italic=True)
    h = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True, align="center")
    h_left = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True)
    cell = f(bottom=1, bottom_color=RULE)
    cell_c = f(bottom=1, bottom_color=RULE, align="center")
    int0 = f(num_format="#,##0", bottom=1, bottom_color=RULE)
    dec1 = f(num_format="#,##0.0", bottom=1, bottom_color=RULE)
    dec2 = f(num_format="0.00", bottom=1, bottom_color=RULE)
    pct0 = f(num_format="0%", bottom=1, bottom_color=RULE)
    label = f(bold=True, font_color=SLATE)
    note = f(font_color=SLATE, text_wrap=True, valign="top")
    inp = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, align="center")
    inp_pct = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, align="center", num_format="0%")
    kpi = f(font_size=14, bold=True, font_color=ACCENT, num_format="#,##0.0")
    tot = f(bold=True, top=2, top_color=INK, num_format="#,##0")
    tot1 = f(bold=True, top=2, top_color=INK, num_format="#,##0.0")

    ws_read = wb.add_worksheet("Read me")
    ws_in = wb.add_worksheet("Inputs")
    ws_sz = wb.add_worksheet("Sizing")
    ws_st = wb.add_worksheet("States")
    ws_ck = wb.add_worksheet("Checks")
    ws_da = wb.add_worksheet("Data")
    ws_sd = wb.add_worksheet("State facts")
    for ws, colour in ((ws_read, SLATE), (ws_in, "#CA8A04"), (ws_sz, ACCENT), (ws_st, ACCENT), (ws_ck, SLATE),
                       (ws_da, "#94A3B8"), (ws_sd, "#94A3B8")):
        ws.set_tab_color(colour)
        ws.hide_gridlines(2)

    # ------------------------------------------------------------------ Data (one row per state, franchise, segment)
    ws_da.write_row(0, 0, ["State", "Franchise", "Segment", "Tier", "Providers", "Calls per provider per year",
                           "Share targeted", "Workload (calls a year)"], h_left)
    for i, r in enumerate(data, start=1):
        ws_da.write_string(i, 0, r["state"])
        ws_da.write_string(i, 1, r["franchise"])
        ws_da.write_string(i, 2, r["segment"])
        ws_da.write_string(i, 3, r["tier"])
        ws_da.write_number(i, 4, r["hcps"], int0)
        ws_da.write_formula(i, 5, f"=INDEX(seg_calls,MATCH($C{i + 1},seg_names,0))", dec1)
        ws_da.write_formula(i, 6, f"=INDEX(seg_share,MATCH($C{i + 1},seg_names,0))", pct0)
        ws_da.write_formula(i, 7, f"=$E{i + 1}*$F{i + 1}*$G{i + 1}", dec1)
    last = len(data) + 1
    ws_da.freeze_panes(1, 0)
    ws_da.set_column(0, 1, 11)
    ws_da.set_column(2, 3, 26)
    ws_da.set_column(4, 7, 18)
    for nm, c in (("d_state", "A"), ("d_fr", "B"), ("d_seg", "C"), ("d_prov", "E"), ("d_work", "H")):
        wb.define_name(nm, f"=Data!${c}$2:${c}${last}")

    ws_sd.write_row(0, 0, ["State", "Franchise", "Adults", "Patients (adults x prevalence)", "Counties"], h_left)
    for i, r in enumerate(state_facts, start=1):
        ws_sd.write_string(i, 0, r["state"])
        ws_sd.write_string(i, 1, r["franchise"])
        ws_sd.write_number(i, 2, r["adults"], int0)
        ws_sd.write_number(i, 3, r["patients"], int0)
        ws_sd.write_number(i, 4, int(r["counties"]), int0)
    lastsd = len(state_facts) + 1
    ws_sd.set_column(0, 4, 20)
    for nm, c in (("s_state", "A"), ("s_fr", "B"), ("s_adults", "C"), ("s_patients", "D")):
        wb.define_name(nm, f"='State facts'!${c}$2:${c}${lastsd}")

    # ------------------------------------------------------------------ Inputs
    ws_in.set_column(0, 0, 2)
    ws_in.set_column(1, 1, 34)
    ws_in.set_column(2, 5, 22)
    ws_in.write("B1", "Field Force Sizing Model: inputs", title)
    ws_in.write("B2", "Change the yellow cells. Every number on Sizing and States recalculates.", sub)
    ws_in.write("B4", "Franchise", label)
    ws_in.write_string("C4", scenarios[0]["franchise"], inp)
    ws_in.data_validation("C4", {"validate": "list", "source": list(franchises)})
    wb.define_name("Franchise", "=Inputs!$C$4")
    ws_in.write("D4", "diabetes: primary care and endocrinology. oncology: oncologists.", sub)
    ws_in.write_row("B7", ["Rep capacity", "Calls per rep per day", "Field days per year", "Calls per rep per year"], h)
    for i, (k, fr) in enumerate(franchises.items()):
        r = 8 + i
        ws_in.write_string(r - 1, 1, k, cell)
        ws_in.write_number(r - 1, 2, fr.calls_per_rep_day, inp)
        ws_in.write_number(r - 1, 3, fr.field_days, inp)
        ws_in.write_formula(r - 1, 4, f"=C{r}*D{r}", int0)
    ws_in.write("B10", "In use", f(bold=True, top=2, top_color=INK))
    ws_in.write_formula("C10", "=INDEX(C8:C9,MATCH(Franchise,B8:B9,0))", f(bold=True, top=2, top_color=INK, align="center"))
    ws_in.write_formula("D10", "=INDEX(D8:D9,MATCH(Franchise,B8:B9,0))", f(bold=True, top=2, top_color=INK, align="center"))
    ws_in.write_formula("E10", "=C10*D10", f(bold=True, top=2, top_color=INK, num_format="#,##0"))
    wb.define_name("Capacity", "=Inputs!$E$10")
    ws_in.write_row("B13", ["Segment", "Franchise", "Tier", "Calls per provider per year", "Share targeted"], h)
    for i, s in enumerate(segs):
        r = 14 + i
        ws_in.write_string(r - 1, 1, s["segment"], cell)
        ws_in.write_string(r - 1, 2, s["franchise"], cell)
        ws_in.write_string(r - 1, 3, s["tier"], cell)
        ws_in.write_number(r - 1, 4, s["calls"], inp)
        ws_in.write_number(r - 1, 5, s["share"], inp_pct)
    nseg = len(segs)
    wb.define_name("seg_names", f"=Inputs!$B$14:$B${13 + nseg}")
    wb.define_name("seg_calls", f"=Inputs!$E$14:$E${13 + nseg}")
    wb.define_name("seg_share", f"=Inputs!$F$14:$F${13 + nseg}")
    ws_in.write(f"B{15 + nseg}", "Share targeted is the share of that provider group a rep calls on (specialists: the top 60% by "
                "volume; generalists: the top quarter). Public data has no provider-level prescribing, so it is an "
                "assumption, not a ranking of individual doctors.", note)
    ws_in.set_row(14 + nseg, 42)

    # ------------------------------------------------------------------ Sizing
    ws_sz.set_column(0, 0, 2)
    ws_sz.set_column(1, 1, 34)
    ws_sz.set_column(2, 7, 18)
    ws_sz.write("B1", "Sizing", title)
    ws_sz.write_formula("B2", '="National result for the "&Franchise&" franchise."', sub)
    ws_sz.write("B4", "Reps needed", label)
    ws_sz.write_formula("C4", f"=SUM(States!D{FIRST}:D{LAST})", kpi)
    ws_sz.write("B5", "Calls needed a year", label)
    ws_sz.write_formula("C5", f"=SUM(States!C{FIRST}:C{LAST})", f(font_size=12, bold=True, num_format="#,##0"))
    ws_sz.write("B6", "Providers targeted", label)
    ws_sz.write_formula("C6", "=SUM(E12:E15)", f(font_size=12, bold=True, num_format="#,##0"))
    ws_sz.write("B7", "Providers in the registry (universe)", label)
    ws_sz.write_formula("C7", "=SUM(C12:C15)", f(font_size=12, bold=True, num_format="#,##0"))
    ws_sz.write("B8", "Territories (reps, rounded)", label)
    ws_sz.write_formula("C8", "=ROUND(C4,0)", f(font_size=12, bold=True, num_format="#,##0"))
    ws_sz.write("B9", "Calls per rep per year", label)
    ws_sz.write_formula("C9", "=Capacity", f(font_size=12, bold=True, num_format="#,##0"))
    ws_sz.write_row("B11", ["Segment", "Providers", "Share targeted", "Targeted", "Calls per provider", "Calls a year"], h)
    for i, s in enumerate(segs):
        r = 12 + i
        ws_sz.write_formula(r - 1, 1, f"=Inputs!B{14 + i}", cell)
        ws_sz.write_formula(r - 1, 2, f'=SUMIFS(d_prov,d_seg,$B{r},d_fr,Franchise)', int0)
        ws_sz.write_formula(r - 1, 3, f"=Inputs!F{14 + i}", pct0)
        ws_sz.write_formula(r - 1, 4, f"=C{r}*D{r}", int0)
        ws_sz.write_formula(r - 1, 5, f"=Inputs!E{14 + i}", dec1)
        ws_sz.write_formula(r - 1, 6, f"=E{r}*F{r}", int0)
    ws_sz.write(11 + nseg, 1, "Total", f(bold=True, top=2, top_color=INK))
    for col, fmt in ((2, tot), (4, tot), (6, tot)):
        c = chr(ord("A") + col)
        ws_sz.write_formula(11 + nseg, col, f"=SUM({c}12:{c}{11 + nseg})", fmt)
    ws_sz.write(13 + nseg, 1, "Segments that belong to the other franchise show zero providers.", sub)

    # ------------------------------------------------------------------ States
    ws_st.set_column(0, 0, 8)
    ws_st.set_column(1, 1, 22)
    ws_st.set_column(2, 7, 17)
    ws_st.write("A1", "Reps by state", title)
    ws_st.write_formula("A2", '="Franchise: "&Franchise&". Reps = calls needed / "&TEXT(Capacity,"#,##0")&" calls per rep per year."', sub)
    ws_st.write_row("A5", ["State", "Name", "Calls a year", "Reps needed", "Adults", "Patients", "Reps per 100,000 adults", "Share of reps"], h)
    for i, s in enumerate(states):
        r = FIRST + i
        ws_st.write_string(r - 1, 0, s, cell_c)
        ws_st.write_string(r - 1, 1, names[s], cell)
        ws_st.write_formula(r - 1, 2, f"=SUMIFS(d_work,d_state,$A{r},d_fr,Franchise)", int0)
        ws_st.write_formula(r - 1, 3, f"=C{r}/Capacity", dec1)
        ws_st.write_formula(r - 1, 4, f"=SUMIFS(s_adults,s_state,$A{r},s_fr,Franchise)", int0)
        ws_st.write_formula(r - 1, 5, f"=SUMIFS(s_patients,s_state,$A{r},s_fr,Franchise)", int0)
        ws_st.write_formula(r - 1, 6, f'=IF(E{r}>0,D{r}/E{r}*100000,"")', dec2)
        ws_st.write_formula(r - 1, 7, f"=D{r}/D${TOTAL}", f(num_format="0.0%", bottom=1, bottom_color=RULE))
    ws_st.write(TOTAL - 1, 1, "United States", f(bold=True, top=2, top_color=INK))
    ws_st.write_formula(TOTAL - 1, 2, f"=SUM(C{FIRST}:C{LAST})", tot)
    ws_st.write_formula(TOTAL - 1, 3, f"=SUM(D{FIRST}:D{LAST})", tot1)
    ws_st.write_formula(TOTAL - 1, 4, f"=SUM(E{FIRST}:E{LAST})", tot)
    ws_st.write_formula(TOTAL - 1, 5, f"=SUM(F{FIRST}:F{LAST})", tot)
    ws_st.write_formula(TOTAL - 1, 6, f"=D{TOTAL}/E{TOTAL}*100000", f(bold=True, top=2, top_color=INK, num_format="0.00"))
    ws_st.write_formula(TOTAL - 1, 7, f"=SUM(H{FIRST}:H{LAST})", f(bold=True, top=2, top_color=INK, num_format="0.0%"))
    ws_st.freeze_panes(5, 2)

    # ------------------------------------------------------------------ Checks
    ws_ck.set_column(0, 0, 3)
    ws_ck.set_column(1, 1, 64)
    ws_ck.set_column(2, 3, 24)
    ws_ck.set_column(4, 4, 12)
    ws_ck.write("B1", "Checks", title)
    ws_ck.write_row("B4", ["Check", "Value", "Rule", "Result"], h_left)
    checks = [
        ("Franchise is one of the two on the Inputs sheet", "=Franchise", "diabetes or oncology",
         '=IF(OR(C5="diabetes",C5="oncology"),"OK","CHECK")'),
        ("Reps by state add up to reps from the segment table", f"=ABS(Sizing!C4-Sizing!G{12 + nseg}/Capacity)", "below 0.000001",
         '=IF(C6<0.000001,"OK","CHECK")'),
        ("Every share targeted is between 0 and 100%", "=MIN(seg_share)&\" to \"&MAX(seg_share)", "0 to 1",
         '=IF(AND(MIN(seg_share)>=0,MAX(seg_share)<=1),"OK","CHECK")'),
        ("Rep capacity is positive", "=Capacity", "above 0", '=IF(Capacity>0,"OK","CHECK")'),
        ("Providers on the Data sheet match the registry count for this franchise", "=SUMIFS(d_prov,d_fr,Franchise)",
         " / ".join(f"{k} {v:,}" for k, v in ctrl.items()),
         '=IF(C9=IF(Franchise="diabetes",' + str(ctrl["diabetes"]) + "," + str(ctrl["oncology"]) + '),"OK","CHECK")'),
        ("All 51 states are listed once", f"=COUNTA(States!A{FIRST}:A{LAST})", "51", '=IF(C10=51,"OK","CHECK")'),
    ]
    for i, (lab, val, rule, res) in enumerate(checks):
        r = 5 + i
        ws_ck.write(r - 1, 1, lab, cell)
        ws_ck.write_formula(r - 1, 2, val, cell_c)
        ws_ck.write(r - 1, 3, rule, cell_c)
        ws_ck.write_formula(r - 1, 4, res, f(bold=True, align="center", bottom=1, bottom_color=RULE))
    ws_ck.write("B12", "Overall", f(bold=True, top=2, top_color=INK))
    ws_ck.write_formula("E12", '=IF(COUNTIF(E5:E10,"OK")=ROWS(E5:E10),"ALL OK","CHECK")',
                        f(bold=True, align="center", top=2, top_color=INK, font_color=ACCENT))

    # ------------------------------------------------------------------ Read me
    ws_read.set_column(0, 0, 2)
    ws_read.set_column(1, 1, 110)
    ws_read.write("B1", "Field Force Sizing Model", title)
    ws_read.write("B2", "Part of Field Force Planner. Providers: CMS NPPES registry, October 2026 file. Patients: CDC PLACES prevalence x Census adults.", sub)
    lines = [
        ("What it answers", "How many reps does this call plan need, in total and state by state?"),
        ("Inputs", "Yellow cells: the franchise, each franchise's calls per rep per day and field days, and for each provider group the calls a year and the share a rep targets."),
        ("Sizing", "Providers x share targeted x calls per provider = calls a year; calls / (calls per rep per year) = reps."),
        ("States", "The same calculation for each state, with reps per 100,000 adults and each state's share of the total."),
        ("What is an assumption", "Calls per rep, call frequency and share targeted are assumptions, written down so they can be changed. The provider counts are facts from the registry; the registry lists who and where, not what each provider prescribes."),
        ("Alignment", "This workbook sizes the force. Cutting counties into balanced territories is done by the Python alignment and shown on the site."),
        ("Checks", "Six formulas that go to CHECK if an input is invalid or the Data sheet is edited."),
        ("Source", "github.com/f20230125-sudo/field-force-planner"),
    ]
    for i, (a, b) in enumerate(lines):
        ws_read.write(3 + 2 * i, 1, a, label)
        ws_read.write(4 + 2 * i, 1, b, note)
        ws_read.set_row(4 + 2 * i, 30)
    ws_read.activate()
    wb.close()
    return path


def main() -> int:
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
