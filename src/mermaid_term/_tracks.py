"""Bus and lane track assignment: pack edge spans into parallel tracks."""

from __future__ import annotations

from ._draw import Placed
from ._model import Graph

Span = tuple[int, int, int, int, int]  # (start, end, from, to, edge index)


def bus_spans_td(
    graph: Graph, ranks: list[int], centers: list[int], r: int, exact: bool
) -> list[Span]:
    spans = []
    for i, e in enumerate(graph.edges):
        if exact:
            jogs = centers[e.from_] != centers[e.to]
        else:
            jogs = abs(centers[e.from_] - centers[e.to]) > 1
        if e.from_ != e.to and ranks[e.from_] == r and ranks[e.to] == r + 1 and jogs:
            a = min(centers[e.from_], centers[e.to])
            b = max(centers[e.from_], centers[e.to])
            spans.append((a, b, e.from_, e.to, i))
    return spans


def lane_spans(
    graph: Graph, ranks: list[int], placed: list[Placed], vertical: bool
) -> list[Span]:
    spans = []
    for i, e in enumerate(graph.edges):
        if e.from_ == e.to or ranks[e.to] == ranks[e.from_] + 1:
            continue
        pf, pt = placed[e.from_], placed[e.to]
        if vertical:
            a, b = min(pf.cy, pt.cy), max(pf.cy, pt.cy)
        else:
            a, b = min(pf.cx, pt.cx), max(pf.cx, pt.cx)
        spans.append((a, b, e.from_, e.to, i))
    return spans


def assign_tracks(spans: list[Span]) -> tuple[list[tuple[int, int]], int]:
    sorted_spans = sorted(spans)
    tracks: list[list[tuple[int, int, int, int]]] = []
    out: list[tuple[int, int]] = []
    for s, e, f, t, idx in sorted_spans:
        slot = _compatible_track(tracks, s, e, f, t)
        if slot is None:
            tracks.append([])
            slot = len(tracks) - 1
        tracks[slot].append((s, e, f, t))
        out.append((idx, slot))
    return (out, len(tracks))


def _compatible_track(
    tracks: list[list[tuple[int, int, int, int]]], s: int, e: int, f: int, t: int
) -> int | None:
    for x, members in enumerate(tracks):
        if all(
            e2 + 2 <= s or e + 2 <= s2 or f2 == f or t2 == t
            for s2, e2, f2, t2 in members
        ):
            return x
    return None


def assign_bus_tracks(
    graph: Graph, ranks: list[int], centers: list[int], max_rank: int, exact: bool
) -> tuple[list[int], list[int]]:
    edge_bus = [0] * len(graph.edges)
    bus_tracks = [0] * (max_rank + 1)
    for r in range(max_rank):
        spans = bus_spans_td(graph, ranks, centers, r, exact)
        if not spans:
            continue
        assigned, count = assign_tracks(spans)
        for idx, slot in assigned:
            edge_bus[idx] = slot
        bus_tracks[r] = count
    return edge_bus, bus_tracks


def assign_lane_tracks(
    graph: Graph, ranks: list[int], placed: list[Placed], vertical: bool, extent: int
) -> tuple[list[int], int, int]:
    """Returns (edge_lane, canvas extent including lanes, lane base)."""
    edge_lane = [0] * len(graph.edges)
    lanes = lane_spans(graph, ranks, placed, vertical)
    if not lanes:
        return edge_lane, extent, 0
    assigned, count = assign_tracks(lanes)
    for idx, slot in assigned:
        edge_lane[idx] = slot
    return edge_lane, extent + 1 + count, extent + 1
