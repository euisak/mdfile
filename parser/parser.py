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
        n = _count_run(s, i, "*", min(MAX_STAR_RUN, len(s) - i))
        return "*" * n
    return None


def _first_star_run_after_index(s: str, start: int) -> Optional[Tuple[int, int]]:
    """`start` 이후 첫 `*` 연속 런의 (시작 인덱스, 길이). `s`는 단일 줄(\\n 없음)."""
    pos = start
    n = len(s)
    while pos < n and s[pos] != "*":
        pos += 1
    if pos >= n:
        return None
    ln = _count_run(s, pos, "*", min(MAX_STAR_RUN, n - pos))
    return (pos, ln)


def _active_styles(stack: Sequence[MarkerFrame]) -> Tuple[str, ...]:
    count_star = 0
    for f in stack:
        if f.marker == "**":
            count_star += 2
        elif f.marker == "***":
            count_star += 3
        elif f.marker == "*":
            count_star += 1
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


def _parse_single_line(line: str, step_no_start: int = 0) -> Tuple[List[Token], List[StepSnapshot], int]:
    """단일 줄(\\n 없음)을 파싱합니다. (tokens, steps, next_step_no) 반환."""
    stack: List[MarkerFrame] = []
    queue: List[str] = []
    tokens_with_pos: List[Tuple[int, Token]] = []
    steps: List[StepSnapshot] = []
    queue_base_pos = 0
    step_no = step_no_start

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
    while i < len(line):
        marker = _detect_marker(line, i)
        if marker is not None:
            if marker.startswith("*"):
                total = len(marker)
                remaining = total
                allow_close_star = total != 2
                closed_any = False

                while remaining > 0 and stack:
                    if stack[-1].marker == "***":
                        q0 = stack[-1].q_start
                        stack.pop()
                        if total == 2 and not allow_close_star:
                            stack.append(MarkerFrame(marker="*", q_start=q0))
                            stack.append(MarkerFrame(marker="**", q_start=q0))
                            split_desc = "[*, **] (아래 `*`, 위 `**`)"
                        else:
                            stack.append(MarkerFrame(marker="**", q_start=q0))
                            stack.append(MarkerFrame(marker="*", q_start=q0))
                            split_desc = "[**, *] (아래 `**`, 위 `*`)"
                        steps.append(
                            _snapshot(
                                step_no=step_no,
                                at_index=i,
                                consumed=marker,
                                action="닫는 별 만남 → `***` 소급 분할",
                                subject_label="스택 (아래→위)",
                                subject_value=f"{split_desc} → {_stack_markers()}",
                                star_remaining=remaining,
                                star_total=total,
                            )
                        )
                        step_no += 1
                        continue

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

                if not stack and queue:
                    step_no = flush_queue_all(step_no, i, marker)

                if remaining > 0 or not closed_any:
                    fc = _first_star_run_after_index(line, i + total)
                    used_lookahead = False
                    if fc is not None:
                        close_pos, C = fc
                        R = remaining
                        # 줄 끝 = len(line) (단일 줄이므로 \n 탐색 불필요)
                        at_end = close_pos + C >= len(line)
                        if R >= C and at_end:
                            _cur = sum(
                                3 if f.marker == "***" else 2 if f.marker == "**" else 1
                                for f in stack if f.marker in ("*", "**", "***")
                            )
                            if not closed_any and _cur % 2 == 1 and (_cur + C) % 2 == 0:
                                queue.extend(["*"] * remaining)
                                steps.append(
                                    _snapshot(
                                        step_no=step_no,
                                        at_index=i,
                                        consumed=marker,
                                        action="이탤릭 충돌 → 전체 리터럴로 처리",
                                        subject_label="리터럴 별",
                                        subject_value=f"{remaining}개",
                                        star_remaining=0,
                                        star_total=total,
                                    )
                                )
                                step_no += 1
                                remaining = 0
                            else:
                                used_lookahead = True
                                lit = R - C
                                if lit > 0:
                                    queue.extend(["*"] * lit)
                                    steps.append(
                                        _snapshot(
                                            step_no=step_no,
                                            at_index=i,
                                            consumed="*" * lit,
                                            action="열 별 런 분해 → 리터럴 `*` 큐에 추가",
                                            subject_label="리터럴 별",
                                            subject_value=f"{lit}개",
                                            star_remaining=remaining,
                                            star_total=total,
                                        )
                                    )
                                    step_no += 1
                                q0 = len(queue)
                                rem_op = C
                                if rem_op == 3:
                                    stack.append(MarkerFrame(marker="***", q_start=q0))
                                    steps.append(
                                        _snapshot(
                                            step_no=step_no,
                                            at_index=i,
                                            consumed=marker,
                                            action="여는 `***` 통째 푸시",
                                            subject_label="스택에 추가된 기호",
                                            subject_value="*** (쪼개지 않음)",
                                            star_remaining=0,
                                            star_total=total,
                                        )
                                    )
                                    step_no += 1
                                    rem_op = 0
                                while rem_op >= 2:
                                    stack.append(MarkerFrame(marker="**", q_start=q0))
                                    rem_op -= 2
                                    steps.append(
                                        _snapshot(
                                            step_no=step_no,
                                            at_index=i,
                                            consumed=marker,
                                            action="푸시",
                                            subject_label="스택에 추가된 기호",
                                            subject_value="**",
                                            star_remaining=rem_op,
                                            star_total=total,
                                        )
                                    )
                                    step_no += 1
                                if rem_op == 1:
                                    stack.append(MarkerFrame(marker="*", q_start=q0))
                                    steps.append(
                                        _snapshot(
                                            step_no=step_no,
                                            at_index=i,
                                            consumed=marker,
                                            action="푸시",
                                            subject_label="스택에 추가된 기호",
                                            subject_value="*",
                                            star_remaining=0,
                                            star_total=total,
                                        )
                                    )
                                    step_no += 1
                                remaining = 0
                    if not used_lookahead:
                        if not closed_any and fc is None:
                            while remaining > 0 and stack:
                                top = stack[-1]
                                if top.marker not in ("*", "**"):
                                    break
                                frame_need = 2 if top.marker == "**" else 1
                                used = min(frame_need, remaining)
                                lit = frame_need - used
                                if lit > 0:
                                    _insert_literal_into_queue(top.q_start, "*" * lit)
                                    flush_start = top.q_start + lit
                                else:
                                    flush_start = top.q_start
                                step_no = flush_queue_range(step_no, i, marker, start=flush_start)
                                stack.pop()
                                steps.append(
                                    _snapshot(
                                        step_no=step_no,
                                        at_index=i,
                                        consumed=marker,
                                        action=f"부분 닫기: {top.marker} ({used}개 소비)",
                                        subject_label="스택에서 제거된 기호",
                                        subject_value=top.marker,
                                        star_remaining=remaining - used,
                                        star_total=total,
                                    )
                                )
                                step_no += 1
                                remaining -= used
                                closed_any = True
                            if remaining > 0 and closed_any:
                                queue.extend(["*"] * remaining)
                                steps.append(
                                    _snapshot(
                                        step_no=step_no,
                                        at_index=i,
                                        consumed="*" * remaining,
                                        action="닫는 별 잉여분 → 리터럴로 추가",
                                        subject_label="리터럴 별",
                                        subject_value=f"{remaining}개",
                                        star_remaining=0,
                                        star_total=total,
                                    )
                                )
                                step_no += 1
                                remaining = 0
                        if remaining == 3:
                            stack.append(MarkerFrame(marker="***", q_start=len(queue)))
                            remaining = 0
                            steps.append(
                                _snapshot(
                                    step_no=step_no,
                                    at_index=i,
                                    consumed=marker,
                                    action="여는 `***` 통째 푸시",
                                    subject_label="스택에 추가된 기호",
                                    subject_value="*** (쪼개지 않음)",
                                    star_remaining=remaining,
                                    star_total=total,
                                )
                            )
                            step_no += 1
                        else:
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

        if line[i] == "\\" and i + 1 < len(line):
            at_idx = i
            nxt = line[i + 1]
            if nxt == "\\":
                queue.append("\\")
                consumed = "\\\\"
                i += 2
            elif nxt == "*":
                queue.append("*")
                consumed = "\\*"
                i += 2
            elif nxt == "_":
                queue.append("_")
                consumed = "\\_"
                i += 2
            else:
                queue.append("\\")
                consumed = "\\"
                i += 1
            steps.append(
                _snapshot(
                    step_no=step_no,
                    at_index=at_idx,
                    consumed=consumed,
                    action="이스케이프 → 문자로 추가",
                    subject_label="추가된 문자",
                    subject_value=consumed,
                )
            )
            step_no += 1
            continue

        ch = line[i]
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
        step_no = _fail_top_frame(step_no, len(line), "", "입력 끝까지 닫히지 않음")

    step_no = flush_queue_all(step_no, len(line), "")
    steps.append(
        _snapshot(
            step_no=step_no,
            at_index=len(line),
            consumed="",
            action="완료",
            subject_label="",
            subject_value="",
        )
    )
    step_no += 1
    return list(_tokens_sorted()), steps, step_no


def parse_with_visualization(md: str) -> Tuple[List[Token], List[StepSnapshot]]:
    """입력을 줄 단위로 분리해 각각 파싱한 뒤 결합합니다."""
    lines = md.split("\n")
    all_tokens: List[Token] = []
    all_steps: List[StepSnapshot] = []
    step_no = 0

    for line_idx, line in enumerate(lines):
        # 이전 줄들의 토큰을 각 스냅샷 앞에 붙여 누적 상태를 유지합니다.
        prefix = tuple(all_tokens)

        line_tokens, line_steps, step_no = _parse_single_line(line, step_no)

        for s in line_steps:
            all_steps.append(
                StepSnapshot(
                    step_no=s.step_no,
                    at_index=s.at_index,
                    consumed=s.consumed,
                    action=s.action,
                    subject_label=s.subject_label,
                    subject_value=s.subject_value,
                    star_remaining=s.star_remaining,
                    star_total=s.star_total,
                    stack=s.stack,
                    queue=s.queue,
                    tokens=prefix + s.tokens,
                )
            )

        all_tokens.extend(line_tokens)

        if line_idx < len(lines) - 1:
            all_tokens.append(Token(kind="TEXT", text="\n", styles=()))
            all_steps.append(
                StepSnapshot(
                    step_no=step_no,
                    at_index=len(line),
                    consumed="\n",
                    action="줄 바꿈 → 다음 줄",
                    subject_label="추가된 문자",
                    subject_value="\\n",
                    star_remaining=None,
                    star_total=None,
                    stack=(),
                    queue=(),
                    tokens=tuple(all_tokens),
                )
            )
            step_no += 1

    return all_tokens, all_steps
