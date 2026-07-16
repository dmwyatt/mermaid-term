"""Box drawing, arrowhead glyphs, and edge routing onto a canvas."""

from __future__ import annotations

from dataclasses import dataclass

from ._canvas import D, L, R, U, Canvas, Cls
from ._model import Edge, Head, LineKind, Shape
from ._text import CONT, MAX_LABEL, PAD, char_width, fit_label, str_width


@dataclass
class Placed:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    cx: int = 0
    cy: int = 0
    rank: int = 0


def draw_box(canvas: Canvas, p: Placed, lines: list[str], shape: Shape) -> None:
    x, y, w, h = p.x, p.y, p.w, p.h
    right = x + w - 1
    bottom = y + h - 1

    if shape in (Shape.ROUND, Shape.DIAMOND):
        tl, tr, bl, br = "╭", "╮", "╰", "╯"
    else:
        tl, tr, bl, br = "┌", "┐", "└", "┘"
    canvas.set(x, y, tl, Cls.BORDER)
    canvas.set(right, y, tr, Cls.BORDER)
    canvas.set(x, bottom, bl, Cls.BORDER)
    canvas.set(right, bottom, br, Cls.BORDER)

    for cx in range(x + 1, right):
        canvas.add_bits(cx, y, L | R)
        canvas.add_bits(cx, bottom, L | R)
    for cy in range(y + 1, bottom):
        canvas.add_bits(x, cy, U | D)
        canvas.add_bits(right, cy, U | D)

    for cy in range(y, bottom + 1):
        for cx in range(x, right + 1):
            canvas.occupied[canvas.idx(cx, cy)] = True

    inner = max(w - (2 * PAD + 2), 1)
    for li, line in enumerate(lines):
        row = y + 1 + li
        text = fit_label(line, inner)
        tw = str_width(text)
        text_x = x + 1 + PAD + max(inner - tw, 0) // 2
        cur = text_x
        for c in text:
            cw = max(char_width(c), 1)
            canvas.set(cur, row, c, Cls.TEXT)
            # Wide glyphs (CJK, emoji) own a second column; mark it as a
            # continuation so the line builder doesn't emit a stray space.
            for k in range(1, cw):
                canvas.set(cur + k, row, CONT, Cls.TEXT)
            cur += cw


def draw_class_box(canvas: Canvas, p: Placed, sections: list[list[str]]) -> None:
    draw_box(canvas, p, [], Shape.RECT)
    inner = max(p.w - (2 * PAD + 2), 1)
    row = p.y + 1
    first = True
    for si, section in enumerate(sections):
        if not section:
            continue
        if not first:
            canvas.set(p.x, row, "├", Cls.BORDER)
            for x in range(p.x + 1, p.x + p.w - 1):
                canvas.set(x, row, "─", Cls.BORDER)
            canvas.set(p.x + p.w - 1, row, "┤", Cls.BORDER)
            row += 1
        first = False
        for line in section:
            text = fit_label(line, inner)
            if si == 0:
                tx = p.x + 1 + PAD + max(inner - str_width(text), 0) // 2
            else:
                tx = p.x + 1 + PAD
            draw_seq_text(canvas, text, tx, row, Cls.TEXT)
            row += 1


def draw_frame(canvas: Canvas, p: Placed, title: str, sub: Canvas) -> None:
    draw_box(canvas, p, [], Shape.RECT)
    t = fit_label(title, max(p.w - 4, 0))
    draw_seq_text(canvas, f" {t} ", p.x + 1, p.y, Cls.TEXT)
    ox = p.x + 1 + (p.w - 2 - sub.w) // 2
    oy = p.y + 1 + (p.h - 2 - sub.h) // 2
    canvas.blit(sub, ox, oy)


def draw_seq_text(canvas: Canvas, text: str, x: int, y: int, cls: Cls) -> None:
    cur = x
    for c in text:
        cw = max(char_width(c), 1)
        for k in range(cw):
            if cur + k < canvas.w and y < canvas.h:
                canvas.mask[canvas.idx(cur + k, y)] = 0
            canvas.set(cur + k, y, c if k == 0 else CONT, cls)
        cur += cw


def head_glyph(head: Head, arrow: str) -> str:
    if head == Head.CIRCLE:
        return "o"
    if head == Head.CROSS:
        return "×"
    if head == Head.DIAMOND_FILL:
        return "◆"
    if head == Head.DIAMOND_OPEN:
        return "◇"
    if head == Head.TRIANGLE:
        return {"▼": "▽", "▲": "△", "◄": "◁", "▶": "▷"}.get(arrow, arrow)
    return arrow


def place_label(canvas: Canvas, label: str, row: int, start_x: int) -> None:
    if row >= canvas.h:
        return
    text = fit_label(label, MAX_LABEL)
    x = start_x
    for c in text:
        cw = max(char_width(c), 1)
        if x + cw > canvas.w:
            break
        blocked = any(
            canvas.ch[canvas.idx(x + k, row)] != " "
            or canvas.mask[canvas.idx(x + k, row)] != 0
            or canvas.occupied[canvas.idx(x + k, row)]
            for k in range(cw)
        )
        if blocked:
            break
        canvas.set(x, row, c, Cls.EDGE_LABEL)
        for k in range(1, cw):
            canvas.set(x + k, row, CONT, Cls.EDGE_LABEL)
        x += cw


def route_forward(canvas: Canvas, from_: Placed, to: Placed, edge: Edge, bus: int) -> None:
    tx = to.cx
    bx = tx if abs(from_.cx - tx) <= 1 else from_.cx
    by = from_.y + from_.h - 1
    head_row = to.y - 1

    canvas.junction(bx, by, D)
    canvas.seg_v(bx, by, bus)
    if bx == tx:
        canvas.seg_v(bx, bus, head_row)
    else:
        canvas.seg_h(bus, bx, tx)
        canvas.seg_v(tx, bus, head_row)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx, head_row, U)
    else:
        canvas.set(tx, head_row, head_glyph(edge.head_to, "▼"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(bx, by, head_glyph(edge.head_from, "▲"), Cls.EDGE)

    if edge.label is not None:
        place_label(canvas, edge.label, head_row, tx + 1)


def route_self(canvas: Canvas, p: Placed, edge: Edge) -> None:
    bottom = p.y + p.h - 1
    exit_x = p.cx + 1
    ret_x = p.x + p.w - 2
    if ret_x <= exit_x or bottom + 2 >= canvas.h:
        return
    if edge.line == LineKind.DOTTED:
        v, h, bl, br = "╎", "╌", "╰", "╯"
    elif edge.line == LineKind.THICK:
        v, h, bl, br = "┃", "━", "┗", "┛"
    else:
        v, h, bl, br = "│", "─", "╰", "╯"
    canvas.junction(exit_x, bottom, D)
    canvas.set(exit_x, bottom + 1, v, Cls.EDGE)
    canvas.set(exit_x, bottom + 2, bl, Cls.EDGE)
    for x in range(exit_x + 1, ret_x):
        canvas.set(x, bottom + 2, h, Cls.EDGE)
    canvas.set(ret_x, bottom + 2, br, Cls.EDGE)
    canvas.set(ret_x, bottom + 1, head_glyph(edge.head_to, "▲"), Cls.EDGE)
    if edge.label is not None:
        place_label(canvas, edge.label, bottom + 1, p.x + p.w + 1)


def route_back(canvas: Canvas, from_: Placed, to: Placed, edge: Edge, lane_x: int) -> None:
    sx = from_.x + from_.w - 1
    sy = from_.cy
    tx = to.x + to.w - 1
    tyc = to.cy

    canvas.junction(sx, sy, R)
    canvas.seg_h(sy, sx, lane_x)
    canvas.seg_v(lane_x, sy, tyc)
    canvas.seg_h(tyc, tx + 1, lane_x)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx + 1, tyc, R)
    else:
        canvas.set(tx + 1, tyc, head_glyph(edge.head_to, "◄"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(sx, sy, head_glyph(edge.head_from, "◄"), Cls.EDGE)

    if edge.label is not None:
        place_label(
            canvas,
            edge.label,
            max(tyc - 1, 0),
            max(lane_x - (str_width(edge.label) + 1), 0),
        )


def route_forward_lr(canvas: Canvas, from_: Placed, to: Placed, edge: Edge, bus: int) -> None:
    rx = from_.x + from_.w - 1
    ry = from_.cy
    ly = to.cy
    head_col = to.x - 1

    canvas.junction(rx, ry, R)
    canvas.seg_h(ry, rx, bus)
    if ry == ly:
        canvas.seg_h(ry, bus, head_col)
    else:
        canvas.seg_v(bus, ry, ly)
        canvas.seg_h(ly, bus, head_col)

    if edge.head_to == Head.NONE:
        canvas.add_bits(head_col, ly, R)
    else:
        canvas.set(head_col, ly, head_glyph(edge.head_to, "▶"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(rx, ry, head_glyph(edge.head_from, "◄"), Cls.EDGE)

    if edge.label is not None:
        place_label(canvas, edge.label, max(ly - 1, 0), bus + 1)


def route_back_lr(canvas: Canvas, from_: Placed, to: Placed, edge: Edge, lane_y: int) -> None:
    sx = from_.cx
    sy = from_.y + from_.h - 1
    tx = to.cx
    ty = to.y + to.h - 1

    canvas.junction(sx, sy, D)
    canvas.seg_v(sx, sy, lane_y)
    canvas.seg_h(lane_y, sx, tx)
    canvas.seg_v(tx, lane_y, ty + 1)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx, ty + 1, D)
    else:
        canvas.set(tx, ty + 1, head_glyph(edge.head_to, "▲"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(sx, sy, head_glyph(edge.head_from, "▲"), Cls.EDGE)

    if edge.label is not None:
        place_label(canvas, edge.label, max(lane_y - 1, 0), (sx + tx) // 2)
