"""Flowchart/graph statement parsing: nodes, links, heads, fan-out."""

from mermaid_term._model import Dir, Head
from mermaid_term._parse_flowchart import parse_graph


def test_parses_nodes_edges_and_direction():
    g = parse_graph("flowchart LR\n  A[Start] --> B[End]")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.nodes[0].label == "Start"
    assert g.nodes[1].label == "End"
    assert g.dir == Dir.RIGHT


def test_non_flowchart_returns_none_from_parse():
    assert parse_graph("sequenceDiagram\n  A->>B: hi") is None


def test_inline_label_with_x_or_o_letters():
    g = parse_graph("graph TD\n A -- no exit --> B")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.edges[0].label == "no exit"


def test_inline_o_word_label_still_parses_as_label():
    g = parse_graph("graph TD\n A -- or else --> B")
    assert g is not None
    assert len(g.nodes) == 2
    assert g.edges[0].label == "or else"


def test_reversed_arrow_swaps_edge_direction_parse():
    g = parse_graph("graph TD\n A <-- B")
    assert g is not None
    assert len(g.edges) == 1
    assert g.edges[0].from_ == g.index["B"]
    assert g.edges[0].to == g.index["A"]
    assert g.edges[0].head_to == Head.ARROW
    assert g.edges[0].head_from == Head.NONE


def test_fan_out_creates_cross_product_edges():
    g = parse_graph("graph TD\n A & B --> C & D")
    assert g is not None
    assert len(g.nodes) == 4
    assert len(g.edges) == 4

    def has(f: str, t: str) -> bool:
        return any(e.from_ == g.index[f] and e.to == g.index[t] for e in g.edges)

    assert has("A", "C") and has("A", "D") and has("B", "C") and has("B", "D")


def test_fan_out_in_chain():
    g = parse_graph("graph LR\n A & B --> C --> D")
    assert g is not None
    assert len(g.edges) == 3


def test_fan_out_with_reversed_arrow():
    g = parse_graph("graph TD\n A & B <-- C")
    assert g is not None
    assert len(g.edges) == 2
    assert all(e.from_ == g.index["C"] for e in g.edges)
    assert all(e.head_to == Head.ARROW for e in g.edges)


def test_circle_and_cross_endings_create_no_phantom_nodes():
    g = parse_graph("graph TD\n A --o B\n C --x D")
    assert g is not None
    assert len(g.nodes) == 4, "no phantom o/x nodes"
    assert "o" not in g.index
    assert "x" not in g.index
    assert g.edges[0].head_to == Head.CIRCLE
    assert g.edges[1].head_to == Head.CROSS


def test_left_endings_decorate_without_reversing():
    g = parse_graph("graph TD\n A o-- B\n C x-- D")
    assert g is not None
    assert g.edges[0].from_ == g.index["A"]
    assert g.edges[0].to == g.index["B"]
    assert g.edges[0].head_from == Head.CIRCLE
    assert g.edges[1].head_from == Head.CROSS
    assert g.edges[0].head_to == Head.NONE


def test_reversed_arrow_with_end_marker_swaps_direction():
    g = parse_graph("graph TD\n A <--o B\n C <--x D")
    assert g is not None
    assert g.edges[0].from_ == g.index["B"]
    assert g.edges[0].to == g.index["A"]
    assert g.edges[0].head_to == Head.ARROW
    assert g.edges[0].head_from == Head.CIRCLE
    assert g.edges[1].from_ == g.index["D"]
    assert g.edges[1].to == g.index["C"]
    assert g.edges[1].head_from == Head.CROSS


def test_both_end_markers_parse():
    g = parse_graph("graph TD\n A o--o B\n C x--x D")
    assert g is not None
    assert g.edges[0].head_from == Head.CIRCLE
    assert g.edges[0].head_to == Head.CIRCLE
    assert g.edges[1].head_from == Head.CROSS
    assert g.edges[1].head_to == Head.CROSS
    assert len(g.nodes) == 4


def test_subgraph_groupless_path_unchanged():
    g = parse_graph("graph TD\n A --> B")
    assert g is not None
    assert not g.groups
