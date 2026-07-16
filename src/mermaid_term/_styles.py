"""Minimal terminal styling layer standing in for ratatui's Style/Span/Line."""

from __future__ import annotations

from dataclasses import dataclass, field

ITALIC = 3


@dataclass(frozen=True)
class Style:
    """An SGR parameter sequence; empty means the terminal default."""

    sgr: tuple[int, ...] = ()

    def add_modifier(self, code: int) -> Style:
        return Style(self.sgr + (code,))


@dataclass(frozen=True)
class Span:
    content: str
    style: Style = Style()


@dataclass(frozen=True)
class Line:
    spans: tuple[Span, ...]

    @classmethod
    def from_spans(cls, spans: list[Span]) -> Line:
        return cls(tuple(spans))

    def to_ansi(self) -> str:
        out: list[str] = []
        for span in self.spans:
            if span.style.sgr and span.content:
                params = ";".join(str(p) for p in span.style.sgr)
                out.append(f"\x1b[{params}m{span.content}\x1b[0m")
            else:
                out.append(span.content)
        return "".join(out)


@dataclass(frozen=True)
class MermaidStyles:
    """Theme-derived styles used when painting a diagram."""

    border: Style = field(default_factory=Style)
    node_text: Style = field(default_factory=Style)
    edge: Style = field(default_factory=Style)
    edge_label: Style = field(default_factory=Style)
    title: Style = field(default_factory=Style)

    @classmethod
    def plain(cls) -> MermaidStyles:
        return cls()

    @classmethod
    def default_colors(cls) -> MermaidStyles:
        return cls(
            border=Style((90,)),
            node_text=Style(),
            edge=Style((90,)),
            edge_label=Style((36,)),
            title=Style((1,)),
        )
