from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Token:
    kind: str  # TEXT / BOLD / ITALIC / STRIKETHROUGH / BOLD+ITALIC / ...
    text: str
    styles: Tuple[str, ...]  # ("bold","italic","strike")


@dataclass(frozen=True)
class StepSnapshot:
    step_no: int
    at_index: int
    consumed: str
    action: str
    subject_label: str
    subject_value: str
    star_remaining: Optional[int]
    star_total: Optional[int]
    stack: Tuple[str, ...]
    queue: Tuple[str, ...]
    tokens: Tuple[Token, ...]


@dataclass(frozen=True)
class MarkerFrame:
    marker: str  # "*", "**", "***"(통째 여는 런), "_", "~~"
    q_start: int  # queue index where this marker opened

