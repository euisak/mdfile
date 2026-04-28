from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import html
import streamlit as st


MAX_STAR_RUN = 10_000
APP_VERSION = "2026-04-26-v2"


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
    marker: str  # "*", "**", "_", "~~"
    q_start: int  # queue index where this marker opened


def _count_run(s: str, i: int, ch: str, max_len: int) -> int:
    n = 0
    while i + n < len(s) and s[i + n] == ch and n < max_len:
        n += 1
    return n


def _detect_marker(s: str, i: int) -> Optional[str]:
    if s.startswith("~~", i):
        return "~~"
    if s[i] == "_":
        return "_"
    if s[i] == "*":
        # 연속 '*'는 길이에 제한 없이 하나의 런(run)으로 감지합니다.
        n = _count_run(s, i, "*", min(MAX_STAR_RUN, len(s) - i))
        return "*" * n
    return None


def _active_styles(stack: Sequence[MarkerFrame]) -> Tuple[str, ...]:
    # '*'는 '*' 또는 '**' 단위로 스택에 들어올 수 있습니다.
    count_star = sum(
        2 if f.marker == "**" else 1 for f in stack if f.marker in ("*", "**")
    )
    count_underscore = sum(1 for f in stack if f.marker == "_")
    count_strike = sum(1 for f in stack if f.marker == "~~")

    bold = ((count_star // 2) % 2) == 1
    italic = ((count_star % 2) == 1) ^ ((count_underscore % 2) == 1)
    strike = (count_strike % 2) == 1

    styles: List[str] = []
    if bold:
        styles.append("bold")
    if italic:
        styles.append("italic")
    if strike:
        styles.append("strike")
    return tuple(styles)


def _kind_from_styles(styles: Sequence[str]) -> str:
    s = set(styles)
    if not s:
        return "TEXT"
    parts: List[str] = []
    if "bold" in s:
        parts.append("BOLD")
    if "italic" in s:
        parts.append("ITALIC")
    if "strike" in s:
        parts.append("STRIKETHROUGH")
    return "+".join(parts)


def _kind_to_korean(kind: str) -> str:
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


def parse_with_visualization(md: str) -> Tuple[List[Token], List[StepSnapshot]]:
    stack: List[MarkerFrame] = []
    queue: List[str] = []
    tokens_with_pos: List[Tuple[int, Token]] = []
    steps: List[StepSnapshot] = []
    queue_base_pos = 0  # absolute plain-text position of queue[0]

    def _star_units_in_stack() -> int:
        return sum(
            2 if f.marker == "**" else 1 for f in stack if f.marker in ("*", "**")
        )

    def _stack_markers() -> Tuple[str, ...]:
        return tuple(f.marker for f in stack)

    def _tokens_sorted() -> Tuple[Token, ...]:
        return tuple(t for _, t in sorted(tokens_with_pos, key=lambda x: x[0]))

    def flush_queue_all(step_no: int, at_index: int, consumed: str) -> int:
        nonlocal tokens_with_pos, queue, queue_base_pos
        if queue:
            styles = _active_styles(stack)
            kind = _kind_from_styles(styles)
            text = "".join(queue)
            tokens_with_pos.append((queue_base_pos, Token(kind=kind, text=text, styles=styles)))
            queue_base_pos += len(queue)
            queue = []
            steps.append(
                StepSnapshot(
                    step_no=step_no,
                    at_index=at_index,
                    consumed=consumed,
                    action="큐 비우기 → 토큰 생성",
                    subject_label="확정된 글자",
                    subject_value=f"{text} → {_kind_to_korean(kind)}",
                    star_remaining=None,
                    star_total=None,
                    stack=_stack_markers(),
                    queue=tuple(queue),
                    tokens=_tokens_sorted(),
                )
            )
            return step_no + 1
        return step_no

    def _insert_literal_into_queue(idx: int, literal: str) -> None:
        """매칭 실패한 기호를 큐에 '문자'로 삽입하고, 아래에 남아있는 frame들의 q_start를 보정합니다."""
        nonlocal queue, stack
        if idx < 0:
            idx = 0
        if idx > len(queue):
            idx = len(queue)
        chars = list(literal)
        queue[idx:idx] = chars
        delta = len(chars)
        if delta:
            for k, f in enumerate(stack):
                if f.q_start >= idx:
                    stack[k] = MarkerFrame(marker=f.marker, q_start=f.q_start + delta)

    def _fail_top_frame(step_no: int, at_index: int, consumed: str, why: str) -> int:
        """스택 TOP을 매칭 실패로 처리해 큐에 되돌립니다."""
        if not stack:
            return step_no
        top = stack.pop()
        _insert_literal_into_queue(top.q_start, top.marker)
        steps.append(
            StepSnapshot(
                step_no=step_no,
                at_index=at_index,
                consumed=consumed,
                action=f"매칭 실패: {top.marker} → 문자로 처리",
                subject_label="스택에서 제거된 기호",
                subject_value=f"{top.marker} (실패: {why})",
                star_remaining=None,
                star_total=None,
                stack=_stack_markers(),
                queue=tuple(queue),
                tokens=_tokens_sorted(),
            )
        )
        return step_no + 1

    def flush_queue_range(
        step_no: int,
        at_index: int,
        consumed: str,
        start: int,
    ) -> int:
        nonlocal tokens_with_pos, queue, queue_base_pos
        if start < 0:
            start = 0
        if start < len(queue):
            # 현재 스택 전체 기준으로 스타일 계산
            styles = _active_styles(stack)
            kind = _kind_from_styles(styles)
            text = "".join(queue[start:])
            tokens_with_pos.append(
                (queue_base_pos + start, Token(kind=kind, text=text, styles=styles))
            )
            del queue[start:]
            steps.append(
                StepSnapshot(
                    step_no=step_no,
                    at_index=at_index,
                    consumed=consumed,
                    action="큐 비우기 → 토큰 생성",
                    subject_label="확정된 글자",
                    subject_value=f"{text} → {_kind_to_korean(kind)}",
                    star_remaining=None,
                    star_total=None,
                    stack=_stack_markers(),
                    queue=tuple(queue),
                    tokens=_tokens_sorted(),
                )
            )
            return step_no + 1
        return step_no

    i = 0
    step_no = 0
    while i < len(md):
        marker = _detect_marker(md, i)
        if marker is not None:
            if marker.startswith("*"):
                total = len(marker)
                remaining = total
                # 닫기 판단/처리:
                # - 입력이 정확히 `**`(2개)일 때는 `**`만 닫을 수 있고 `*`는 닫지 않습니다. (서로 다른 기호)
                # - 그 외(`*`, `***`, `****`...)는 TOP부터 가능한 만큼 닫되,
                #   현재 남은 별로 닫을 수 없는 프레임은 "매칭 실패"로 간주해 문자로 되돌리고 계속 탐색합니다.
                allow_close_star = total != 2
                closed_any = False

                while remaining > 0 and stack:
                    # TOP부터 내려가며 이번 remaining으로 닫을 수 있는 프레임을 찾습니다.
                    match_idx = None
                    for j in range(len(stack) - 1, -1, -1):
                        m = stack[j].marker
                        if m not in ("**", "*"):
                            break
                        if m == "*" and not allow_close_star:
                            continue
                        need = 2 if m == "**" else 1
                        if need <= remaining:
                            match_idx = j
                            break
                    if match_idx is None:
                        break

                    # match_idx 위에 있는(더 최근에 열린) 프레임들은 이번 remaining으로 닫을 수 없으므로 실패 처리
                    while len(stack) - 1 > match_idx:
                        step_no = _fail_top_frame(step_no, i, marker, "이번 별 개수로 닫을 수 없음")

                    top = stack[-1]
                    need = 2 if top.marker == "**" else 1

                    # 팝 직전: 해당 marker가 연 이후(q_start 이후) 텍스트만 토큰화
                    step_no = flush_queue_range(step_no, i, marker, start=top.q_start)
                    stack.pop()
                    remaining -= need
                    closed_any = True
                    steps.append(
                        StepSnapshot(
                            step_no=step_no,
                            at_index=i,
                            consumed=marker,
                            action=f"{marker}에서 {top.marker} 소비 → 팝",
                            subject_label="스택에서 제거된 기호",
                            subject_value=top.marker,
                            star_remaining=remaining,
                            star_total=total,
                            stack=_stack_markers(),
                            queue=tuple(queue),
                            tokens=_tokens_sorted(),
                        )
                    )
                    step_no += 1

                # 남은 별이 있거나, 애초에 닫을 게 없었던 경우는 "열기"로 푸시 (큐/토큰 건드리지 않음)
                if remaining > 0 or not closed_any:
                    while remaining >= 2:
                        stack.append(MarkerFrame(marker="**", q_start=len(queue)))
                        remaining -= 2
                        steps.append(
                            StepSnapshot(
                                step_no=step_no,
                                at_index=i,
                                consumed=marker,
                                action="푸시",
                                subject_label="스택에 추가된 기호",
                                subject_value="**",
                                star_remaining=remaining,
                                star_total=total,
                                stack=_stack_markers(),
                                queue=tuple(queue),
                                tokens=_tokens_sorted(),
                            )
                        )
                        step_no += 1
                    if remaining == 1:
                        stack.append(MarkerFrame(marker="*", q_start=len(queue)))
                        remaining -= 1
                        steps.append(
                            StepSnapshot(
                                step_no=step_no,
                                at_index=i,
                                consumed=marker,
                                action="푸시",
                                subject_label="스택에 추가된 기호",
                                subject_value="*",
                                star_remaining=remaining,
                                star_total=total,
                                stack=_stack_markers(),
                                queue=tuple(queue),
                                tokens=_tokens_sorted(),
                            )
                        )
                        step_no += 1

                i += len(marker)
                continue

            # 비-별표: 닫을 때만 큐 비우기
            closing = bool(stack) and stack[-1].marker == marker
            if closing:
                top = stack[-1]
                step_no = flush_queue_range(
                    step_no,
                    i,
                    marker,
                    start=top.q_start,
                )
                stack.pop()
                action = f"{marker} 닫기 → 팝"
            else:
                stack.append(MarkerFrame(marker=marker, q_start=len(queue)))
                action = f"푸시"

            steps.append(
                StepSnapshot(
                    step_no=step_no,
                    at_index=i,
                    consumed=marker,
                    action=action,
                    subject_label="스택에 추가된 기호" if action == "푸시" else "스택에서 제거된 기호",
                    subject_value=marker,
                    star_remaining=None,
                    star_total=None,
                    stack=_stack_markers(),
                    queue=tuple(queue),
                    tokens=_tokens_sorted(),
                )
            )
            step_no += 1
            i += len(marker)
            continue

        ch = md[i]
        queue.append(ch)
        steps.append(
            StepSnapshot(
                step_no=step_no,
                at_index=i,
                consumed=ch,
                action="문자 큐에 추가",
                subject_label="추가된 문자",
                subject_value=ch,
                star_remaining=None,
                star_total=None,
                stack=_stack_markers(),
                queue=tuple(queue),
                tokens=_tokens_sorted(),
            )
        )
        step_no += 1
        i += 1

    # 입력 끝: 남은 스택 프레임들은 전부 매칭 실패로 보고 문자로 되돌립니다.
    while stack:
        step_no = _fail_top_frame(step_no, len(md), "", "입력 끝까지 닫히지 않음")

    step_no = flush_queue_all(step_no, len(md), "")
    if steps and steps[-1].action.startswith("큐 비우기 → 토큰 생성"):
        # flush_queue가 남긴 snapshot은 star 정보가 없으므로 그대로 둡니다.
        pass
    steps.append(
        StepSnapshot(
            step_no=step_no,
            at_index=len(md),
            consumed="",
            action="완료",
            subject_label="",
            subject_value="",
            star_remaining=None,
            star_total=None,
            stack=_stack_markers(),
            queue=tuple(queue),
            tokens=_tokens_sorted(),
        )
    )
    return list(_tokens_sorted()), steps


def render_tokens_to_html(tokens: Sequence[Token]) -> str:
    out: List[str] = []
    for t in tokens:
        esc = html.escape(t.text).replace("\n", "<br/>")
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


def easy_trace_line(snap: StepSnapshot) -> str:
    consumed = snap.consumed if snap.consumed else "∅"
    remain = f"{snap.star_remaining}/{snap.star_total}" if snap.star_total is not None else "-"
    return (
        f"{snap.step_no:>3}. {consumed:<6} → {snap.action} | "
        f"스택 {_brief_stack(snap.stack)} | 큐 {_brief_queue(snap.queue)} | 남은* {remain}"
    )


def main() -> None:
    st.set_page_config(page_title="Markdown Inline Parser Visualizer", layout="wide")

    st.title("마크다운 인라인 서식 파서 시각화")
    st.caption("지원: `**bold**`, `*italic*` / `_italic_`, `***bold italic***`, `~~strikethrough~~` (테이블/헤딩/링크 제외)")
    st.caption(f"버전: `{APP_VERSION}`")

    default = "**bold** and *italic* and _italic_ and ***both*** and ~~strike~~"
    if "md_input" not in st.session_state:
        st.session_state.md_input = default

    md = st.text_area("입력", height=140, key="md_input")

    tokens, steps = parse_with_visualization(md)

    st.divider()

    if len(steps) <= 1:
        st.info("입력이 비어있어 단계가 없습니다.")
        return

    idx = st.slider("처리 단계 (step)", min_value=0, max_value=len(steps) - 1, value=len(steps) - 1)
    snap = steps[idx]

    colA, colB, colC = st.columns([1.1, 1.6, 1.3], gap="large")

    with colA:
        st.subheader("스택 뷰")
        st.markdown(pretty_stack(snap.stack), unsafe_allow_html=True)
        st.caption("선택 단계 기준: 현재 열려있는 서식 기호들 (TOP이 가장 최근)")

    with colB:
        st.subheader("큐 뷰")
        st.markdown(pretty_queue(snap.queue), unsafe_allow_html=True)
        st.caption("선택 단계 기준: 처리 대기 중인 일반 문자들")

    with colC:
        st.subheader("현재 처리 정보")
        st.markdown("**동작**")
        st.text(snap.action)
        if snap.subject_label:
            st.markdown(f"**{snap.subject_label}**")
            st.text(snap.subject_value if snap.subject_value else "(없음)")

    st.divider()

    st.subheader("렌더링 결과")
    html_out = render_tokens_to_html(snap.tokens)
    if html_out:
        st.markdown(
            f"""
            <div style="
              border:1px solid rgba(0,0,0,.12);
              border-radius:14px;
              padding:14px 16px;
              background: rgba(255,255,255,1);
              font-size:18px;
              line-height:1.55;
            ">{html_out}</div>
            """.strip(),
            unsafe_allow_html=True,
        )
    else:
        st.write("렌더링할 내용이 없습니다.")

    st.subheader("토큰 결과")
    if snap.tokens:
        st.markdown(chips(snap.tokens), unsafe_allow_html=True)
    else:
        st.write("토큰이 없습니다.")

    with st.expander("파서 규칙 요약"):
        st.markdown(
            """
- **닫기 여부**: 스택 안의 `*`/`**`가 나타내는 **별 개수 합**을 세고, 입력 연속 `*` 개수가 그 합 **이하**이면 닫기로 봅니다. (예: 스택 `[*, **]` → 합 3 → `***`는 닫기)
- **닫기**: 각 **팝 직전**에 `flush_queue`로 큐를 비웁니다. 이때 스택은 아직 맨 위 구분자가 남아 있으므로, `테스트`는 `[*, **]` 기준으로 **BOLD+ITALIC**으로 토큰화됩니다.
- **열기**: `*`만 열린 채 `**`를 열 때는 **푸시 전**에 큐를 비워 `시험`을 **ITALIC**만으로 확정합니다.
- 닫은 뒤 남은 별은 `**`·`*` 단위로 푸시합니다.
- `_`는 1개 단위로 이탤릭 토글, `~~`는 2글자 단위로 취소선 토글입니다.
- 큐의 텍스트는 **flush 시점의 활성 스타일(스택 기준)** 로 토큰화됩니다.
- 렌더링: 이탤릭+볼드가 겹치면 HTML은 `<em><strong>…</strong></em>` 순서로 감쌉니다.
            """.strip()
        )


if __name__ == "__main__":
    main()