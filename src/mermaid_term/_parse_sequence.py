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


def parse_sequence(src: str) -> Sequence | None:
    statements = statements_of(src)
    if not statements:
        return None
    header_tokens = statements[0].split()
    if not header_tokens or header_tokens[0].lower() != "sequencediagram":
        return None

    seq = Sequence()
    autonumber = False
    msg_count = 0
    blocks: list[bool] = []

    for st in statements[1:]:
        words = st.split()
        first = words[0].lower() if words else ""
        if first in ("participant", "actor"):
            rest = st[len(first) :].strip()
            if not rest:
                return None
            if " as " in rest:
                pid, label_part = rest.split(" as ", 1)
                pid = pid.strip()
                label: str | None = clean_label(label_part)
            else:
                pid, label = rest, None
            if seq.participant(pid, label) is None:
                return None
        elif first == "autonumber":
            autonumber = True
        elif first in _SKIPPED:
            pass
        elif first == "note":
            rest = st[len(first) :].strip()
            parsed = parse_note_anchor(rest, seq)
            if parsed is None:
                return None
            text_part, anchor = parsed
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqNote(anchor, text_part))
        elif first in _DIVIDERS:
            if first in ("else", "and", "option"):
                if not blocks or blocks[-1] is not True:
                    continue
            else:
                blocks.append(True)
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqDivider(decode_html_entities(st)))
        elif first in ("rect", "box"):
            blocks.append(False)
        elif first == "end":
            if blocks and blocks.pop() is True:
                if len(seq.items) >= MAX_EDGES:
                    return None
                seq.items.append(SeqDivider("end"))
        else:
            msg = parse_seq_message(st, seq)
            if msg is None:
                return None
            from_, to, text, dashed, head = msg
            if autonumber:
                msg_count += 1
                text = f"{msg_count}. {text}" if text is not None else f"{msg_count}."
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqMessage(from_, to, text, dashed, head))

    if not seq.labels:
        return None
    return seq


def parse_note_anchor(rest: str, seq: Sequence) -> tuple[str, NoteAnchor] | None:
    lower = rest.lower()
    if lower.startswith("over "):
        ids_and_text, kind = rest[len("over ") :], 0
    elif lower.startswith("left of "):
        ids_and_text, kind = rest[len("left of ") :], 1
    elif lower.startswith("right of "):
        ids_and_text, kind = rest[len("right of ") :], 2
    else:
        return None
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
    if kind == 0:
        if len(parts) > 1:
            b = seq.participant(parts[1], None)
            if b is None:
                return None
        else:
            b = a
        return (text, NoteOver(min(a, b), max(a, b)))
    if kind == 1:
        return (text, NoteLeft(a))
    return (text, NoteRight(a))


def parse_seq_message(
    st: str, seq: Sequence
) -> tuple[int, int, str | None, bool, SeqHead] | None:
    found: tuple[int, str, bool, SeqHead] | None = None
    for pos in range(len(st)):
        for op, dashed, head in SEQ_OPS:
            if st.startswith(op, pos):
                found = (pos, op, dashed, head)
                break
        if found is not None:
            break
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
