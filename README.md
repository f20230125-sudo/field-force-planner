# Field Force Planner

How many sales reps does a US launch need, and how should the country's counties be cut into territories so that every rep has about the same work? Built from the public NPI registry (9,852,180 records), Census and CDC data, with the sizing as a live-formula Excel model and the alignment as tested Python.

> The README is generated: `python -m ff.readme` fills every number from `dashboard/public/data/headline.json`, and a test fails if this file is out of date.

## What it found

At the assumptions written down in `data/ref/` (calls per rep per day, field days, calls per provider per year, share of providers targeted). They are assumptions, not facts about any company, and the Excel model lets you change all of them.

- **Diabetes (oral therapy sold to primary care and endocrinology): about 1,310 reps.** 919,249 providers in the registry, 233,313 targeted, 1,990,916 calls a year at 1,520 calls per rep per year. California needs the most (130.6).
- **Oncology (specialist sale to oncologists): about 474 reps.** 33,325 providers, 19,995 targeted, 359,910 calls a year at 760 per rep.
- **The alignment balances the work.** Cutting the counties into one territory per rep, the spread of territory workload (coefficient of variation) is 7.5% for diabetes and 6.8% for oncology. An alignment drawn with equal numbers of counties, blind to workload, gives 274% and 206%. 99.6% of the diabetes territories are within 25% of the target workload (8.8% for the county-count baseline); every territory is one connected piece.
- **Balance has a price, and it is shape.** Mean territory radius is 36 km against 29 km for the baseline (diabetes), because balanced territories are drawn around the work, not the map. 865 counties (the big-city ones) are split between territories, a stated shortcut for ZIP-code bricks.
- **Public prevalence ranks states by size, not by spend per enrollee.** Across the 51 states and DC, demand built from CDC prevalence tracks Medicaid drug spend with a rank correlation of 0.86 (diabetes) and 0.95 (oncology), which is mostly population, and tracks spend per enrollee not at all (-0.10 and -0.04). So the territory weight is workload first, with patients as a minor term.

## Contents

| Path | What it is |
|---|---|
| `src/ff/` | fetch, NPPES extraction, build, sizing, alignment, validation, scorecard, JSON export, Excel builder, README renderer |
| `sql/` | stage, model (counties, ZIP-to-county map, providers with a specialty), marts |
| `data/ref/` | committed inputs: the call plan (`segments.csv`), rep capacity (`franchises.csv`), the Rx Market Pulse state table |
| `data/marts/` | committed results (CSV and JSON), including the 25-check scorecard and both alignments |
| `excel/Field-Force-Sizing-Model.xlsx` | pick a franchise and a call plan, get reps by state; live formulas |
| `dashboard/` | the Next.js site (data in `public/data/`) |
| `tests/` | pytest: sizing arithmetic, alignment invariants on grids, warehouse tie-outs, workbook |
| `docs/` | `data-quality-scorecard.md`, `case-studies.md` (what went wrong and how it was found), `design.md` |

## How it works

1. **Providers.** The October 2026 NPPES file (9,852,180 records, 11.8 GB unzipped) is streamed through DuckDB. Records with no entity type (357,925) are deactivated numbers and match the separate deactivation report; 7,458,766 individuals are active and in the 50 states and DC.
2. **Specialty.** The primary taxonomy code (the one flagged "primary") is mapped to a segment through `data/ref/segments.csv`; every code is checked against the NUCC code set.
3. **Geography.** A provider's ZIP code goes to a Census ZIP-code area and from there to the county holding most of its land: 98.9% of providers reach a county.
4. **Sizing.** Providers x share targeted x calls per provider = calls a year; calls / (calls per rep per day x field days) = reps. The same arithmetic runs in `sizing.py` and in Excel; a script drives Excel through six scenarios and compares every cell with an independent calculation.
5. **Alignment.** Each county gets a weight (half workload, half patients) scaled so a perfect territory weighs 1.0; heavy counties are split into pieces of at most 0.15; weighted k-means picks seeds; region growing builds connected territories; a local search moves border pieces while keeping each territory in one piece. Alaska and Hawaii are aligned on their own.
6. **Checks.** 25 scorecard checks, of which 18 are pass/fail and pass.

## Run it

```
pip install -r requirements.txt
set PYTHONPATH=src
python -m ff.fetch              # small inputs and the 1.2 GB registry file
python -m ff.nppes_extract      # unzip (11.8 GB) and keep the columns used
python -m ff.build              # warehouse
python -m ff.align              # alignment for both franchises
python -m ff.validate           # reality check against Rx Market Pulse
python -m ff.dq                 # scorecard
python -m ff.export_json        # JSON for the site
python -m ff.workbook           # Excel model
python -m ff.readme             # this file
python -m pytest
cd dashboard && npm ci && npm run build && npm run start
```

## Limits, stated plainly

- **No prescribing data.** The CMS Part D prescriber files, which say what each doctor prescribes, are served from data.cms.gov and refuse requests from the UAE, so this project knows who the providers are and where, not who prescribes most. Targeting is by specialty and a flat share, not a ranking of individual doctors.
- **Call plan and capacity are assumptions.** The sizing is as good as they are; change them in Excel.
- **Counties, split.** Real alignments use ZIP-code or smaller bricks. Here a county heavier than 0.15 of a territory is cut into equal pieces, which is a modelling shortcut, reported per county.
- **Alignment is a heuristic.** It is deterministic and tested for coverage, connection and balance, not proven optimal. The baseline (equal counties per territory) is a deliberately naive comparison, not any company's alignment.
- **Vintages.** Counties are the 2020 Census counties; population is the July 2021 estimate; prevalence is CDC PLACES 2023 (survey year 2021), with Florida from the 2024 release (survey year 2022). Connecticut's 2022 planning regions are not used because the ZIP crosswalk and adjacency files predate them.
- **Registry quality.** A ZIP code is not a Census ZIP-code area, so PO-box and single-building ZIPs are lost; every county count is a slight undercount.

Data: CMS NPPES, NUCC, US Census Bureau, CDC PLACES, and State Drug Utilization Data via [Rx Market Pulse](https://github.com/f20230125-sudo/rx-market-pulse). Not affiliated with CMS or any company named.
