"""Alignment invariants, on small grids where the right answer can be seen by eye."""

from __future__ import annotations

import pytest

from conftest import grid
from ff import align


def run(weights=None, rows=8, cols=8, t=4, **kw):
    w, coords, states, edges = grid(rows, cols, weights)
    scale = t / sum(w.values())
    w = {c: v * scale for c, v in w.items()}  # a balanced territory weighs 1.0
    return align.align(w, coords, edges, t, states, **kw), w, edges


def test_every_county_is_in_exactly_one_territory_per_piece_and_none_is_empty():
    res, w, _ = run()
    g, assign = res["graph"], res["assign"]
    assert len(assign) == len(g.weight)
    assert all(0 <= k < 4 for k in assign)
    assert set(assign) == {0, 1, 2, 3}


def test_territory_weights_add_up_to_the_total():
    res, w, _ = run(t=5, rows=10, cols=10)
    g, assign = res["graph"], res["assign"]
    tw = [0.0] * 5
    for v, k in enumerate(assign):
        tw[k] += g.weight[v]
    assert sum(tw) == pytest.approx(sum(w.values()))


def test_every_territory_is_one_connected_piece():
    res, _, _ = run(t=6, rows=12, cols=12)
    assert res["metrics"]["aligned"]["disconnected"] == 0
    assert res["metrics"]["baseline"]["disconnected"] == 0


def test_uniform_weights_give_near_equal_territories():
    res, _, _ = run(t=4, rows=8, cols=8)
    m = res["metrics"]["aligned"]
    assert m["cv"] < 0.15
    assert m["min_over_mean"] > 0.7


def test_a_heavy_corner_is_balanced_by_the_aligner_but_not_by_the_count_baseline():
    heavy = {(r, c): 12.0 for r in range(2) for c in range(2)}  # four counties carry most of the work
    res, w, _ = run(weights=heavy, t=4, rows=8, cols=8)
    a, b = res["metrics"]["aligned"], res["metrics"]["baseline"]
    assert a["cv"] < 0.25
    assert b["cv"] > 2 * a["cv"]


def test_a_county_worth_several_territories_is_split_and_its_pieces_are_in_more_than_one_territory():
    heavy = {(3, 3): 60.0}
    res, w, _ = run(weights=heavy, t=6, rows=7, cols=7)
    g, assign = res["graph"], res["assign"]
    pieces = g.pieces["r3c3"]
    assert len(pieces) > 5
    assert len({assign[v] for v in pieces}) > 1
    assert res["metrics"]["aligned"]["split_counties"] >= 1


def test_local_search_never_makes_balance_worse():
    res, _, _ = run(weights={(1, 1): 8.0, (6, 5): 6.0}, t=5, rows=9, cols=9)
    assert res["metrics"]["aligned"]["cv"] <= res["metrics"]["before_local_search"]["cv"] + 1e-12


def test_result_is_deterministic():
    a, _, _ = run(t=4)
    b, _, _ = run(t=4)
    assert a["assign"] == b["assign"]


def test_a_near_island_is_joined_to_the_nearest_county_and_reported():
    w, coords, states, edges = grid(4, 4)
    w["island"] = 1.0
    coords["island"] = (30.0, -97.8)  # about 100 km east of the grid, touching nothing
    states["island"] = "S2"
    scale = 4 / sum(w.values())
    w = {c: v * scale for c, v in w.items()}
    res = align.align(w, coords, edges, 4, states)
    assert len(res["regions"]) == 1
    assert len(res["graph"].bridges) == 1
    assert res["graph"].bridges[0][0] == "island"
    assert res["metrics"]["aligned"]["disconnected"] == 0


def test_a_far_region_is_aligned_on_its_own_with_territories_in_proportion_to_its_work():
    w, coords, states, edges = grid(6, 6)
    far = {f"far{i}": (60.0 + i * 0.3, -150.0) for i in range(4)}  # thousands of km from the grid
    for c, xy in far.items():
        w[c], coords[c], states[c] = 1.0, xy, "AK"
    edges = edges + [("far0", "far1"), ("far1", "far2"), ("far2", "far3")]
    scale = 10 / sum(w.values())
    w = {c: v * scale for c, v in w.items()}
    res = align.align(w, coords, edges, 10, states)
    assert len(res["regions"]) == 2
    far_weight = sum(w[c] for c in far)
    assert res["regions"][1]["territories"] == max(1, round(far_weight))
    assert res["regions"][0]["territories"] + res["regions"][1]["territories"] == 10
    assert res["metrics"]["aligned"]["disconnected"] == 0
    assert res["metrics"]["aligned"]["bridges"] == 0  # no tie across thousands of km


def test_county_table_reports_split_counties():
    heavy = {(2, 2): 40.0}
    res, w, _ = run(weights=heavy, t=5, rows=5, cols=5)
    rows = align.county_table(res, {c: "S" for c in w})
    big = next(r for r in rows if r["county"] == "r2c2")
    assert big["territories"] > 1 and 0 < big["share"] <= 1
