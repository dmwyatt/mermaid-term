"""Flowchart layout: node placement, bus/lane assignment, canvas painting."""

from __future__ import annotations

from dataclasses import dataclass

from ._canvas import STY_DOT, STY_SOLID, STY_THICK, Canvas
from ._draw import (
    Placed,
    draw_box,
    draw_class_box,
    draw_frame,
    route_back,
    route_back_lr,
    route_forward,
    route_forward_lr,
    route_self,
)
from ._model import MAX_CANVAS_CELLS, Dir, Graph, LineKind
from ._ranks import assign_positions, compute_ranks, order_ranks
from ._text import GAP_X, GAP_Y, MAX_LABEL, MAX_LINES, PAD, WRAP_WIDTH, fit_label, str_width, wrap_label


class OversizeError(Exception):
    """Layout exceeds the width budget or the canvas cell cap."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind  # "width" or "cells"


@dataclass
class NodeExtra:
    """Extra content for a node: a sub-canvas frame or class compartments."""

    frame: Canvas | None = None
    compartments: list[list[str]] | None = None


PLAIN = NodeExtra()


@dataclass
class NodeSizes:
    box_w: list[int]
    box_h: list[int]
    lay_w: list[int]
    lay_h: list[int]
    extra_h: list[int]
    self_label_w: list[int]


@dataclass
class RoutePlan:
    canvas: tuple[int, int]
    band_end: list[int]
    edge_bus: list[int]
    lane_base: int
    edge_lane: list[int]


def layout_canvas(graph: Graph, extras: list[NodeExtra], max_width: int | None) -> Canvas:
    n = len(graph.nodes)
    if n == 0:
        raise OversizeError("cells")

    ranks = compute_ranks(graph)
    max_rank = max(ranks, default=0)

    by_rank: list[list[int]] = [[] for _ in range(max_rank + 1)]
    for idx, r in enumerate(ranks):
        by_rank[r].append(idx)
    order_ranks(by_rank, graph.edges, ranks)

    wrapped = [wrap_label(node.label, WRAP_WIDTH, MAX_LINES) for node in graph.nodes]
    sizes = _node_sizes(graph, extras, wrapped)

    placed = [Placed() for _ in range(n)]
    # BT/RL reuse the TD/LR layout, then flip the finished canvas (so text
    # stays readable) into the bottom-up / right-to-left orientation.
    vertical = graph.dir in (Dir.DOWN, Dir.UP)
    if vertical:
        plan = place_td(ranks, max_rank, by_rank, sizes, graph, placed)
    else:
        plan = place_lr(ranks, max_rank, by_rank, sizes, graph, placed)
    canvas_w, canvas_h = plan.canvas

    if max_width is not None and canvas_w > max_width:
        raise OversizeError("width")
    if canvas_w * canvas_h > MAX_CANVAS_CELLS:
        raise OversizeError("cells")

    canvas = Canvas(canvas_w, canvas_h)
    for idx in range(n):
        extra = extras[idx]
        if extra.frame is not None:
            draw_frame(canvas, placed[idx], graph.nodes[idx].label, extra.frame)
        elif extra.compartments is not None:
            draw_class_box(canvas, placed[idx], extra.compartments)
        else:
            draw_box(canvas, placed[idx], wrapped[idx], graph.nodes[idx].shape)
    for i, edge in enumerate(graph.edges):
        canvas.cur_style = {
            LineKind.SOLID: STY_SOLID,
            LineKind.DOTTED: STY_DOT,
            LineKind.THICK: STY_THICK,
        }[edge.line]
        if edge.from_ == edge.to:
            route_self(canvas, placed[edge.from_], edge)
            continue
        from_, to = placed[edge.from_], placed[edge.to]
        adjacent = to.rank == from_.rank + 1
        bus = plan.band_end[from_.rank] + plan.edge_bus[i]
        lane = plan.lane_base + plan.edge_lane[i]
        if vertical and adjacent:
            route_forward(canvas, from_, to, edge, bus)
        elif vertical:
            route_back(canvas, from_, to, edge, lane)
        elif adjacent:
            route_forward_lr(canvas, from_, to, edge, bus)
        else:
            route_back_lr(canvas, from_, to, edge, lane)

    canvas.finalize_mask()
    return canvas


def _node_sizes(graph: Graph, extras: list[NodeExtra], wrapped: list[list[str]]) -> NodeSizes:
    n = len(graph.nodes)
    box_w: list[int] = []
    box_h: list[int] = []
    for i in range(n):
        extra = extras[i]
        if extra.frame is not None:
            title_w = str_width(fit_label(graph.nodes[i].label, WRAP_WIDTH))
            box_w.append(max(extra.frame.w + 2, title_w + 4))
            box_h.append(extra.frame.h + 2)
        elif extra.compartments is not None:
            sections = extra.compartments
            widest = max((str_width(l) for s in sections for l in s), default=1)
            box_w.append(max(widest, 1) + 2 * PAD + 2)
            filled = sum(1 for s in sections if s)
            box_h.append(sum(len(s) for s in sections) + max(filled - 1, 0) + 2)
        else:
            widest = max((str_width(l) for l in wrapped[i]), default=1)
            box_w.append(max(widest, 1) + 2 * PAD + 2)
            box_h.append(len(wrapped[i]) + 2)

    extra_h = [0] * n
    self_label_w = [0] * n
    for e in graph.edges:
        if e.from_ == e.to:
            extra_h[e.from_] = 2
            if e.label is not None:
                self_label_w[e.from_] = max(
                    self_label_w[e.from_], min(str_width(e.label), MAX_LABEL)
                )
    for i in range(n):
        if extra_h[i] > 0:
            box_w[i] = max(box_w[i], 7)
    lay_w = [
        box_w[i] + (2 * (self_label_w[i] + 3) if self_label_w[i] > 0 else 0)
        for i in range(n)
    ]
    lay_h = [box_h[i] + extra_h[i] for i in range(n)]
    return NodeSizes(box_w, box_h, lay_w, lay_h, extra_h, self_label_w)


def bus_spans_td(
    graph: Graph, ranks: list[int], centers: list[int], r: int, exact: bool
) -> list[tuple[int, int, int, int, int]]:
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
) -> list[tuple[int, int, int, int, int]]:
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


def assign_tracks(
    spans: list[tuple[int, int, int, int, int]],
) -> tuple[list[tuple[int, int]], int]:
    sorted_spans = sorted(spans)
    tracks: list[list[tuple[int, int, int, int]]] = []
    out: list[tuple[int, int]] = []
    for s, e, f, t, idx in sorted_spans:
        slot = None
        for x, members in enumerate(tracks):
            if all(
                e2 + 2 <= s or e + 2 <= s2 or f2 == f or t2 == t
                for s2, e2, f2, t2 in members
            ):
                slot = x
                break
        if slot is None:
            tracks.append([])
            slot = len(tracks) - 1
        tracks[slot].append((s, e, f, t))
        out.append((idx, slot))
    return (out, len(tracks))


def place_td(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    centers = assign_positions(by_rank, sizes.lay_w, GAP_X, graph.edges, ranks)

    edge_bus = [0] * len(graph.edges)
    bus_tracks = [0] * (max_rank + 1)
    for r in range(max_rank):
        spans = bus_spans_td(graph, ranks, centers, r, False)
        if not spans:
            continue
        assigned, count = assign_tracks(spans)
        for idx, slot in assigned:
            edge_bus[idx] = slot
        bus_tracks[r] = count

    rank_h = [
        max((sizes.box_h[i] + sizes.extra_h[i] for i in row), default=3)
        for row in by_rank
    ]
    rank_y = [0] * (max_rank + 1)
    for r in range(1, max_rank + 1):
        gap = max(GAP_Y, bus_tracks[r - 1] + 1)
        rank_y[r] = rank_y[r - 1] + rank_h[r - 1] + gap
    canvas_h = rank_y[max_rank] + rank_h[max_rank]
    band_end = [rank_y[r] + rank_h[r] for r in range(max_rank + 1)]

    diagram_w = 1
    for r, row in enumerate(by_rank):
        for idx in row:
            w = sizes.box_w[idx]
            h = sizes.box_h[idx]
            cx = centers[idx]
            x = max(cx - w // 2, 0)
            y = rank_y[r] + (rank_h[r] - h - sizes.extra_h[idx]) // 2
            placed[idx] = Placed(x, y, w, h, cx, y + h // 2, r)
            diagram_w = max(diagram_w, x + w)
            if sizes.extra_h[idx] > 0 and sizes.self_label_w[idx] > 0:
                diagram_w = max(diagram_w, x + w + 2 + sizes.self_label_w[idx])

    content_w = diagram_w
    for e in graph.edges:
        if e.from_ == e.to:
            continue
        if e.label is not None:
            lw = min(str_width(e.label), MAX_LABEL)
            if ranks[e.to] == ranks[e.from_] + 1:
                content_w = max(content_w, placed[e.to].cx + 2 + lw)
            else:
                content_w = max(content_w, diagram_w + lw + 1)

    edge_lane = [0] * len(graph.edges)
    lanes = lane_spans(graph, ranks, placed, True)
    if not lanes:
        canvas_w, lane_base = content_w, 0
    else:
        assigned, count = assign_tracks(lanes)
        for idx, slot in assigned:
            edge_lane[idx] = slot
        canvas_w, lane_base = content_w + 1 + count, content_w + 1

    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)


def place_lr(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    col_w = [max((sizes.box_w[i] for i in row), default=0) for row in by_rank]

    max_label = max(
        (
            min(str_width(e.label), MAX_LABEL)
            for e in graph.edges
            if (e.from_ == e.to or ranks[e.to] == ranks[e.from_] + 1)
            and e.label is not None
        ),
        default=0,
    )
    base_gap = max(GAP_X + 1, max_label + 3)

    centers = assign_positions(by_rank, sizes.lay_h, 1, graph.edges, ranks)

    edge_bus = [0] * len(graph.edges)
    bus_tracks = [0] * (max_rank + 1)
    for r in range(max_rank):
        spans = bus_spans_td(graph, ranks, centers, r, True)
        if not spans:
            continue
        assigned, count = assign_tracks(spans)
        for idx, slot in assigned:
            edge_bus[idx] = slot
        bus_tracks[r] = count

    rank_x = [0] * (max_rank + 1)
    for r in range(1, max_rank + 1):
        gap = max(base_gap, bus_tracks[r - 1] + 1)
        rank_x[r] = rank_x[r - 1] + col_w[r - 1] + gap
    canvas_w = (
        rank_x[max_rank]
        + col_w[max_rank]
        + max(
            (
                2 + sizes.self_label_w[i]
                for i in by_rank[max_rank]
                if sizes.extra_h[i] > 0 and sizes.self_label_w[i] > 0
            ),
            default=0,
        )
    )
    band_end = [rank_x[r] + col_w[r] for r in range(max_rank + 1)]

    diagram_h = 1
    for r, row in enumerate(by_rank):
        x = rank_x[r]
        for idx in row:
            w = sizes.box_w[idx]
            h = sizes.box_h[idx]
            cy = centers[idx]
            y = max(cy - (h + sizes.extra_h[idx]) // 2, 0)
            placed[idx] = Placed(x, y, w, h, x + w // 2, y + h // 2, r)
            diagram_h = max(diagram_h, y + h + sizes.extra_h[idx])

    edge_lane = [0] * len(graph.edges)
    lanes = lane_spans(graph, ranks, placed, False)
    if not lanes:
        canvas_h, lane_base = diagram_h, 0
    else:
        assigned, count = assign_tracks(lanes)
        for idx, slot in assigned:
            edge_lane[idx] = slot
        canvas_h, lane_base = diagram_h + 1 + count, diagram_h + 1

    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)
