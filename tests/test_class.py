"""Class diagram parsing and compartment rendering."""

from mermaid_term._model import Head, LineKind
from mermaid_term._parse_class import parse_class

from .util import plain


def test_class_renders_compartments():
    out = plain(
        "classDiagram\n class Animal {\n +int age\n +isMammal() bool\n }\n Animal <|-- Duck"
    )
    assert "Animal" in out, out
    assert "+int age" in out, out
    assert "+isMammal() bool" in out, out
    assert "├" in out and "┤" in out, f"section rules:\n{out}"
    lines = out.splitlines()
    name = next(i for i, l in enumerate(lines) if "Animal" in l)
    attr = next(i for i, l in enumerate(lines) if "+int age" in l)
    method = next(i for i, l in enumerate(lines) if "+isMammal() bool" in l)
    assert name < attr < method, out


def test_class_inheritance_triangle_at_parent():
    out = plain("classDiagram\n Animal <|-- Duck\n Animal <|-- Fish")
    assert "△" in out, f"hollow triangle:\n{out}"
    lines = out.splitlines()
    animal = next(i for i, l in enumerate(lines) if "Animal" in l)
    duck = next(i for i, l in enumerate(lines) if "Duck" in l)
    assert animal < duck, f"parent above child:\n{out}"
    tri = next(i for i, l in enumerate(lines) if "△" in l)
    assert animal <= tri < duck, f"triangle at parent end:\n{out}"


def test_class_realization_is_dotted_triangle():
    parsed = parse_class("classDiagram\n IShape <|.. Circle")
    assert parsed is not None
    g = parsed[0]
    assert g.edges[0].head_from == Head.TRIANGLE
    assert g.edges[0].line == LineKind.DOTTED
    out = plain("classDiagram\n IShape <|.. Circle")
    assert "╎" in out or "╌" in out, out


def test_class_composition_and_aggregation_diamonds():
    out = plain("classDiagram\n Car *-- Engine\n Pond o-- Duck")
    assert "◆" in out, f"filled diamond:\n{out}"
    assert "◇" in out, f"open diamond:\n{out}"


def test_class_dependency_dotted_arrow():
    parsed = parse_class("classDiagram\n A ..> B")
    assert parsed is not None
    g = parsed[0]
    assert g.edges[0].head_to == Head.ARROW
    assert g.edges[0].line == LineKind.DOTTED


def test_class_colon_members_merge_with_block():
    out = plain("classDiagram\n class Duck {\n +swim()\n }\n Duck : +String beakColor\n S --> Duck")
    assert "+swim()" in out, out
    assert "+String beakColor" in out, out


def test_class_annotation_renders_guillemets():
    out = plain("classDiagram\n <<interface>> Shape\n Shape <|.. Circle")
    assert "«interface»" in out, out


def test_class_generics_display_as_angle_brackets():
    out = plain("classDiagram\n Shape~T~ : +area() T\n S --> Shape~T~")
    assert "Shape<T>" in out, out
    assert "~" not in out, out


def test_class_cardinalities_fold_into_label():
    out = plain('classDiagram\n Student "many" --> "1" School : attends')
    assert "many attends 1" in out, out


def test_class_from_end_head_survives_fan_out_jog():
    out = plain("classDiagram\n Animal <|-- Duck\n Animal <|-- Fish\n Animal <|-- Cow")
    assert out.count("△") + out.count("▽") == 1, (
        f"merged from-end glyph on the parent border:\n{out}"
    )


def test_class_empty_class_is_plain_titled_box():
    out = plain("classDiagram\n class Loner\n A --> Loner")
    assert "Loner" in out, out


def test_class_unknown_statement_falls_back():
    out = plain("classDiagram\n A --> B\n total garbage here")
    assert "mermaid: classDiagram" in out, out


def test_class_member_cap_ellipsis():
    src = "classDiagram\n class Big {\n"
    for i in range(12):
        src += f" +field{i}\n"
    src += " }\n A --> Big"
    out = plain(src)
    assert "+field7" in out, out
    assert "+field9" not in out, out
    assert "…" in out, out


def test_class_direction_lr():
    out = plain("classDiagram\n direction LR\n A --> B")
    line = next(l for l in out.splitlines() if "A" in l)
    assert "B" in line, out
