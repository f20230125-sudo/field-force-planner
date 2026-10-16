"""The sizing arithmetic, on a hand-made two-county example."""

from __future__ import annotations

import pytest

from ff import sizing

FR = sizing.Franchise("f", "Test", "M", calls_per_rep_day=5.0, field_days=200.0, patient_label="x")
RULES = {
    ("f", "Specialist"): sizing.SegmentRule("f", "Specialist", "specialist", 20.0, 0.5),
    ("f", "Generalist"): sizing.SegmentRule("f", "Generalist", "generalist", 10.0, 0.2),
}
ROWS = [
    {"county": "A", "state": "S1", "franchise": "f", "segment": "Specialist", "hcps": 100},
    {"county": "A", "state": "S1", "franchise": "f", "segment": "Generalist", "hcps": 500},
    {"county": "B", "state": "S2", "franchise": "f", "segment": "Generalist", "hcps": 250},
    {"county": "B", "state": "S2", "franchise": "other", "segment": "Specialist", "hcps": 9999},  # another franchise
]


def test_capacity_is_calls_a_day_times_field_days():
    assert FR.capacity == 1000.0


def test_county_workload_is_providers_times_share_times_calls():
    w = sizing.county_workload("f", ROWS, RULES)
    assert w == {"A": 100 * 0.5 * 20 + 500 * 0.2 * 10, "B": 250 * 0.2 * 10}  # 2000 and 500
    assert "other" not in w


def test_reps_are_workload_over_capacity():
    total = sum(sizing.county_workload("f", ROWS, RULES).values())
    assert total == 2500
    assert sizing.reps_needed(total, FR) == pytest.approx(2.5)


def test_state_and_segment_roll_ups_add_to_the_same_total():
    total = sum(sizing.county_workload("f", ROWS, RULES).values())
    assert sum(v["calls"] for v in sizing.by_state("f", ROWS, RULES, FR).values()) == pytest.approx(total)
    assert sum(r["calls"] for r in sizing.by_segment("f", ROWS, RULES)) == pytest.approx(total)
    assert sizing.by_state("f", ROWS, RULES, FR)["S1"]["reps"] == pytest.approx(2.0)


def test_overrides_change_only_the_named_segment():
    r2 = sizing.with_overrides(RULES, calls={"Generalist": 20.0}, share={"Specialist": 1.0})
    assert r2[("f", "Generalist")].calls_per_year == 20.0
    assert r2[("f", "Generalist")].targeted_share == 0.2
    assert r2[("f", "Specialist")].targeted_share == 1.0
    assert r2[("f", "Specialist")].calls_per_year == 20.0
    assert RULES[("f", "Generalist")].calls_per_year == 10.0  # the original is untouched


def test_doubling_capacity_halves_the_headcount():
    fast = sizing.Franchise("f", "Test", "M", 10.0, 200.0, "x")
    total = sum(sizing.county_workload("f", ROWS, RULES).values())
    assert sizing.reps_needed(total, fast) == pytest.approx(sizing.reps_needed(total, FR) / 2)


def test_real_rules_cover_every_segment_in_the_data():
    rules = sizing.load_rules()
    segs = sizing.load_county_segments()
    keys = {(r["franchise"], r["segment"]) for r in segs}
    assert keys <= set(rules)
