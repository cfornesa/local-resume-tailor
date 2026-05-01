# Agent Guidelines

Before making any change to this codebase, read the following files in order:

1. **[CONSTRAINTS.md](CONSTRAINTS.md)** — hard limits you must not violate (resume structure, validation rules, mode-specific behaviour, Gradio 6.13.0 compatibility)
2. **[DECISIONS.md](DECISIONS.md)** — why the code is the way it is; check here before proposing an alternative approach
3. **[DESIGN.md](DESIGN.md)** — UX principles and layout rules; any UI change must be consistent with these
4. **[MEMORY.md](MEMORY.md)** — non-obvious facts about the codebase (version-specific quirks, unused code, timing assumptions, delimiter conventions)

## Critical rules (summary — full detail in the files above)

- Validation + retry + fallback runs **only** in `tailor_resume` (Improve mode). Never add it to `refine_resume` or `ask_about_resume`.
- `refine_resume` yields LLM output directly. The fallback target in Improve mode is `resume_text` (raw PDF); in Refine mode there is no fallback.
- `show_copy_button` does not exist in Gradio 6.13.0. Use `gr.Button` + JS.
- `gr.update()` (no kwargs) is the correct no-op sentinel for `gr.State` during streaming yields. Never yield `None` for a state output.
- Generator functions that yield tuples must match the length of `outputs=[...]` exactly on every yield path.
- The layout order is: inputs → Submit/Stop → outputs. Do not place output fields above input fields.
- Mode switching must not clear any field except the Specifications/Refinements/Question field.
- Title, Industry, and Job Description rows must be hidden (not just empty) in Refine and Ask modes.
- ATS keyword coverage (`extract_jd_keywords`, `analyze_keyword_coverage`, `format_ats_report`) is deterministic Python — no LLM. Never replace it with an LLM call. `format_keyword_report` no longer exists; use `format_ats_report(found, missing, resume_text)`.
- The ATS Compatibility Report is appended to Insights **after** `summarize_changes` finishes, gated by `_stop_event`. It must not interrupt streaming.
- `build_refine_messages` accepts `job_description=None`. When provided, it is a preservation hint only — it must not widen the edit scope.
- `improve_ats_resume` is Python-first: it runs `_deterministic_ats_rewrite` before the LLM fallback. Never make the LLM the primary ATS improvement mechanism.
- Deterministic ATS rewrites must be line-local and conservative. Do not add new entries, keyword-only lines, comma-separated keyword dumps, URLs, or contact edits.
- In Improve mode, deterministic ATS rewrites are validation-aware: `tailor_resume` protects source-required lines and revalidates before accepting the rewrite.
- `improve_ats_resume` yields directly (no validation, no retry) but has fallback gates: unchanged output, section loss, keyword dumps, and non-improving keyword counts all return `prior_output`. Never remove these gates.
- Bigrams in `extract_jd_keywords` require ≥ 2 occurrences in the JD (via `collections.Counter`). Never lower this threshold without user approval.
- `build_messages` (Improve mode) does NOT inject a keyword list. The full JD text provides sufficient signal. Explicit keyword lists cause weak models to dump terms as comma-separated blobs. Do not add keyword injection to `build_messages`.
- `improve_ats_fn` does NOT stream to Resume Output — it buffers the entire generator output. After the loop it checks: stop event → restore prior; `last_chunk == resume_state` → show "No supported ATS improvement" message; otherwise → show result. Never add a per-chunk yield to this function.
- `STOP_WORDS` has been extended twice. Before adding new noise terms, check they are not already present. Before removing existing terms, confirm they truly carry ATS signal in a resume context.
- `validate_resume_output` uses `_line_present(line, text)` for all required-line checks — a regex requiring complete-line boundaries, not substring presence. Never revert these checks to `line not in output_text`.

## File map

```
src/resume.py        — Gradio UI, layout, event wiring, mode dispatch
src/resume_core.py   — PDF extraction, prompt builders, streaming generators, validation,
                       ATS keyword extraction and coverage analysis
```

Key functions in `resume_core.py`:
- `tailor_resume` — Improve mode generator (validation + retry + fallback)
- `refine_resume(job_description=None)` — Refine mode generator (direct yield)
- `ask_about_resume` — Ask mode generator
- `summarize_changes` — LLM change summary generator
- `improve_ats_resume` — Improve ATS generator (Python-first deterministic rewrite + guarded LLM fallback; direct yield, no validation/retry)
- `extract_jd_keywords` / `analyze_keyword_coverage` / `format_ats_report` — deterministic ATS analysis (no LLM)
- `_deterministic_ats_rewrite` / `_rewrite_resume_line_for_terms` / `_apply_supported_term_templates` — deterministic ATS keyword integration helpers
- `check_ats_format` / `check_ats_structure` — format and structure dimensions of the ATS report
- `build_ats_improve_messages` — prompt builder for Improve ATS pass
- `ATS_SECTION_HEADERS` — frozenset of 35+ ATS-recognized section name variants (distinct from `SECTION_HEADERS`)

All business logic lives in `resume_core.py`. All Gradio components and event handlers live in `resume.py`. Keep this separation.

## Warning

Never change this file unless explicitly instructed to do so by the user or unless you are given explicit permission.
