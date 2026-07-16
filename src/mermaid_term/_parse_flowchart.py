"""Parser for ``graph`` / ``flowchart`` diagrams, including subgraphs."""

from __future__ import annotations

from ._labels import clean_label, decode_html_entities, non_empty, statements_of
from ._model import (
    MAX_EDGES,
    MAX_GROUP_DEPTH,
    MAX_GROUPS,
    Edge,
    Graph,
    Group,
    Head,
    LineKind,
    Shape,
    parse_dir,
)


def parse_graph(src: str) -> Graph | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens:
        return None
    kind = header_tokens[0].lower()
    if kind not in ("graph", "flowchart"):
        return None
    dir_token = header_tokens[1] if len(header_tokens) > 1 else "TB"

    graph = Graph(dir=parse_dir(dir_token))
    stack: list[int] = []
    for st in statements[1:]:
        words = st.split()
        first_word = words[0].lower() if words else ""
        if first_word == "subgraph":
            if len(graph.groups) >= MAX_GROUPS or len(stack) >= MAX_GROUP_DEPTH:
                return None
            gid, label = parse_subgraph_decl(st[len("subgraph") :].strip())
            graph.groups.append(Group(gid, label, stack[-1] if stack else None))
            stack.append(len(graph.groups) - 1)
            graph.cur_group = stack[-1]
            continue
        if first_word == "end":
            if stack:
                stack.pop()
            graph.cur_group = stack[-1] if stack else None
            continue
        if first_word in ("classdef", "class", "style", "linkstyle", "click", "direction"):
            continue
        parse_statement(st, graph)
        if graph.over_cap:
            return None

    if not graph.nodes:
        return None
    return graph


def parse_subgraph_decl(rest: str) -> tuple[str, str]:
    if rest.startswith('"'):
        end = rest.find('"', 1)
        if end != -1:
            label = rest[1:end]
            return (label, decode_html_entities(label))
    open_ = rest.find("[")
    if open_ != -1:
        gid = rest[:open_].strip()
        label = clean_label(rest[open_ + 1 :].rstrip("]").strip())
        if gid and label:
            return (gid, label)
    return (rest, rest)


def parse_statement(st: str, graph: Graph) -> None:
    parsed = parse_node_group(st, 0, graph)
    if parsed is None:
        return
    prev, i = parsed

    while True:
        i = skip_spaces(st, i)
        if i >= len(st):
            break
        link = parse_link(st, i)
        if link is None:
            break
        left, right, line, label, ni = link
        i = skip_spaces(st, ni)
        parsed = parse_node_group(st, i, graph)
        if parsed is None:
            break
        nxt, i = parsed
        for f in prev:
            for t in nxt:
                if len(graph.edges) >= MAX_EDGES:
                    graph.over_cap = True
                    return
                if left == Head.ARROW and right != Head.ARROW:
                    from_, to, head_to, head_from = t, f, Head.ARROW, right
                else:
                    from_, to, head_to, head_from = f, t, right, left
                graph.edges.append(Edge(from_, to, label, head_to, head_from, line))
        prev = nxt


def parse_node_group(st: str, start: int, graph: Graph) -> tuple[list[int], int] | None:
    parsed = parse_node(st, start, graph)
    if parsed is None:
        return None
    first, i = parsed
    group = [first]
    while True:
        j = skip_spaces(st, i)
        if j >= len(st) or st[j] != "&":
            break
        parsed = parse_node(st, j + 1, graph)
        if parsed is None:
            return None
        nxt, i = parsed
        group.append(nxt)
    return (group, i)


def skip_spaces(st: str, i: int) -> int:
    while i < len(st) and st[i] in " \t":
        i += 1
    return i


def is_id_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def parse_node(st: str, start: int, graph: Graph) -> tuple[int, int] | None:
    i = skip_spaces(st, start)
    id_start = i
    while i < len(st) and is_id_char(st[i]):
        i += 1
    if i == id_start:
        return None
    node_id = st[id_start:i]

    shape: Shape | None = None
    label: str | None = None
    after = i
    c = st[i] if i < len(st) else ""
    c2 = st[i + 1] if i + 1 < len(st) else ""
    if c == "[":
        if c2 == "[":
            shape, label, after = read_shape(st, i + 2, "]]", Shape.RECT)
        elif c2 == "(":
            shape, label, after = read_shape(st, i + 2, ")]", Shape.ROUND)
        else:
            shape, label, after = read_shape(st, i + 1, "]", Shape.RECT)
    elif c == "(":
        if c2 == "(":
            shape, label, after = read_shape(st, i + 2, "))", Shape.ROUND)
        elif c2 == "[":
            shape, label, after = read_shape(st, i + 2, "])", Shape.ROUND)
        else:
            shape, label, after = read_shape(st, i + 1, ")", Shape.ROUND)
    elif c == "{":
        if c2 == "{":
            shape, label, after = read_shape(st, i + 2, "}}", Shape.DIAMOND)
        else:
            shape, label, after = read_shape(st, i + 1, "}", Shape.DIAMOND)
    elif c == ">":
        shape, label, after = read_shape(st, i + 1, "]", Shape.RECT)

    idx = graph.node_index(node_id, label, shape if shape is not None else Shape.RECT)
    if idx is None:
        return None
    return (idx, after)


def read_shape(st: str, start: int, closer: str, shape: Shape) -> tuple[Shape, str, int]:
    i = start
    text: list[str] = []
    j = start
    while j < len(st) and st[j] in " \t":
        j += 1
    quoted = j < len(st) and st[j] == '"'
    in_quotes = False
    while i < len(st):
        c = st[i]
        if quoted and c == '"':
            in_quotes = not in_quotes
            text.append(c)
            i += 1
            continue
        if not in_quotes and st.startswith(closer, i):
            return (shape, clean_label("".join(text)), i + len(closer))
        text.append(c)
        i += 1
    return (shape, clean_label("".join(text)), len(st))


def is_link_char(c: str) -> bool:
    return c in "-.=<>"


def parse_link(
    st: str, start: int
) -> tuple[Head, Head, LineKind, str | None, int] | None:
    i = skip_spaces(st, start)
    left = Head.NONE
    if (
        i < len(st)
        and st[i] in "ox"
        and i + 1 < len(st)
        and st[i + 1] in "-.="
    ):
        left = Head.CIRCLE if st[i] == "o" else Head.CROSS
        i += 1
    op_start = i
    while i < len(st) and st[i] in "-.=<>":
        i += 1
    if i == op_start:
        return None
    op1 = st[op_start:i]
    if left == Head.NONE and op1.startswith("<"):
        left = Head.ARROW
    line = line_kind(op1)
    right = Head.ARROW if ">" in op1 else Head.NONE
    if right == Head.NONE:
        trailing = trailing_head(st, i)
        if trailing is not None:
            right, i = trailing

    if i < len(st) and st[i] == "|":
        i += 1
        l_start = i
        while i < len(st) and st[i] != "|":
            i += 1
        label = clean_label(st[l_start:i])
        if i < len(st) and st[i] == "|":
            i += 1
        return (left, right, line, non_empty(label), i)

    if right == Head.NONE:
        text_start = skip_spaces(st, i)
        j = text_start
        while j < len(st) and not is_link_char(st[j]):
            j += 1
        if j < len(st) and j > text_start and st[j] in "-.=>":
            text = st[text_start:j]
            op2_start = j
            while j < len(st) and is_link_char(st[j]):
                j += 1
            op2 = st[op2_start:j]
            if ">" in op2:
                right = Head.ARROW
            else:
                trailing = trailing_head(st, j)
                if trailing is not None:
                    right, j = trailing
            if line == LineKind.SOLID:
                line = line_kind(op2)
            return (left, right, line, non_empty(clean_label(text)), j)

    return (left, right, line, None, i)


def line_kind(op: str) -> LineKind:
    if "=" in op:
        return LineKind.THICK
    if "." in op:
        return LineKind.DOTTED
    return LineKind.SOLID


def trailing_head(st: str, i: int) -> tuple[Head, int] | None:
    c = st[i] if i < len(st) else ""
    if c == "o":
        head = Head.CIRCLE
    elif c == "x":
        head = Head.CROSS
    else:
        return None
    nxt = st[i + 1] if i + 1 < len(st) else None
    if nxt is None or nxt in " \t|&;":
        return (head, i + 1)
    return None
