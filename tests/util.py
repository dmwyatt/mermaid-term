"""Shared helpers mirroring the upstream Rust test harness."""

from mermaid_term import MermaidStyles, render
from mermaid_term._text import str_width

__all__ = ["styles", "plain", "str_width"]


def styles() -> MermaidStyles:
    return MermaidStyles.plain()


def plain(src: str) -> str:
    art = render(src, styles(), 120)
    assert art is not None
    return "\n".join(art.plain_lines)
