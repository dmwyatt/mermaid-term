"""Parser for ``stateDiagram`` / ``stateDiagram-v2`` blocks."""

from __future__ import annotations

from ._labels import decode_html_entities, non_empty, statements_of
from ._model import MAX_EDGES, Dir, Edge, Graph, Head, LineKind, Shape, parse_dir

_SKIP_WORDS = frozenset(("classdef", "class", "hide", "scale", "}", "--"))


def parse_state(src: str) -> Graph | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or not header_tokens[0].lower().startswith("statediagram"):
        return None

    graph = Graph(dir=Dir.DOWN)
    if not _parse_state_statements(statements[1:], graph):
        return None
    if not graph.nodes:
        return None
    return graph


def _parse_state_statements(statements: list[str], graph: Graph) -> bool:
    in_note = False
    for st in statements:
        if in_note:
            in_note = st.lower() != "end note"
            continue
        words = st.split()
        first = words[0].lower() if words else ""
        if first == "note":
            in_note = ":" not in st
            continue
        if not _apply_state_statement(st, first, words, graph) or graph.over_cap:
            return False
    return True


def _apply_state_statement(st: str, first: str, words: list[str], graph: Graph) -> bool:
    if first == "direction":
        graph.dir = parse_dir(words[1] if len(words) > 1 else "")
        return True
    if first == "state":
        return parse_state_decl(st, graph)
    if first in _SKIP_WORDS:
        return True
    if "-->" in st:
        return parse_transition(st, graph)
    return parse_state_desc(st, graph)


def parse_state_decl(st: str, graph: Graph) -> bool:
    rest = st[len("state") :].strip().rstrip("{").strip()
    if not rest:
        return True
    if rest.startswith('"'):
        return _quoted_state_decl(rest, graph)
    shape, state_id, stereotyped = _stereotyped_state(rest)
    if not state_id or any(c.isspace() for c in state_id):
        return False
    label = state_id if stereotyped else None
    return graph.node_index(state_id, label, shape) is not None


def _quoted_state_decl(rest: str, graph: Graph) -> bool:
    end = rest.find('"', 1)
    if end == -1:
        return False
    label = rest[1:end]
    after = rest[end + 1 :].strip()
    state_id = after[len("as") :].strip() if after.startswith("as") else label
    return graph.node_label(state_id, decode_html_entities(label)) is not None


def _stereotyped_state(rest: str) -> tuple[Shape, str, bool]:
    pos = rest.find("<<")
    if pos == -1:
        return (Shape.ROUND, rest, False)
    stereo = rest[pos + 2 :]
    while stereo.endswith(">>"):
        stereo = stereo[:-2]
    shape = Shape.DIAMOND if stereo.strip() == "choice" else Shape.ROUND
    return (shape, rest[:pos].strip(), True)


def parse_transition(st: str, graph: Graph) -> bool:
    rest = st
    prev: int | None = None
    while "-->" in rest:
        lhs, rhs = rest.split("-->", 1)
        from_ = _transition_source(lhs, prev, graph)
        if from_ is None:
            return False
        to_part, tail = _split_next_hop(rhs)
        to_part, label = _transition_label(to_part)
        to_id = to_part.lstrip().lstrip(">").rstrip().rstrip("-").strip()
        if not to_id:
            return False
        to = state_endpoint(graph, to_id, False)
        if to is None:
            return False
        if len(graph.edges) >= MAX_EDGES:
            graph.over_cap = True
            return True
        graph.edges.append(Edge(from_, to, label, Head.ARROW, Head.NONE, LineKind.SOLID))
        prev = to
        rest = tail
    return True


def _transition_source(lhs: str, prev: int | None, graph: Graph) -> int | None:
    from_id = lhs.rstrip().rstrip("-").strip()
    if prev is not None:
        return None if from_id else prev
    if not from_id:
        return None
    return state_endpoint(graph, from_id, True)


def _split_next_hop(rhs: str) -> tuple[str, str]:
    if "-->" in rhs:
        to_part = rhs.split("-->", 1)[0]
        return (to_part, rhs[len(to_part) :])
    return (rhs, "")


def _transition_label(to_part: str) -> tuple[str, str | None]:
    if ":" in to_part:
        to_part, label_part = to_part.split(":", 1)
        return (to_part, non_empty(decode_html_entities(label_part.strip())))
    return (to_part, None)


def state_endpoint(graph: Graph, state_id: str, is_source: bool) -> int | None:
    if state_id == "[*]":
        key = "[*]start" if is_source else "[*]end"
        return graph.node_index(key, "●", Shape.ROUND)
    return graph.node_index(state_id, None, Shape.ROUND)


def parse_state_desc(st: str, graph: Graph) -> bool:
    if ":" in st:
        state_id, desc = st.split(":", 1)
        state_id = state_id.strip()
        desc = desc.strip()
        if not state_id or any(c.isspace() for c in state_id) or not desc:
            return False
        return graph.node_label(state_id, decode_html_entities(desc)) is not None
    if not any(c.isspace() for c in st):
        return graph.node_index(st, None, Shape.ROUND) is not None
    return False
