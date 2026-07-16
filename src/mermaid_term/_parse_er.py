"""Parser for ``erDiagram`` blocks."""

from __future__ import annotations

from ._labels import clean_label, decode_html_entities, non_empty, statements_of
from ._model import (
    MAX_EDGES,
    MAX_MEMBERS,
    ClassInfo,
    Dir,
    Edge,
    Graph,
    Head,
    LineKind,
    Shape,
)
from ._parse_class import sync_infos


def parse_er(src: str) -> tuple[Graph, list[ClassInfo]] | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or header_tokens[0].lower() != "erdiagram":
        return None

    graph = Graph(dir=Dir.DOWN)
    infos: list[ClassInfo] = []
    cur_entity: int | None = None

    for st in statements[1:]:
        if cur_entity is not None:
            cur_entity = _attribute_line(st, infos, cur_entity)
            continue
        ok, cur_entity = _apply_er_statement(st, graph, infos)
        if not ok:
            return None

    if not graph.nodes:
        return None
    sync_infos(graph, infos)
    return (graph, infos)


def _attribute_line(st: str, infos: list[ClassInfo], cur_entity: int) -> int | None:
    if st == "}":
        return None
    push_er_attribute(infos[cur_entity], st)
    return cur_entity


def _apply_er_statement(
    st: str, graph: Graph, infos: list[ClassInfo]
) -> tuple[bool, int | None]:
    rel = split_er_relationship(st)
    if rel is not None:
        return (_add_er_relationship(rel, graph, infos), None)
    return _entity_decl(st, graph, infos)


def _add_er_relationship(
    rel: tuple[str, str | None], graph: Graph, infos: list[ClassInfo]
) -> bool:
    rel_part, label_part = rel
    tokens = rel_part.split()
    if len(tokens) != 3:
        return False
    lhs, op, rhs = tokens
    parsed_op = parse_er_op(op)
    if parsed_op is None:
        return False
    card_l, card_r, line = parsed_op
    f = er_entity(graph, infos, lhs)
    if f is None:
        return False
    t = er_entity(graph, infos, rhs)
    if t is None:
        return False
    if len(graph.edges) >= MAX_EDGES:
        return False
    rel_label = clean_label(label_part) if label_part is not None else ""
    parts = [p for p in (card_l, rel_label, card_r) if p]
    graph.edges.append(Edge(f, t, non_empty(" ".join(parts)), Head.NONE, Head.NONE, line))
    return True


def _entity_decl(st: str, graph: Graph, infos: list[ClassInfo]) -> tuple[bool, int | None]:
    """Returns (ok, index-of-opened-block); the index is None for a bare declaration."""
    if st.endswith("{"):
        decl, open_ = st[:-1].strip(), True
    else:
        decl, open_ = st, False
    if not decl or len(decl.split()) != 1:
        return (False, None)
    idx = er_entity(graph, infos, decl)
    if idx is None:
        return (False, None)
    return (True, idx if open_ else None)


def er_entity(graph: Graph, infos: list[ClassInfo], token: str) -> int | None:
    open_ = token.find("[")
    if open_ != -1:
        entity_id = token[:open_]
        label = clean_label(token[open_ + 1 :].rstrip("]"))
        if not entity_id or not label:
            return None
        idx = graph.node_label(entity_id, label)
    else:
        idx = graph.node_index(token, None, Shape.RECT)
    if idx is None:
        return None
    sync_infos(graph, infos)
    return idx


def split_er_relationship(st: str) -> tuple[str, str | None] | None:
    if ":" in st:
        rel, label = st.split(":", 1)
        label = label.strip()
    else:
        rel, label = st, None
    has_op = any(parse_er_op(t) is not None for t in rel.split())
    return (rel, label) if has_op else None


def parse_er_op(tok: str) -> tuple[str, str, LineKind] | None:
    if not tok.isascii() or len(tok) != 6:
        return None
    mid = tok[2:4]
    if mid == "--":
        line = LineKind.SOLID
    elif mid == "..":
        line = LineKind.DOTTED
    else:
        return None
    card_l = er_card(tok[:2])
    card_r = er_card(tok[4:6])
    if card_l is None or card_r is None:
        return None
    return (card_l, card_r, line)


_ER_CARDS = {
    "|o": "0..1",
    "o|": "0..1",
    "||": "1",
    "}o": "0..*",
    "o{": "0..*",
    "}|": "1..*",
    "|{": "1..*",
}


def er_card(tok: str) -> str | None:
    return _ER_CARDS.get(tok)


def push_er_attribute(info: ClassInfo, raw: str) -> None:
    parts: list[str] = []
    for tok in raw.split():
        if tok.startswith('"'):
            break
        parts.append(tok)
    if not parts:
        return
    line = decode_html_entities(" ".join(parts))
    if len(info.attrs) < MAX_MEMBERS:
        info.attrs.append(line)
    elif len(info.attrs) == MAX_MEMBERS:
        info.attrs.append("…")
