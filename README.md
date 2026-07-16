# mermaid-term

Render [Mermaid](https://mermaid.js.org/) diagrams as Unicode box-drawing art
in your terminal. No browser, no Node, no image files.

This is a Python port of the terminal Mermaid renderer from
[xai-org/grok-build](https://github.com/xai-org/grok-build)
(`crates/codegen/xai-grok-markdown/src/mermaid.rs`), including its test suite.

```
$ mermaid-term flow.mmd
       ┌─────────┐
       │ Request │
       └────┬────┘
            │
            ▼validate
       ╭────────╮
       │ Valid? │
       ╰────┬───╯
      ┌─────┴──────┐
      ▼yes         ▼no
 ┌─────────┐  ┌────────┐
 │ Process │  │ Reject │
 └────┬────┘  └────┬───┘
      └─────┬──────┘
            ▼
        ╭───────╮
        │ Store │
        ╰───────╯
```

## Supported diagram types

- `graph` / `flowchart` (all directions, subgraphs, `&` fan-out, edge labels,
  dotted/thick lines, circle/cross/arrow heads, self-loops)
- `stateDiagram` / `stateDiagram-v2`
- `classDiagram` (compartments, annotations, generics, cardinalities)
- `erDiagram` (attributes, cardinalities)
- `sequenceDiagram` (notes, dividers, autonumber, self-messages)

Anything else (gantt, pie, ...) renders as the raw source in a framed box.

## Install / run

Run without installing, via [uv](https://docs.astral.sh/uv/):

```sh
uvx mermaid-term diagram.mmd
```

Or install as a persistent tool:

```sh
uv tool install mermaid-term
```

Works on Windows, macOS, and Linux (pure Python, one small dependency).

## Usage

```sh
mermaid-term diagram.mmd          # render a file
cat diagram.mmd | mermaid-term    # or read stdin
mermaid-term --markdown README.md # render every ```mermaid fence in a Markdown file
mermaid-term -w 60 diagram.mmd    # cap the diagram width at 60 columns
mermaid-term -w 0 diagram.mmd     # no width limit
mermaid-term --color always diagram.mmd | less -R
```

- `--width` defaults to the terminal width when stdout is a terminal and
  unlimited otherwise. Diagrams that exceed the width limit fall back to the
  framed source with a hint.
- `--color` is `auto` by default: ANSI styling on a terminal, plain text when
  piped. `NO_COLOR` is respected.

## Library use

```python
from mermaid_term import render, MermaidStyles

art = render("graph TD\n A --> B", MermaidStyles.plain(), max_width=80)
print("\n".join(art.plain_lines))          # plain text
print("\n".join(l.to_ansi() for l in art.styled_lines))  # ANSI-styled
```

`render` returns `None` for blank input. Unsupported or oversized diagrams
return the framed-source fallback rather than raising.

## Development

```sh
uv sync
uv run pytest
```

The test suite is ported from the upstream Rust module and pins parser
behavior and rendered output; new rendering changes should keep it green.
