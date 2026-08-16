"""The block vocabulary.

A section never draws anything. It returns blocks, and the renderers know how to
draw a block in Excel, PDF or PowerPoint. That is what makes a new client format
a template change instead of renderer work.

There are only five kinds, which is enough for every sheet in the DVA and CBH
workbooks:

    kpi     a stack of label/value pairs
    funnel  ordered stages, each with a count and a rate
    table   columns + rows, optionally with total/baseline emphasis
    matrix  a cross-tab (the "four boxes")
    text    a note, caveat or verdict
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Align = Literal["left", "right"]
Fmt = Literal["text", "number", "money", "pct", "pp", "delta", "multiple", "p", "int"]
Tone = Literal["neutral", "accent", "pos", "warn", "crit"]


@dataclass
class Col:
    key: str
    label: str
    fmt: Fmt = "text"
    align: Align = "left"
    decimals: int | None = None


@dataclass
class Item:
    label: str
    value: Any
    fmt: Fmt = "text"
    note: str | None = None
    tone: Tone = "neutral"


@dataclass
class Stage:
    label: str
    value: int
    rate: float | None = None
    of: str | None = None       # what the rate is a share of
    dim: bool = False


@dataclass
class Block:
    kind: Literal["kpi", "funnel", "table", "matrix", "text"]
    title: str | None = None
    subtitle: str | None = None
    items: list[Item] = field(default_factory=list)         # kpi
    stages: list[Stage] = field(default_factory=list)       # funnel
    columns: list[Col] = field(default_factory=list)        # table / matrix
    rows: list[dict] = field(default_factory=list)          # table / matrix
    body: str | None = None                                 # text
    notes: list[str] = field(default_factory=list)
    emphasis: dict[str, str] = field(default_factory=dict)  # row key -> "total" | "baseline" | "verdict"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Section:
    """One rendered section — a sheet in Excel, a page group in PDF."""
    key: str
    title: str
    blocks: list[Block] = field(default_factory=list)
    available: bool = True
    unavailable_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "blocks": [b.to_dict() for b in self.blocks],
        }


def kpi(title: str, items: list[Item], subtitle: str | None = None, notes: list[str] | None = None) -> Block:
    return Block(kind="kpi", title=title, subtitle=subtitle, items=items, notes=notes or [])


def funnel(title: str, stages: list[Stage], subtitle: str | None = None, notes: list[str] | None = None) -> Block:
    return Block(kind="funnel", title=title, subtitle=subtitle, stages=stages, notes=notes or [])


def table(title: str, columns: list[Col], rows: list[dict], subtitle: str | None = None,
          notes: list[str] | None = None, emphasis: dict[str, str] | None = None) -> Block:
    return Block(kind="table", title=title, subtitle=subtitle, columns=columns, rows=rows,
                 notes=notes or [], emphasis=emphasis or {})


def matrix(title: str, columns: list[Col], rows: list[dict], subtitle: str | None = None,
           notes: list[str] | None = None) -> Block:
    return Block(kind="matrix", title=title, subtitle=subtitle, columns=columns, rows=rows,
                 notes=notes or [])


def text(body: str, title: str | None = None) -> Block:
    return Block(kind="text", title=title, body=body)
