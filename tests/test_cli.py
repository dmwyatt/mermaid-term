"""CLI behavior: input sources, width, color modes, markdown extraction."""

import io

import pytest

from mermaid_term.cli import extract_mermaid_blocks, main

FLOW = "graph TD\n A[Start] --> B[End]\n"


def test_renders_file(tmp_path, capsys):
    f = tmp_path / "d.mmd"
    f.write_text(FLOW, encoding="utf-8")
    assert main([str(f)]) == 0
    out = capsys.readouterr().out
    assert "Start" in out
    assert "▼" in out
    assert "\x1b[" not in out, "non-tty defaults to no color"


def test_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(FLOW))
    assert main([]) == 0
    assert "Start" in capsys.readouterr().out


def test_narrow_width_falls_back(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(
        "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]\n"
    ))
    assert main(["--width", "40"]) == 0
    out = capsys.readouterr().out
    assert "mermaid: flowchart" in out
    assert "too wide" in out


def test_width_zero_means_unlimited(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(
        "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]\n"
    ))
    assert main(["--width", "0"]) == 0
    out = capsys.readouterr().out
    assert "▶" in out
    assert "mermaid: flowchart" not in out


def test_color_always_emits_ansi(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(FLOW))
    assert main(["--color", "always"]) == 0
    assert "\x1b[" in capsys.readouterr().out


def test_color_never_stays_plain(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(FLOW))
    assert main(["--color", "never"]) == 0
    assert "\x1b[" not in capsys.readouterr().out


def test_markdown_mode_renders_each_fence(tmp_path, capsys):
    md = tmp_path / "doc.md"
    md.write_text(
        "# Title\n\n```mermaid\ngraph TD\n A --> B\n```\n\nprose\n\n"
        "~~~mermaid\nsequenceDiagram\n X->>Y: hi\n~~~\n",
        encoding="utf-8",
    )
    assert main(["--markdown", str(md)]) == 0
    out = capsys.readouterr().out
    assert "▼" in out, "flowchart rendered"
    assert "hi" in out, "sequence rendered"
    assert "# Title" not in out, "prose is not echoed"


def test_markdown_mode_without_fences_errors(tmp_path, capsys):
    md = tmp_path / "doc.md"
    md.write_text("no diagrams here\n", encoding="utf-8")
    assert main(["--markdown", str(md)]) == 1
    assert "no mermaid" in capsys.readouterr().err.lower()


def test_missing_file_errors(capsys):
    assert main(["does-not-exist.mmd"]) == 1
    assert "does-not-exist.mmd" in capsys.readouterr().err


def test_blank_input_errors(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n"))
    assert main([]) == 1
    assert "empty" in capsys.readouterr().err.lower()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("```mermaid\ngraph TD\n A-->B\n```\n", ["graph TD\n A-->B"]),
        ("~~~mermaid\ngraph TD\n A-->B\n~~~\n", ["graph TD\n A-->B"]),
        ("```mermaid \ngraph LR\n A-->B\n```\nmore\n```py\nx=1\n```\n", ["graph LR\n A-->B"]),
        ("  ```mermaid\n  graph TD\n  A-->B\n  ```\n", ["graph TD\nA-->B"]),
        ("no fences\n", []),
        ("```python\nprint()\n```\n", []),
    ],
)
def test_extract_mermaid_blocks(text, expected):
    assert extract_mermaid_blocks(text) == expected
