"""Parser for ``graph`` / ``flowchart`` diagrams, including subgraphs."""

from __future__ import annotations

from ._labels import Statement, clean_label, decode_html_entities, non_empty, statements_of
from ._model import (
    MAX_EDGES,
    MAX_GROUP_DEPTH,
    MAX_GROUPS,
    Edge,
    Graph,
    Group,
    Head,
    LineKind,
    ParseIssue,
    Shape,
    parse_dir,
)

_SKIP_WORDS = frozenset(("classdef", "class", "style", "linkstyle", "click", "direction"))


def parse_graph(src: str) -> Graph | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].text.split()
    if not header_tokens or header_tokens[0].lower() not in ("graph", "flowchart"):
        return None
    dir_token = header_tokens[1] if len(header_tokens) > 1 else "TB"

    graph = Graph(dir=parse_dir(dir_token))
    stack: list[int] = []
    for stmt in statements[1:]:
        if not _apply_graph_statement(stmt, graph, stack):
            return None
    if not graph.nodes:
        return None
    return graph


def _apply_graph_statement(stmt: Statement, graph: Graph, stack: list[int]) -> bool:
    st = stmt.text
    words = st.split()
    first_word = words[0].lower() if words else ""
    if first_word == "subgraph":
        return _open_subgraph(st, graph, stack)
    if first_word == "end":
        if stack:
            stack.pop()
        graph.cur_group = stack[-1] if stack else None
        return True
    if first_word in _SKIP_WORDS:
        return True
    complete = parse_statement(st, graph)
    if graph.over_cap:
        return False
    if not complete:
        graph.issues.append(ParseIssue(stmt.line, st))
    return True


def _open_subgraph(st: str, graph: Graph, stack: list[int]) -> bool:
    if len(graph.groups) >= MAX_GROUPS or len(stack) >= MAX_GROUP_DEPTH:
        return False
    gid, label = parse_subgraph_decl(st[len("subgraph") :].strip())
    graph.groups.append(Group(gid, label, stack[-1] if stack else None))
    stack.append(len(graph.groups) - 1)
    graph.cur_group = stack[-1]
    return True


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


def parse_statement(st: str, graph: Graph) -> bool:
    """Apply one node/link statement; report whether it parsed completely.

    Returns False when the statement could not be fully consumed: no leading
    node group, a link with no target, or leftover non-space input. Partial
    effects (nodes and edges created before the failure) stay in ``graph``.
    Capacity stops (``over_cap``) return True; they are not parse failures.
    """
    parsed = parse_node_group(st, 0, graph)
    if parsed is None:
        return graph.over_cap
    prev, i = parsed

    while True:
        i = skip_spaces(st, i)
        if i >= len(st):
            return True
        link = parse_link(st, i)
        if link is None:
            return False
        i = skip_spaces(st, link[4])
        parsed = parse_node_group(st, i, graph)
        if parsed is None:
            return graph.over_cap
        nxt, i = parsed
        if not _connect(graph, prev, nxt, link):
            return True
        prev = nxt


def _connect(
    graph: Graph,
    prev: list[int],
    nxt: list[int],
    link: tuple[Head, Head, LineKind, str | None, int],
) -> bool:
    left, right, line, label, _ = link
    for f in prev:
        for t in nxt:
            if len(graph.edges) >= MAX_EDGES:
                graph.over_cap = True
                return False
            if left == Head.ARROW and right != Head.ARROW:
                from_, to, head_to, head_from = t, f, Head.ARROW, right
            else:
                from_, to, head_to, head_from = f, t, right, left
            graph.edges.append(Edge(from_, to, label, head_to, head_from, line))
    return True


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


# Two-char openers are matched before their one-char prefixes.
_NODE_SHAPES = (
    ("[[", "]]", Shape.RECT),
    ("[(", ")]", Shape.ROUND),
    ("[", "]", Shape.RECT),
    ("((", "))", Shape.ROUND),
    ("([", "])", Shape.ROUND),
    ("(", ")", Shape.ROUND),
    ("{{", "}}", Shape.DIAMOND),
    ("{", "}", Shape.DIAMOND),
    (">", "]", Shape.RECT),
)


def parse_node(st: str, start: int, graph: Graph) -> tuple[int, int] | None:
    i = skip_spaces(st, start)
    id_start = i
    while i < len(st) and is_id_char(st[i]):
        i += 1
    if i == id_start:
        return None
    node_id = st[id_start:i]

    shape, label, after = Shape.RECT, None, i
    for opener, closer, sh in _NODE_SHAPES:
        if st.startswith(opener, i):
            shape, label, after = read_shape(st, i + len(opener), closer, sh)
            break
    after = skip_class_shorthand(st, after)

    idx = graph.node_index(node_id, label, shape)
    if idx is None:
        return None
    return (idx, after)


def skip_class_shorthand(st: str, i: int) -> int:
    """Consume an optional ``:::className`` suffix; leave it unconsumed if empty."""
    if not st.startswith(":::", i):
        return i
    j = i + 3
    name_start = j
    while j < len(st) and is_id_char(st[j]):
        j += 1
    return j if j > name_start else i


def read_shape(st: str, start: int, closer: str, shape: Shape) -> tuple[Shape, str, int]:
    i = start
    text: list[str] = []
    quoted = st[skip_spaces(st, start) :].startswith('"')
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
    left, i = _left_head(st, i)
    op_start = i
    while i < len(st) and is_link_char(st[i]):
        i += 1
    if i == op_start:
        return None
    op1 = st[op_start:i]
    if left == Head.NONE and op1.startswith("<"):
        left = Head.ARROW
    line = line_kind(op1)
    right, i = _right_head(st, i, op1)

    piped = _piped_label(st, i)
    if piped is not None:
        label, i = piped
        return (left, right, line, label, i)

    if right == Head.NONE:
        inline = _inline_label(st, i, line)
        if inline is not None:
            right, line, label, i = inline
            return (left, right, line, label, i)

    return (left, right, line, None, i)


def _left_head(st: str, i: int) -> tuple[Head, int]:
    if i < len(st) and st[i] in "ox" and i + 1 < len(st) and st[i + 1] in "-.=":
        return (Head.CIRCLE if st[i] == "o" else Head.CROSS, i + 1)
    return (Head.NONE, i)


def _right_head(st: str, i: int, op: str) -> tuple[Head, int]:
    if ">" in op:
        return (Head.ARROW, i)
    trailing = trailing_head(st, i)
    if trailing is not None:
        return trailing
    return (Head.NONE, i)


def _piped_label(st: str, i: int) -> tuple[str | None, int] | None:
    if i >= len(st) or st[i] != "|":
        return None
    i += 1
    l_start = i
    while i < len(st) and st[i] != "|":
        i += 1
    label = clean_label(st[l_start:i])
    if i < len(st) and st[i] == "|":
        i += 1
    return (non_empty(label), i)


def _inline_label(
    st: str, i: int, line: LineKind
) -> tuple[Head, LineKind, str | None, int] | None:
    text_start = skip_spaces(st, i)
    j = text_start
    while j < len(st) and not is_link_char(st[j]):
        j += 1
    if j >= len(st) or j == text_start or st[j] not in "-.=>":
        return None
    text = st[text_start:j]
    op2_start = j
    while j < len(st) and is_link_char(st[j]):
        j += 1
    op2 = st[op2_start:j]
    right, j = _right_head(st, j, op2)
    if line == LineKind.SOLID:
        line = line_kind(op2)
    return (right, line, non_empty(clean_label(text)), j)


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
