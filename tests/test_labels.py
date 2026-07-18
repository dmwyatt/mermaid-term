"""Label cleaning: HTML tags, entities, markdown strings, quoting."""

from mermaid_term._labels import Statement, decode_html_entities, statements_of
from mermaid_term._model import ClassInfo
from mermaid_term._parse_class import parse_class, push_member
from mermaid_term._parse_er import push_er_attribute
from mermaid_term._parse_flowchart import parse_graph
from mermaid_term._parse_sequence import SeqDivider, SeqMessage, SeqNote, parse_sequence
from mermaid_term._parse_state import parse_state

from .util import plain


def test_statements_carry_their_source_line_numbers():
    stmts = statements_of("graph TD\n  A --> B\n  B --> C\n")
    assert stmts == [
        Statement("graph TD", 1),
        Statement("A --> B", 2),
        Statement("B --> C", 3),
    ]


def test_semicolon_split_statements_share_one_line():
    stmts = statements_of("graph TD\n A-->B; B-->C\n")
    assert stmts == [
        Statement("graph TD", 1),
        Statement("A-->B", 2),
        Statement("B-->C", 2),
    ]


def test_blank_and_comment_lines_advance_line_numbers():
    src = "graph TD\n\n%% comment only\n A --> B %% trailing\n"
    assert statements_of(src) == [Statement("graph TD", 1), Statement("A --> B", 4)]


def test_html_tags_are_stripped_from_labels():
    g = parse_graph('flowchart TD\n  A["<b>Bold</b> and <i>italic</i>"] --> B')
    assert g is not None
    assert g.nodes[0].label == "Bold and italic"


def test_br_tag_becomes_a_space():
    g = parse_graph('flowchart TD\n  A["Line1<br/>Line2<br>Line3"]')
    assert g is not None
    assert g.nodes[0].label == "Line1 Line2 Line3"


def test_markdown_string_strips_bold_italic_and_code():
    g = parse_graph(
        'flowchart TD\n  A["`**Start** here`"] --> B["`Save to **database**`"]\n  B --> C["`**Done!**`"]'
    )
    assert g is not None
    assert g.nodes[0].label == "Start here"
    assert g.nodes[1].label == "Save to database"
    assert g.nodes[2].label == "Done!"


def test_markdown_string_preserves_snake_case_and_strips_inline_code():
    g = parse_graph('flowchart TD\n  A["`_italic_ uses `vocab_size` with __all__`"]')
    assert g is not None
    assert g.nodes[0].label == "italic uses vocab_size with all"


def test_markdown_string_edge_label_is_stripped():
    g = parse_graph('flowchart TD\n  A -->|"`**yes**`"| B\n  A -->|"`__no__`"| C')
    assert g is not None
    assert g.edges[0].label == "yes"
    assert g.edges[1].label == "no"


def test_plain_label_keeps_literal_text_and_underscores():
    # Not a markdown string (no backtick wrapper): Mermaid renders it
    # literally, so brackets, snake_case, and any `*`/`_` must survive.
    g = parse_graph('flowchart TD\n  A["[ 464, 3797 ] seq_len d_model"]')
    assert g is not None
    assert g.nodes[0].label == "[ 464, 3797 ] seq_len d_model"


def test_code_and_span_tags_are_stripped():
    g = parse_graph(
        'flowchart TD\n  A["<code>vocab_size</code> <span style=\\"color:red\\">x</span>"]'
    )
    assert g is not None
    assert g.nodes[0].label == "vocab_size x"


def test_bare_angle_brackets_are_kept():
    g = parse_graph('flowchart TD\n  A["a < b and c > d"]')
    assert g is not None
    assert g.nodes[0].label == "a < b and c > d"


def test_generic_types_are_not_stripped_as_html():
    # `<String>` / `<i32>` / `<id>` look like tags but are not HTML
    # formatting tags, so they must survive (only b/i/code/span/… etc. and
    # <br> are stripped).
    g = parse_graph('flowchart TD\n  A["Returns Vec<String>"] --> B["Option<i32> for <id>"]')
    assert g is not None
    assert g.nodes[0].label == "Returns Vec<String>"
    assert g.nodes[1].label == "Option<i32> for <id>"


def test_decode_html_entities_covers_named_numeric_and_double_escape():
    assert decode_html_entities("&lt;a&gt; &amp; &quot;x&quot; &apos;y&apos;") == "<a> & \"x\" 'y'"
    assert decode_html_entities("it&#39;s &#60;ok&#62;") == "it's <ok>"
    assert decode_html_entities("&#x3c;tag&#X3E; &#x27;q&#x27;") == "<tag> 'q'"
    # `&amp;lt;` must yield the literal `&lt;`, never `<`.
    assert decode_html_entities("&amp;lt;") == "&lt;"
    assert decode_html_entities("a &foo; b & c") == "a &foo; b & c"
    # Control chars (NUL collides with CONT, ESC injects ANSI) never decode.
    assert decode_html_entities("a&#27;b&#0;c") == "a&#27;b&#0;c"
    assert decode_html_entities("x&#x1b;y") == "x&#x1b;y"


def test_entity_escaped_flowchart_label_decodes_in_box_art():
    src = (
        'flowchart LR\n  YAML["models-config/&lt;model&gt;/&lt;env&gt;.yaml\\n'
        'enterprise_api_config:"]\n  PY["model_config_map.py\\n'
        'language_model_dict_to_proto()"]\n  YAML --> PY'
    )
    g = parse_graph(src)
    assert g is not None
    assert "models-config/<model>/<env>.yaml" in g.nodes[0].label, g.nodes[0].label
    art = plain(src)
    assert "<model>" in art and "<env>" in art, art
    assert "&lt;" not in art and "&gt;" not in art, art


def test_direct_push_sinks_decode_entities():
    # Entities contain `;`, which split_statements treats as a separator, so
    # they reach a sink intact only inside quotes; assert through the real
    # parsers where such quoting works.
    g = parse_state(
        'stateDiagram-v2\n  state "work &lt;job&gt;" as J\n  Idle --> Run: "on &lt;go&gt;"\n  Run: "d &lt;e&gt;"',
        [],
    )
    assert g is not None

    def node(s: str) -> bool:
        return any(s in n.label for n in g.nodes)

    def edge(s: str) -> bool:
        return any(e.label is not None and s in e.label for e in g.edges)

    assert node("work <job>") and node("d <e>") and edge("on <go>")
    assert not node("&lt;") and not edge("&lt;")

    parsed = parse_class('classDiagram\n  A --> B : "uses &lt;X&gt;"', [])
    assert parsed is not None
    cg, _ = parsed
    assert any(
        e.label is not None and "uses <X>" in e.label and "&lt;" not in e.label
        for e in cg.edges
    )

    s = parse_sequence(
        'sequenceDiagram\n  A->>B: "call &lt;svc&gt;"\n  Note over A,B: "memo &lt;o&gt;"\n  alt "c &lt;x&gt;"\n    A->>B: ok\n  end'
    )
    assert s is not None
    assert any(
        isinstance(it, SeqMessage)
        and it.text is not None
        and "call <svc>" in it.text
        and "&lt;" not in it.text
        for it in s.items
    )
    assert any(
        isinstance(it, SeqNote) and "memo <o>" in it.text and "&lt;" not in it.text
        for it in s.items
    )
    assert any(
        isinstance(it, SeqDivider) and "c <x>" in it.text and "&lt;" not in it.text
        for it in s.items
    )

    # Class members and ER attributes have no clean quoted form (splitter
    # fragments unquoted `;`; ER drops quoted text as a comment), so exercise
    # those decodes at the finalizer directly.
    member = ClassInfo()
    push_member(member, "+run &lt;R&gt;")
    assert member.attrs == ["+run <R>"]
    attr = ClassInfo()
    push_er_attribute(attr, "string &lt;pk&gt;")
    assert attr.attrs == ["string <pk>"]


def test_quoted_label_with_inner_brackets_is_one_node():
    g = parse_graph('flowchart TD\n  IDs["<b>Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>"]')
    assert g is not None
    assert len(g.nodes) == 1, "inner brackets must not split the node"
    assert len(g.edges) == 0, "no phantom edges from <br/> + brackets"
    assert g.nodes[0].label == "Token IDs [ 464, 3797 ] indices"


def test_unquoted_label_with_embedded_quote_closes_at_bracket():
    g = parse_graph('flowchart TD\n  A[5" pipe] --> B[24" display]')
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.nodes[0].label == '5" pipe'
    assert g.nodes[1].label == '24" display'


def test_quoted_label_with_inner_parens_is_one_node():
    g = parse_graph('flowchart TD\n  A["Tokenizer (BPE / WordPiece)"] --> B[Done]')
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.nodes[0].label == "Tokenizer (BPE / WordPiece)"


def test_diagram_with_html_labels_renders_without_tag_artifacts():
    src = 'flowchart TD\n  IDs["<b>3. Token IDs</b><br/>[ 464, 3797 ]<br/><i>indices</i>"] --> Out["<b>done</b>"]'
    out = plain(src)
    assert "<b>" not in out, f"raw HTML tag leaked:\n{out}"
    assert "</" not in out, f"raw closing tag leaked:\n{out}"
    assert "br/" not in out, f"phantom br artifact leaked:\n{out}"
    assert "Token IDs" in out, f"label text missing:\n{out}"


def test_semicolon_and_comment_survive_inside_quoted_label():
    g = parse_graph('graph TD\n A["wait; 50%% done"] --> B')
    assert g is not None
    assert len(g.nodes) == 2
    assert g.nodes[0].label == "wait; 50%% done"


def test_comment_outside_quotes_is_stripped():
    g = parse_graph("graph TD %% main flow\n A --> B %% trailing\n %% full line\n")
    assert g is not None
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
