# Screenshots / Demo

Add 2–3 screenshots of the application here for the README demo section.

## Recommended screenshots

1. **`chat_rag_flow.png`** — The main chat interface mid-conversation, showing a RAG response
   with the citation/source card expanded. Demonstrates: streaming response, source traceability,
   and the medical disclaimer footer.

2. **`triage_emergency_overlay.png`** — The emergency overlay triggered by a cardiac or
   suicide-crisis query. Demonstrates: the safety layer intercepting before LLM generation,
   hardcoded emergency contact numbers, and the overlay UI component.

3. **`symptom_checker_results.png`** — The symptom checker card showing matched conditions,
   confidence scores, severity badge, and recommendations panel.

## How to capture them

Run the development server locally:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000` and use the browser's built-in screenshot tool
(Firefox: Ctrl+Shift+S full-page; Chrome: DevTools → Capture screenshot).

Save each file in this directory (`docs/screenshots/`) as a `.png`.
Then update the Screenshots section in `README.md` to point to them.

## Filename convention

```
docs/screenshots/chat_rag_flow.png
docs/screenshots/triage_emergency_overlay.png
docs/screenshots/symptom_checker_results.png
```
