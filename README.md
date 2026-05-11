# Markdown Inline Parser Visualizer (Streamlit)

마크다운 인라인 서식 파서를 **스택/큐/토큰/렌더링**으로 실시간 시각화합니다.

## 지원 서식

- `**bold**`
- `*italic*` 또는 `_italic_`
- `***bold italic***`
- `~~strikethrough~~`

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
