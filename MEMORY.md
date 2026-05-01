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

## `STOP_WORDS` is broader than standard English stop words

`resume_core.py` defines `STOP_WORDS` for ATS keyword extraction. It has been extended in two passes:

- **First pass:** Common JD filler: `experience`, `qualifications`, `required`, `preferred`, `ability`, `years`, `role`, `position`, `team`, `company`, `organization`, `candidate`, `including`, and similar.
- **Second pass (~30 additions):** JD prose fragments that inflated keyword counts: `amount`, `associates`, `companies`, `crafting`, `cross`, `duties`, `effectiveness`, `encompasses`, `establishing`, `external`, `figures`, `functional`, `gleaned`, `information`, `informational`, `informed`, `internal`, `maintaining`, `members`, `methods`, `needs`, `professionals`, `relevant`, `sets`, `several`, `skilled`, `structuring`, `usable`, `using`, `vast`.

Without these additions, one paragraph of JD boilerplate could produce 10–15 noise keywords, making a realistic 30–40% match rate appear as 11%. If a legitimate keyword is being filtered, check `STOP_WORDS` first.

---

## Job description now flows into Refine mode

`build_refine_messages` accepts an optional `job_description` parameter. When provided, it is appended to the user prompt with an explicit instruction that the model should use it for keyword preservation only — not as license to widen the edit scope. This parameter is passed through `refine_resume` → `build_refine_messages` and sourced from `job_input` in `resume.py`.

---

## ATS Compatibility Report is appended after LLM summary, not streamed

The composite ATS report (`---\nATS Compatibility Report\nFormat:...\nStructure:...\nKeywords:...`) is a single synchronous Python call (`analyze_keyword_coverage` + `format_ats_report`) that runs after the `summarize_changes` generator finishes. It is appended by yielding `final_insights + "\n\n" + report` as a final update to the Insights field. If Stop is clicked during the LLM summary, the report is suppressed (the `_stop_event` check gates it).

`format_ats_report` replaced the earlier `format_keyword_report`. The old function is gone; any reference to `format_keyword_report` in the codebase is a bug.

---

## ATS improvement is Python-first

`improve_ats_resume` first calls `_deterministic_ats_rewrite` before attempting any Ollama generation. The deterministic path selects supported missing JD keywords, maps them to existing resume lines, applies small template rewrites, and accepts the result only when keyword match count increases and resume shape is preserved.

The deterministic rewrite intentionally skips contact lines, URLs, `|` entry title lines, `:` skill-category lines, section headers, and unsupported terms. In initial Improve mode, `tailor_resume` passes `_protected_source_lines(resume_text)` so source-required lines are not changed unless the final output still validates.

The LLM-based ATS prompt remains as a fallback only when deterministic rewriting cannot improve coverage. Its output is still rejected if it is unchanged, loses section structure, looks like a keyword dump, or does not increase keyword count.

---

## ATS section headers use a broad set, not the validation set

`ATS_SECTION_HEADERS` (in `resume_core.py`) is a frozenset of 35+ recognized section name variants covering diverse resume styles (`WORK EXPERIENCE`, `PROFESSIONAL EXPERIENCE`, `CAREER OBJECTIVE`, `CORE COMPETENCIES`, etc.). It is used by `check_ats_structure` in the ATS report and by the guarded LLM fallback in `improve_ats_resume`.

This is distinct from `SECTION_HEADERS` — the 6-item list (`PROFESSIONAL SUMMARY`, `SKILLS`, `EDUCATION`, `EXPERIENCE`, `PROJECTS`, `CERTIFICATES`) used by `validate_resume_output`. `SECTION_HEADERS` enforces the specific structure of the example resume. `ATS_SECTION_HEADERS` gives honest coverage scores for any resume style.

---

## `check_ats_format` strips `<think>` before HTML scan

`check_ats_format` strips `</?think>` fragments from the text with `re.sub(r"</?think>", "", text)` before running the HTML tag regex. Without this, a trailing `</think>` fragment from a reasoning model that survived `strip_think_streaming` would trigger a false `⚠ HTML tags` warning on otherwise clean output.

---

## `validate_resume_output` uses complete-line matching, not substring search

Required lines (header lines and section-specific required lines) are checked with `_line_present(line, text)` — a regex requiring `(?:^|\n){line}[ \t]*(?:\n|$)`. The original `line not in output_text` was a substring check: a weak model could append a keyword dump to the end of a required line and the source line would still be "found" as a prefix, passing validation. The stricter check catches this and triggers retry. The trailing `[ \t]*` tolerates trailing spaces without allowing appended content.

---

## `improve_ats_fn` buffers output — no streaming to Resume Output

`improve_ats_fn` in `resume.py` does NOT stream intermediate chunks to Resume Output. It iterates the `improve_ats_resume` generator silently (buffering `last_chunk`), then shows the final result only after the loop completes. This prevents users from watching hallucinated word-salad appear live when a weak model fails the task.

After the loop, three paths:
1. `_stop_event.is_set()` → restore `resume_state`, show "Generation stopped."
2. `last_chunk.strip() == resume_state.strip()` → no deterministic or model-safe improvement was accepted; show `⚠ No supported ATS improvement was accepted` message + current ATS report
3. Otherwise → show improved resume + fresh ATS report

---

## `improve_ats_resume` has fallback gates

If deterministic rewriting cannot improve coverage and the LLM fallback streams, `improve_ats_resume` checks the cleaned output before accepting it. Outputs are rejected if they are unchanged beyond whitespace, lose section structure, look like keyword dumps, or do not increase keyword count. Rejected outputs yield `prior_output` instead.

The `build_ats_improve_messages` system prompt is also hardened with: `"Your entire response must be the complete resume text only. Begin immediately with the candidate's name on the first line."` — the post-generation fallback gates are a second layer of defense.

---

## Resume state is a `gr.State`, not a Python variable

The current tailored resume text is stored in `resume_state = gr.State(value=None)` inside the `gr.Blocks` context. This means:
- Each browser session (each pywebview window instance) has its own isolated state.
- State is not shared between runs or persisted to disk.
- Refresh Resume and Refresh Insights both read `resume_state` as an input, so they always operate on the most recently generated resume.
- Ask mode reads but never writes `resume_state`.
