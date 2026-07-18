"""Sequence diagram parsing and rendering."""

from mermaid_term import render
from mermaid_term._model import ParseIssue
from mermaid_term._text import CONT

from .util import plain, styles


def test_sequence_renders_actors_and_messages():
    out = plain("sequenceDiagram\n Alice->>Bob: Hello Bob\n Bob-->>Alice: Hi Alice")
    assert "Alice" in out, out
    assert "Bob" in out, out
    assert "Hello Bob" in out, out
    assert "▶" in out, f"solid call arrow:\n{out}"
    assert "◄" in out, f"reply arrow:\n{out}"
    assert "╌" in out, f"reply line is dashed:\n{out}"
    assert out.count("│ Alice │") == 2, f"actor boxes repeat at bottom:\n{out}"


def test_sequence_participant_as_label():
    out = plain(
        "sequenceDiagram\n participant C as Client\n participant S as Server\n C->>S: GET /"
    )
    assert "Client" in out, out
    assert "Server" in out, out


def test_sequence_declared_order_wins():
    out = plain("sequenceDiagram\n participant B\n participant A\n A->>B: hi")
    line = out.splitlines()[1]
    assert line.index("B") < line.index("A"), f"B declared first sits left:\n{out}"


def test_sequence_self_message_loops():
    out = plain("sequenceDiagram\n A->>A: think")
    assert "╮" in out, out
    assert "╯" in out, out
    assert "think" in out, out


def test_sequence_cross_head():
    out = plain("sequenceDiagram\n A-x B: lost")
    assert "×" in out, out


def test_sequence_note_over_renders_box():
    out = plain("sequenceDiagram\n A->>B: hi\n Note over A,B: happy path")
    assert "happy path" in out, out


def test_sequence_autonumber_prefixes_messages():
    out = plain("sequenceDiagram\n autonumber\n A->>B: one\n B->>A: two")
    assert "1. one" in out, out
    assert "2. two" in out, out


def test_sequence_loop_renders_divider_and_end():
    out = plain("sequenceDiagram\n A->>B: hi\n loop retry x3\n A->>B: again\n end")
    assert "loop retry x3" in out, out
    assert " end " in out, out


def test_sequence_rect_block_is_invisible():
    out = plain("sequenceDiagram\n rect rgb(0,0,0)\n A->>B: hi\n end")
    assert "rect" not in out, out
    assert " end " not in out, f"rect end is silent:\n{out}"


def test_sequence_box_end_does_not_close_enclosing_block():
    out = plain(
        "sequenceDiagram\n loop l1\n box g\n participant A\n end\n A->>B: hi\n A->>B: bye\n end"
    )
    assert out.count(" end ") == 1, f"box end is silent, loop end renders:\n{out}"
    lines = out.splitlines()

    def row(needle: str) -> int:
        return next(i for i, l in enumerate(lines) if needle in l)

    assert row("loop l1") < row("hi") and row("bye") < row(" end "), (
        f"messages stay inside the loop:\n{out}"
    )
    assert "box" not in out, out


def test_sequence_critical_option_renders_dividers():
    out = plain(
        "sequenceDiagram\n critical connect\n A->>B: try\n option timeout\n A->>A: log\n end"
    )
    assert "critical connect" in out, f"valid critical diagram renders:\n{out}"
    assert "option timeout" in out, out
    assert " end " in out, out


def test_sequence_long_label_widens_gap():
    out = plain("sequenceDiagram\n A->>B: a very long message label that needs room\n B-->>A: ok")
    assert "a very long message label that needs room" in out, out


def test_sequence_unparseable_arrow_falls_back():
    out = plain("sequenceDiagram\n ->>B: orphan")
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_unknown_statement_falls_back():
    out = plain("sequenceDiagram\n A->>B: hi\n garbage statement here")
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_bad_statement_reports_issue_and_falls_back():
    art = render("sequenceDiagram\n A->>B: hi\n garbage statement here\n", styles(), 120)
    assert art is not None
    assert art.fallback is True
    assert art.issues == [ParseIssue(3, "garbage statement here")]


def test_sequence_skip_words_record_no_issues():
    art = render(
        "sequenceDiagram\n title My Title\n autonumber\n A->>B: call\n"
        " activate B\n loop retry\n B-->>A: return\n end\n deactivate B\n",
        styles(),
        120,
    )
    assert art is not None
    assert art.fallback is False
    assert art.issues == []


def test_sequence_over_cap_falls_back_with_no_issues():
    src = "sequenceDiagram\n" + "".join(f" A->>B: msg {i}\n" for i in range(600))
    art = render(src, styles(), 120)
    assert art is not None
    assert art.fallback is True
    assert art.issues == []


def test_sequence_over_wide_falls_back():
    out = "\n".join(
        render(
            "sequenceDiagram\n A->>B: this label is far wider than the available pane width",
            styles(),
            30,
        ).plain_lines
    )
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_over_cap_falls_back():
    src = "sequenceDiagram\n" + "".join(f" A->>B: msg {i}\n" for i in range(600))
    out = plain(src)
    assert "mermaid: sequenceDiagram" in out, out


def test_sequence_activation_markers_are_stripped():
    out = plain("sequenceDiagram\n A->>+B: call\n B-->>-A: return")
    assert "call" in out, out
    assert "return" in out, out
    assert "+" not in out, out


def test_sequence_rows_are_rectangular_and_sentinel_free():
    out = plain("sequenceDiagram\n Alice->>Bob: hi\n Note over Alice: solo note")
    assert CONT not in out, f"sentinel leaked:\n{out}"
    assert "solo note" in out, out
