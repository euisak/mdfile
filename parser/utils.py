from __future__ import annotations

from .models import StepSnapshot
from .ui_components import _brief_queue, _brief_stack


def kind_to_korean(kind: str) -> str:
    if kind == "TEXT":
        return "일반"
    if kind == "BOLD":
        return "굵게"
    if kind == "ITALIC":
        return "기울임"
    if kind == "STRIKETHROUGH":
        return "취소선"
    if kind == "BOLD+ITALIC":
        return "굵게+기울임"
    if kind == "BOLD+STRIKETHROUGH":
        return "굵게+취소선"
    if kind == "ITALIC+STRIKETHROUGH":
        return "기울임+취소선"
    if kind == "BOLD+ITALIC+STRIKETHROUGH":
        return "굵게+기울임+취소선"
    return kind


def easy_trace_line(snap: StepSnapshot) -> str:
    consumed = snap.consumed if snap.consumed else "∅"
    remain = f"{snap.star_remaining}/{snap.star_total}" if snap.star_total is not None else "-"
    return (
        f"{snap.step_no:>3}. {consumed:<6} → {snap.action} | "
        f"스택 {_brief_stack(snap.stack)} | 큐 {_brief_queue(snap.queue)} | 남은* {remain}"
    )

