"""ER diagram parsing and rendering."""

from mermaid_term._model import LineKind
from mermaid_term._parse_er import parse_er, parse_er_op

from .util import plain


def test_er_renders_entities_and_relationship_labels():
    out = plain(
        'erDiagram\n CUSTOMER ||--o{ ORDER : places\n CUSTOMER {\n string name PK "full name"\n int custNumber\n }'
    )
    assert "CUSTOMER" in out, out
    assert "ORDER" in out, out
    assert "string name PK" in out, out
    assert "full name" not in out, f"attribute comments dropped:\n{out}"
    assert "1 places 0..*" in out, out
    assert "├" in out, f"attribute compartment rule:\n{out}"


def test_er_cardinality_map():
    cases = [
        ("||--||", "1", "1"),
        ("|o--o|", "0..1", "0..1"),
        ("}o--o{", "0..*", "0..*"),
        ("}|--|{", "1..*", "1..*"),
        ("||--o{", "1", "0..*"),
    ]
    for op, l, r in cases:
        parsed = parse_er_op(op)
        assert parsed is not None, op
        cl, cr, line = parsed
        assert (cl, cr) == (l, r), op
        assert line == LineKind.SOLID
    assert parse_er_op("||..o{")[2] == LineKind.DOTTED
    assert parse_er_op("||==o{") is None
    assert parse_er_op("garbage") is None


def test_er_non_identifying_renders_dotted():
    out = plain("erDiagram\n A ||..o{ B : uses")
    assert "╎" in out or "╌" in out, out


def test_er_relationships_have_no_arrowheads():
    out = plain("erDiagram\n A ||--o{ B : has")
    for head in "▼▲◄▶△◆◇":
        assert head not in out, f"{head} in:\n{out}"


def test_er_entity_alias_label():
    out = plain('erDiagram\n p[Person] ||--o{ a["Bank Account"] : owns')
    assert "Person" in out, out
    assert "Bank Account" in out, out


def test_er_unquoted_label_and_bare_entity_decl():
    parsed = parse_er("erDiagram\n LONER\n A ||--|| B : linked")
    assert parsed is not None
    g = parsed[0]
    assert len(g.nodes) == 3
    out = plain("erDiagram\n LONER\n A ||--|| B : linked")
    assert "LONER" in out, out
    assert "1 linked 1" in out, out


def test_er_attribute_cap_ellipsis():
    src = "erDiagram\n BIG {\n"
    for i in range(12):
        src += f" int f{i}\n"
    src += " }\n BIG ||--|| OTHER : x"
    out = plain(src)
    assert "int f7" in out, out
    assert "int f9" not in out, out
    assert "…" in out, out


def test_er_unknown_statement_falls_back():
    out = plain("erDiagram\n A ||--|| B : ok\n utter nonsense statement")
    assert "mermaid: erDiagram" in out, out
