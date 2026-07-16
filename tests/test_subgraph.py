"""Subgraph parsing and titled-frame rendering."""

from mermaid_term._parse_flowchart import parse_graph

from .util import plain


def test_subgraph_renders_titled_frame():
    out = plain(
        "graph TD\n S[Start] --> one\n subgraph one [Group One]\n A --> B\n end\n one --> E[End]"
    )
    assert " Group One " in out, out
    lines = out.splitlines()

    def row(pred) -> int:
        return next(i for i, l in enumerate(lines) if pred(l))

    title = row(lambda l: "Group One" in l)
    a = row(lambda l: "│ A │" in l)
    b = row(lambda l: "│ B │" in l)
    frame_close = max(i for i, l in enumerate(lines) if l.lstrip().startswith("└"))
    assert title < a < b <= frame_close, out
    assert "Start" in out and "End" in out, out
    assert out.count("▼") == 3, out


def test_subgraph_edge_between_groups():
    out = plain(
        "graph TD\n subgraph api [API]\n A1 --> A2\n end\n subgraph db [Storage]\n B1\n end\n api --> db"
    )
    assert " API " in out, out
    assert " Storage " in out, out
    lines = out.splitlines()
    api = next(i for i, l in enumerate(lines) if "API" in l)
    db = next(i for i, l in enumerate(lines) if "Storage" in l)
    assert api < db, f"API frame ranks above Storage:\n{out}"


def test_subgraph_nested_frames():
    out = plain(
        "graph TD\n subgraph outer [Outer]\n subgraph inner [Inner]\n X --> Y\n end\n W --> X\n end\n S --> outer"
    )
    assert " Outer " in out, out
    assert " Inner " in out, out
    lines = out.splitlines()
    outer = next(i for i, l in enumerate(lines) if "Outer" in l)
    inner = next(i for i, l in enumerate(lines) if "Inner" in l)
    assert outer < inner, out


def test_subgraph_cross_member_edge_attaches_to_frame():
    out = plain("graph LR\n S --> A\n subgraph g [Workers]\n A --> B\n end\n B --> T")
    assert " Workers " in out, out
    assert "S" in out and "T" in out, out
    assert out.count("▶") == 3, out
    row = next(l for l in out.splitlines() if "│ A ├" in l)
    assert row.index("S") < row.index("A"), (
        f"A stays outside the group (first definition wins):\n{out}"
    )


def test_subgraph_id_referenced_before_declaration():
    g = parse_graph("graph TD\n X --> two\n subgraph two\n C --> D\n end")
    assert g is not None
    assert len(g.groups) == 1
    out = plain("graph TD\n X --> two\n subgraph two\n C --> D\n end")
    assert " two " in out, f"frame titled by id:\n{out}"
    assert "│ C │" in out, out


def test_subgraph_quoted_and_plain_titles():
    out = plain('graph TD\n subgraph "My Stuff"\n A\n end\n S --> A')
    assert " My Stuff " in out, out
    out2 = plain("graph TD\n subgraph batch jobs\n B\n end\n S --> B")
    assert " batch jobs " in out2, out2
    out3 = plain('graph TD\n subgraph "a &lt;b&gt;"\n C\n end\n S --> C')
    assert "a <b>" in out3 and "&lt;" not in out3, out3


def test_subgraph_empty_is_dropped():
    out = plain("graph TD\n subgraph ghost\n end\n A --> B")
    assert "ghost" not in out, out
    assert "▼" in out, out


def test_subgraph_bt_flips_frame_and_contents():
    out = plain("flowchart BT\n S --> one\n subgraph one [Up]\n A --> B\n end")
    assert " Up " in out, out
    lines = out.splitlines()

    def row(needle: str) -> int:
        return next(i for i, l in enumerate(lines) if needle in l)

    assert row("│ B │") < row("│ A │"), f"contents flip with BT:\n{out}"
    assert row(" Up ") < row("S"), f"frame above source in BT:\n{out}"
    assert "▲" in out, out


def test_subgraph_depth_over_cap_falls_back():
    src = "graph TD\n"
    for i in range(8):
        src += f" subgraph g{i}\n"
    src += " A --> B\n"
    src += " end\n" * 8
    out = plain(src)
    assert "mermaid: graph" in out, out
