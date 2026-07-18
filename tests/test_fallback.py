"""Fallback framing for unsupported, over-cap, and over-wide diagrams."""

from mermaid_term import render

from .util import plain, str_width, styles


def test_unsupported_diagram_uses_fallback_box():
    out = plain("gantt\n title Plan\n section A\n task :a1, 2024-01-01, 30d")
    assert "mermaid: gantt" in out, out
    assert "Plan" in out, out


def test_blank_source_returns_none():
    assert render("   \n  ", styles(), 80) is None


def test_adversarial_chain_falls_back():
    src = "graph TD\n" + "".join(f" N{i} --> N{i + 1}\n" for i in range(10_000))
    out = plain(src)
    assert "mermaid: graph" in out, f"expected fallback:\n{out}"


def test_single_statement_chain_over_cap_falls_back():
    src = "graph LR\n " + "".join(f"N{i}-->" for i in range(10_000)) + "N10000"
    out = plain(src)
    assert "mermaid: graph" in out, "expected fallback"


def test_fallback_styled_and_plain_widths_match():
    art = render("gantt\n title Plan\n a\n", styles(), 120)
    assert art is not None
    assert len(art.styled_lines) == len(art.plain_lines)
    frame_w = str_width(art.plain_lines[0])
    for styled, plain_row in zip(art.styled_lines, art.plain_lines):
        styled_w = sum(str_width(s.content) for s in styled.spans)
        assert styled_w == str_width(plain_row), "styled/plain widths diverge"
        assert str_width(plain_row) == frame_w, "fallback box must be rectangular"


def test_over_wide_diagram_falls_back():
    src = "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]"
    out = render(src, styles(), 40).plain_lines
    joined = "\n".join(out)
    assert "mermaid: flowchart" in joined, (
        f"expected fallback for over-wide diagram:\n{joined}"
    )
    max_w = max((str_width(l) for l in out), default=0)
    fits = render(src, styles(), 120).plain_lines
    assert any("▶" in l for l in fits), "same diagram should render when it fits"
    assert max_w <= len(src), "fallback width bounded by source"


def test_too_wide_fallback_appends_hint_below_box():
    src = "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]"
    out = render(src, styles(), 40).plain_lines
    joined = "\n".join(out)

    assert "mermaid: flowchart" in joined, f"plain header:\n{joined}"
    assert "(too wide)" not in joined, f"header stays plain:\n{joined}"
    assert "flowchart LR" in joined, f"raw source kept:\n{joined}"

    bottom = next(i for i, l in enumerate(out) if "╰" in l)
    note = next(i for i, l in enumerate(out) if "too wide" in l)
    assert note > bottom, f"note must be below the box:\n{joined}"
    assert "wider terminal" in joined, f"note suggests a fix:\n{joined}"

    assert all(str_width(l) <= 40 for l in out), f"fits 40 cols:\n{joined}"


def test_unsupported_diagram_fallback_not_flagged_too_wide():
    out = plain("gantt\n title Plan\n section A\n task :a1, 2024-01-01, 30d")
    assert "mermaid: gantt" in out, out
    assert "too wide" not in out, f"unsupported type is not a width problem:\n{out}"


def test_fitting_diagram_has_no_width_warning():
    out = plain("flowchart LR\n A[Start] --> B[End]")
    assert "too wide" not in out, f"fitting diagram must not warn:\n{out}"
    assert "mermaid: flowchart" not in out, f"should draw art, not box:\n{out}"
    assert "▶" in out, f"should draw edges:\n{out}"


def test_issues_survive_too_wide_fallback():
    src = (
        "flowchart LR\n"
        " A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]\n"
        " D -->\n"
    )
    art = render(src, styles(), 40)
    assert art is not None
    assert "mermaid: flowchart" in "\n".join(art.plain_lines)
    assert [(i.line, i.text) for i in art.issues] == [(3, "D -->")]


def test_over_cap_fallback_reports_no_issues():
    src = "graph TD\n" + "".join(f" N{i} --> N{i + 1}\n" for i in range(10_000))
    art = render(src, styles(), 120)
    assert art is not None
    assert "mermaid: graph" in "\n".join(art.plain_lines)
    assert art.issues == []


def test_fallback_wraps_long_lines_to_max_width():
    out = render(
        "gantt\n title a very long line that should wrap inside the fallback box nicely",
        styles(),
        40,
    ).plain_lines
    assert all(str_width(l) <= 40 for l in out), "\n".join(out)
    for line in out[1:-1]:
        assert line.startswith("│") and line.endswith("│"), (
            f"body rows keep both borders: {line!r}"
        )
    assert "nicely" in "\n".join(out), "\n".join(out)
