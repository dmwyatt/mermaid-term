# Porting notes: how mermaid-term was made

mermaid-term is a Python port of the terminal Mermaid renderer from
[xai-org/grok-build](https://github.com/xai-org/grok-build)
(`crates/codegen/xai-grok-markdown/src/mermaid.rs`). The port was done in a
single session on July 16, 2026 by an AI agent (Claude Fable 5), with a human
in the loop for direction. First prompt to final commit took about 40 minutes.
This document describes how that session went: the strategy, how fidelity was
handled, what went wrong (very little), and a few things worth knowing about
the result.

## Where it started

The original request pointed at the Rust source file and said, in full:

> I want a CLI version of this. [...] make it happen. It should work on at
> least windows and macos. linux compatibility if possible without a lot of
> extra work would be nice

The agent fetched the file and started probing its dependency surface. Two
minutes in, it was heading toward building a Rust CLI around the module. The
one course correction of the session happened here: the human interrupted to
say the tool should be Python, so it could run via `uvx`. Everything after
that followed from the pivot: pure Python, one small dependency, a package
built for PyPI from the start.

Before scaffolding anything, the agent checked name availability on PyPI.
`termaid` and `merm` were taken, `mermaid-term` was free, so the package never
needed a rename.

## Strategy: read everything, port the tests first, implement bottom-up

The source is one 5,237-line Rust file with its test module at the bottom:
roughly 120 tests covering the parsers and the rendered output. The session
treated that test suite as the specification and worked through a ten-task
plan laid out up front:

1. **Read and map the whole source.** All 5,237 lines were read before any
   Python was written: the data structures, one parser per diagram type, the
   rank and position algorithms, canvas painting, and the top-level render
   orchestration.
2. **Scaffold.** `uv init --package`, `wcwidth` as the only runtime
   dependency, pytest for development.
3. **Port the test suite before the implementation.** Every test file was
   translated from the Rust `mod tests` first. The suite was run once to
   confirm it failed with `ModuleNotFoundError` and nothing else, the usual
   TDD baseline.
4. **Implement bottom-up in dependency order.** Text-width primitives and
   label cleaning, then the model types and styling layer, the canvas, the
   five parsers, rank assignment and ordering, drawing primitives and edge
   routing, the flowchart layout engine, subgraph rendering, sequence layout,
   and finally the public `render()`.
5. **CLI last, also test-first.** File and stdin input, `--width`,
   `--color auto/always/never` with `NO_COLOR` respected, `--markdown` fence
   extraction, and the two Windows accommodations (UTF-8 stdout
   reconfiguration and VT processing enabled via ctypes).

The single Rust file became sixteen focused modules under `src/mermaid_term/`
(a seventeenth, `_tracks.py`, was split out later in the session), plus the
CLI. Two dependencies were substituted rather than ported: ratatui's
`Style`/`Span`/`Line` types became a small in-house ANSI styling layer, and
the `unicode-width` crate became `wcwidth`.

## How fidelity was handled

The ported test suite is the fidelity instrument. The Rust tests pin parser
results and rendered output, so translating them faithfully (around 120 Rust
tests became 146 pytest tests, 162 once the CLI tests were added) carried the
upstream behavior contract across the language boundary.

The first time the full suite ran against the finished implementation, all
146 tests passed. There were no intermediate green runs; the modules were
written straight through in dependency order and the suite went from
"everything fails to import" to fully passing in one step.

That worked because the known Rust-to-Python traps were ported deliberately
instead of discovered by debugging:

- Rust's `round()` rounds half away from zero; Python's built-in `round()`
  uses banker's rounding. Layout math that depends on rounding uses an
  explicit half-away-from-zero helper.
- Rust's `trim_end_matches` strips a multi-character pattern repeatedly;
  Python's `str.rstrip` strips a character set. The pattern semantics were
  reproduced where the parsers rely on them.
- The canvas marks the continuation cell of a double-width (CJK) glyph with a
  NUL sentinel so column arithmetic stays correct. Ported as-is.
- BT and RL flowchart directions reuse the TD/LR layout and then flip the
  finished canvas, keeping the text itself unflipped. This design was
  inherited from the original rather than reinvented.

Beyond the suite, every diagram type was rendered end-to-end through the real
CLI on Windows and inspected, along with Markdown fence extraction, ANSI color
output, and a `uvx --from .` run to prove the packaging worked.

One honest caveat: the port was never diffed against the running Rust
original. Building the upstream crate was out of scope, so "fidelity" here
means the translated tests and spot checks agree with the upstream
expectations, and both the tests and the implementation were translated by
the same agent. The README's vibe-coding warning exists for this reason.

## Pitfalls

There were almost none at runtime. Across the whole session the only tool
errors were two harness guards (attempting to overwrite a scaffolded file
before reading it), and there was not a single failing test run after
implementation started. The real pitfalls were the anticipated ones listed
above, which is the point: in a port, the dangerous differences are known
properties of the two languages, so they can be handled up front rather than
found the hard way.

The other pitfall class was scope, and it produced the session's only
interruption. "I want a CLI version of this" did not say what the CLI should
be built in, and the agent defaulted to the source language. Stating the
runtime constraint ("I want to run it via uvx") up front would have saved the
detour.

One piece of debt did arrive with the port itself: complexity. A faithful
translation inherits the original's structure, and the Rust functions ran up
to cyclomatic complexity 35 (the ported `layout_sequence` scored a radon D at
26). The house rule is CC of 9 or less, so a dedicated refactoring pass
followed the port: helpers were extracted file by file with the suite run
after each one, and `_tracks.py` was split out of `_layout.py`. The pass
ended with every function at CC 9 or below, the largest module at 332 lines,
and a rendered sample diagram byte-identical to the pre-refactor output.

## Numbers

- 40 minutes from first prompt to final commit, in 5 commits: scaffold, port,
  CLI, complexity pass, README.
- 5,237 lines of Rust became about 3,700 lines of Python.
- 162 tests, running in about half a second.
- The session's context window peaked around 349k tokens. Reading the Rust
  source in (five reads covering the full file) plus all command output came
  to about 220 KB of tool results; the Python written back out came to about
  269 KB of write payloads, inflated by the complexity pass rewriting several
  modules. The code the session wrote cost more context than the code it
  read.

## Afterward

Later sessions published the repository to GitHub and PyPI (with trusted
publishing on version tags), added the NOTICE attribution file, and replaced
the README's text diagram with a terminal screenshot. The porting session
itself ended with a working, tested, locally-runnable tool.
