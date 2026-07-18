"""State diagram parsing and rendering."""

from mermaid_term import render
from mermaid_term._model import MAX_NODES, ParseIssue, Shape
from mermaid_term._parse_state import parse_state

from .util import plain, styles


def test_state_diagram_renders_states_and_transitions():
    out = plain("stateDiagram-v2\n [*] --> Idle\n Idle --> Running: start\n Running --> [*]")
    assert "Idle" in out, out
    assert "Running" in out, out
    assert "start" in out, out
    assert "▼" in out, out
    assert out.count("●") == 2, f"distinct start and end markers:\n{out}"
    lines = out.splitlines()
    first_dot = next(i for i, l in enumerate(lines) if "●" in l)
    last_dot = max(i for i, l in enumerate(lines) if "●" in l)
    idle = next(i for i, l in enumerate(lines) if "Idle" in l)
    assert first_dot < idle < last_dot, out


def test_state_v1_header_renders():
    out = plain("stateDiagram\n A --> B")
    assert "▼" in out, out


def test_state_boxes_are_rounded():
    out = plain("stateDiagram-v2\n A --> B")
    assert "╭" in out, out
    assert "┌" not in out, f"states render rounded:\n{out}"


def test_state_alias_label_renders():
    out = plain('stateDiagram-v2\n state "Waiting for input" as W\n W --> Done')
    assert "Waiting for input" in out, out


def test_state_choice_parses_as_diamond():
    g = parse_state(
        "stateDiagram-v2\n state c <<choice>>\n A --> c\n c --> B: yes\n c --> D: no", []
    )
    assert g is not None
    assert g.nodes[g.index["c"]].shape == Shape.DIAMOND
    assert len(g.edges) == 3


def test_state_description_sets_label():
    out = plain("stateDiagram-v2\n s2 : waits patiently\n A --> s2")
    assert "waits patiently" in out, out


def test_state_direction_lr():
    out = plain("stateDiagram-v2\n direction LR\n A --> B --> C")
    td = plain("stateDiagram-v2\n A --> B")
    assert len(out.splitlines()) <= len(td.splitlines()) + 2, f"LR stays flat:\n{out}"
    line = next(l for l in out.splitlines() if "A" in l)
    assert "B" in line, f"A and B share a row in LR:\n{out}"


def test_state_composite_contents_render_flat():
    out = plain("stateDiagram-v2\n state Active {\n A --> B\n }\n Active --> Done")
    assert "Active" in out, out
    assert "A" in out and "B" in out, out
    assert "Done" in out, out


def test_state_notes_are_skipped():
    out = plain(
        "stateDiagram-v2\n A --> B\n note right of A: inline note\n note left of B\n block text\n end note"
    )
    assert "▼" in out, out
    assert "note" not in out, out
    assert "block text" not in out, out


def test_state_back_transition_uses_lane():
    out = plain("stateDiagram-v2\n A --> B\n B --> C\n C --> B: retry")
    assert "◄" in out, out
    assert "retry" in out, out


def test_state_unknown_statement_falls_back():
    out = plain("stateDiagram-v2\n A --> B\n some garbage line")
    assert "mermaid: stateDiagram-v2" in out, out


def test_state_bad_statement_reports_issue_and_falls_back():
    art = render("stateDiagram-v2\n A --> B\n some garbage line\n", styles(), 120)
    assert art is not None
    assert art.fallback is True
    assert art.rejected is True
    assert art.issues == [ParseIssue(3, "some garbage line")]


def test_state_skip_words_and_note_block_record_no_issues():
    art = render(
        "stateDiagram-v2\n A --> B\n note right of A: inline note\n"
        " note left of B\n block text\n end note\n hide empty description\n scale 2\n",
        styles(),
        120,
    )
    assert art is not None
    assert art.fallback is False
    assert art.issues == []


def test_state_over_cap_falls_back():
    src = "stateDiagram-v2\n" + "".join(f" S{i} --> S{i + 1}\n" for i in range(600))
    out = plain(src)
    assert "mermaid: stateDiagram-v2" in out, out


def test_state_over_cap_reports_no_issues():
    src = "stateDiagram-v2\n" + "".join(f" S{i} --> S{i + 1}\n" for i in range(600))
    art = render(src, styles(), 120)
    assert art is not None
    assert art.fallback is True
    assert art.issues == []


def test_state_exactly_at_node_cap_renders_normally():
    src = "stateDiagram-v2\n" + "".join(f" S{i} --> S{i + 1}\n" for i in range(MAX_NODES - 1))
    art = render(src, styles(), 200)
    assert art is not None
    assert art.fallback is False, "a diagram that exactly fills the node cap is still valid"
    assert art.issues == []


def test_state_extra_dash_arrow_tolerated():
    g = parse_state("stateDiagram-v2\n A ---> B", [])
    assert g is not None
    assert len(g.edges) == 1
    assert len(g.nodes) == 2


def test_state_description_preserves_choice_shape():
    g = parse_state(
        "stateDiagram-v2\n state c <<choice>>\n c : pick a path\n A --> c\n c --> B", []
    )
    assert g is not None
    assert g.nodes[g.index["c"]].shape == Shape.DIAMOND
    assert g.nodes[g.index["c"]].label == "pick a path"
    g2 = parse_state('stateDiagram-v2\n state c <<choice>>\n state "pick" as c\n A --> c', [])
    assert g2 is not None
    assert g2.nodes[g2.index["c"]].shape == Shape.DIAMOND
    assert g2.nodes[g2.index["c"]].label == "pick"


def test_state_chained_transitions_parse_as_separate_edges():
    g = parse_state("stateDiagram-v2\n A --> B --> C", [])
    assert g is not None
    assert len(g.nodes) == 3, "three distinct states"
    assert len(g.edges) == 2, "two edges"
    assert "B" in g.index
    assert "C" in g.index
    assert not any("-->" in n.label for n in g.nodes), "no node swallows the arrow"
    assert any(e.from_ == g.index["A"] and e.to == g.index["B"] for e in g.edges)
    assert any(e.from_ == g.index["B"] and e.to == g.index["C"] for e in g.edges)


def test_state_chain_with_markers_and_label():
    g = parse_state("stateDiagram-v2\n [*] --> A --> B: done", [])
    assert g is not None
    assert len(g.edges) == 2
    assert any(e.label == "done" for e in g.edges)
    out = plain("stateDiagram-v2\n [*] --> A --> B: done")
    assert "●" in out, out
    assert "done" in out, out


def test_state_dangling_chain_falls_back():
    out = plain("stateDiagram-v2\n A --> B -->")
    assert "mermaid: stateDiagram-v2" in out, out
