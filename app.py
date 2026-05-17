import streamlit as st

from parser import chips, parse_with_visualization, pretty_queue, pretty_stack, render_tokens_to_html


APP_VERSION = "2026-04-26-v2"


def main() -> None:
    st.set_page_config(page_title="Markdown Inline Parser Visualizer", layout="wide")

    st.title("마크다운 인라인 서식 파서 시각화")
    st.caption(
        "지원: `**bold**`, `*italic*` / `_italic_`, `***bold italic***`, `~~strikethrough~~`, "
        "리터럴 별 `\\*` (테이블/헤딩/링크 제외)"
    )
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
        st.html(
            f"""
            <div style="
              border:1px solid rgba(0,0,0,.12);
              border-radius:14px;
              padding:14px 16px;
              background: rgba(255,255,255,1);
              font-size:18px;
              line-height:1.55;
            ">{html_out}</div>
            """.strip()
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
- **여는 `***`**: 처음에는 **쪼개지 않고** 스택에 `***` 한 덩어리로 올립니다. (단계: **여는 `***` 통째 푸시**)
- **열 별 런 + 줄 끝 첫 닫힘**: 본문 뒤 첫 닫는 별 런이 **입력 끝에서 끝나면**, 열 별 `R`개와 그 닫힘 `C`개로 **리터럴 `R−C`개 + 서식 `C`개**로 나눕니다. (예: `***테스트**` → `*` 리터럴 + `**` 볼드 열기)
- **닫을 때 `***` 소급 분할**: 닫는 별 런을 만나 TOP이 `***`이면, 그때 스택을 **소급해서** `*` / `**` 두 프레임으로 나눈 뒤 닫기를 진행합니다. (단계: **닫는 별 만남 → `***` 소급 분할** — 스택 튜플이 곧 아래→위 순서)
  - 닫는 런이 정확히 `**`이면(이때는 `*`만으로는 닫지 않음) → `[*, **]` (아래 `*`, 위 `**`)
  - 그 외(`*`, `***` 등) → `[**, *]` (아래 `**`, 위 `*`)
- **닫기 여부**: 스택의 별 개수 합(`*` 1, `**` 2, `***` 3)과 입력 별 런 길이로 닫기를 판단합니다. 입력이 정확히 `**`일 때는 `**`만 닫고 `*`는 건너뜁니다.
- **닫기**: 각 **팝 직전**에 큐를 `flush`합니다. 스택이 비면 남은 큐는 곧바로 TEXT로 확정합니다.
- 그 외 별 런은 기존처럼 `*` 한 개 + `**` 쌍으로 푸시합니다.
- `_`는 1개 단위로 이탤릭 토글, `~~`는 2글자 단위로 취소선 토글입니다.
- 렌더링: 이탤릭+볼드가 겹치면 HTML은 `<em><strong>…</strong></em>` 순서로 감쌉니다.
- **이스케이프**: `\\*`, `\\_`, `\\\\`는 각각 글자 `*`, `_`, `\\`로 큐에 들어갑니다. (예: `\\*`**굵게**` → 글자 `*` + 굵게)
            """.strip()
        )


if __name__ == "__main__":
    main()