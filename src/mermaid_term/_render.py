"""Top-level rendering: dispatch to a diagram layout or the framed fallback."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canvas import Canvas
from ._groups import grouped_canvas
from ._labels import display_generics
from ._layout import PLAIN, NodeExtra, OversizeError, layout_canvas
from ._model import ClassInfo, Dir, Graph, ParseIssue
from ._parse_class import parse_class
from ._parse_er import parse_er
from ._parse_flowchart import parse_graph
from ._parse_sequence import parse_sequence
from ._parse_state import parse_state
from ._sequence_layout import layout_sequence
from ._styles import ITALIC, Line, MermaidStyles, Span
from ._text import chunk_line, str_width, wrap_words


@dataclass
class MermaidArt:
    """Rendered diagram: styled lines for ANSI output and plain text lines.

    ``issues`` lists source statements the parser skipped, by 1-based line
    number within the mermaid block. ``fallback`` is ``True`` when the
    diagram could not be laid out and the raw source is framed instead.
    """

    styled_lines: list[Line]
    plain_lines: list[str]
    issues: list[ParseIssue] = field(default_factory=list)
    fallback: bool = False


TOO_WIDE_HINT = (
    "This diagram is too wide to render at this width; "
    "try a wider terminal or --width 0."
)


def render(src: str, styles: MermaidStyles | None = None, max_width: int | None = None) -> MermaidArt | None:
    """Render a mermaid source block, or ``None`` for blank input."""
    if not src.strip():
        return None
    if styles is None:
        styles = MermaidStyles.plain()

    issues: list[ParseIssue] = []
    try:
        canvas = _diagram_canvas(src, max_width, issues)
    except OversizeError as oversize:
        return _fallback(src, styles, max_width, oversize.kind == "width", issues)
    if canvas is None:
        return _fallback(src, styles, max_width, False, issues)
    styled_lines, plain_lines = canvas.to_lines(styles)
    return MermaidArt(styled_lines, plain_lines, issues)


def _diagram_canvas(
    src: str, max_width: int | None, issues: list[ParseIssue]
) -> Canvas | None:
    graph = parse_graph(src)
    if graph is not None:
        issues.extend(graph.issues)
        if graph.groups:
            canvas = grouped_canvas(graph, max_width)
        else:
            canvas = _flowchart_canvas(graph, max_width)
        return _oriented(canvas, graph.dir)

    graph = parse_state(src, issues)
    if graph is not None:
        return _oriented(_flowchart_canvas(graph, max_width), graph.dir)

    for parser in (parse_class, parse_er):
        parsed = parser(src, issues)
        if parsed is not None:
            graph, infos = parsed
            return _oriented(_class_canvas(graph, infos, max_width), graph.dir)

    seq = parse_sequence(src)
    if seq is not None:
        return layout_sequence(seq, max_width)
    return None


def _oriented(canvas: Canvas, dir: Dir) -> Canvas:
    if dir == Dir.UP:
        canvas.flip_vertical()
    elif dir == Dir.LEFT:
        canvas.flip_horizontal()
    return canvas


def _flowchart_canvas(graph: Graph, max_width: int | None) -> Canvas:
    extras = [PLAIN] * len(graph.nodes)
    return layout_canvas(graph, extras, max_width)


def _class_canvas(graph: Graph, infos: list[ClassInfo], max_width: int | None) -> Canvas:
    extras: list[NodeExtra] = []
    for node, info in zip(graph.nodes, infos):
        title = []
        if info.annotation is not None:
            title.append(f"«{info.annotation}»")
        title.append(display_generics(node.label))
        extras.append(NodeExtra(compartments=[title, list(info.attrs), list(info.methods)]))
    return layout_canvas(graph, extras, max_width)


def _fallback(
    src: str,
    styles: MermaidStyles,
    max_width: int | None,
    too_wide: bool,
    issues: list[ParseIssue],
) -> MermaidArt:
    title = f" mermaid: {_first_word(src)} "
    limit = max(max_width - 4, 8) if max_width is not None else None
    body = _fallback_body(src, limit)
    art = _framed_source(title, body, styles)
    art.issues = issues
    art.fallback = True
    if too_wide:
        _append_hint(art, styles, max_width)
    return art


def _fallback_body(src: str, limit: int | None) -> list[str]:
    raw_lines = [l.rstrip() for l in src.splitlines()]
    while raw_lines and not raw_lines[0]:
        raw_lines.pop(0)
    return [chunk for line in raw_lines for chunk in chunk_line(line, limit)]


def _framed_source(title: str, body: list[str], styles: MermaidStyles) -> MermaidArt:
    content_w = max([str_width(l) for l in body] + [str_width(title)], default=0)
    inner = content_w + 2

    styled: list[Line] = []
    plain: list[str] = []

    dashes = "─" * max(inner - str_width(title), 0)
    styled.append(
        Line.from_spans(
            [
                Span("╭", styles.border),
                Span(title, styles.title),
                Span(f"{dashes}╮", styles.border),
            ]
        )
    )
    plain.append(f"╭{title}{dashes}╮")

    for line in body:
        pad = " " * max(content_w - str_width(line), 0)
        styled.append(
            Line.from_spans(
                [
                    Span("│ ", styles.border),
                    Span(line, styles.node_text),
                    Span(f"{pad} │", styles.border),
                ]
            )
        )
        plain.append(f"│ {line}{pad} │")

    bottom = f"╰{'─' * inner}╯"
    styled.append(Line.from_spans([Span(bottom, styles.border)]))
    plain.append(bottom)
    return MermaidArt(styled, plain)


def _append_hint(art: MermaidArt, styles: MermaidStyles, max_width: int | None) -> None:
    hint_style = styles.border.add_modifier(ITALIC)
    for chunk in wrap_words(TOO_WIDE_HINT, max_width):
        art.styled_lines.append(Line.from_spans([Span(chunk, hint_style)]))
        art.plain_lines.append(chunk)


def _first_word(src: str) -> str:
    words = src.split()
    return words[0] if words else "diagram"
