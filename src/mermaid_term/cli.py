"""Command-line interface: render mermaid source (or markdown fences) to a terminal."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import sys
from importlib.metadata import version

from ._render import MermaidArt, render
from ._styles import MermaidStyles


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _configure_stdio()

    try:
        text = _read_input(args.file)
    except OSError as err:
        print(f"mermaid-term: {err}", file=sys.stderr)
        return 1

    if args.markdown:
        sources = extract_mermaid_blocks(text)
        if not sources:
            print("mermaid-term: no mermaid blocks found in input", file=sys.stderr)
            return 1
    else:
        sources = [text]

    color = _resolve_color(args.color)
    width = _resolve_width(args.width)
    styles = MermaidStyles.default_colors() if color else MermaidStyles.plain()
    if color:
        _enable_windows_vt()

    outputs: list[str] = []
    for src in sources:
        art = render(src, styles, width)
        if art is not None:
            outputs.append(_art_to_text(art, color))
    if not outputs:
        print("mermaid-term: input is empty", file=sys.stderr)
        return 1
    print("\n\n".join(outputs))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mermaid-term",
        description=(
            "Render Mermaid diagrams as Unicode box-drawing art. Supports "
            "flowchart/graph, stateDiagram, classDiagram, erDiagram, and "
            "sequenceDiagram; other diagram types are shown as framed source."
        ),
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="mermaid source file (default: read stdin; '-' also means stdin)",
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=None,
        metavar="N",
        help=(
            "maximum diagram width in columns; diagrams wider than this fall "
            "back to framed source (default: terminal width when stdout is a "
            "terminal, otherwise unlimited; 0 means unlimited)"
        ),
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize output with ANSI styles (default: auto)",
    )
    parser.add_argument(
        "-m",
        "--markdown",
        action="store_true",
        help="treat input as Markdown and render every ```mermaid fence",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('mermaid-term')}"
    )
    return parser.parse_args(argv)


def _configure_stdio() -> None:
    # Box-drawing glyphs must survive redirection on Windows, where a piped
    # stdout defaults to the legacy code page.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _read_input(file: str | None) -> str:
    if file is None or file == "-":
        return sys.stdin.read()
    with open(file, encoding="utf-8") as fh:
        return fh.read()


def _resolve_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _resolve_width(width: int | None) -> int | None:
    if width is not None:
        return None if width == 0 else width
    if sys.stdout.isatty():
        return shutil.get_terminal_size().columns
    return None


def _enable_windows_vt() -> None:
    if sys.platform != "win32":
        return
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)


def _art_to_text(art: MermaidArt, color: bool) -> str:
    if color:
        return "\n".join(line.to_ansi() for line in art.styled_lines)
    return "\n".join(art.plain_lines)


def extract_mermaid_blocks(text: str) -> list[str]:
    """Collect the contents of every ``` / ~~~ mermaid fence in ``text``."""
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        fence = None
        for marker in ("```", "~~~"):
            if stripped.startswith(marker):
                fence = marker
                break
        if fence is None or stripped[len(fence) :].strip().lower() != "mermaid":
            i += 1
            continue
        body: list[str] = []
        i += 1
        while i < len(lines):
            inner = lines[i].lstrip()
            if inner.startswith(fence) and not inner[len(fence) :].strip():
                break
            body.append(_dedent_by(lines[i], indent))
            i += 1
        blocks.append("\n".join(body))
        i += 1
    return blocks


def _dedent_by(line: str, indent: int) -> str:
    removed = 0
    while removed < indent and line[:1] == " ":
        line = line[1:]
        removed += 1
    return line
