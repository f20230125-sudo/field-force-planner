"""Where every input comes from. One place, so the README and the code cannot drift apart.

Everything is free and public. Two choices worth knowing:

* Counties are the 2020 Census counties. Connecticut replaced its counties with nine planning regions in 2022; the
  newest CDC PLACES releases (2024, 2025) follow that, but the Census ZIP crosswalk and county adjacency files this
  project needs do not. PLACES 2023 (BRFSS 2021) is the newest release on the old counties, so it is used.
* The CMS Part D prescriber files (what each doctor prescribes) are served from data.cms.gov, which refuses requests
  from the UAE, so this project works from who the HCPs are and where, not from what each one prescribes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "ff.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

NPPES_ZIP = "NPPES_Data_Dissemination_October_2026_V2.zip"
NPPES_MEMBER = "npidata_pfile_20050523-20261011.csv"

PLACES_MEASURES = ["DIABETES", "CANCER", "CHD", "COPD", "OBESITY", "KIDNEY", "STROKE", "BPHIGH", "CASTHMA",
                   "CSMOKING", "DEPRESSION", "ARTHRITIS"]


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str
    filename: str
    params: dict = field(default_factory=dict, hash=False, compare=False)
    min_bytes: int = 1


def all_sources() -> list[Source]:
    places_where = ("datavaluetypeid='CrdPrv' AND measureid in(" + ",".join(f"'{m}'" for m in PLACES_MEASURES) + ")")
    return [
        Source("nppes", "NPPES monthly file (V2), October 2026", f"https://download.cms.gov/nppes/{NPPES_ZIP}",
               NPPES_ZIP, min_bytes=1_000_000_000),
        Source("nppes_deactivated", "NPPES deactivation report, 12 October 2026",
               "https://download.cms.gov/nppes/NPPES_Deactivated_NPI_Report_101226_V2.zip",
               "NPPES_Deactivated_NPI_Report_101226_V2.zip", min_bytes=100_000),
        Source("nucc", "NUCC Health Care Provider Taxonomy 25.1", "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_251.csv",
               "nucc_taxonomy_251.csv", min_bytes=100_000),
        Source("zcta_county", "Census 2020 ZCTA to county relationship file",
               "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
               "tab20_zcta520_county20_natl.txt", min_bytes=1_000_000),
        # The 2021 Gazetteer, not a newer one: from 2022 Connecticut's counties became planning regions.
        Source("gazetteer", "Census 2021 county Gazetteer (centroids, land area)",
               "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2021_Gazetteer/2021_Gaz_counties_national.zip",
               "2021_Gaz_counties_national.zip", min_bytes=50_000),
        Source("adjacency", "Census county adjacency file", "https://www2.census.gov/geo/docs/reference/county_adjacency.txt",
               "county_adjacency.txt", min_bytes=100_000),
        Source("places", "CDC PLACES 2023 release, county crude prevalence",
               "https://data.cdc.gov/resource/h3ej-a9ec.csv", "places_2023_county.csv",
               params={"$where": places_where, "$limit": "200000",
                       "$select": "year,stateabbr,locationname,locationid,measureid,data_value,low_confidence_limit,"
                                  "high_confidence_limit,totalpopulation"}, min_bytes=1_000_000),
        # Florida did not release its 2021 survey data, so the 2023 release has no Florida counties. The 2024 release
        # (survey year 2022) does, on the same county codes.
        Source("places_fl", "CDC PLACES 2024 release, Florida counties (survey year 2022)",
               "https://data.cdc.gov/resource/fu4u-a9bh.csv", "places_2024_fl.csv",
               params={"$where": places_where + " AND stateabbr='FL' AND year='2022'", "$limit": "10000",
                       "$select": "year,stateabbr,locationname,locationid,measureid,data_value,low_confidence_limit,"
                                  "high_confidence_limit,totalpopulation"}, min_bytes=10_000),
        Source("popest", "Census county population estimates by age, vintage 2021 (YEAR 3 = 1 July 2021)",
               "https://www2.census.gov/programs-surveys/popest/datasets/2020-2021/counties/asrh/cc-est2021-agesex-all.csv",
               "cc-est2021-agesex-all.csv", min_bytes=1_000_000),
    ]
