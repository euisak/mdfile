from __future__ import annotations

from typing import List, Sequence

import html

from .models import Token


def render_tokens_to_html(tokens: Sequence[Token]) -> str:
    out: List[str] = []
    for t in tokens:
        esc = html.escape(t.text).replace("\n", "<br/>").replace("*", "&#42;")
        s = set(t.styles)
        if "strike" in s:
            esc = f"<del>{esc}</del>"
        # 볼드를 먼저 감싼 뒤 이탤릭 → `<em><strong>…</strong></em>` (바깥 이탤릭 안쪽 볼드)
        if "bold" in s:
            esc = f"<strong>{esc}</strong>"
        if "italic" in s:
            esc = f"<em>{esc}</em>"
        out.append(esc)
    return "".join(out) if out else ""

