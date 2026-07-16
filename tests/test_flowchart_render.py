"""Flowchart rendering: box art, edge routing, buses/lanes, line styles."""

from mermaid_term import render
from mermaid_term._text import CONT

from .util import plain, str_width, styles


def test_td_render_has_boxes_labels_and_arrow():
    out = plain("graph TD\n A[Start] --> B[End]")
    assert "Start" in out, out
    assert "End" in out, out
    assert "┌" in out or "╭" in out, out
    assert "▼" in out, out


def test_edge_label_is_rendered():
    out = plain("graph TD\n A-->|yes| B")
    assert "yes" in out, out


def test_lr_is_shorter_than_td_for_a_chain():
    chain = "A --> B --> C --> D"
    td = len(render(f"graph TD\n {chain}", styles(), 120).plain_lines)
    lr = len(render(f"flowchart LR\n {chain}", styles(), 120).plain_lines)
    assert lr < td, f"expected LR ({lr}) shorter than TD ({td})"


def test_wide_glyph_box_stays_aligned():
    lines = render("graph TD\n A[日本語ab]", styles(), 120).plain_lines
    widths = [str_width(l) for l in lines if l.strip()]
    assert all(a == b for a, b in zip(widths, widths[1:])), (
        f"box rows must share one width: {widths!r}\n{lines!r}"
    )
    assert not any(CONT in l for l in lines), "sentinel leaked"


def test_merge_has_single_arrowhead():
    out = plain("graph TD\n A[aaa] --> D[ddddddd]\n B[bb] --> D\n C[ccccc] --> D")
    assert out.count("▼") == 1, f"merge edges share one arrowhead:\n{out}"
    assert "▼▼" not in out, f"must not stack arrowheads:\n{out}"


def test_long_label_wraps_without_truncation():
    out = plain("graph TD\n A[Check if the user has permission to access resource] --> B[Done]")
    assert "permission" in out, out
    assert "resource" in out, out
    assert "…" not in out, f"should wrap, not truncate:\n{out}"


def test_very_long_label_truncates_after_max_lines():
    long = "alpha " * 40
    out = plain(f"graph TD\n A[{long.strip()}] --> B[x]")
    assert "…" in out, f"should truncate past max lines:\n{out}"


def test_flowchart_long_identifier_breaks_on_boundary_not_mid_segment():
    out = plain("graph TD\n A[mark_filter_restore_context] --> B[Done]")
    # The boundary-respecting pieces are present in the rendered art; the
    # `test_wrap_label_breaks_long_identifier_on_boundary` unit test proves
    # there is no mid-segment slice (losslessly), so no offset-coupled guard here.
    assert "mark_filter_restore_" in out, out
    assert "context" in out, out


def test_bt_flips_orientation():
    out = plain("flowchart BT\n A[first] --> B[second] --> C[third]")
    lines = out.splitlines()

    def row(needle: str) -> int:
        return next(i for i, l in enumerate(lines) if needle in l)

    assert row("third") < row("first"), f"BT: 'third' should sit above 'first':\n{out}"


def test_rl_flips_orientation():
    out = plain("flowchart RL\n A[first] --> B[second] --> C[third]")
    line = next(l for l in out.splitlines() if "first" in l)
    assert line.index("third") < line.index("first"), (
        f"RL: 'third' should sit left of 'first':\n{out}"
    )


def test_undirected_piped_label_has_no_arrowhead():
    out = plain("graph TD\n A ---|maybe| B")
    assert "maybe" in out, out
    assert "▼" not in out, f"undirected link should not draw an arrow:\n{out}"


def test_chain_edges_are_straight():
    out = plain("graph TD\n A[aaaa] --> B[b] --> C[cccccccc]")
    for line in out.splitlines():
        assert "└" not in line or "┐" not in line, f"chain should not jog: {line!r}"


def test_deep_chain_within_caps_renders():
    src = "graph TD\n" + "".join(f" N{i} --> N{i + 1}\n" for i in range(100))
    out = render(src, styles(), 200).plain_lines
    joined = "\n".join(out)
    assert "N0" in joined, joined
    assert "N100" in joined, joined
    assert "▼" in joined, joined


def test_skip_edge_routes_around_intermediate_boxes():
    out = plain("graph TD\n A --> B\n B --> C\n A --> C")
    assert "┼" not in out, f"no border corruption:\n{out}"
    assert "◄" in out, f"skip edge enters target from lane:\n{out}"


def test_crossing_edges_render_untangled():
    out = plain("graph TD\n C[ccc]\n D[ddd]\n A --> D\n B --> C")
    row = next(l for l in out.splitlines() if "ccc" in l and "ddd" in l)
    assert row.index("ddd") < row.index("ccc"), (
        f"children reorder under their parents:\n{out}"
    )
    assert "┼" not in out, out


def test_unavoidable_crossing_gets_separate_bus_rows():
    crossing = plain("graph TD\n A --> D[ddd]\n A --> C[ccc]\n B --> C\n B --> D")
    parallel = plain("graph TD\n A --> C[ccc]\n B --> D[ddd]")
    assert "┼" in crossing, f"wire crossing renders:\n{crossing}"
    assert len(crossing.splitlines()) == len(parallel.splitlines()) + 1, (
        f"crossing pair claims one extra bus row:\n{crossing}"
    )
    assert crossing.count("▼") == 2, crossing


def test_fan_out_keeps_single_bus_row():
    out = plain("graph TD\n A --> C[ccc]\n A --> D[ddd]")
    baseline = plain("graph TD\n A --> C[ccc]")
    assert len(out.splitlines()) == len(baseline.splitlines()), (
        f"shared-source jogs share one bus row:\n{out}"
    )
    assert "┼" not in out, out


def test_shared_target_back_edges_share_one_lane():
    two = plain("graph TD\n A --> B\n B --> C\n B --> A\n C --> A")
    one = plain("graph TD\n A --> B\n B --> C\n C --> A")
    assert max(str_width(l) for l in two.splitlines()) == max(
        str_width(l) for l in one.splitlines()
    ), f"shared-target back edges merge into one lane:\n{two}"
    assert two.count("◄") == 1, two


def test_distinct_back_edges_get_separate_lanes():
    split = plain("graph TD\n A --> B\n B --> C\n B --> A\n C --> B")
    single = plain("graph TD\n A --> B\n B --> C\n C --> B")
    assert split.count("◄") == 2, split
    assert max(str_width(l) for l in split.splitlines()) > max(
        str_width(l) for l in single.splitlines()
    ), f"overlapping unrelated back edges claim a second lane:\n{split}"


def test_bidirectional_link_draws_both_arrowheads():
    lr = plain("flowchart LR\n A <--> B")
    assert "◄" in lr and "▶" in lr, lr
    td = plain("graph TD\n A <--> B")
    assert "▲" in td and "▼" in td, td


def test_reversed_arrow_renders_target_above():
    out = plain("graph TD\n A <-- B")
    lines = out.splitlines()

    def row(needle: str) -> int:
        return next(i for i, l in enumerate(lines) if needle in l)

    assert row("B") < row("A"), f"B should rank above A:\n{out}"


def test_dotted_and_thick_lines_render_distinctly():
    dotted = plain("graph TD\n A -.-> B")
    assert "╎" in dotted, f"dotted vertical:\n{dotted}"
    thick = plain("graph TD\n A ==> B")
    assert "┃" in thick, f"thick vertical:\n{thick}"
    solid = plain("graph TD\n A --> B")
    assert "╎" not in solid and "┃" not in solid, f"solid unchanged:\n{solid}"


def test_dotted_label_form_renders_dashed():
    out = plain("graph LR\n A -. maybe .-> B")
    assert "╌" in out, out
    assert "maybe" in out, out


def test_thick_jog_uses_thick_corners():
    out = plain("graph TD\n A[aaaaaaa] ==> B\n A ==> C[ccccccc]")
    assert "┏" in out or "┓" in out or "┳" in out, f"thick corners on jog:\n{out}"


def test_mixed_solid_and_dotted_bus_stays_light():
    out = plain("graph TD\n A --> C\n B -.-> C")
    assert "╌" in out, f"dotted branch survives:\n{out}"
    assert "─" in out, f"solid branch survives:\n{out}"
    assert "┬" in out, f"shared merge cell stays light:\n{out}"


def test_box_borders_stay_light_next_to_styled_edges():
    out = plain("graph TD\n A ==> B")
    assert "┌" in out and "└" in out, out
    assert "┏" not in out, f"borders not restyled:\n{out}"


def test_self_loop_renders_below_box():
    out = plain("graph TD\n A --> A")
    assert "╰" in out and "╯" in out, out
    assert "▲" in out, f"loop returns into the box:\n{out}"


def test_self_loop_label_renders():
    out = plain("graph TD\n A -->|again| A")
    assert "again" in out, out


def test_self_loop_coexists_with_forward_edge():
    out = plain("graph TD\n A --> A\n A --> B")
    assert "▲" in out, out
    assert "▼" in out, out
    assert "B" in out, out
    assert "┼" not in out, out


def test_self_loop_flips_with_bt():
    out = plain("flowchart BT\n A --> A\n A --> B")
    assert "▼" in out, f"flipped loop head points down:\n{out}"
    assert "╭" in out or "╮" in out, out


def test_self_loop_in_lr():
    out = plain("flowchart LR\n A --> A\n A --> B")
    assert "▲" in out, out
    assert "▶" in out, out
