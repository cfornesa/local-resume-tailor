# Constraints

## Runtime requirements

| Requirement | Detail |
|---|---|
| Python | 3.x (enforced by launcher; `arch -arm64 python3` on Apple Silicon) |
| Ollama | Must be running locally before the app is launched |
| Port | `7860` must be free on `127.0.0.1` |
| PDF | Must have extractable text — scanned/image-only PDFs are rejected |
| Models | At least one non-embedding model must be installed in Ollama |

---

## Resume structure expected by validation (Improve mode)

The validation layer (`validate_resume_output` in `resume_core.py`) expects resumes that follow this exact structure. Resumes that do not conform will produce validation errors and trigger a retry.

### Required section headers (in this exact order)

```
PROFESSIONAL SUMMARY
SKILLS
EDUCATION
EXPERIENCE
PROJECTS
CERTIFICATES
```

All six must be present. Order is enforced. Additional sections are not supported.

### Required lines per section

| Section | Required line pattern |
|---|---|
| HEADER | Every non-empty line above the first section header must appear verbatim |
| SKILLS | Every line containing `:` must appear verbatim |
| EDUCATION | Every line containing `\|` must appear verbatim |
| EXPERIENCE | Every line containing `\|` or ending with `.` must appear verbatim |
| PROJECTS | Every line containing `\|` must appear verbatim |
| CERTIFICATES | Every non-empty line must appear verbatim |

### Additional structural rules

- Each section must have at least as many non-empty lines as the source resume
- `|`-delimited entry title lines must not be collapsed or merged (each entry must remain on its own line)
- No line in any section may contain more than two `|` characters (detects merged entries)
- All URLs from the source must appear unchanged in the output; no new URLs may be added
- No markdown patterns: headings (`#`), list bullets (`-` or `*`), bold (`**`), horizontal rules (`---`), code fences (` ``` `)

---

## Model constraints

- **Embedding models are excluded** from the model dropdown. Detection: model name contains `"embed"`, or model family (per Ollama metadata) contains `"bert"` or `"nomic-bert"`.
- The model must support the Ollama `chat` API with streaming. If it does not, the app surfaces an error.
- Output quality is entirely dependent on the selected model. Smaller models (1.5B–3B parameters) may struggle with the strict formatting requirements and trigger more retries.

---

## Output format constraints

These apply to all generated text that goes into Resume Output:

- Plain text only — no markdown, no HTML, no special characters beyond what was in the source
- No invented facts — every claim in the output must originate from the source PDF
- Contact information and header lines must be reproduced verbatim
- URLs must be reproduced verbatim — no shortening, expanding, or paraphrasing
- Section names must match exactly (e.g. `EXPERIENCE` not `Work Experience`)

These constraints are enforced programmatically in Improve mode. In Refine mode, they are stated in the system prompt but not programmatically enforced — the model is trusted to apply targeted changes without structural drift.

---

## Mode-specific constraints

### Improve mode

- Requires a PDF upload
- Requires a job description
- Runs full validation + retry cycle after streaming
- Falls back to the original source resume text if both candidates have critical errors

### Refine mode

- Requires a prior resume output (must run Improve first)
- Requires a PDF upload (used as factual context for the model, not for validation)
- Requires non-empty refinement instructions
- Yields LLM output directly — no validation, no retry, no fallback
- Each Refine pass builds on the output of the previous pass (not on the original PDF)

### Ask mode

- Requires a prior resume output (must run Improve or Refine first)
- Does not require a PDF
- Requires a non-empty question
- Output goes to Insights & Answers only — Resume Output is never modified
- Resume state is not updated by Ask mode

---

## Gradio 6.13.0 compatibility notes

- `gr.Textbox(show_copy_button=True)` — **does not exist** in this version. Copy buttons are implemented as separate `gr.Button` elements with a JS handler.
- `gr.Row` can be used as an event output target to toggle `visible`. This collapses the row with no empty space remaining.
- `gr.State` with `value=None` as initial value — `gr.update()` (no kwargs) must be used to leave state unchanged during streaming yields. Yielding `None` would overwrite the state with `None`.
- The `js` parameter on `.click()` accepts a JavaScript function string. When `fn=None`, only the JS executes (no Python round-trip).

---

## Distribution constraints

### macOS

- App bundle at `Resume Tailor.app/` — the launcher shell script at `Contents/MacOS/Resume Tailor` detects whether it is running from the installed bundle (`Contents/Resources/resume.py`) or from the development source tree (`src/resume.py`)
- DMG is built by `build_dmg.sh`, which copies `src/resume.py`, `src/resume_core.py`, `src/requirements.txt`, and `src/image.png` into `Contents/Resources/`
- The app is **not notarized** — first launch requires right-click → Open to bypass Gatekeeper

### Windows

- Launched via `Resume Tailor.vbs` (WScript), which checks for Ollama and Python via `where`, auto-installs pip dependencies, and runs `python resume.py`
- A native Inno Setup installer is planned but not yet built
