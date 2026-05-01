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
- ATS keyword analysis and ATS report formatting are deterministic Python. Do not replace them with LLM calls.
- Improve ATS is Python-first: run deterministic line-local ATS rewrites before the LLM fallback, and never accept unchanged, regressed, section-broken, or keyword-dump output.
- Do not inject explicit keyword lists into initial Improve mode prompts. Weak local models tend to dump keyword lists.

## File map

```
src/resume.py        — Gradio UI, layout, event wiring, mode dispatch
src/resume_core.py   — PDF extraction, prompt builders, streaming generators, validation,
                       deterministic ATS keyword analysis and ATS improvement
```

All business logic lives in `resume_core.py`. All Gradio components and event handlers live in `resume.py`. Keep this separation.

## Warning

Never change this file unless explicitly instructed to do so by the user or unless you are given explicit permission.
