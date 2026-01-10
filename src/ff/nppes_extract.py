"""Extract the NPPES provider file from the zip and keep the columns this project uses.

    python -m ff.nppes_extract

The monthly file has 330 columns and 8+ million rows (11.7 GB unzipped). The extraction streams it through DuckDB
and writes data/raw/nppes_slim.parquet with only individual providers' identity, practice location, dates and
taxonomy codes, so the rest of the build never has to read the big CSV again.
"""

from __future__ import annotations

import sys
import time
import zipfile

import duckdb

from .sources import NPPES_MEMBER, NPPES_ZIP, RAW

CSV = RAW / "nppes" / NPPES_MEMBER
OUT = RAW / "nppes_slim.parquet"


def unzip() -> None:
    CSV.parent.mkdir(parents=True, exist_ok=True)
    zpath = RAW / NPPES_ZIP
    if CSV.exists() and CSV.stat().st_mtime >= zpath.stat().st_mtime:
        print(f"  have  {CSV.name} ({CSV.stat().st_size / 1e9:.1f} GB)", flush=True)
        return
    started = time.time()
    with zipfile.ZipFile(zpath) as z:
        z.extract(NPPES_MEMBER, CSV.parent)
    print(f"  unzipped {CSV.name} ({CSV.stat().st_size / 1e9:.1f} GB in {time.time() - started:,.0f}s)", flush=True)


def slim() -> None:
    started = time.time()
    tax = ", ".join(f'"Healthcare Provider Taxonomy Code_{n}" as tax{n}' for n in range(1, 16))
    sw = ", ".join(f'"Healthcare Provider Primary Taxonomy Switch_{n}" as sw{n}' for n in range(1, 16))
    con = duckdb.connect()
    con.execute("set preserve_insertion_order = false")
    con.execute(f"""
        copy (
          select "NPI" as npi,
                 "Entity Type Code" as entity_type,
                 "Provider Credential Text" as credential,
                 "Provider Business Practice Location Address City Name" as city,
                 "Provider Business Practice Location Address State Name" as state,
                 "Provider Business Practice Location Address Postal Code" as postal,
                 "Provider Business Practice Location Address Country Code (If outside U.S.)" as country,
                 "Provider Enumeration Date" as enumerated,
                 "Last Update Date" as last_update,
                 "NPI Deactivation Reason Code" as deact_reason,
                 "NPI Deactivation Date" as deact_date,
                 "NPI Reactivation Date" as react_date,
                 {tax}, {sw}
          from read_csv('{CSV.as_posix()}', header = true, all_varchar = true, quote = '"', escape = '"',
                        sample_size = 20000, parallel = true)
        ) to '{OUT.as_posix()}' (format parquet, compression zstd)""")
    n = con.execute(f"select count(*) from read_parquet('{OUT.as_posix()}')").fetchone()[0]
    print(f"  wrote {OUT.name}: {n:,} rows ({OUT.stat().st_size / 1e6:,.0f} MB) in {time.time() - started:,.0f}s", flush=True)


def deactivated() -> None:
    """The monthly deactivation report is an Excel file; keep its NPI list as Parquet for the cross-check."""
    import io

    import openpyxl

    zpath = RAW / "NPPES_Deactivated_NPI_Report_101226_V2.zip"
    with zipfile.ZipFile(zpath) as z:
        data = io.BytesIO(z.read(z.namelist()[0]))
    wb = openpyxl.load_workbook(data, read_only=True)
    ws = wb.worksheets[0]
    tmp = RAW / "nppes_deactivated.csv"
    n = 0
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        fh.write("npi,deact_date\n")
        for r in ws.iter_rows(min_row=3, values_only=True):
            if r[0]:
                fh.write(f"{r[0]},{r[1]}\n")
                n += 1
    out = RAW / "nppes_deactivated.parquet"
    duckdb.connect().execute(
        f"copy (select * from read_csv('{tmp.as_posix()}', header = true, all_varchar = true)) "
        f"to '{out.as_posix()}' (format parquet)")
    tmp.unlink()
    print(f"  wrote {out.name}: {n:,} deactivated NPIs", flush=True)


def main() -> int:
    unzip()
    slim()
    deactivated()
    return 0


if __name__ == "__main__":
    sys.exit(main())
