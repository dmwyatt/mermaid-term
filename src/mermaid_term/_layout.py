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
from ._tracks import assign_bus_tracks, assign_lane_tracks

_LINE_STYLES = {
    LineKind.SOLID: STY_SOLID,
    LineKind.DOTTED: STY_DOT,
    LineKind.THICK: STY_THICK,
}


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
    by_rank = _rank_rows(ranks, max_rank)
    order_ranks(by_rank, graph.edges, ranks)

    wrapped = [wrap_label(node.label, WRAP_WIDTH, MAX_LINES) for node in graph.nodes]
    sizes = _node_sizes(graph, extras, wrapped)

    placed = [Placed() for _ in range(n)]
    # BT/RL reuse the TD/LR layout, then flip the finished canvas (so text
    # stays readable) into the bottom-up / right-to-left orientation.
    vertical = graph.dir in (Dir.DOWN, Dir.UP)
    place = place_td if vertical else place_lr
    plan = place(ranks, max_rank, by_rank, sizes, graph, placed)
    canvas_w, canvas_h = plan.canvas

    if max_width is not None and canvas_w > max_width:
        raise OversizeError("width")
    if canvas_w * canvas_h > MAX_CANVAS_CELLS:
        raise OversizeError("cells")

    canvas = Canvas(canvas_w, canvas_h)
    _paint_nodes(canvas, graph, extras, placed, wrapped)
    _paint_edges(canvas, graph, placed, plan, vertical)
    canvas.finalize_mask()
    return canvas


def _rank_rows(ranks: list[int], max_rank: int) -> list[list[int]]:
    by_rank: list[list[int]] = [[] for _ in range(max_rank + 1)]
    for idx, r in enumerate(ranks):
        by_rank[r].append(idx)
    return by_rank


def _paint_nodes(
    canvas: Canvas,
    graph: Graph,
    extras: list[NodeExtra],
    placed: list[Placed],
    wrapped: list[list[str]],
) -> None:
    for idx, extra in enumerate(extras):
        if extra.frame is not None:
            draw_frame(canvas, placed[idx], graph.nodes[idx].label, extra.frame)
        elif extra.compartments is not None:
            draw_class_box(canvas, placed[idx], extra.compartments)
        else:
            draw_box(canvas, placed[idx], wrapped[idx], graph.nodes[idx].shape)


def _paint_edges(
    canvas: Canvas, graph: Graph, placed: list[Placed], plan: RoutePlan, vertical: bool
) -> None:
    for i, edge in enumerate(graph.edges):
        canvas.cur_style = _LINE_STYLES[edge.line]
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


def _node_sizes(graph: Graph, extras: list[NodeExtra], wrapped: list[list[str]]) -> NodeSizes:
    n = len(graph.nodes)
    dims = [
        _box_dims(graph.nodes[i].label, extras[i], wrapped[i]) for i in range(n)
    ]
    box_w = [w for w, _ in dims]
    box_h = [h for _, h in dims]

    extra_h, self_label_w = _self_loop_extents(graph, n)
    for i in range(n):
        if extra_h[i] > 0:
            box_w[i] = max(box_w[i], 7)
    lay_w = [
        box_w[i] + (2 * (self_label_w[i] + 3) if self_label_w[i] > 0 else 0)
        for i in range(n)
    ]
    lay_h = [box_h[i] + extra_h[i] for i in range(n)]
    return NodeSizes(box_w, box_h, lay_w, lay_h, extra_h, self_label_w)


def _box_dims(label: str, extra: NodeExtra, wrapped: list[str]) -> tuple[int, int]:
    if extra.frame is not None:
        title_w = str_width(fit_label(label, WRAP_WIDTH))
        return (max(extra.frame.w + 2, title_w + 4), extra.frame.h + 2)
    if extra.compartments is not None:
        sections = extra.compartments
        widest = max((str_width(l) for s in sections for l in s), default=1)
        filled = sum(1 for s in sections if s)
        height = sum(len(s) for s in sections) + max(filled - 1, 0) + 2
        return (max(widest, 1) + 2 * PAD + 2, height)
    widest = max((str_width(l) for l in wrapped), default=1)
    return (max(widest, 1) + 2 * PAD + 2, len(wrapped) + 2)


def _self_loop_extents(graph: Graph, n: int) -> tuple[list[int], list[int]]:
    extra_h = [0] * n
    self_label_w = [0] * n
    for e in graph.edges:
        if e.from_ == e.to:
            extra_h[e.from_] = 2
            if e.label is not None:
                self_label_w[e.from_] = max(
                    self_label_w[e.from_], min(str_width(e.label), MAX_LABEL)
                )
    return extra_h, self_label_w


def place_td(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    centers = assign_positions(by_rank, sizes.lay_w, GAP_X, graph.edges, ranks)
    edge_bus, bus_tracks = assign_bus_tracks(graph, ranks, centers, max_rank, False)

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

    diagram_w = _place_td_nodes(by_rank, sizes, centers, rank_y, rank_h, placed)
    content_w = _td_content_width(graph, ranks, placed, diagram_w)
    edge_lane, canvas_w, lane_base = assign_lane_tracks(
        graph, ranks, placed, True, content_w
    )
    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)


def _place_td_nodes(
    by_rank: list[list[int]],
    sizes: NodeSizes,
    centers: list[int],
    rank_y: list[int],
    rank_h: list[int],
    placed: list[Placed],
) -> int:
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
    return diagram_w


def _td_content_width(
    graph: Graph, ranks: list[int], placed: list[Placed], diagram_w: int
) -> int:
    content_w = diagram_w
    for e in graph.edges:
        if e.from_ == e.to or e.label is None:
            continue
        lw = min(str_width(e.label), MAX_LABEL)
        if ranks[e.to] == ranks[e.from_] + 1:
            content_w = max(content_w, placed[e.to].cx + 2 + lw)
        else:
            content_w = max(content_w, diagram_w + lw + 1)
    return content_w


def place_lr(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    col_w = [max((sizes.box_w[i] for i in row), default=0) for row in by_rank]
    base_gap = max(GAP_X + 1, _lr_max_label(graph, ranks) + 3)

    centers = assign_positions(by_rank, sizes.lay_h, 1, graph.edges, ranks)
    edge_bus, bus_tracks = assign_bus_tracks(graph, ranks, centers, max_rank, True)

    rank_x = [0] * (max_rank + 1)
    for r in range(1, max_rank + 1):
        gap = max(base_gap, bus_tracks[r - 1] + 1)
        rank_x[r] = rank_x[r - 1] + col_w[r - 1] + gap
    canvas_w = rank_x[max_rank] + col_w[max_rank] + _lr_self_label_margin(
        sizes, by_rank[max_rank]
    )
    band_end = [rank_x[r] + col_w[r] for r in range(max_rank + 1)]

    diagram_h = _place_lr_nodes(by_rank, sizes, centers, rank_x, placed)
    edge_lane, canvas_h, lane_base = assign_lane_tracks(
        graph, ranks, placed, False, diagram_h
    )
    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)


def _lr_max_label(graph: Graph, ranks: list[int]) -> int:
    return max(
        (
            min(str_width(e.label), MAX_LABEL)
            for e in graph.edges
            if (e.from_ == e.to or ranks[e.to] == ranks[e.from_] + 1)
            and e.label is not None
        ),
        default=0,
    )


def _lr_self_label_margin(sizes: NodeSizes, last_rank: list[int]) -> int:
    return max(
        (
            2 + sizes.self_label_w[i]
            for i in last_rank
            if sizes.extra_h[i] > 0 and sizes.self_label_w[i] > 0
        ),
        default=0,
    )


def _place_lr_nodes(
    by_rank: list[list[int]],
    sizes: NodeSizes,
    centers: list[int],
    rank_x: list[int],
    placed: list[Placed],
) -> int:
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
    return diagram_h
