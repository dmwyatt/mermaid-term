"""Display-width measurement, label wrapping, and fitting.

Ported from the Rust renderer's text helpers; ``wcwidth`` stands in for the
``unicode-width`` crate.
"""

from __future__ import annotations

from wcwidth import wcwidth

MAX_LABEL = 28
PAD = 1
GAP_X = 3
GAP_Y = 2
# Node labels wrap to at most this many display columns per line, and at most
# this many lines (overflow is truncated with an ellipsis).
WRAP_WIDTH = 24
MAX_LINES = 4
# Identifier-boundary characters preferred as break points when a single word
# is too wide to fit, so it is not sliced mid-segment.
LABEL_BREAK_CHARS = ("_", "-", ".", "/")
# Sentinel marking the trailing column of a wide glyph (never emitted).
CONT = "\x00"


def char_width(c: str) -> int:
    w = wcwidth(c)
    return w if w > 0 else 0


def str_width(s: str) -> int:
    return sum(char_width(c) for c in s)


def _rfind_break(s: str) -> int:
    return max(s.rfind(c) for c in LABEL_BREAK_CHARS)


def _hard_break_word(word: str, width: int, lines: list[str]) -> tuple[str, int]:
    """Split an over-wide word onto ``lines``, returning the carry chunk."""
    chunk = ""
    chunk_w = 0
    for ch in word:
        cw = max(char_width(ch), 1)
        if chunk_w + cw > width and chunk:
            # Prefer breaking after the last identifier boundary so a long
            # token is not sliced mid-segment; fall back to a per-char break.
            p = _rfind_break(chunk)
            carry = chunk[p + 1 :] if p >= 0 else ""
            lines.append(chunk[: p + 1] if p >= 0 else chunk)
            chunk = carry
            chunk_w = sum(max(char_width(c), 1) for c in carry)
        chunk += ch
        chunk_w += cw
    return chunk, chunk_w


def _truncate_last_line(lines: list[str], width: int) -> None:
    target = max(width - 1, 1)
    s = ""
    sw = 0
    for ch in lines[-1]:
        cw = max(char_width(ch), 1)
        if sw + cw > target:
            break
        s += ch
        sw += cw
    lines[-1] = s + "…"


def wrap_label(label: str, width: int, max_lines: int) -> list[str]:
    width = max(width, 1)
    lines: list[str] = []
    cur = ""
    cur_w = 0
    for word in label.split():
        ww = str_width(word)
        if ww > width:
            if cur:
                lines.append(cur)
            cur, cur_w = _hard_break_word(word, width, lines)
        elif not cur:
            cur = word
            cur_w = ww
        elif cur_w + 1 + ww <= width:
            cur += " " + word
            cur_w += 1 + ww
        else:
            lines.append(cur)
            cur = word
            cur_w = ww
    if cur:
        lines.append(cur)
    if not lines:
        lines.append("")
    if len(lines) > max_lines:
        del lines[max_lines:]
        _truncate_last_line(lines, width)
    return lines


def fit_label(label: str, inner: int) -> str:
    if str_width(label) <= inner:
        return label
    out = ""
    used = 0
    for c in label:
        cw = char_width(c)
        if used + cw + 1 > inner:
            break
        out += c
        used += cw
    return out + "…"


def chunk_line(line: str, limit: int | None) -> list[str]:
    if limit is None:
        return [line]
    if str_width(line) <= limit:
        return [line]
    out: list[str] = []
    cur = ""
    cur_w = 0
    for c in line:
        cw = max(char_width(c), 1)
        if cur_w + cw > limit and cur:
            out.append(cur)
            cur = ""
            cur_w = 0
        cur += c
        cur_w += cw
    if cur:
        out.append(cur)
    return out


def wrap_words(text: str, limit: int | None) -> list[str]:
    if limit is None:
        return [text]
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):
        if not word:
            continue
        if not cur:
            cur = word
        elif str_width(cur) + 1 + str_width(word) <= limit:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return [chunk for line in lines for chunk in chunk_line(line, limit)]
