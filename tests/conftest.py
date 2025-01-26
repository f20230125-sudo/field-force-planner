"""Shared test helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ff.sources import WAREHOUSE  # noqa: E402


def grid(rows: int, cols: int, weights: dict[tuple[int, int], float] | None = None):
    """A rows x cols grid of 'counties' with 4-neighbour adjacency, for alignment tests.

    County id is 'r{row}c{col}'; coordinates are on a 1-degree lattice; default weight 1.
    """
    weights = weights or {}
    w, coords, states, edges = {}, {}, {}, []
    for r in range(rows):
        for c in range(cols):
            cid = f"r{r}c{c}"
            w[cid] = weights.get((r, c), 1.0)
            coords[cid] = (30.0 + r * 0.5, -100.0 + c * 0.5)
            states[cid] = "S1" if c < cols // 2 else "S2"
            if r + 1 < rows:
                edges.append((cid, f"r{r + 1}c{c}"))
            if c + 1 < cols:
                edges.append((cid, f"r{r}c{c + 1}"))
    return w, coords, states, edges


@pytest.fixture(scope="session")
def real():
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not built: run python -m ff.fetch && python -m ff.nppes_extract && python -m ff.build")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield con
    con.close()
