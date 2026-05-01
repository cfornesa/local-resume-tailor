# Project Memory

Key facts and context that are not obvious from reading the code alone.

---

## What this project is

A local desktop application for tailoring a resume to a specific job description using a locally-run LLM. The user uploads their PDF resume, provides job context, and the model rewrites the resume to better match the role — without inventing or removing any information.

The application is built for the creator's personal use but distributed publicly via a macOS DMG and a Windows VBS launcher.

---

## The example resume

`EXAMPLE.md` contains a real resume (Christopher Fornesa, MS Data Science) used as the canonical test case throughout development. The validation rules in `resume_core.py` — particularly the section headers, `|`-delimited entry lines, and bullet point patterns — were designed around this resume's structure. Any significant change to how the resume is formatted may require updates to the validation logic.

---

## Why `|` is used as an entry delimiter

The source resume uses `|` as a separator within title lines (e.g. `Company | Role | Date`). The validation layer treats any line containing `|` as a "required line" in EDUCATION, EXPERIENCE, and PROJECTS sections. This is not a universal resume convention — it is specific to the format used in the example resume. If a user's resume uses a different delimiter (e.g. `—` or tabs), those lines will not be treated as required by the validator.

---

## Thinking model behaviour

Reasoning models (DeepSeek R1, Gemma 3, QwQ, and others) wrap their chain-of-thought in `<think>…</think>` XML tags before producing the actual resume. The `strip_think_streaming` function handles this incrementally during streaming:
- While the `<think>` block is open (incomplete), the output field shows `"Thinking..."`.
- Once `</think>` is seen, the reasoning block is stripped and the resume text takes over.
- The final output strips all think blocks with a regex before yielding.

---

## Gradio server start-up timing

`resume.py` starts the Gradio server in a daemon thread, then calls `time.sleep(2)` before creating the pywebview window. This 2-second wait is a hardcoded delay to give Gradio time to bind to port 7860 before the window tries to load `http://127.0.0.1:7860`. If Gradio takes longer to start (slow machine, high system load), the window may open to a blank page. The fix would be to poll the port rather than sleeping.

---

## The `_stream_ollama` helper is unused

`resume_core.py` contains a `_stream_ollama` helper function that was written as a refactor target but never integrated. The actual streaming is implemented inline in `tailor_resume`, `refine_resume`, `ask_about_resume`, and `summarize_changes`. The helper can be removed or used to DRY up those functions in a future refactor.

---

## PyMuPDF is loaded via LangChain

The dependency chain is `langchain-community` → `PyMuPDFLoader` → `pymupdf`. Only `PyMuPDFLoader` is used from LangChain — no chains, embeddings, or other LangChain features are in use. A future simplification could remove the LangChain dependency and call `pymupdf` (fitz) directly.

---

## macOS launcher uses `arch -arm64`

The launcher script at `Resume Tailor.app/Contents/MacOS/Resume Tailor` runs:

```bash
arch -arm64 python3 resume.py
```

This forces the process onto Apple Silicon even if Rosetta is available. If the user's Python 3 is an x86_64 build without an arm64 slice, this will fail. The assumption is that users on Apple Silicon have an arm64 Python 3 installed (e.g. from Homebrew or python.org universal installer).

---

## Port 7860 is hardcoded

The Gradio server always binds to `127.0.0.1:7860`. If another process is already using this port (e.g. a previous instance of the app left running), the new instance will fail to start. There is no automatic port fallback or conflict detection.

---

## Gradio version pinned to 6.13.0

`requirements.txt` pins Gradio to `6.13.0`. Key version-specific behaviours:
- `show_copy_button` on `gr.Textbox` does **not** exist — copy is implemented via JS buttons.
- `gr.Row` can be toggled visible/invisible via event outputs.
- Generator functions that yield tuples map positionally to `outputs=[...]` in `.click()`.
- `gr.update()` with no arguments is the no-op sentinel for state components during streaming.

---

## Resume state is a `gr.State`, not a Python variable

The current tailored resume text is stored in `resume_state = gr.State(value=None)` inside the `gr.Blocks` context. This means:
- Each browser session (each pywebview window instance) has its own isolated state.
- State is not shared between runs or persisted to disk.
- Refresh Resume and Refresh Insights both read `resume_state` as an input, so they always operate on the most recently generated resume.
- Ask mode reads but never writes `resume_state`.
