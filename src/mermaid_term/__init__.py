"""Render Mermaid diagrams as Unicode box-drawing art in the terminal.

Python port of the terminal Mermaid renderer from xai-org/grok-build
(crates/codegen/xai-grok-markdown/src/mermaid.rs). Supports flowchart/graph,
stateDiagram, classDiagram, erDiagram, and sequenceDiagram blocks; anything
else renders as the raw source in a framed box.
"""

from ._render import MermaidArt, render
from ._styles import Line, MermaidStyles, Span, Style

__all__ = ["MermaidArt", "MermaidStyles", "Line", "Span", "Style", "render"]
