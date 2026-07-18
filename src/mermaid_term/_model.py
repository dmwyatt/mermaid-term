"""Shared diagram model: nodes, edges, graphs, and size caps."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

MAX_NODES = 128
MAX_EDGES = 512
MAX_GROUPS = 24
MAX_GROUP_DEPTH = 6
MAX_CANVAS_CELLS = 1 << 21
MAX_MEMBERS = 8


class Shape(Enum):
    RECT = "rect"
    ROUND = "round"
    DIAMOND = "diamond"


class Head(Enum):
    NONE = "none"
    ARROW = "arrow"
    CIRCLE = "circle"
    CROSS = "cross"
    TRIANGLE = "triangle"
    DIAMOND_FILL = "diamond_fill"
    DIAMOND_OPEN = "diamond_open"


class LineKind(Enum):
    SOLID = "solid"
    DOTTED = "dotted"
    THICK = "thick"


class Dir(Enum):
    DOWN = "down"
    UP = "up"
    RIGHT = "right"
    LEFT = "left"


@dataclass
class Node:
    label: str
    shape: Shape


@dataclass
class Edge:
    from_: int
    to: int
    label: str | None
    head_to: Head
    head_from: Head
    line: LineKind


@dataclass
class Group:
    id: str
    label: str
    parent: int | None


@dataclass(frozen=True)
class ParseIssue:
    """A statement the parser could not fully consume.

    ``line`` is 1-based within the mermaid source block; ``text`` is the
    offending statement.
    """

    line: int
    text: str


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
    node_group: list[int | None] = field(default_factory=list)
    cur_group: int | None = None
    over_cap: bool = False
    dir: Dir = Dir.DOWN
    issues: list[ParseIssue] = field(default_factory=list)

    def node_index(self, id: str, label: str | None, shape: Shape) -> int | None:
        i = self.index.get(id)
        if i is not None:
            if label is not None:
                self.nodes[i].label = label
                self.nodes[i].shape = shape
            return i
        if len(self.nodes) >= MAX_NODES:
            self.over_cap = True
            return None
        self.index[id] = len(self.nodes)
        self.nodes.append(Node(label if label is not None else id, shape))
        self.node_group.append(self.cur_group)
        return len(self.nodes) - 1

    def node_label(self, id: str, label: str) -> int | None:
        i = self.index.get(id)
        if i is not None:
            self.nodes[i].label = label
            return i
        return self.node_index(id, label, Shape.ROUND)

    def over_capacity(self) -> bool:
        """Whether a size cap has been reached, even if a caller forgot to set ``over_cap``."""
        return self.over_cap or len(self.nodes) >= MAX_NODES or len(self.edges) >= MAX_EDGES


@dataclass
class ClassInfo:
    annotation: str | None = None
    attrs: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


def parse_dir(token: str) -> Dir:
    return {"LR": Dir.RIGHT, "RL": Dir.LEFT, "BT": Dir.UP}.get(token.upper(), Dir.DOWN)
