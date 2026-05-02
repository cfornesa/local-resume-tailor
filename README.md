# Resume Tailor

A local, private resume tailoring tool. Upload your PDF resume, select a model, and paste a job description — the model rewrites your resume to better match the role without inventing or removing any information.

Runs as a native desktop window. All inference happens on your machine — your resume never leaves your device.

## How it works

- Extracts text from your uploaded PDF resume
- Sends the resume and job description to whichever Ollama model you select
- Validates the output against the source to catch hallucinations or structural changes
- Retries once if validation errors are found, then returns the best candidate
- Applies conservative Python-based ATS keyword improvements when they can be made without breaking validation
- Appends a deterministic ATS Compatibility Report covering format, structure, and keyword coverage
- Returns a plain-text tailored resume

## Prerequisites

- [Ollama](https://ollama.com) — runs AI models locally
- [Python 3](https://python.org) — runs the app
- At least one model pulled in Ollama (e.g. `ollama pull deepseek-r1:7b`)

## Installation

### macOS

1. Download [`Resume Tailor.dmg`](Resume%20Tailor.dmg) from this repository
2. Open the DMG, drag **Resume Tailor** to your Applications folder, then double-click it

> On first open, macOS may show a security warning because the app is not notarized. Right-click `Resume Tailor` → **Open** → **Open** to bypass it once. Normal double-clicking works from then on.

### Windows

1. Download `Resume Tailor.exe` from this repository
2. Run the installer — it will warn you if Ollama or Python is missing before proceeding
3. Click the **Resume Tailor** shortcut on your Desktop

> On first launch a small "Installing dependencies…" window will appear briefly while Python packages are installed. This is expected. The app window will open automatically once it closes.

See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for build instructions and troubleshooting.

---

On first launch (both platforms), Python dependencies are installed automatically. If Ollama or Python is not installed, a native dialog will tell you what's missing.

## Usage

1. Select a model from the dropdown (populated from your locally installed Ollama models)
2. Upload your PDF resume
3. Paste the job description into the text box
4. Click **Submit** — the tailored resume streams into the output panel
   - Reasoning models (e.g. DeepSeek R1, Gemma) will show **Thinking...** while reasoning before the resume text begins streaming
5. Click **Stop** at any time to cancel generation cleanly
   - After streaming ends, the app silently validates and optionally retries the output. The output border may pulse for up to a minute during this phase — this is normal.
6. Review the ATS Compatibility Report in **Insights & Answers**
   - The report is computed locally in Python from the final resume and job description
   - Use **↑ Improve ATS** to run a Python-first keyword integration pass on the current resume; the model is used only as a fallback if deterministic edits cannot improve coverage

See [EXAMPLE.md](EXAMPLE.md) for sample input and output.

## Technical Details

### Repository layout

```
Resume Tailor.dmg              ← macOS installer — download this to install on Mac
Resume Tailor.app/             ← macOS app bundle (used by build_dmg.sh to produce the DMG)
├── Contents/
│   ├── Info.plist             ← Bundle metadata (ID, display name, icon reference)
│   ├── MacOS/
│   │   └── Resume Tailor      ← Shell script: checks deps, pip-installs, launches resume.py
│   └── Resources/
│       └── AppIcon.icns       ← macOS app icon
Resume Tailor.vbs              ← Windows launcher — checks Ollama/Python, pip-installs, launches resume.py
build_exe.iss                  ← Inno Setup script — compiles into Resume Tailor.exe
build_dmg.sh                   ← Builds Resume Tailor.dmg from the app bundle + src/
src/
├── resume.py                  ← Gradio UI (model selector, file upload, streaming output)
├── resume_core.py             ← Core logic (PDF extraction, prompting, validation, ATS analysis/improvement)
├── requirements.txt           ← Python dependencies
└── image.png                  ← Favicon shown in the Gradio web UI tab
```

### Stack

| Component | Role |
|-----------|------|
| [Gradio](https://gradio.app) (`gr.Blocks`) | Web UI — streaming output, file upload, dropdown |
| [pywebview](https://pywebview.flowrl.com) | Wraps the Gradio server in a native desktop window |
| [Ollama](https://ollama.com) | Local LLM inference via its Python client |
| [PyMuPDF](https://pymupdf.readthedocs.io) (via LangChain) | PDF text extraction |

### PDF extraction

`PyMuPDFLoader` from `langchain_community` reads each page of the uploaded PDF and joins them into a single plain-text string. If the extracted text is empty (scanned/image-only PDFs), the app raises an error rather than silently sending blank input to the model.

### Streaming and the Stop button

The Gradio UI is built with `gr.Blocks`. Submitting calls `run_tailor`, which is a Python generator that `yield`s text chunks as they arrive from Ollama's streaming API. Gradio updates the output textbox after each yield.

Stopping is handled by a `threading.Event` (`_stop_event`). The Stop button is registered with `queue=False` so Gradio executes `stop_generation()` immediately, bypassing the event queue that the active generator occupies. The generator checks the event after each chunk and exits cleanly when it is set.

### Validation

After streaming completes, `validate_resume_output` compares the model's output against the source resume. It checks:

- **Header lines** — name, contact info, and other pre-section lines must appear verbatim
- **Section headers** — all six sections (`PROFESSIONAL SUMMARY`, `SKILLS`, `EDUCATION`, `EXPERIENCE`, `PROJECTS`, `CERTIFICATES`) must be present and in the original order
- **Required lines** — key lines per section (skill categories, education/project/experience title lines containing `|`, certificate entries, bullet points ending in `.`) must appear verbatim
- **Line counts** — each section must have at least as many non-empty lines as the source
- **Entry counts** — sections must not collapse or drop title lines (detected by counting `|`-delimited lines)
- **URL integrity** — every URL in the source must appear unchanged; no new URLs may be introduced
- **No markdown** — headings, bullets, bold markers, code fences, and horizontal rules are rejected

Errors are classified as critical (missing headers, changed contact info, missing lines, URL changes) or non-critical (e.g. line count differences).

### Retry and candidate selection

If any validation errors are found, the app makes one non-streaming retry call, appending the error list to the conversation so the model can self-correct. Both the first answer and the retry answer are kept as candidates. The candidate with the fewest critical errors (and then fewest total errors) is returned. If both candidates have critical errors, the original source resume text is returned unchanged.

### ATS keyword handling

ATS analysis is deterministic Python, not an LLM judgment. `extract_jd_keywords` filters the job description, `analyze_keyword_coverage` checks which terms appear in the resume, and `format_ats_report` appends the final report to Insights.

After a valid Improve-mode resume is selected, the app tries a conservative deterministic ATS rewrite. This rewrite only changes safe existing lines, revalidates the result, and accepts it only if keyword coverage improves. The **↑ Improve ATS** button uses the same Python-first strategy on the current resume state. If Python cannot safely improve the resume, the app falls back to a tightly constrained model pass and still rejects keyword dumps, section loss, unchanged output, or any result that fails to improve keyword count.

### Think-block filtering

Reasoning models (DeepSeek R1, Gemma, and others) wrap their chain-of-thought in `<think>…</think>` tags. The app strips these tags from streaming output as they arrive, showing **Thinking...** as a placeholder while the reasoning block is incomplete. The final output has think blocks fully removed.

### Model filtering

The model dropdown excludes embedding models by checking for `"embed"` in the model name and `"bert"` or `"nomic-bert"` in the model family reported by Ollama. This prevents selecting models that do not support text generation.
