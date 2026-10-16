"""Data tests on the built warehouse and the alignment output (skipped when they have not been built)."""

from __future__ import annotations

import csv
import json

import pytest

from ff import dq, sizing
from ff.sources import MARTS

pytestmark = pytest.mark.usefixtures("real")


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_registry_records_split_into_individuals_organisations_and_deactivated(real):
    n = one(real, "select count(*) from stg_nppes")
    parts = one(real, "select count(*) filter (where entity_type = '1') + count(*) filter (where entity_type = '2') + "
                      "count(*) filter (where entity_type is null) from stg_nppes")
    assert n == parts == 9852180


def test_every_blank_entity_record_is_on_the_deactivation_report(real):
    n = one(real, "select count(*) from stg_nppes n join stg_deactivated d using (npi) where n.entity_type is null")
    assert n == one(real, "select count(*) from stg_nppes where entity_type is null")


def test_no_deactivated_number_is_counted_as_a_provider(real):
    assert one(real, "select count(*) from dim_hcp h join stg_deactivated d using (npi)") == 0


def test_providers_are_unique_individuals_in_the_fifty_states_and_dc(real):
    assert one(real, "select count(*) - count(distinct npi) from dim_hcp") == 0
    assert one(real, "select count(distinct state) from dim_hcp") == 51


def test_every_county_is_kept_once_per_franchise(real):
    assert one(real, "select count(distinct county) from dim_county") == 3143
    assert one(real, "select count(*) from dim_county") == 3143 * 2


def test_population_matches_the_census_file(real):
    assert one(real, "select sum(pop) from (select distinct county, pop from dim_county)") == one(real, "select sum(pop) from stg_popest")


def test_florida_has_prevalence_from_the_2024_release_and_nothing_is_imputed(real):
    assert one(real, "select count(*) from dim_county where prevalence_imputed") == 0
    yrs = {y for (y,) in real.execute("select distinct prevalence_year from dim_county where state = 'FL'").fetchall()}
    assert yrs == {2022}


def test_prevalence_is_a_plausible_share(real):
    lo, hi = real.execute("select min(prevalence), max(prevalence) from dim_county").fetchone()
    assert 0.005 < lo and hi < 0.40


def test_patients_equal_adults_times_prevalence(real):
    bad = one(real, "select count(*) from dim_county where abs(patients - round(adults * prevalence)) > 0.5")
    assert bad == 0


def test_zip_to_county_map_has_one_county_per_zcta(real):
    assert one(real, "select count(*) - count(distinct zcta) from map_zip_county") == 0
    assert one(real, "select count(*) from map_zip_county where share_in_county <= 0 or share_in_county > 1") == 0


def test_provider_segment_counts_add_up(real):
    assert one(real, "select sum(hcps) from fact_hcp_county") == one(real, "select count(*) from hcp_segment where county is not null")


def test_edges_are_unique_undirected_pairs_between_known_counties(real):
    assert one(real, "select count(*) from mart_edges where a >= b") == 0
    assert one(real, "select count(*) - count(distinct (a, b)) from mart_edges") == 0
    assert one(real, "select count(*) from mart_edges where a not in (select county from dim_county) or b not in (select county from dim_county)") == 0


def test_alignment_covers_every_county_exactly_once_per_franchise():
    for key in sizing.load_franchises():
        with (MARTS / f"alignment_county_{key}.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 3143 == len({r["county"] for r in rows})


def test_alignment_territory_workloads_add_up_to_the_total_calls():
    segs, rules = sizing.load_county_segments(), sizing.load_rules()
    for key in sizing.load_franchises():
        total = sum(sizing.county_workload(key, segs, rules).values())
        with (MARTS / f"alignment_territory_{key}.csv").open(encoding="utf-8", newline="") as fh:
            got = sum(float(r["calls"]) for r in csv.DictReader(fh))
        assert got == pytest.approx(total, rel=1e-3)


def test_alignment_territory_count_equals_rounded_reps():
    al = json.loads((MARTS / "alignment.json").read_text(encoding="utf-8"))
    for key, a in al.items():
        with (MARTS / f"alignment_territory_{key}.csv").open(encoding="utf-8", newline="") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        assert n == a["territories"] == round(a["reps"])


def test_alignment_beats_the_county_count_baseline_by_a_wide_margin():
    al = json.loads((MARTS / "alignment.json").read_text(encoding="utf-8"))
    for a in al.values():
        assert a["metrics"]["aligned"]["cv"] < 0.15
        assert a["metrics"]["baseline"]["cv"] > 1.0
        assert a["metrics"]["aligned"]["disconnected"] == 0


def test_scorecard_has_no_failures(real):
    checks = dq.run(real)
    assert len(checks) >= 20
    assert [c.id for c in checks if c.status == "fail"] == []
