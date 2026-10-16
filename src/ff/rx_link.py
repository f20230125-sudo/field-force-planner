"""Bring one table from Rx Market Pulse (the sibling project, rx-analytics) for a reality check.

data/ref/rx_state_area.csv has, for each state in 2025, Medicaid drug spend (before rebates) in the diabetes and oncology
therapeutic areas and Medicaid enrollment. `ff.validate` asks whether the prevalence-based demand used here ranks
states the way that observed spend does.

    python -m ff.rx_link --refresh      # rewrite the CSV from rx-analytics (only if Rx Market Pulse changes)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from .sources import REF

RX_WAREHOUSE = Path(r"D:\claude-workspace\rx-analytics\data\warehouse\rx.duckdb")
OUT = REF / "rx_state_area.csv"


def refresh(src: Path = RX_WAREHOUSE) -> int:
    con = duckdb.connect(str(src), read_only=True)
    sql = """
        select s.state, s.state_name, s.is_state, y.enrollment,
               max(a.spend) filter (where a.area = 'Diabetes & obesity') as spend_diabetes,
               max(a.spend) filter (where a.area = 'Oncology')           as spend_oncology,
               y.spend as spend_all
        from mart_state_year y
        join dim_state s using (state)
        join mart_state_area_year a on a.state = y.state and a.year = y.year
        where y.year = 2025 and s.is_state
        group by s.state, s.state_name, s.is_state, y.enrollment, y.spend
        order by s.state"""
    con.execute(f"copy ({sql}) to '{OUT.as_posix()}' (header, delimiter ',')")
    return con.execute(f"select count(*) from ({sql})").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true")
    if not ap.parse_args(argv).refresh:
        ap.print_help()
        return 0
    if not RX_WAREHOUSE.exists():
        print(f"missing {RX_WAREHOUSE}", file=sys.stderr)
        return 1
    print(f"{refresh()} states -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
