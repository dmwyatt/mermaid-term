"""Parser for ``stateDiagram`` / ``stateDiagram-v2`` blocks."""

from __future__ import annotations

from ._labels import decode_html_entities, non_empty, statements_of
from ._model import MAX_EDGES, Dir, Edge, Graph, Head, LineKind, Shape, parse_dir


def parse_state(src: str) -> Graph | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or not header_tokens[0].lower().startswith("statediagram"):
        return None

    graph = Graph(dir=Dir.DOWN)
    in_note = False
    for st in statements[1:]:
        if in_note:
            if st.lower() == "end note":
                in_note = False
            continue
        words = st.split()
        first = words[0].lower() if words else ""
        if first == "direction":
            graph.dir = parse_dir(words[1] if len(words) > 1 else "")
        elif first == "note":
            if ":" not in st:
                in_note = True
        elif first == "state":
            if not parse_state_decl(st, graph):
                return None
        elif first in ("classdef", "class", "hide", "scale", "}", "--"):
            pass
        elif "-->" in st:
            if not parse_transition(st, graph):
                return None
        elif not parse_state_desc(st, graph):
            return None
        if graph.over_cap:
            return None

    if not graph.nodes:
        return None
    return graph


def parse_state_decl(st: str, graph: Graph) -> bool:
    rest = st[len("state") :].strip().rstrip("{").strip()
    if not rest:
        return True
    if rest.startswith('"'):
        end = rest.find('"', 1)
        if end == -1:
            return False
        label = rest[1:end]
        after = rest[end + 1 :].strip()
        state_id = after[len("as") :].strip() if after.startswith("as") else label
        return graph.node_label(state_id, decode_html_entities(label)) is not None
    shape = Shape.ROUND
    state_id = rest
    stereotyped = False
    pos = rest.find("<<")
    if pos != -1:
        stereo = rest[pos + 2 :]
        while stereo.endswith(">>"):
            stereo = stereo[:-2]
        stereo = stereo.strip()
        if stereo == "choice":
            shape = Shape.DIAMOND
        state_id = rest[:pos].strip()
        stereotyped = True
    if not state_id or any(c.isspace() for c in state_id):
        return False
    label = state_id if stereotyped else None
    return graph.node_index(state_id, label, shape) is not None


def parse_transition(st: str, graph: Graph) -> bool:
    rest = st
    prev: int | None = None
    while "-->" in rest:
        lhs, rhs = rest.split("-->", 1)
        from_id = lhs.rstrip().rstrip("-").strip()
        if prev is not None:
            if from_id:
                return False
            from_ = prev
        else:
            if not from_id:
                return False
            endpoint = state_endpoint(graph, from_id, True)
            if endpoint is None:
                return False
            from_ = endpoint
        if "-->" in rhs:
            to_part = rhs.split("-->", 1)[0]
            tail = rhs[len(to_part) :]
        else:
            to_part, tail = rhs, ""
        label: str | None = None
        if ":" in to_part:
            to_part, label_part = to_part.split(":", 1)
            label = non_empty(decode_html_entities(label_part.strip()))
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
