from __future__ import annotations

from typing import List, Sequence

import html

from .models import Token


def chips(tokens: Sequence[Token]) -> str:
    parts: List[str] = []
    for t in tokens:
        label = html.escape(t.kind)
        text = html.escape(t.text).replace("\n", "⏎")
        parts.append(
            f"""
            <div style="
              display:inline-flex; gap:8px; align-items:center;
              border:1px solid rgba(0,0,0,.12);
              padding:6px 10px; border-radius:999px;
              margin:4px 6px 4px 0;
              background: rgba(248,250,252,1);
              font-family: ui-sans-serif, system-ui, -apple-system;
              ">
              <span style="
                font-size:12px; padding:2px 8px; border-radius:999px;
                background: rgba(37,99,235,.12);
                color: rgba(29,78,216,1);
                border:1px solid rgba(37,99,235,.20);
              ">{label}</span>
              <span style="font-size:14px; color: rgba(15,23,42,1);">{text}</span>
            </div>
            """.strip()
        )
    return "<div>" + "\n".join(parts) + "</div>"


def pretty_stack(stack: Sequence[str]) -> str:
    if not stack:
        return """
        <div style="
          border:1px dashed rgba(0,0,0,.22);
          background: rgba(248,250,252,1);
          padding:14px 12px;
          border-radius:12px;
          color: rgba(100,116,139,1);
          font-family: ui-sans-serif, system-ui, -apple-system;
        ">
          비어있음
        </div>
        """.strip()
    rows = []
    for idx, m in enumerate(reversed(stack), start=1):
        rows.append(
            f"""
            <div style="
              border:1px solid rgba(0,0,0,.12);
              background: rgba(255,255,255,1);
              padding:8px 10px; border-radius:10px;
              margin-bottom:8px;
              font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            ">
              <div style="font-size:12px; color: rgba(100,116,139,1);">TOP-{idx}</div>
              <div style="font-size:18px; font-weight:700;">{html.escape(m)}</div>
            </div>
            """.strip()
        )
    return "\n".join(rows)


def pretty_queue(queue: Sequence[str]) -> str:
    if not queue:
        return """
        <div style="
          border:1px dashed rgba(0,0,0,.22);
          background: rgba(248,250,252,1);
          padding:14px 12px;
          border-radius:12px;
          color: rgba(100,116,139,1);
          font-family: ui-sans-serif, system-ui, -apple-system;
        ">
          비어있음
        </div>
        """.strip()
    items = []
    for ch in queue:
        show = "␠" if ch == " " else ("⏎" if ch == "\n" else ch)
        items.append(
            f"""
            <span style="
              display:inline-block;
              border:1px solid rgba(0,0,0,.12);
              background: rgba(255,255,255,1);
              padding:6px 8px; border-radius:10px;
              margin:0 6px 6px 0;
              font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            ">{html.escape(show)}</span>
            """.strip()
        )
    return "<div style='display:flex; flex-wrap:wrap;'>" + "\n".join(items) + "</div>"


def _brief_stack(stack: Sequence[str], limit: int = 6) -> str:
    if not stack:
        return "[]"
    show = list(stack[-limit:])
    prefix = ["…"] if len(stack) > limit else []
    return "[" + ", ".join(prefix + show) + "]"


def _brief_queue(queue: Sequence[str], limit: int = 10) -> str:
    if not queue:
        return "[]"
    show = list(queue[:limit])
    suffix = ["…"] if len(queue) > limit else []
    pretty = []
    for ch in show:
        if ch == " ":
            pretty.append("␠")
        elif ch == "\n":
            pretty.append("⏎")
        else:
            pretty.append(ch)
    return "[" + ", ".join(pretty + suffix) + "]"

