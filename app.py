import streamlit as st

from parser import chips, parse_with_visualization, pretty_queue, pretty_stack, render_tokens_to_html


APP_VERSION = "2026-04-26-v2"


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