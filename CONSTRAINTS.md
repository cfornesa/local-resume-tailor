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
- Required lines are matched using `_line_present` — a regex requiring the line to occupy its own line in the output (bounded by `\n` or start/end of text). A required line with garbage appended on the same line **fails** this check. Do not revert to substring (`in`) matching.

---

## Model constraints

- **Embedding models are excluded** from the model dropdown. Detection: model name contains `"embed"`, or model family (per Ollama metadata) contains `"bert"` or `"nomic-bert"`.
- The model must support the Ollama `chat` API with streaming. If it does not, the app surfaces an error.
- Broad resume generation quality depends on the selected model. Smaller models (1.5B–3B parameters) may struggle with the strict formatting requirements and trigger more retries, but ATS scoring and the first ATS improvement attempt are deterministic Python.

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

## ATS keyword coverage constraints

- Keyword extraction uses `STOP_WORDS` in `resume_core.py` — a superset of standard English stop words extended in two passes: common JD boilerplate (`experience`, `qualifications`, `required`, `years`, `role`, `team`, `company`, `ability`, etc.) and JD prose fragments (`vast`, `several`, `figures`, `duties`, `effectiveness`, `information`, `using`, `cross`, `functional`, `members`, `sets`, `structuring`, `gleaned`, and ~20 more). The second pass was added after observed JD boilerplate inflating the keyword count from ~25 genuine terms to 80+. If a legitimate keyword is being filtered, check `STOP_WORDS` first.
- Single keywords: length ≥ 3 characters, not in `STOP_WORDS`, not purely numeric
- Bigrams: adjacent non-stop-word pairs, both ≥ 3 characters, **must appear ≥ 2 times in the job description** (enforced via `collections.Counter`). One-off boilerplate phrases are excluded.
- Matching is **case-insensitive substring** — `"python"` matches `"cpython"`. This is intentional; ATS systems commonly use substring matching
- The ATS report is a composite of three dimensions, all computed dynamically from the actual output text:
  - **Format** — detects markdown patterns and HTML tags (`check_ats_format`). Strips `<think>` / `</think>` fragments before scanning to avoid false positives from reasoning models.
  - **Structure** — scans the output against `ATS_SECTION_HEADERS` (35+ section name variants covering common resume styles) using `check_ats_structure`. Flags missing core sections (summary, skills, education, experience) by category.
  - **Keywords** — percentage of job-description keywords found in the output; `found / (found + missing)`.
- Report format (appended to Insights as a trailing plain-text block):
  ```
  ---
  ATS Compatibility Report
  Format:    ✓ No formatting issues detected
  Structure: ✓ 5 standard section(s) detected (EDUCATION, EXPERIENCE, ...)
  Keywords:  42% (9/21 matched)

  Found (9): data, insights, leadership, ...
  Missing (12): analyze, findings, recommendations, ...
  ```
- Report omitted entirely if there are no job-description keywords (empty JD or all terms filtered by `STOP_WORDS`)
- Report only appears in Improve and Refine modes with a non-empty JD field. Ask mode never shows an ATS report
- The report is appended **after** the LLM summary completes streaming — it does not interrupt streaming
- Stopping generation before the summary finishes will also suppress the ATS report
- Improve mode runs a validation-aware deterministic ATS rewrite after candidate selection. It may only be accepted if the rewritten resume still passes validation without critical errors and keyword count improves.
- `↑ Improve ATS` runs `improve_ats_resume`, which tries deterministic Python line rewrites before any LLM call. The LLM path is a fallback only when deterministic edits cannot improve coverage. Output is buffered — no intermediate chunks stream to Resume Output.
- `↑ Improve ATS` accepts output only when keyword match count increases, ATS section shape is preserved, and the result is not a keyword dump. Otherwise the prior resume is restored and Insights says no supported ATS improvement was accepted.
- Deterministic ATS rewrites must be line-local: do not add new entries, do not create keyword-only lines, do not edit URLs/contact lines, and do not edit `|` title lines or `:` skill-category lines.

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
