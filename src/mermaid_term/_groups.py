"""Subgraph rendering: group edges by scope and nest framed sub-canvases."""

from __future__ import annotations

from ._canvas import Canvas
from ._layout import PLAIN, NodeExtra, layout_canvas
from ._model import Edge, Graph, Node, Shape

# Items are ("node", index) or ("group", index) tuples.
Item = tuple[str, int]


def grouped_canvas(graph: Graph, max_width: int | None) -> Canvas:
    proxy: dict[int, int] = {}
    for gi, g in enumerate(graph.groups):
        ni = graph.index.get(g.id)
        if ni is not None:
            proxy[ni] = gi

    def group_chain(g: int | None) -> list[int]:
        chain: list[int] = []
        cur = g
        while cur is not None:
            chain.append(cur)
            cur = graph.groups[cur].parent
        chain.reverse()
        return chain

    def endpoint(n: int) -> tuple[Item, list[int]]:
        gi = proxy.get(n)
        if gi is not None:
            return (("group", gi), group_chain(graph.groups[gi].parent))
        return (("node", n), group_chain(graph.node_group[n]))

    scope_edges: dict[int | None, list[tuple[Item, Item, int]]] = {}
    referenced = [False] * len(graph.groups)
    for ei, e in enumerate(graph.edges):
        item_f, chain_f = endpoint(e.from_)
        item_t, chain_t = endpoint(e.to)
        k = 0
        for a, b in zip(chain_f, chain_t):
            if a != b:
                break
            k += 1
        scope = chain_f[k - 1] if k > 0 else None
        f = ("group", chain_f[k]) if len(chain_f) > k else item_f
        t = ("group", chain_t[k]) if len(chain_t) > k else item_t
        if f[0] == "group":
            referenced[f[1]] = True
        if t[0] == "group":
            referenced[t[1]] = True
        scope_edges.setdefault(scope, []).append((f, t, ei))

    direct_nodes: dict[int | None, list[int]] = {}
    for ni, g in enumerate(graph.node_group):
        if ni not in proxy:
            direct_nodes.setdefault(g, []).append(ni)

    keep = [False] * len(graph.groups)
    for gi in range(len(graph.groups) - 1, -1, -1):
        has_nodes = bool(direct_nodes.get(gi))
        has_children = any(
            graph.groups[c].parent == gi and keep[c] for c in range(len(graph.groups))
        )
        keep[gi] = has_nodes or has_children or referenced[gi]

    return _build_scope(graph, None, scope_edges, direct_nodes, keep, max_width)


def _build_scope(
    graph: Graph,
    scope: int | None,
    scope_edges: dict[int | None, list[tuple[Item, Item, int]]],
    direct_nodes: dict[int | None, list[int]],
    keep: list[bool],
    max_width: int | None,
) -> Canvas:
    items: list[Item] = [("node", n) for n in direct_nodes.get(scope, [])]
    child_groups = [
        gi
        for gi in range(len(graph.groups))
        if graph.groups[gi].parent == scope and keep[gi]
    ]
    items.extend(("group", gi) for gi in child_groups)

    if not items:
        return Canvas(1, 1)

    index_of: dict[Item, int] = {}
    nodes: list[Node] = []
    extras: list[NodeExtra] = []
    for item in items:
        index_of[item] = len(nodes)
        kind, i = item
        if kind == "node":
            nodes.append(Node(graph.nodes[i].label, graph.nodes[i].shape))
            extras.append(PLAIN)
        else:
            sub = _build_scope(graph, i, scope_edges, direct_nodes, keep, None)
            nodes.append(Node(graph.groups[i].label, Shape.RECT))
            extras.append(NodeExtra(frame=sub))

    edges: list[Edge] = []
    for f, t, ei in scope_edges.get(scope, []):
        fi = index_of.get(f)
        ti = index_of.get(t)
        if fi is None or ti is None:
            continue
        e = graph.edges[ei]
        edges.append(Edge(fi, ti, e.label, e.head_to, e.head_from, e.line))

    synth = Graph(nodes=nodes, edges=edges, dir=graph.dir)
    return layout_canvas(synth, extras, max_width)
