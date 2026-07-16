"""Rank assignment and crossing-reduction ordering."""

from mermaid_term._parse_flowchart import parse_graph
from mermaid_term._ranks import compute_ranks, count_crossings, order_ranks


def test_ranks_ignore_back_edges():
    g = parse_graph("graph TD\n A-->B\n B-->C\n C-->A")
    assert g is not None
    r = compute_ranks(g)
    assert r[g.index["A"]] == 0
    assert r[g.index["B"]] == 1
    assert r[g.index["C"]] == 2


def ordered_ranks(src: str):
    g = parse_graph(src)
    assert g is not None
    ranks = compute_ranks(g)
    max_rank = max(ranks)
    by_rank = [[] for _ in range(max_rank + 1)]
    for idx, r in enumerate(ranks):
        by_rank[r].append(idx)
    order_ranks(by_rank, g.edges, ranks)
    return g, ranks, by_rank


def positions(g, by_rank):
    pos = [0] * len(g.nodes)
    for row in by_rank:
        for i, v in enumerate(row):
            pos[v] = i
    return pos


def test_order_ranks_removes_avoidable_crossing():
    g, ranks, by_rank = ordered_ranks("graph TD\n C[ccc]\n D[ddd]\n A --> D\n B --> C")
    pos = positions(g, by_rank)
    assert count_crossings(g.edges, ranks, pos) == 0
    assert pos[g.index["D"]] < pos[g.index["C"]], "D follows parent A leftward"


def test_order_ranks_keeps_crossing_free_order():
    g, ranks, by_rank = ordered_ranks("graph TD\n A --> C\n B --> D")
    assert by_rank[0] == [g.index["A"], g.index["B"]]
    assert by_rank[1] == [g.index["C"], g.index["D"]]
    pos = positions(g, by_rank)
    assert count_crossings(g.edges, ranks, pos) == 0


def test_three_layer_weave_untangles():
    g, ranks, by_rank = ordered_ranks(
        "graph TD\n X[x]\n Y[y]\n A --> Y\n B --> X\n X --> Q\n Y --> P\n P[p]\n Q[q]"
    )
    pos = positions(g, by_rank)
    assert count_crossings(g.edges, ranks, pos) == 0, "both layers untangle"
