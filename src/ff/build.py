"""Build the DuckDB warehouse from data/raw.

    python -m ff.build              # stage -> model -> marts
    python -m ff.build stage        # only the staging layer
    python -m ff.build model marts  # re-run later layers on an existing staging layer

Layers (each is a numbered SQL file in sql/, run in order):
    01     staging: every source as published
    02     model: counties, ZIP-to-county map, providers with a specialty and a county
    03+    marts: small tables the sizing, alignment, workbook and dashboard read
"""

from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

import duckdb

from .sources import MARTS, RAW, REF, ROOT, WAREHOUSE

SQL_DIR = ROOT / "sql"


def connect(path: Path = WAREHOUSE, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def _run_sql(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    started = time.time()
    con.execute(sql)
    print(f"  {name:<24} {time.time() - started:5.1f}s", flush=True)


def _gazetteer_txt() -> Path:
    zpath = RAW / "2021_Gaz_counties_national.zip"
    dest = RAW / "2021_Gaz_counties_national.txt"
    if not dest.exists() or dest.stat().st_mtime < zpath.stat().st_mtime:
        with zipfile.ZipFile(zpath) as z:
            dest.write_bytes(z.read("2021_Gaz_counties_national.txt"))
    return dest


def load_adjacency(con: duckdb.DuckDBPyConnection) -> None:
    """county_adjacency.txt: tab separated, county name in quotes. A county's first row names it, the rows after it
    (county columns blank) name its neighbours, and a county is listed as its own first neighbour."""
    rows: list[tuple[str, str]] = []
    current = None
    for line in (RAW / "county_adjacency.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        if parts[1].strip():
            current = parts[1].strip()
        nb = parts[3].strip()
        if current and nb and nb != current:
            rows.append((current, nb))
    con.execute("create or replace table stg_adjacency (county varchar, neighbour varchar)")
    con.executemany("insert into stg_adjacency values (?, ?)", rows)
    print(f"  {'adjacency (python)':<24} {len(rows):,} county pairs", flush=True)


def stage(con: duckdb.DuckDBPyConnection) -> None:
    print("stage")
    needed = [RAW / "nppes_slim.parquet", RAW / "nppes_deactivated.parquet"]
    for p in needed:
        if not p.exists():
            raise SystemExit(f"missing {p.name}: run python -m ff.fetch && python -m ff.nppes_extract")
    _run_sql(con, "01_stage.sql",
             nppes=(RAW / "nppes_slim.parquet").as_posix(), deact=(RAW / "nppes_deactivated.parquet").as_posix(),
             nucc=(RAW / "nucc_taxonomy_251.csv").as_posix(), zcta=(RAW / "tab20_zcta520_county20_natl.txt").as_posix(),
             gazetteer=_gazetteer_txt().as_posix(), places=(RAW / "places_2023_county.csv").as_posix(),
             places_fl=(RAW / "places_2024_fl.csv").as_posix(),
             popest=(RAW / "cc-est2021-agesex-all.csv").as_posix())
    load_adjacency(con)


def model(con: duckdb.DuckDBPyConnection) -> None:
    print("model")
    for name in sorted(p.name for p in SQL_DIR.glob("02*.sql")):
        _run_sql(con, name, ref_dir=REF.as_posix())


def marts(con: duckdb.DuckDBPyConnection) -> None:
    print("marts")
    MARTS.mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in SQL_DIR.glob("[0-9][0-9]*.sql") if int(p.name[:2]) >= 3):
        _run_sql(con, name, marts_dir=MARTS.as_posix(), ref_dir=REF.as_posix())


LAYERS = {"stage": stage, "model": model, "marts": marts}


def main(argv: list[str] | None = None) -> int:
    wanted = (argv if argv is not None else sys.argv[1:]) or list(LAYERS)
    unknown = [w for w in wanted if w not in LAYERS]
    if unknown:
        print(f"unknown layer(s): {', '.join(unknown)}; choose from {', '.join(LAYERS)}", file=sys.stderr)
        return 2
    con = connect()
    for layer in wanted:
        LAYERS[layer](con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
