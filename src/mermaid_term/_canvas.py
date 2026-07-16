"""Character-cell canvas with box-drawing mask composition and styling runs."""

from __future__ import annotations

from enum import Enum

from ._styles import Line, MermaidStyles, Span, Style
from ._text import CONT

U = 1
D = 2
L = 4
R = 8


class Cls(Enum):
    EMPTY = "empty"
    BORDER = "border"
    TEXT = "text"
    EDGE = "edge"
    EDGE_LABEL = "edge_label"


STY_DOT = 1
STY_THICK = 2
STY_SOLID = 4


class Canvas:
    def __init__(self, w: int, h: int) -> None:
        n = w * h
        self.w = w
        self.h = h
        self.ch: list[str] = [" "] * n
        self.cls: list[Cls] = [Cls.EMPTY] * n
        self.mask: list[int] = [0] * n
        self.style: list[int] = [0] * n
        self.occupied: list[bool] = [False] * n
        self.cur_style = STY_SOLID

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def set(self, x: int, y: int, c: str, cls: Cls) -> None:
        if not self._in_bounds(x, y):
            return
        i = self.idx(x, y)
        self.ch[i] = c
        self.cls[i] = cls

    def add_bits(self, x: int, y: int, bits: int) -> None:
        if not self._in_bounds(x, y):
            return
        i = self.idx(x, y)
        if self.occupied[i]:
            return
        self.mask[i] |= bits
        self.style[i] |= self.cur_style
        if self.cls[i] != Cls.BORDER:
            self.cls[i] = Cls.EDGE

    def blit(self, sub: Canvas, ox: int, oy: int) -> None:
        for sy in range(sub.h):
            for sx in range(sub.w):
                x, y = ox + sx, oy + sy
                if not self._in_bounds(x, y):
                    continue
                si = sub.idx(sx, sy)
                di = self.idx(x, y)
                self.ch[di] = sub.ch[si]
                self.cls[di] = sub.cls[si]
                self.style[di] = sub.style[si]
                self.occupied[di] = True

    def junction(self, x: int, y: int, bits: int) -> None:
        if not self._in_bounds(x, y):
            return
        i = self.idx(x, y)
        self.mask[i] |= bits
        if self.cls[i] != Cls.BORDER:
            self.cls[i] = Cls.EDGE

    def seg_v(self, x: int, y0: int, y1: int) -> None:
        a, b = min(y0, y1), max(y0, y1)
        for y in range(a, b + 1):
            bits = 0
            if y > a:
                bits |= U
            if y < b:
                bits |= D
            self.add_bits(x, y, bits)

    def seg_h(self, y: int, x0: int, x1: int) -> None:
        a, b = min(x0, x1), max(x0, x1)
        for x in range(a, b + 1):
            bits = 0
            if x > a:
                bits |= L
            if x < b:
                bits |= R
            self.add_bits(x, y, bits)

    def finalize_mask(self) -> None:
        for i in range(len(self.ch)):
            if self.mask[i] != 0 and self.ch[i] == " ":
                c = mask_char(self.mask[i])
                if self.style[i] == STY_DOT:
                    c = dotted_char(c)
                elif self.style[i] == STY_THICK:
                    c = thick_char(c)
                self.ch[i] = c

    def flip_vertical(self) -> None:
        """Mirror top-to-bottom for ``BT`` (rows reorder; within-row text is
        unaffected, so labels stay readable). Box-drawing glyphs flip too."""
        for y in range(self.h // 2):
            y2 = self.h - 1 - y
            for x in range(self.w):
                i, j = self.idx(x, y), self.idx(x, y2)
                self.ch[i], self.ch[j] = self.ch[j], self.ch[i]
                self.cls[i], self.cls[j] = self.cls[j], self.cls[i]
        self.ch = [flip_glyph_v(c) for c in self.ch]

    def flip_horizontal(self) -> None:
        """Mirror left-to-right for ``RL``. Mirroring reverses each row, so
        after flipping glyphs we reverse each text/label run back to reading
        order."""
        for y in range(self.h):
            for x in range(self.w // 2):
                x2 = self.w - 1 - x
                i, j = self.idx(x, y), self.idx(x2, y)
                self.ch[i], self.ch[j] = self.ch[j], self.ch[i]
                self.cls[i], self.cls[j] = self.cls[j], self.cls[i]
        self.ch = [flip_glyph_h(c) for c in self.ch]
        for y in range(self.h):
            x = 0
            while x < self.w:
                cls = self.cls[self.idx(x, y)]
                if cls in (Cls.TEXT, Cls.EDGE_LABEL):
                    start = self.idx(x, y)
                    while x < self.w and self.cls[self.idx(x, y)] == cls:
                        x += 1
                    end = self.idx(x, y)
                    self.ch[start:end] = self.ch[start:end][::-1]
                else:
                    x += 1

    def _row_end(self, y: int) -> int:
        for x in range(self.w - 1, -1, -1):
            c = self.ch[self.idx(x, y)]
            if c != " " and c != CONT:
                return x + 1
        return 0

    def to_lines(self, styles: MermaidStyles) -> tuple[list[Line], list[str]]:
        styled: list[Line] = []
        plain: list[str] = []
        for y in range(self.h):
            last = self._row_end(y)
            spans: list[Span] = []
            plain_row: list[str] = []
            run: list[str] = []
            run_cls = Cls.EMPTY
            for x in range(last):
                i = self.idx(x, y)
                c = self.ch[i]
                if c == CONT:
                    continue
                cls = self.cls[i]
                plain_row.append(c)
                if cls != run_cls and run:
                    spans.append(Span("".join(run), style_for(run_cls, styles)))
                    run = []
                run_cls = cls
                run.append(c)
            if run:
                spans.append(Span("".join(run), style_for(run_cls, styles)))
            styled.append(Line.from_spans(spans))
            plain.append("".join(plain_row).rstrip())
        return styled, plain


def style_for(cls: Cls, styles: MermaidStyles) -> Style:
    return {
        Cls.EMPTY: Style(),
        Cls.BORDER: styles.border,
        Cls.TEXT: styles.node_text,
        Cls.EDGE: styles.edge,
        Cls.EDGE_LABEL: styles.edge_label,
    }[cls]


_MASK_CHARS = {
    U: "│",
    D: "│",
    U | D: "│",
    L: "─",
    R: "─",
    L | R: "─",
    D | R: "┌",
    D | L: "┐",
    U | R: "└",
    U | L: "┘",
    U | D | R: "├",
    U | D | L: "┤",
    D | L | R: "┬",
    U | L | R: "┴",
}


def mask_char(mask: int) -> str:
    if mask == 0:
        return " "
    return _MASK_CHARS.get(mask, "┼")


def dotted_char(c: str) -> str:
    return {"─": "╌", "│": "╎"}.get(c, c)


_THICK = {
    "─": "━", "│": "┃", "┌": "┏", "┐": "┓", "└": "┗", "┘": "┛",
    "├": "┣", "┤": "┫", "┬": "┳", "┴": "┻", "┼": "╋",
}


def thick_char(c: str) -> str:
    return _THICK.get(c, c)


_FLIP_V = {
    "┌": "└", "└": "┌", "┐": "┘", "┘": "┐",
    "┏": "┗", "┗": "┏", "┓": "┛", "┛": "┓",
    "╭": "╰", "╰": "╭", "╮": "╯", "╯": "╮",
    "┬": "┴", "┴": "┬", "┳": "┻", "┻": "┳",
    "▼": "▲", "▲": "▼", "▽": "△", "△": "▽",
}


def flip_glyph_v(c: str) -> str:
    return _FLIP_V.get(c, c)


_FLIP_H = {
    "┌": "┐", "┐": "┌", "└": "┘", "┘": "└",
    "┏": "┓", "┓": "┏", "┗": "┛", "┛": "┗",
    "╭": "╮", "╮": "╭", "╰": "╯", "╯": "╰",
    "├": "┤", "┤": "├", "┣": "┫", "┫": "┣",
    "▶": "◄", "◄": "▶", "▷": "◁", "◁": "▷",
}


def flip_glyph_h(c: str) -> str:
    return _FLIP_H.get(c, c)
