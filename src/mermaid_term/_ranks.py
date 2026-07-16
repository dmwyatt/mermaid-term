"""Rank assignment, crossing reduction, and cross-axis positioning."""

from __future__ import annotations

import math

from ._model import Edge, Graph


def compute_ranks(graph: Graph) -> list[int]:
    n = len(graph.nodes)
    children: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for e in graph.edges:
        if e.from_ != e.to:
            children[e.from_].append(e.to)
            indeg[e.to] += 1

    color = [0] * n
    dag: list[list[int]] = [[] for _ in range(n)]
    order: list[int] = []

    roots = [i for i in range(n) if indeg[i] == 0]
    for start in roots + list(range(n)):
        if color[start] == 0:
            _dfs_dag(start, children, color, dag, order)

    rank = [0] * n
    for u in reversed(order):
        for v in dag[u]:
            rank[v] = max(rank[v], rank[u] + 1)
    return rank


def _dfs_dag(
    start: int,
    children: list[list[int]],
    color: list[int],
    dag: list[list[int]],
    order: list[int],
) -> None:
    stack: list[list[int]] = [[start, 0]]
    color[start] = 1
    while stack:
        frame = stack[-1]
        u = frame[0]
        if frame[1] < len(children[u]):
            v = children[u][frame[1]]
            frame[1] += 1
            if color[v] == 1:
                continue
            dag[u].append(v)
            if color[v] == 0:
                color[v] = 1
                stack.append([v, 0])
        else:
            color[u] = 2
            order.append(u)
            stack.pop()


def order_ranks(by_rank: list[list[int]], edges: list[Edge], ranks: list[int]) -> None:
    """Reorder nodes within each rank to minimize edge crossings (Sugiyama-style
    barycenter sweeps): alternate down/up passes sort each rank by the mean
    position of its forward neighbours, keeping the ordering with the fewest
    crossings between adjacent ranks."""
    n = len(ranks)
    if len(by_rank) < 2 or n < 3:
        return
    parents: list[list[int]] = [[] for _ in range(n)]
    children: list[list[int]] = [[] for _ in range(n)]
    for e in edges:
        if e.from_ != e.to and ranks[e.to] > ranks[e.from_]:
            parents[e.to].append(e.from_)
            children[e.from_].append(e.to)

    pos = [0] * n
    for row in by_rank:
        for i, v in enumerate(row):
            pos[v] = i

    best = [list(row) for row in by_rank]
    best_crossings = count_crossings(edges, ranks, pos)
    if best_crossings == 0:
        return

    for it in range(8):
        if it % 2 == 0:
            for row in by_rank[1:]:
                _sort_by_barycenter(row, parents, pos)
                for i, v in enumerate(row):
                    pos[v] = i
        else:
            for row in reversed(by_rank[:-1]):
                _sort_by_barycenter(row, children, pos)
                for i, v in enumerate(row):
                    pos[v] = i
        crossings = count_crossings(edges, ranks, pos)
        if crossings < best_crossings:
            best_crossings = crossings
            best = [list(row) for row in by_rank]
        if best_crossings == 0:
            break

    for row, b in zip(by_rank, best):
        row[:] = b


def _sort_by_barycenter(row: list[int], neigh: list[list[int]], pos: list[int]) -> None:
    keyed = [
        (
            sum(pos[u] for u in neigh[v]) / len(neigh[v]) if neigh[v] else float(pos[v]),
            v,
        )
        for v in row
    ]
    keyed.sort(key=lambda kv: kv[0])
    row[:] = [v for _, v in keyed]


def count_crossings(edges: list[Edge], ranks: list[int], pos: list[int]) -> int:
    adjacent = [
        (ranks[e.from_], pos[e.from_], pos[e.to])
        for e in edges
        if e.from_ != e.to and ranks[e.to] == ranks[e.from_] + 1
    ]
    crossings = 0
    for i, a in enumerate(adjacent):
        for b in adjacent[i + 1 :]:
            if a[0] == b[0] and ((a[1] < b[1] and a[2] > b[2]) or (a[1] > b[1] and a[2] < b[2])):
                crossings += 1
    return crossings


def assign_positions(
    by_rank: list[list[int]],
    size: list[int],
    sep: int,
    edges: list[Edge],
    ranks: list[int],
) -> list[int]:
    """Assign a center coordinate (along the cross-axis) to every node so nodes
    line up under their neighbours. Iterative barycenter relaxation: each node
    drifts toward the average of its forward neighbours while ranks keep order
    and a minimum ``sep`` between boxes, which straightens chains and centers
    branches."""
    n = len(size)
    parents: list[list[int]] = [[] for _ in range(n)]
    children: list[list[int]] = [[] for _ in range(n)]
    for e in edges:
        if e.from_ != e.to and ranks[e.to] > ranks[e.from_]:
            parents[e.to].append(e.from_)
            children[e.from_].append(e.to)

    pos = [0.0] * n
    for row in by_rank:
        x = 0.0
        for v in row:
            half = size[v] / 2.0
            x += half
            pos[v] = x
            x += half + sep

    for it in range(10):
        if it % 2 == 0:
            for row in by_rank:
                _relax_rank(row, parents, pos, size, sep)
        else:
            for row in reversed(by_rank):
                _relax_rank(row, children, pos, size, sep)

    min_left = min((pos[v] - size[v] / 2.0 for v in range(n)), default=math.inf)
    if not math.isfinite(min_left):
        min_left = 0.0
    # Round half away from zero to match Rust's f64::round.
    return [max(int(math.floor(pos[v] - min_left + 0.5)), 0) for v in range(n)]


def _relax_rank(
    nodes: list[int],
    neigh: list[list[int]],
    pos: list[float],
    size: list[int],
    sep: int,
) -> None:
    n = len(nodes)
    if n == 0:
        return
    desired = [
        sum(pos[u] for u in neigh[v]) / len(neigh[v]) if neigh[v] else pos[v]
        for v in nodes
    ]

    def half(i: int) -> float:
        return size[nodes[i]] / 2.0

    left = [0.0] * n
    right = [0.0] * n
    for i in range(n):
        if i == 0:
            left[i] = desired[i]
        else:
            left[i] = max(desired[i], left[i - 1] + half(i - 1) + sep + half(i))
    for i in range(n - 1, -1, -1):
        if i == n - 1:
            right[i] = desired[i]
        else:
            right[i] = min(desired[i], right[i + 1] - half(i + 1) - sep - half(i))
    for i in range(n):
        pos[nodes[i]] = (left[i] + right[i]) / 2.0
    for i in range(1, n):
        min_p = pos[nodes[i - 1]] + half(i - 1) + sep + half(i)
        if pos[nodes[i]] < min_p:
            pos[nodes[i]] = min_p
