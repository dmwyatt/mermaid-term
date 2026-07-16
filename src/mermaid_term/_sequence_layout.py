"""Sequence diagram layout: lifelines, messages, notes, and dividers."""

from __future__ import annotations

from ._canvas import Canvas, Cls, D, L, R, U
from ._draw import Placed, draw_box, draw_seq_text
from ._layout import OversizeError
from ._model import MAX_CANVAS_CELLS, Shape
from ._parse_sequence import (
    NoteAnchor,
    NoteLeft,
    NoteOver,
    NoteRight,
    SeqDivider,
    SeqHead,
    SeqItem,
    SeqMessage,
    SeqNote,
    Sequence,
)
from ._text import PAD, WRAP_WIDTH, fit_label, str_width

SEQ_GAP = 5
_BOX_H = 3


def layout_sequence(seq: Sequence, max_width: int | None) -> Canvas:
    n = len(seq.labels)
    labels = [fit_label(l, WRAP_WIDTH) for l in seq.labels]
    box_w = [max(str_width(l), 1) + 2 * PAD + 2 for l in labels]

    xs = _lifeline_positions(seq, n, box_w)
    canvas_w = _canvas_width(seq, xs, box_w, n)
    rows, bottom_top = _item_rows(seq)
    canvas_h = bottom_top + _BOX_H

    if max_width is not None and canvas_w > max_width:
        raise OversizeError("width")
    if canvas_w * canvas_h > MAX_CANVAS_CELLS:
        raise OversizeError("cells")

    canvas = Canvas(canvas_w, canvas_h)
    _draw_actor_boxes(canvas, xs, box_w, labels, bottom_top)
    _draw_note_boxes(canvas, seq, xs, rows)
    _draw_lifelines(canvas, xs, bottom_top)
    _draw_items(canvas, seq, xs, rows, canvas_w)
    canvas.finalize_mask()
    return canvas


def note_geometry(xs: list[int], anchor: NoteAnchor, text_w: int) -> tuple[int, int]:
    if isinstance(anchor, NoteOver):
        center = (xs[anchor.left] + xs[anchor.right]) // 2
        w = max(xs[anchor.right] - xs[anchor.left] + 5, text_w + 2 * PAD + 2)
        return (max(center - w // 2, 0), w)
    if isinstance(anchor, NoteLeft):
        w = text_w + 2 * PAD + 2
        return (max(xs[anchor.of] - (2 + w - 1), 0), w)
    return (xs[anchor.of] + 2, text_w + 2 * PAD + 2)


def _div_ceil(a: int, b: int) -> int:
    return -(-a // b)


def _lifeline_positions(seq: Sequence, n: int, box_w: list[int]) -> list[int]:
    gaps = [
        max(SEQ_GAP, _div_ceil(box_w[i], 2) + _div_ceil(box_w[i + 1], 2) + 1)
        for i in range(max(n - 1, 0))
    ]
    reqs = _gap_requirements(seq, n)
    reqs.sort(key=lambda lrn: lrn[1] - lrn[0])
    for l, r, need in reqs:
        cur = sum(gaps[l:r])
        if cur < need:
            gaps[r - 1] += need - cur

    xs = [0] * n
    xs[0] = box_w[0] // 2
    for i in range(1, n):
        xs[i] = xs[i - 1] + gaps[i - 1]
    return xs


def _gap_requirements(seq: Sequence, n: int) -> list[tuple[int, int, int]]:
    reqs: list[tuple[int, int, int]] = []
    for item in seq.items:
        if isinstance(item, SeqMessage):
            _message_requirement(item, n, reqs)
        elif isinstance(item, SeqNote):
            _note_requirement(item, n, reqs)
    return reqs


def _message_requirement(item: SeqMessage, n: int, reqs: list[tuple[int, int, int]]) -> None:
    tw = str_width(item.text) if item.text is not None else 0
    if item.from_ != item.to:
        l, r = min(item.from_, item.to), max(item.from_, item.to)
        reqs.append((l, r, max(tw + 2, 4)))
    elif item.from_ + 1 < n:
        reqs.append((item.from_, item.from_ + 1, 5 + tw + 2))


def _note_requirement(item: SeqNote, n: int, reqs: list[tuple[int, int, int]]) -> None:
    tw = str_width(item.text)
    anchor = item.anchor
    if isinstance(anchor, NoteOver):
        _note_over_requirement(anchor, tw, n, reqs)
    elif isinstance(anchor, NoteLeft) and anchor.of > 0:
        reqs.append((anchor.of - 1, anchor.of, tw + 7))
    elif isinstance(anchor, NoteRight) and anchor.of + 1 < n:
        reqs.append((anchor.of, anchor.of + 1, tw + 7))


def _note_over_requirement(
    anchor: NoteOver, tw: int, n: int, reqs: list[tuple[int, int, int]]
) -> None:
    if anchor.left < anchor.right:
        reqs.append((anchor.left, anchor.right, max(tw - 1, 0)))
        return
    i = anchor.left
    half = _div_ceil(tw + 4, 2) + 2
    if i > 0:
        reqs.append((i - 1, i, half))
    if i + 1 < n:
        reqs.append((i, i + 1, half))


def _canvas_width(seq: Sequence, xs: list[int], box_w: list[int], n: int) -> int:
    canvas_w = xs[n - 1] + _div_ceil(box_w[n - 1], 2) + 1
    for item in seq.items:
        if isinstance(item, SeqMessage) and item.from_ == item.to:
            tw = str_width(item.text) if item.text is not None else 0
            canvas_w = max(canvas_w, xs[item.from_] + 5 + tw + 1)
        elif isinstance(item, SeqNote):
            x, w = note_geometry(xs, item.anchor, str_width(item.text))
            canvas_w = max(canvas_w, x + w + 1)
        elif isinstance(item, SeqDivider):
            canvas_w = max(canvas_w, str_width(item.text) + 4)
    return canvas_w


def _item_rows(seq: Sequence) -> tuple[list[int], int]:
    rows: list[int] = []
    y = _BOX_H + 1
    for item in seq.items:
        rows.append(y)
        y += _item_height(item)
    return rows, y


def _item_height(item: SeqItem) -> int:
    if isinstance(item, SeqMessage):
        if item.from_ == item.to:
            return 4
        return 3 if item.text is not None else 2
    if isinstance(item, SeqNote):
        return 4
    return 2


def _draw_actor_boxes(
    canvas: Canvas, xs: list[int], box_w: list[int], labels: list[str], bottom_top: int
) -> None:
    for i in range(len(xs)):
        for by in (0, bottom_top):
            p = Placed(
                x=max(xs[i] - box_w[i] // 2, 0),
                y=by,
                w=box_w[i],
                h=_BOX_H,
                cx=xs[i],
                cy=by + 1,
            )
            draw_box(canvas, p, [labels[i]], Shape.RECT)


def _draw_note_boxes(canvas: Canvas, seq: Sequence, xs: list[int], rows: list[int]) -> None:
    for item, r in zip(seq.items, rows):
        if isinstance(item, SeqNote):
            x, w = note_geometry(xs, item.anchor, str_width(item.text))
            p = Placed(x=x, y=r, w=w, h=3, cx=x + w // 2, cy=r + 1)
            draw_box(canvas, p, [item.text], Shape.RECT)


def _draw_lifelines(canvas: Canvas, xs: list[int], bottom_top: int) -> None:
    for x in xs:
        canvas.junction(x, _BOX_H - 1, D)
        canvas.seg_v(x, _BOX_H, bottom_top - 1)
        canvas.junction(x, bottom_top, U)


def _draw_items(
    canvas: Canvas, seq: Sequence, xs: list[int], rows: list[int], canvas_w: int
) -> None:
    for item, r in zip(seq.items, rows):
        if isinstance(item, SeqMessage):
            _draw_message(canvas, xs, item, r)
        elif isinstance(item, SeqDivider):
            for x in range(canvas_w):
                canvas.set(x, r, "─", Cls.EDGE)
            t = fit_label(item.text, max(canvas_w - 4, 0))
            draw_seq_text(canvas, f" {t} ", 2, r, Cls.EDGE_LABEL)


def _draw_message(canvas: Canvas, xs: list[int], item: SeqMessage, r: int) -> None:
    if item.from_ == item.to:
        _draw_self_message(canvas, xs, item, r)
    else:
        _draw_span_message(canvas, xs, item, r)


def _draw_self_message(canvas: Canvas, xs: list[int], item: SeqMessage, r: int) -> None:
    line_ch = "╌" if item.dashed else "─"
    x = xs[item.from_]
    canvas.junction(x, r, R)
    canvas.set(x + 1, r, line_ch, Cls.EDGE)
    canvas.set(x + 2, r, line_ch, Cls.EDGE)
    canvas.set(x + 3, r, "╮", Cls.EDGE)
    canvas.set(x + 3, r + 1, "│", Cls.EDGE)
    canvas.set(x + 1, r + 2, "×" if item.head == SeqHead.CROSS else "◄", Cls.EDGE)
    canvas.set(x + 2, r + 2, line_ch, Cls.EDGE)
    canvas.set(x + 3, r + 2, "╯", Cls.EDGE)
    if item.text is not None:
        draw_seq_text(canvas, item.text, x + 5, r + 1, Cls.TEXT)


def _draw_span_message(canvas: Canvas, xs: list[int], item: SeqMessage, r: int) -> None:
    line_ch = "╌" if item.dashed else "─"
    x0, x1 = xs[item.from_], xs[item.to]
    rightward = x1 > x0
    arrow_row = r + 1 if item.text is not None else r
    lo, hi = min(x0, x1), max(x0, x1)
    canvas.junction(x0, arrow_row, R if rightward else L)
    for x in range(lo + 1, hi):
        canvas.set(x, arrow_row, line_ch, Cls.EDGE)
    if item.head == SeqHead.CROSS:
        head_ch = "×"
    else:
        head_ch = "▶" if rightward else "◄"
    head_x = x1 - 1 if rightward else x1 + 1
    canvas.set(head_x, arrow_row, head_ch, Cls.EDGE)
    if item.text is not None:
        span = hi - lo - 1
        t = fit_label(item.text, max(span, 1))
        tx = lo + 1 + max(span - str_width(t), 0) // 2
        draw_seq_text(canvas, t, tx, r, Cls.TEXT)
