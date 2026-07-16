"""Subgraph rendering: group edges by scope and nest framed sub-canvases."""

from __future__ import annotations

from ._canvas import Canvas
from ._layout import PLAIN, NodeExtra, layout_canvas
from ._model import Edge, Graph, Node, Shape

# Items are ("node", index) or ("group", index) tuples.
Item = tuple[str, int]
_ScopeEdges = dict[int | None, list[tuple[Item, Item, int]]]


def grouped_canvas(graph: Graph, max_width: int | None) -> Canvas:
    proxy = _group_proxies(graph)
    scope_edges, referenced = _scoped_edges(graph, proxy)
    direct_nodes = _direct_nodes(graph, proxy)
    keep = _kept_groups(graph, direct_nodes, referenced)
    return _build_scope(graph, None, scope_edges, direct_nodes, keep, max_width)


def _group_proxies(graph: Graph) -> dict[int, int]:
    """Nodes whose id names a group stand in for that group in edges."""
    proxy: dict[int, int] = {}
    for gi, g in enumerate(graph.groups):
        ni = graph.index.get(g.id)
        if ni is not None:
            proxy[ni] = gi
    return proxy


def _group_chain(graph: Graph, g: int | None) -> list[int]:
    chain: list[int] = []
    cur = g
    while cur is not None:
        chain.append(cur)
        cur = graph.groups[cur].parent
    chain.reverse()
    return chain


def _endpoint(graph: Graph, proxy: dict[int, int], n: int) -> tuple[Item, list[int]]:
    gi = proxy.get(n)
    if gi is not None:
        return (("group", gi), _group_chain(graph, graph.groups[gi].parent))
    return (("node", n), _group_chain(graph, graph.node_group[n]))


def _common_prefix(a: list[int], b: list[int]) -> int:
    k = 0
    for x, y in zip(a, b):
        if x != y:
            break
        k += 1
    return k


def _scoped_edges(graph: Graph, proxy: dict[int, int]) -> tuple[_ScopeEdges, list[bool]]:
    scope_edges: _ScopeEdges = {}
    referenced = [False] * len(graph.groups)
    for ei, e in enumerate(graph.edges):
        item_f, chain_f = _endpoint(graph, proxy, e.from_)
        item_t, chain_t = _endpoint(graph, proxy, e.to)
        k = _common_prefix(chain_f, chain_t)
        scope = chain_f[k - 1] if k > 0 else None
        f = ("group", chain_f[k]) if len(chain_f) > k else item_f
        t = ("group", chain_t[k]) if len(chain_t) > k else item_t
        for item in (f, t):
            if item[0] == "group":
                referenced[item[1]] = True
        scope_edges.setdefault(scope, []).append((f, t, ei))
    return scope_edges, referenced


def _direct_nodes(graph: Graph, proxy: dict[int, int]) -> dict[int | None, list[int]]:
    direct: dict[int | None, list[int]] = {}
    for ni, g in enumerate(graph.node_group):
        if ni not in proxy:
            direct.setdefault(g, []).append(ni)
    return direct


def _kept_groups(
    graph: Graph, direct_nodes: dict[int | None, list[int]], referenced: list[bool]
) -> list[bool]:
    keep = [False] * len(graph.groups)
    for gi in range(len(graph.groups) - 1, -1, -1):
        has_nodes = bool(direct_nodes.get(gi))
        has_children = any(
            graph.groups[c].parent == gi and keep[c] for c in range(len(graph.groups))
        )
        keep[gi] = has_nodes or has_children or referenced[gi]
    return keep


def _build_scope(
    graph: Graph,
    scope: int | None,
    scope_edges: _ScopeEdges,
    direct_nodes: dict[int | None, list[int]],
    keep: list[bool],
    max_width: int | None,
) -> Canvas:
    items: list[Item] = [("node", n) for n in direct_nodes.get(scope, [])]
    items.extend(
        ("group", gi)
        for gi in range(len(graph.groups))
        if graph.groups[gi].parent == scope and keep[gi]
    )
    if not items:
        return Canvas(1, 1)

    index_of, nodes, extras = _scope_members(
        graph, items, scope_edges, direct_nodes, keep
    )
    edges = _synth_edges(graph, scope_edges.get(scope, []), index_of)
    synth = Graph(nodes=nodes, edges=edges, dir=graph.dir)
    return layout_canvas(synth, extras, max_width)


def _scope_members(
    graph: Graph,
    items: list[Item],
    scope_edges: _ScopeEdges,
    direct_nodes: dict[int | None, list[int]],
    keep: list[bool],
) -> tuple[dict[Item, int], list[Node], list[NodeExtra]]:
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
    return index_of, nodes, extras


def _synth_edges(
    graph: Graph, edge_list: list[tuple[Item, Item, int]], index_of: dict[Item, int]
) -> list[Edge]:
    edges: list[Edge] = []
    for f, t, ei in edge_list:
        fi = index_of.get(f)
        ti = index_of.get(t)
        if fi is None or ti is None:
            continue
        e = graph.edges[ei]
        edges.append(Edge(fi, ti, e.label, e.head_to, e.head_from, e.line))
    return edges
