"""
Backward-compatibility shim.

기존 `md_inline_parser.py` import를 깨지 않기 위해 `parser/` 패키지로 이동한 API를 재-export합니다.
"""

from parser import (  # noqa: F401
    MarkerFrame,
    StepSnapshot,
    Token,
    chips,
    easy_trace_line,
    kind_to_korean,
    parse_with_visualization,
    pretty_queue,
    pretty_stack,
    render_tokens_to_html,
)

__all__ = [
    "MarkerFrame",
    "StepSnapshot",
    "Token",
    "chips",
    "easy_trace_line",
    "kind_to_korean",
    "parse_with_visualization",
    "pretty_queue",
    "pretty_stack",
    "render_tokens_to_html",
]

