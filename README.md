# Markdown Inline Parser Visualizer (Streamlit)

마크다운 인라인 서식 파서를 **스택/큐/토큰/렌더링**으로 실시간 시각화합니다.

## 지원 서식

- `**bold**`
- `*italic*` 또는 `_italic_`
- `***bold italic***`
- `~~strikethrough~~`
- 리터럴 별: `\*` (백슬래시 + 별)은 서식이 아니라 글자 `*`로 들어갑니다.

### `***…` / `**…` 한 줄 끝 패턴

본문 뒤에 나오는 **첫 닫는 별 런이 곧 줄(입력) 끝**이면, 열 때 쓴 별 `R`개와 닫는 별 `C`개로 `R−C`개는 **리터럴 `*`**, 나머지 `C`개는 **서식 열기**로 나눕니다.

- `***테스트*` → `**` 리터럴 + `*테스트*` 이탤릭  
- `***테스트**` → `*` 리터럴 + `**테스트**` 볼드  
- `**테스트*` → `*` 리터럴 + `*테스트*` 이탤릭  

닫는 별 뒤에 글자가 더 있으면(예: `***a**b*`) 이 규칙은 쓰지 않고, 통째 `***`·소급 분할 등 **기존 별 규칙**을 따릅니다.

명시적으로만 리터럴을 쓰고 싶을 때는 여전히 `\*` 이스케이프를 쓸 수 있습니다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 배포

### Streamlit Community Cloud

- GitHub에 이 폴더를 올린 뒤, Streamlit Cloud에서 새 앱을 생성합니다.
- **Main file path**는 `app.py`로 지정하면 됩니다.
- `requirements.txt`에 `streamlit`이 이미 포함되어 있어 추가 설정 없이 동작합니다.
- 배포된 앱: https://mdfile.streamlit.app
