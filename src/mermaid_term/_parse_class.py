"""Parser for ``classDiagram`` blocks."""

from __future__ import annotations

from ._labels import (
    decode_html_entities,
    display_generics,
    non_empty,
    statements_of,
)
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
    parse_dir,
)
from ._parse_flowchart import is_id_char

CLASS_OPS: list[tuple[str, Head, Head, LineKind]] = [
    ("<|--", Head.TRIANGLE, Head.NONE, LineKind.SOLID),
    ("--|>", Head.NONE, Head.TRIANGLE, LineKind.SOLID),
    ("<|..", Head.TRIANGLE, Head.NONE, LineKind.DOTTED),
    ("..|>", Head.NONE, Head.TRIANGLE, LineKind.DOTTED),
    ("*--", Head.DIAMOND_FILL, Head.NONE, LineKind.SOLID),
    ("--*", Head.NONE, Head.DIAMOND_FILL, LineKind.SOLID),
    ("o--", Head.DIAMOND_OPEN, Head.NONE, LineKind.SOLID),
    ("--o", Head.NONE, Head.DIAMOND_OPEN, LineKind.SOLID),
    ("<--", Head.ARROW, Head.NONE, LineKind.SOLID),
    ("-->", Head.NONE, Head.ARROW, LineKind.SOLID),
    ("<..", Head.ARROW, Head.NONE, LineKind.DOTTED),
    ("..>", Head.NONE, Head.ARROW, LineKind.DOTTED),
    ("--", Head.NONE, Head.NONE, LineKind.SOLID),
    ("..", Head.NONE, Head.NONE, LineKind.DOTTED),
]


def parse_class(src: str) -> tuple[Graph, list[ClassInfo]] | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or not header_tokens[0].lower().startswith("classdiagram"):
        return None

    graph = Graph(dir=Dir.DOWN)
    infos: list[ClassInfo] = []
    cur_class: int | None = None

    for st in statements[1:]:
        if cur_class is not None:
            if st == "}":
                cur_class = None
            else:
                push_member(infos[cur_class], st)
            continue
        words = st.split()
        first = words[0].lower() if words else ""
        if first == "direction":
            graph.dir = parse_dir(words[1] if len(words) > 1 else "")
            continue
        if first in (
            "note", "callback", "click", "link", "style", "cssclass",
            "classdef", "namespace", "}",
        ):
            continue
        if first == "class":
            rest = st[len("class") :].strip()
            if rest.endswith("{"):
                name, open_ = rest[:-1].strip(), True
            else:
                name, open_ = rest, False
            if not name or any(c.isspace() for c in name):
                return None
            idx = graph.node_index(name, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            if open_:
                cur_class = idx
            continue
        if st.startswith("<<"):
            end = st.find(">>", 2)
            if end == -1:
                return None
            ann = st[2:end]
            name = st[end + 2 :].strip()
            if not name or any(c.isspace() for c in name):
                return None
            idx = graph.node_index(name, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            infos[idx].annotation = ann.strip()
            continue
        relation = parse_class_relation(st)
        if relation is not None:
            from_id, to_id, head_from, head_to, line, label = relation
            f = graph.node_index(from_id, None, Shape.RECT)
            if f is None:
                return None
            sync_infos(graph, infos)
            t = graph.node_index(to_id, None, Shape.RECT)
            if t is None:
                return None
            sync_infos(graph, infos)
            if len(graph.edges) >= MAX_EDGES:
                return None
            graph.edges.append(Edge(f, t, label, head_to, head_from, line))
            continue
        if ":" in st:
            class_id, member = st.split(":", 1)
            class_id = class_id.strip()
            member = member.strip()
            if not class_id or any(c.isspace() for c in class_id) or not member:
                return None
            idx = graph.node_index(class_id, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            push_member(infos[idx], member)
            continue
        return None

    if not graph.nodes:
        return None
    sync_infos(graph, infos)
    return (graph, infos)


def sync_infos(graph: Graph, infos: list[ClassInfo]) -> None:
    while len(infos) < len(graph.nodes):
        infos.append(ClassInfo())


def push_member(info: ClassInfo, raw: str) -> None:
    if raw.startswith("<<"):
        end = raw.find(">>", 2)
        if end != -1:
            info.annotation = raw[2:end].strip()
        return
    member = decode_html_entities(display_generics(raw.strip()))
    target = info.methods if "(" in member else info.attrs
    if len(target) < MAX_MEMBERS:
        target.append(member)
    elif len(target) == MAX_MEMBERS:
        target.append("…")


def parse_class_relation(
    st: str,
) -> tuple[str, str, Head, Head, LineKind, str | None] | None:
    found: tuple[int, str, Head, Head, LineKind] | None = None
    for pos in range(len(st)):
        for op, hf, ht, line in CLASS_OPS:
            if st.startswith(op, pos):
                if op.startswith("o") and pos > 0 and is_id_char(st[pos - 1]):
                    continue
                if (
                    op.endswith("o")
                    and pos + len(op) < len(st)
                    and is_id_char(st[pos + len(op)])
                ):
                    continue
                found = (pos, op, hf, ht, line)
                break
        if found is not None:
            break
    if found is None:
        return None
    pos, op, head_from, head_to, line = found
    lhs = st[:pos].strip()
    rhs = st[pos + len(op) :].strip()

    lhs, card_from = strip_cardinality_suffix(lhs)
    rhs, card_to = strip_cardinality_prefix(rhs)
    rel_label: str | None = None
    if ":" in rhs:
        to_id, label_part = rhs.split(":", 1)
        to_id = to_id.strip()
        rel_label = non_empty(decode_html_entities(label_part.strip()))
    else:
        to_id = rhs.strip()
    if (
        not lhs
        or not to_id
        or any(c.isspace() for c in lhs)
        or any(c.isspace() for c in to_id)
    ):
        return None
    parts = [p for p in (card_from, rel_label or "", card_to) if p]
    label = non_empty(" ".join(parts))
    return (lhs, to_id, head_from, head_to, line, label)


def strip_cardinality_suffix(s: str) -> tuple[str, str]:
    t = s.rstrip()
    if t.endswith('"'):
        rest = t[:-1]
        q = rest.rfind('"')
        if q != -1:
            return (rest[:q].rstrip(), rest[q + 1 :])
    return (t, "")


def strip_cardinality_prefix(s: str) -> tuple[str, str]:
    t = s.lstrip()
    if t.startswith('"'):
        rest = t[1:]
        q = rest.find('"')
        if q != -1:
            return (rest[q + 1 :].lstrip(), rest[:q])
    return (t, "")
