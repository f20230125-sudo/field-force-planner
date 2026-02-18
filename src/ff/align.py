"""Territory alignment: cut the counties into T territories of equal workload that are each one connected piece.

    python -m ff.align              # both franchises at their sized headcount -> data/marts/alignment_*.csv, alignment.json

Method (deterministic, no solver):
 1. Each county has a weight: the share of national workload (and, with weight 1 - alpha, of patients) it carries,
    scaled so a perfectly balanced territory weighs 1.0. A county heavier than 0.15 is split into equal pieces (Los
    Angeles County alone is worth dozens of territories); pieces of one county touch each other and every piece of a
    neighbouring county. Splitting is a modelling shortcut for ZIP-code-level bricks, and every split county is reported.
 2. Islands within 300 km of the mainland (a few coastal counties) are joined to their nearest county by distance and
    reported. Alaska and Hawaii are farther than that, so each is aligned on its own with territories in proportion to
    its workload (at least one).
 3. Seeds: weighted k-means on county centres gives T starting points that follow where the work is.
 4. Region growing: the lightest territory takes the free neighbour nearest its seed, until every piece is taken.
 5. Local search: a piece on a border moves to the neighbouring territory when that lowers the sum of squared weight
    deviations and leaves its old territory in one connected piece.
The baseline for comparison is the same procedure with every county counted as 1 (equal numbers of counties, blind to
workload), which is what an alignment drawn by county count produces.
"""

from __future__ import annotations

import heapq
import json
import math
import random
from dataclasses import dataclass, field

import numpy as np

from . import sizing
from .sources import MARTS

MAX_PIECE = 0.15
KM_LAT = 110.57
KM_LON_EQ = 111.32


@dataclass
class Graph:
    county: list[str]            # county of each node
    weight: list[float]
    x: np.ndarray                # km east of a reference longitude
    y: np.ndarray                # km north
    adj: list[set[int]]
    pieces: dict[str, list[int]]
    bridges: list[tuple[str, str, float]] = field(default_factory=list)


def to_km(lat: float, lon: float) -> tuple[float, float]:
    return (lon + 96.0) * KM_LON_EQ * math.cos(math.radians(lat)), lat * KM_LAT


def build_graph(weights: dict[str, float], coords: dict[str, tuple[float, float]], edges: list[tuple[str, str]],
                max_piece: float = MAX_PIECE) -> Graph:
    county, weight, xs, ys = [], [], [], []
    pieces: dict[str, list[int]] = {}
    for c in sorted(weights):
        w = weights[c]
        k = max(1, math.ceil(w / max_piece - 1e-9)) if max_piece else 1
        x, y = to_km(*coords[c])
        pieces[c] = []
        for _ in range(k):
            pieces[c].append(len(county))
            county.append(c)
            weight.append(w / k)
            xs.append(x)
            ys.append(y)
    adj: list[set[int]] = [set() for _ in county]
    for ids in pieces.values():
        for a in ids:
            for b in ids:
                if a != b:
                    adj[a].add(b)
    for ca, cb in edges:
        if ca in pieces and cb in pieces:
            for a in pieces[ca]:
                for b in pieces[cb]:
                    adj[a].add(b)
                    adj[b].add(a)
    g = Graph(county, weight, np.array(xs), np.array(ys), adj, pieces)
    _join_islands(g)
    return g


def _components(adj: list[set[int]]) -> list[list[int]]:
    seen = [False] * len(adj)
    comps = []
    for s in range(len(adj)):
        if seen[s]:
            continue
        seen[s] = True
        stack, comp = [s], []
        while stack:
            v = stack.pop()
            comp.append(v)
            for u in adj[v]:
                if not seen[u]:
                    seen[u] = True
                    stack.append(u)
        comps.append(comp)
    return comps


def _join_islands(g: Graph) -> None:
    comps = _components(g.adj)
    if len(comps) <= 1:
        return
    comps.sort(key=len, reverse=True)
    main = set(comps[0])
    for comp in comps[1:]:
        idx = np.array(comp)
        others = np.array(sorted(main))
        d = np.hypot(g.x[idx][:, None] - g.x[others][None, :], g.y[idx][:, None] - g.y[others][None, :])
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        a, b = int(idx[i]), int(others[j])
        g.adj[a].add(b)
        g.adj[b].add(a)
        g.bridges.append((g.county[a], g.county[b], float(d[i, j])))
        main.update(comp)


def kmeans_seeds(g: Graph, t: int, seed: int = 7, iters: int = 20) -> list[int]:
    """T seed nodes: weighted k-means centres snapped to the nearest unused node."""
    rng = np.random.default_rng(seed)
    pts = np.column_stack([g.x, g.y])
    w = np.array(g.weight) + 1e-6
    centres = pts[rng.choice(len(pts), size=t, replace=False, p=w / w.sum())]
    for _ in range(iters):
        d = ((pts[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1)
        for k in range(t):
            m = lab == k
            if m.any():
                centres[k] = (pts[m] * w[m, None]).sum(axis=0) / w[m].sum()
    used: set[int] = set()
    seeds = []
    for k in range(t):
        order = np.argsort(((pts - centres[k]) ** 2).sum(axis=1))
        for v in order:
            if int(v) not in used:
                used.add(int(v))
                seeds.append(int(v))
                break
    return seeds


def grow(g: Graph, seeds: list[int]) -> list[int]:
    """Region growing: the lightest territory that still has a free neighbour takes the one nearest its seed."""
    n, t = len(g.weight), len(seeds)
    assign = [-1] * n
    tw = [0.0] * t
    frontier: list[set[int]] = [set() for _ in range(t)]
    for k, s in enumerate(seeds):
        assign[s] = k
        tw[k] = g.weight[s]
    for k, s in enumerate(seeds):
        frontier[k] = {u for u in g.adj[s] if assign[u] == -1}
    heap = [(tw[k], k) for k in range(t)]
    heapq.heapify(heap)
    while heap:
        wk, k = heapq.heappop(heap)
        if wk != tw[k]:
            continue
        free = [u for u in frontier[k] if assign[u] == -1]
        if not free:
            continue
        sx, sy = g.x[seeds[k]], g.y[seeds[k]]
        v = min(free, key=lambda u: ((g.x[u] - sx) ** 2 + (g.y[u] - sy) ** 2, u))
        assign[v] = k
        tw[k] += g.weight[v]
        frontier[k] = set(free)
        frontier[k].discard(v)
        frontier[k].update(u for u in g.adj[v] if assign[u] == -1)
        heapq.heappush(heap, (tw[k], k))
    if -1 in assign:  # cannot happen on a connected graph; kept as a guard
        raise RuntimeError("region growing left nodes unassigned")
    return assign


def _stays_connected(g: Graph, assign: list[int], a: int, v: int) -> bool:
    nbrs = [u for u in g.adj[v] if assign[u] == a]
    if len(nbrs) <= 1:
        return True
    seen = {nbrs[0]}
    stack = [nbrs[0]]
    left = set(nbrs[1:])
    while stack and left:
        x = stack.pop()
        for y in g.adj[x]:
            if y != v and assign[y] == a and y not in seen:
                seen.add(y)
                left.discard(y)
                stack.append(y)
    return not left


def improve(g: Graph, assign: list[int], t: int, target: float = 1.0, max_passes: int = 60) -> list[int]:
    """Move border pieces to a neighbouring territory when it lowers the sum of squared deviations from the target."""
    assign = list(assign)
    tw = [0.0] * t
    size = [0] * t
    for v, k in enumerate(assign):
        tw[k] += g.weight[v]
        size[k] += 1
    for _ in range(max_passes):
        moved = 0
        # visit pieces of the most overweight territories first
        order = sorted(range(len(assign)), key=lambda v: -tw[assign[v]])
        for v in order:
            wv = g.weight[v]
            if wv <= 0:
                continue
            a = assign[v]
            if size[a] <= 1:
                continue
            best = None
            for b in {assign[u] for u in g.adj[v]} - {a}:
                delta = ((tw[a] - wv - target) ** 2 + (tw[b] + wv - target) ** 2
                         - (tw[a] - target) ** 2 - (tw[b] - target) ** 2)
                if delta < -1e-12 and (best is None or delta < best[0]):
                    best = (delta, b)
            if best and _stays_connected(g, assign, a, v):
                b = best[1]
                assign[v] = b
                tw[a] -= wv
                tw[b] += wv
                size[a] -= 1
                size[b] += 1
                moved += 1
        if not moved:
            break
    return assign


def territory_weights(g: Graph, assign: list[int], t: int, real_weight: dict[str, float] | None = None) -> list[float]:
    """Weight of each territory. With `real_weight`, a territory made of whole counties (the baseline) is weighed by the
    real county weights rather than by the unit weights it was grown with."""
    tw = [0.0] * t
    for v, k in enumerate(assign):
        if real_weight is None:
            tw[k] += g.weight[v]
        else:
            c = g.county[v]
            tw[k] += real_weight[c] / len(g.pieces[c])
    return tw


def metrics(g: Graph, assign: list[int], t: int, real_weight: dict[str, float] | None = None,
            states: dict[str, str] | None = None) -> dict:
    """Balance, compactness, contiguity. Weights are the real county weights when `real_weight` is given (the baseline
    treats a county as one node, so its pieces are not splittable and its territory weight is the sum of whole counties)."""
    members: list[list[int]] = [[] for _ in range(t)]
    for v, k in enumerate(assign):
        members[k].append(v)
    tw = territory_weights(g, assign, t, real_weight)
    arr = np.array(tw)
    dev = arr / arr.mean()
    comp = []
    for k in range(t):
        idx = np.array(members[k])
        w = np.array([g.weight[v] for v in members[k]])
        w = w if w.sum() > 0 else np.ones_like(w)
        cx, cy = (g.x[idx] * w).sum() / w.sum(), (g.y[idx] * w).sum() / w.sum()
        comp.append(float((np.hypot(g.x[idx] - cx, g.y[idx] - cy) * w).sum() / w.sum()))
    disconnected = 0
    for k in range(t):
        ms = set(members[k])
        start = next(iter(ms))
        seen = {start}
        stack = [start]
        while stack:
            x = stack.pop()
            for y in g.adj[x]:
                if y in ms and y not in seen:
                    seen.add(y)
                    stack.append(y)
        if len(seen) != len(ms):
            disconnected += 1
    split = sum(1 for c, ids in g.pieces.items() if len({assign[v] for v in ids}) > 1)
    crossing = 0
    if states:
        for k in range(t):
            if len({states[g.county[v]] for v in members[k]}) > 1:
                crossing += 1
    return {
        "territories": t, "mean_weight": float(arr.mean()), "cv": float(arr.std() / arr.mean()),
        "min_over_mean": float(dev.min()), "max_over_mean": float(dev.max()),
        "within_10pct": float(((dev >= 0.9) & (dev <= 1.1)).mean()),
        "within_25pct": float(((dev >= 0.75) & (dev <= 1.25)).mean()),
        "mean_radius_km": float(np.mean(comp)), "median_radius_km": float(np.median(comp)),
        "disconnected": disconnected, "split_counties": split, "crossing_state_share": crossing / t if states else None,
        "bridges": len(g.bridges),
    }


REMOTE_KM = 300.0


def regions(weights: dict[str, float], coords: dict[str, tuple[float, float]], edges: list[tuple[str, str]],
            remote_km: float = REMOTE_KM) -> list[list[str]]:
    """Groups of counties to align separately. The mainland (with islands closer than `remote_km`, which get a
    distance link) is one group; a region farther away than that (Alaska, Hawaii) is its own group, so it gets its own
    territories rather than being tied to a state thousands of kilometres away."""
    parent = {c: c for c in weights}

    def find(c: str) -> str:
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    for a, b in edges:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for c in sorted(weights):
        groups.setdefault(find(c), []).append(c)
    comps = sorted(groups.values(), key=len, reverse=True)
    main = list(comps[0])
    xy = {c: to_km(*coords[c]) for c in weights}
    out_remote = []
    for comp in comps[1:]:
        d = min(math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]) for a in comp for b in main)
        if d <= remote_km:
            main.extend(comp)
        else:
            out_remote.append(comp)
    # Alaska's boroughs are not all adjacent to each other: reunite remote groups within 1,500 km of one another
    # (Alaska stays one region; Hawaii, 4,000 km from it, is another)
    merged: list[list[str]] = []
    for comp in sorted(out_remote, key=len, reverse=True):
        for m in merged:
            if min(math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]) for a in comp for b in m) <= 5 * remote_km:
                m.extend(comp)
                break
        else:
            merged.append(list(comp))
    return [sorted(main)] + [sorted(m) for m in merged]


def merge(graphs: list[Graph]) -> Graph:
    """One graph from several that share no nodes (indices are shifted)."""
    county: list[str] = []
    weight: list[float] = []
    adj: list[set[int]] = []
    pieces: dict[str, list[int]] = {}
    bridges: list[tuple[str, str, float]] = []
    for g in graphs:
        off = len(county)
        county += g.county
        weight += g.weight
        adj += [{u + off for u in s} for s in g.adj]
        pieces.update({c: [v + off for v in ids] for c, ids in g.pieces.items()})
        bridges += g.bridges
    return Graph(county, weight, np.concatenate([g.x for g in graphs]), np.concatenate([g.y for g in graphs]), adj,
                 pieces, bridges)


def _solve(g: Graph, t: int, seed: int) -> tuple[list[int], list[int]]:
    grown = grow(g, kmeans_seeds(g, t, seed))
    return grown, improve(g, grown, t)


def align(weights: dict[str, float], coords: dict[str, tuple[float, float]], edges: list[tuple[str, str]], t: int,
          states: dict[str, str] | None = None, seed: int = 7, max_piece: float = MAX_PIECE) -> dict:
    """Aligned territories and the count-balanced baseline, with metrics for both."""
    groups = regions(weights, coords, edges)
    ts = [max(1, round(sum(weights[c] for c in grp))) for grp in groups[1:]]
    ts = [max(1, t - sum(ts))] + ts  # the mainland takes what is left
    graphs, grown_all, final_all, base_graphs, base_all = [], [], [], [], []
    off = boff = 0
    for grp, tg in zip(groups, ts):
        sub = set(grp)
        w = {c: weights[c] for c in grp}
        e = [(a, b) for a, b in edges if a in sub and b in sub]
        g = build_graph(w, coords, e, max_piece)
        grown, final = _solve(g, tg, seed)
        graphs.append(g)
        grown_all += [k + off for k in grown]
        final_all += [k + off for k in final]
        gb = build_graph({c: 1.0 for c in grp}, coords, e, max_piece=0)
        base = grow(gb, kmeans_seeds(gb, tg, seed))
        base_graphs.append(gb)
        base_all += [k + boff for k in base]
        off += tg
        boff += tg
    g, gb = merge(graphs), merge(base_graphs)
    t_all = sum(ts)
    return {"graph": g, "assign": final_all, "grown": grown_all, "baseline_graph": gb, "baseline": base_all,
            "regions": [{"counties": len(grp), "territories": tg} for grp, tg in zip(groups, ts)],
            "metrics": {"aligned": metrics(g, final_all, t_all, states=states),
                        "before_local_search": metrics(g, grown_all, t_all, states=states),
                        "baseline": metrics(gb, base_all, t_all, real_weight=weights, states=states)}}


def territory_table(res: dict, weights: dict[str, float], extra: dict[str, dict[str, float]]) -> list[dict]:
    """One row per territory, numbered west to east."""
    g: Graph = res["graph"]
    assign = res["assign"]
    t = max(assign) + 1
    members: list[list[int]] = [[] for _ in range(t)]
    for v, k in enumerate(assign):
        members[k].append(v)
    rows = []
    for k in range(t):
        idx = members[k]
        counties = sorted({g.county[v] for v in idx})
        w = sum(g.weight[v] for v in idx)
        row = {"k": k, "weight": w, "pieces": len(idx), "counties": len(counties),
               "x": float(np.mean(g.x[idx])), "y": float(np.mean(g.y[idx]))}
        for name, series in extra.items():
            row[name] = sum(series.get(c, 0.0) * sum(1 for v in idx if g.county[v] == c) / len(g.pieces[c])
                            for c in counties)
        rows.append(row)
    order = sorted(range(t), key=lambda k: (round(rows[k]["x"] / 150), -rows[k]["y"]))
    rename = {old: new for new, old in enumerate(order)}
    for r in rows:
        r["id"] = f"T{rename[r['k']] + 1:04d}"
    return sorted(rows, key=lambda r: r["id"])


def county_table(res: dict, states: dict[str, str]) -> list[dict]:
    """One row per county: its main territory, how much of it that territory holds, and how many territories touch it."""
    g: Graph = res["graph"]
    assign = res["assign"]
    rows = {}
    for c, ids in g.pieces.items():
        counts: dict[int, int] = {}
        for v in ids:
            counts[assign[v]] = counts.get(assign[v], 0) + 1
        main, n_main = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        rows[c] = {"county": c, "state": states[c], "k": main, "share": n_main / len(ids), "territories": len(counts)}
    return list(rows.values())


def main() -> int:
    import csv

    franchises = sizing.load_franchises()
    rules = sizing.load_rules()
    segs = sizing.load_county_segments()
    with (MARTS / "edges.csv").open(encoding="utf-8", newline="") as fh:
        edges = [(r["a"], r["b"]) for r in csv.DictReader(fh)]
    alpha = 0.5
    out: dict[str, dict] = {}
    for key, fr in franchises.items():
        counties = sizing.load_counties(key)
        calls = sizing.county_workload(key, segs, rules)
        reps = sizing.reps_needed(sum(calls.values()), fr)
        t = round(reps)
        total_calls = sum(calls.values())
        total_patients = sum(c["patients"] for c in counties.values())
        weights = {c: t * (alpha * calls.get(c, 0.0) / total_calls + (1 - alpha) * counties[c]["patients"] / total_patients)
                   for c in counties}
        coords = {c: (counties[c]["lat"], counties[c]["lon"]) for c in counties}
        states = {c: counties[c]["state"] for c in counties}
        res = align(weights, coords, edges, t, states)
        cal = territory_table(res, weights, {"calls": calls, "patients": {c: counties[c]["patients"] for c in counties}})
        cty = county_table(res, states)
        # relabel counties to the public territory id
        ids = {r["k"]: r["id"] for r in cal}
        for r in cty:
            r["territory"] = ids[r["k"]]
        t_all = max(res["assign"]) + 1
        out[key] = {"franchise": key, "reps": reps, "territories": t, "alpha": alpha, "metrics": res["metrics"],
                    "regions": res["regions"],
                    "weights": {"aligned": [round(x, 4) for x in territory_weights(res["graph"], res["assign"], t_all)],
                                "baseline": [round(x, 4) for x in territory_weights(res["baseline_graph"], res["baseline"], t_all, weights)]},
                    "bridges": [{"a": a, "b": b, "km": round(d, 1)} for a, b, d in res["graph"].bridges]}
        for r in cal:
            r.pop("k")
        with (MARTS / f"alignment_territory_{key}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "weight", "pieces", "counties", "calls", "patients", "x", "y"],
                               lineterminator="\n")
            w.writeheader()
            for r in cal:
                w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k in w.fieldnames})
        with (MARTS / f"alignment_county_{key}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["county", "state", "territory", "share", "territories"], lineterminator="\n")
            w.writeheader()
            for r in sorted(cty, key=lambda r: r["county"]):
                w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in w.fieldnames})
        m = res["metrics"]
        print(f"{key}: {reps:,.1f} reps -> {t} territories | CV aligned {m['aligned']['cv']:.3f} "
              f"(baseline {m['baseline']['cv']:.3f}) | radius {m['aligned']['mean_radius_km']:.0f} km "
              f"(baseline {m['baseline']['mean_radius_km']:.0f}) | disconnected {m['aligned']['disconnected']} "
              f"| split counties {m['aligned']['split_counties']}", flush=True)
    (MARTS / "alignment.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
