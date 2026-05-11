from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .models import MarkerFrame, StepSnapshot, Token
from .utils import kind_to_korean

MAX_STAR_RUN = 10_000


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


def _first_star_run_len_after_text(s: str, start: int) -> Optional[int]:
    """`start`부터 다음 `*` 연속 런의 길이. 없으면 None.

    CommonMark는 `***`를 열 때 뒤에서 **먼저 닫히는 별 런이 `*`인지 `**`인지**에 따라
    `[**, *]` vs `[*, **]` 중 하나를 택하는데, 여기서는 그 휴리스틱만 흉내 냅니다.
    (첫 별 런이 `*` 한 개면 볼드가 바깥 `[**, *]`, 그렇지 않으면 이탤릭이 바깥 `[*, **]`.)
    """
    pos = start
    n = len(s)
    while pos < n and s[pos] != "*":
        pos += 1
    if pos >= n:
        return None
    return _count_run(s, pos, "*", min(MAX_STAR_RUN, n - pos))


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


def parse_with_visualization(md: str) -> Tuple[List[Token], List[StepSnapshot]]:
    stack: List[MarkerFrame] = []
    queue: List[str] = []
    tokens_with_pos: List[Tuple[int, Token]] = []
    steps: List[StepSnapshot] = []
    queue_base_pos = 0  # absolute plain-text position of queue[0]

    def _stack_markers() -> Tuple[str, ...]:
        return tuple(f.marker for f in stack)

    def _tokens_sorted() -> Tuple[Token, ...]:
        return tuple(t for _, t in sorted(tokens_with_pos, key=lambda x: x[0]))

    def _snapshot(
        *,
        step_no: int,
        at_index: int,
        consumed: str,
        action: str,
        subject_label: str,
        subject_value: str,
        star_remaining: Optional[int] = None,
        star_total: Optional[int] = None,
    ) -> StepSnapshot:
        return StepSnapshot(
            step_no=step_no,
            at_index=at_index,
            consumed=consumed,
            action=action,
            subject_label=subject_label,
            subject_value=subject_value,
            star_remaining=star_remaining,
            star_total=star_total,
            stack=_stack_markers(),
            queue=tuple(queue),
            tokens=_tokens_sorted(),
        )

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
                _snapshot(
                    step_no=step_no,
                    at_index=at_index,
                    consumed=consumed,
                    action="큐 비우기 → 토큰 생성",
                    subject_label="확정된 글자",
                    subject_value=f"{text} → {kind_to_korean(kind)}",
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
            _snapshot(
                step_no=step_no,
                at_index=at_index,
                consumed=consumed,
                action=f"매칭 실패: {top.marker} → 문자로 처리",
                subject_label="스택에서 제거된 기호",
                subject_value=f"{top.marker} (실패: {why})",
            )
        )
        return step_no + 1

    def flush_queue_range(step_no: int, at_index: int, consumed: str, start: int) -> int:
        nonlocal tokens_with_pos, queue, queue_base_pos
        if start < 0:
            start = 0
        if start < len(queue):
            styles = _active_styles(stack)
            kind = _kind_from_styles(styles)
            text = "".join(queue[start:])
            flushed_len = len(queue) - start
            tokens_with_pos.append((queue_base_pos + start, Token(kind=kind, text=text, styles=styles)))
            del queue[start:]
            # `flush_queue_all`과 같이, 큐가 비면 다음 글자의 절대 위치를 진행합니다.
            # 안 하면 토큰 (pos)가 겹쳐 정렬될 때 순서가 원문과 어긋납니다.
            if not queue:
                queue_base_pos += start + flushed_len
            steps.append(
                _snapshot(
                    step_no=step_no,
                    at_index=at_index,
                    consumed=consumed,
                    action="큐 비우기 → 토큰 생성",
                    subject_label="확정된 글자",
                    subject_value=f"{text} → {kind_to_korean(kind)}",
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

                    while len(stack) - 1 > match_idx:
                        step_no = _fail_top_frame(step_no, i, marker, "이번 별 개수로 닫을 수 없음")

                    top = stack[-1]
                    need = 2 if top.marker == "**" else 1

                    step_no = flush_queue_range(step_no, i, marker, start=top.q_start)
                    stack.pop()
                    remaining -= need
                    closed_any = True
                    steps.append(
                        _snapshot(
                            step_no=step_no,
                            at_index=i,
                            consumed=marker,
                            action=f"{marker}에서 {top.marker} 소비 → 팝",
                            subject_label="스택에서 제거된 기호",
                            subject_value=top.marker,
                            star_remaining=remaining,
                            star_total=total,
                        )
                    )
                    step_no += 1

                # 접미사만 flush한 뒤 스택이 비면, 앞에 남은 글자는 더 이상 어떤
                # 서식에도 속하지 않으므로 즉시 TEXT로 확정합니다. (그렇지 않으면
                # `*a*` 뒤의 ` and ` 같은 접두가 큐에 쌓여 이후에 한꺼번에 붙습니다.)
                if not stack and queue:
                    step_no = flush_queue_all(step_no, i, marker)

                if remaining > 0 or not closed_any:
                    # `***`만: 뒤에서 첫 별 런이 `*` 한 개면 `[**, *]`(볼드 바깥),
                    # 아니면 `[*, **]`(이탤릭 바깥)으로 엽니다. (CommonMark 휴리스틱 단순화)
                    triple_open_handled = False
                    if total == 3 and remaining == 3:
                        nxt = _first_star_run_len_after_text(md, i + len(marker))
                        if nxt == 1:
                            triple_open_handled = True
                            stack.append(MarkerFrame(marker="**", q_start=len(queue)))
                            remaining -= 2
                            steps.append(
                                _snapshot(
                                    step_no=step_no,
                                    at_index=i,
                                    consumed=marker,
                                    action="푸시",
                                    subject_label="스택에 추가된 기호",
                                    subject_value="**",
                                    star_remaining=remaining,
                                    star_total=total,
                                )
                            )
                            step_no += 1
                            stack.append(MarkerFrame(marker="*", q_start=len(queue)))
                            remaining -= 1
                            steps.append(
                                _snapshot(
                                    step_no=step_no,
                                    at_index=i,
                                    consumed=marker,
                                    action="푸시",
                                    subject_label="스택에 추가된 기호",
                                    subject_value="*",
                                    star_remaining=remaining,
                                    star_total=total,
                                )
                            )
                            step_no += 1
                    if not triple_open_handled:
                        # 홀수 런: 먼저 `*` 한 개, 나머지는 `**` 쌍 → `***a**b*` 등
                        if remaining % 2 == 1:
                            stack.append(MarkerFrame(marker="*", q_start=len(queue)))
                            remaining -= 1
                            steps.append(
                                _snapshot(
                                    step_no=step_no,
                                    at_index=i,
                                    consumed=marker,
                                    action="푸시",
                                    subject_label="스택에 추가된 기호",
                                    subject_value="*",
                                    star_remaining=remaining,
                                    star_total=total,
                                )
                            )
                            step_no += 1
                        while remaining >= 2:
                            stack.append(MarkerFrame(marker="**", q_start=len(queue)))
                            remaining -= 2
                            steps.append(
                                _snapshot(
                                    step_no=step_no,
                                    at_index=i,
                                    consumed=marker,
                                    action="푸시",
                                    subject_label="스택에 추가된 기호",
                                    subject_value="**",
                                    star_remaining=remaining,
                                    star_total=total,
                                )
                            )
                            step_no += 1

                i += len(marker)
                continue

            closing = bool(stack) and stack[-1].marker == marker
            if closing:
                top = stack[-1]
                step_no = flush_queue_range(step_no, i, marker, start=top.q_start)
                stack.pop()
                action = f"{marker} 닫기 → 팝"
                subject_label = "스택에서 제거된 기호"
            else:
                stack.append(MarkerFrame(marker=marker, q_start=len(queue)))
                action = "푸시"
                subject_label = "스택에 추가된 기호"

            steps.append(
                _snapshot(
                    step_no=step_no,
                    at_index=i,
                    consumed=marker,
                    action=action,
                    subject_label=subject_label,
                    subject_value=marker,
                )
            )
            step_no += 1
            if not stack and queue:
                step_no = flush_queue_all(step_no, i, marker)
            i += len(marker)
            continue

        ch = md[i]
        queue.append(ch)
        steps.append(
            _snapshot(
                step_no=step_no,
                at_index=i,
                consumed=ch,
                action="문자 큐에 추가",
                subject_label="추가된 문자",
                subject_value=ch,
            )
        )
        step_no += 1
        i += 1

    while stack:
        step_no = _fail_top_frame(step_no, len(md), "", "입력 끝까지 닫히지 않음")

    step_no = flush_queue_all(step_no, len(md), "")
    steps.append(
        _snapshot(
            step_no=step_no,
            at_index=len(md),
            consumed="",
            action="완료",
            subject_label="",
            subject_value="",
        )
    )
    return list(_tokens_sorted()), steps

