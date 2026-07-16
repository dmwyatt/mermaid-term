"""Label wrapping unit tests."""

from mermaid_term._text import LABEL_BREAK_CHARS, MAX_LINES, WRAP_WIDTH, wrap_label


def test_wrap_label_breaks_long_identifier_on_boundary():
    lines = wrap_label("mark_filter_restore_context", WRAP_WIDTH, MAX_LINES)
    # The first line ends on an identifier boundary, not a mid-segment slice.
    assert lines[0].endswith("_"), f"first line must end on a boundary: {lines!r}"
    # Every break (all but the last line) lands on a boundary char.
    for line in lines[:-1]:
        assert line.endswith(tuple(LABEL_BREAK_CHARS)), f"line must break on a boundary: {line!r}"
    # Nothing is lost: the wrapped lines reconstruct the original word.
    assert "".join(lines) == "mark_filter_restore_context"


def test_wrap_label_token_without_break_char_falls_back_per_char():
    token = "a" * 40
    lines = wrap_label(token, WRAP_WIDTH, MAX_LINES)
    # No boundary char -> per-char hard break across multiple lines.
    assert len(lines) >= 2, f"must hard-break: {lines!r}"
    # 40 narrow chars fit in <= MAX_LINES, so nothing is truncated or lost.
    assert "".join(lines) == token


def test_wrap_label_mixed_boundary_then_no_boundary_tail():
    token = "ab_" + "c" * 40
    lines = wrap_label(token, WRAP_WIDTH, MAX_LINES)
    # The boundary is taken first ...
    assert lines[0].endswith("_"), f"first break on boundary: {lines!r}"
    # ... then the long no-boundary tail falls back to a per-char break.
    assert any(
        not any(b in line for b in LABEL_BREAK_CHARS) for line in lines[1:]
    ), f"a later line must be a per-char break: {lines!r}"
    # 43 cols < MAX_LINES*WRAP_WIDTH, so it must not truncate; fully lossless.
    assert "".join(lines) == token


def test_wrap_label_boundary_breaking_still_truncates_at_max_lines():
    ident = "_".join(["segment"] * 20)
    lines = wrap_label(ident, WRAP_WIDTH, MAX_LINES)
    # The identifier far exceeds MAX_LINES*WRAP_WIDTH, so it truncates ...
    assert len(lines) == MAX_LINES
    # ... with the ellipsis still on the final line.
    assert lines[-1].endswith("…"), f"truncation must keep the ellipsis: {lines!r}"
