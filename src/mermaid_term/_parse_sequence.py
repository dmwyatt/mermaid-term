"""Parser for ``sequenceDiagram`` blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._labels import clean_label, decode_html_entities, non_empty, statements_of
from ._model import MAX_EDGES, MAX_NODES


class SeqHead(Enum):
    ARROW = "arrow"
    CROSS = "cross"


SEQ_OPS: list[tuple[str, bool, SeqHead]] = [
    ("-->>", True, SeqHead.ARROW),
    ("->>", False, SeqHead.ARROW),
    ("--x", True, SeqHead.CROSS),
    ("-x", False, SeqHead.CROSS),
    ("--)", True, SeqHead.ARROW),
    ("-)", False, SeqHead.ARROW),
    ("-->", True, SeqHead.ARROW),
    ("->", False, SeqHead.ARROW),
]


@dataclass(frozen=True)
class NoteOver:
    left: int
    right: int


@dataclass(frozen=True)
class NoteLeft:
    of: int


@dataclass(frozen=True)
class NoteRight:
    of: int


NoteAnchor = NoteOver | NoteLeft | NoteRight


@dataclass(frozen=True)
class SeqMessage:
    from_: int
    to: int
    text: str | None
    dashed: bool
    head: SeqHead


@dataclass(frozen=True)
class SeqNote:
    anchor: NoteAnchor
    text: str


@dataclass(frozen=True)
class SeqDivider:
    text: str


SeqItem = SeqMessage | SeqNote | SeqDivider


@dataclass
class Sequence:
    labels: list[str] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)
    items: list[SeqItem] = field(default_factory=list)

    def participant(self, id: str, label: str | None) -> int | None:
        i = self.index.get(id)
        if i is not None:
            if label is not None:
                self.labels[i] = label
            return i
        if len(self.labels) >= MAX_NODES:
            return None
        self.index[id] = len(self.labels)
        self.labels.append(label if label is not None else id)
        return len(self.labels) - 1


_SKIPPED = frozenset(
    [
        "activate", "deactivate", "create", "destroy", "title", "acctitle",
        "accdescr", "links", "link", "properties",
    ]
)
_DIVIDERS = frozenset(
    ["loop", "alt", "opt", "par", "critical", "break", "else", "and", "option"]
)


@dataclass
class _ParseState:
    autonumber: bool = False
    msg_count: int = 0
    blocks: list[bool] = field(default_factory=list)


def parse_sequence(src: str) -> Sequence | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or header_tokens[0].lower() != "sequencediagram":
        return None

    seq = Sequence()
    state = _ParseState()
    for st in statements[1:]:
        if not _apply_seq_statement(st, seq, state):
            return None

    if not seq.labels:
        return None
    return seq


def _apply_seq_statement(st: str, seq: Sequence, state: _ParseState) -> bool:
    words = st.split()
    first = words[0].lower() if words else ""
    if first in ("participant", "actor"):
        return _participant_stmt(st, first, seq)
    if first == "autonumber":
        state.autonumber = True
        return True
    if first in _SKIPPED:
        return True
    if first == "note":
        return _note_stmt(st, first, seq)
    if first in _DIVIDERS:
        return _divider_stmt(st, first, seq, state.blocks)
    if first in ("rect", "box"):
        state.blocks.append(False)
        return True
    if first == "end":
        return _end_stmt(seq, state.blocks)
    return _message_stmt(st, seq, state)


def _push_item(seq: Sequence, item: SeqItem) -> bool:
    if len(seq.items) >= MAX_EDGES:
        return False
    seq.items.append(item)
    return True


def _participant_stmt(st: str, first: str, seq: Sequence) -> bool:
    rest = st[len(first) :].strip()
    if not rest:
        return False
    if " as " in rest:
        pid, label_part = rest.split(" as ", 1)
        pid = pid.strip()
        label: str | None = clean_label(label_part)
    else:
        pid, label = rest, None
    return seq.participant(pid, label) is not None


def _note_stmt(st: str, first: str, seq: Sequence) -> bool:
    parsed = parse_note_anchor(st[len(first) :].strip(), seq)
    if parsed is None:
        return False
    text_part, anchor = parsed
    return _push_item(seq, SeqNote(anchor, text_part))


def _divider_stmt(st: str, first: str, seq: Sequence, blocks: list[bool]) -> bool:
    if first in ("else", "and", "option"):
        if not blocks or blocks[-1] is not True:
            return True
    else:
        blocks.append(True)
    return _push_item(seq, SeqDivider(decode_html_entities(st)))


def _end_stmt(seq: Sequence, blocks: list[bool]) -> bool:
    if blocks and blocks.pop() is True:
        return _push_item(seq, SeqDivider("end"))
    return True


def _message_stmt(st: str, seq: Sequence, state: _ParseState) -> bool:
    msg = parse_seq_message(st, seq)
    if msg is None:
        return False
    from_, to, text, dashed, head = msg
    if state.autonumber:
        state.msg_count += 1
        text = f"{state.msg_count}. {text}" if text is not None else f"{state.msg_count}."
    return _push_item(seq, SeqMessage(from_, to, text, dashed, head))


def parse_note_anchor(rest: str, seq: Sequence) -> tuple[str, NoteAnchor] | None:
    target = _note_target(rest)
    if target is None:
        return None
    ids_and_text, kind = target
    if ":" not in ids_and_text:
        return None
    ids, text = ids_and_text.split(":", 1)
    text = decode_html_entities(text.strip())
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if not parts:
        return None
    a = seq.participant(parts[0], None)
    if a is None:
        return None
    return _anchored(kind, parts, a, seq, text)


def _note_target(rest: str) -> tuple[str, int] | None:
    lower = rest.lower()
    for prefix, kind in (("over ", 0), ("left of ", 1), ("right of ", 2)):
        if lower.startswith(prefix):
            return (rest[len(prefix) :], kind)
    return None


def _anchored(
    kind: int, parts: list[str], a: int, seq: Sequence, text: str
) -> tuple[str, NoteAnchor] | None:
    if kind == 1:
        return (text, NoteLeft(a))
    if kind == 2:
        return (text, NoteRight(a))
    b = a
    if len(parts) > 1:
        maybe = seq.participant(parts[1], None)
        if maybe is None:
            return None
        b = maybe
    return (text, NoteOver(min(a, b), max(a, b)))


def parse_seq_message(
    st: str, seq: Sequence
) -> tuple[int, int, str | None, bool, SeqHead] | None:
    found = _find_seq_op(st)
    if found is None:
        return None
    pos, op, dashed, head = found
    from_id = st[:pos].strip()
    if not from_id:
        return None
    rest = st[pos + len(op) :].lstrip().lstrip("+-")
    text: str | None = None
    if ":" in rest:
        to_id, text_part = rest.split(":", 1)
        to_id = to_id.strip()
        text = non_empty(decode_html_entities(text_part.strip()))
    else:
        to_id = rest.strip()
    if not to_id:
        return None
    from_ = seq.participant(from_id, None)
    if from_ is None:
        return None
    to = seq.participant(to_id, None)
    if to is None:
        return None
    return (from_, to, text, dashed, head)


def _find_seq_op(st: str) -> tuple[int, str, bool, SeqHead] | None:
    for pos in range(len(st)):
        for op, dashed, head in SEQ_OPS:
            if st.startswith(op, pos):
                return (pos, op, dashed, head)
    return None
