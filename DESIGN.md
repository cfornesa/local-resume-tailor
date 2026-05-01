# Design

## Philosophy

Resume Tailor is a single-purpose, local-first tool. Every design choice prioritises two things: keeping the user's data on their machine, and getting out of the way so the user can focus on their resume.

---

## Privacy by default

The application makes no network calls except to the locally running Ollama server on `127.0.0.1`. The user's resume PDF, job description, and all generated text stay on their machine. There are no accounts, no telemetry, and no cloud dependencies beyond the one-time act of pulling a model into Ollama.

---

## Layout: inputs before outputs, top to bottom

```
Mode selector
──────────────
PDF upload
Model dropdown
──────────────
Title           (Improve only)
Industry        (Improve only)
Job Description (Improve only)
Specifications / Refinements / Question
──────────────
Submit | Stop
──────────────
Resume Output      [⧉ Copy] [↺ Refresh Resume]
Insights & Answers [⧉ Copy] [↺ Refresh Insights]
```

The user works top-to-bottom: fill in what you know, click Submit, read the results below. Output fields are never positioned above input fields.

---

## Mode switching is non-destructive

Switching between Improve, Refine, and Ask does not erase the user's work. The PDF, model selection, title, industry, job description, and both output fields are preserved. Only the Specifications/Refinements/Question field is cleared and relabelled, because its content is mode-specific and carrying it forward would be misleading.

---

## Progressive disclosure of inputs

Title, Industry, and Job Description are only visible in Improve mode. They collapse entirely (no empty space left behind) when the user switches to Refine or Ask. This keeps the interface uncluttered in modes where those fields have no effect.

---

## Two-phase streaming with visible progress

In Improve and Refine modes, generation happens in two sequential phases:

1. **Resume phase** — the model streams the tailored resume into Resume Output. The user can read it, scroll it, and click Stop at any point.
2. **Analysis phase** — once the resume is finalised, "Analyzing changes..." appears in the Insights field, then the model streams a bullet-point summary of what changed.

The user always sees the resume before the analysis. The analysis is informed by the final resume, not a draft.

---

## Inline error surfacing

Errors appear inside the output field they relate to, not as modal dialogs or toast notifications. If the PDF is missing, the error appears in Resume Output. If no prior resume exists when the user clicks Submit in Refine mode, the error appears in Resume Output. This keeps the user in context and makes the error easy to dismiss by simply providing the missing input.

---

## Plain text output only

Resume Output always contains plain text. Markdown headings, bullets, bold markers, code fences, and horizontal rules are explicitly rejected by the validation layer in Improve mode, and the prompt in all modes instructs the model not to introduce them. This makes the output paste-ready into any editor, applicant tracking system, or word processor without cleanup.

---

## Stop is always available, always immediate

The Stop button is registered with `queue=False` in Gradio, meaning it bypasses the event queue and executes `_stop_event.set()` immediately — even while a streaming generation is in progress. The active generator checks the event after each chunk and exits cleanly. Stop works in all three phases: resume streaming, analysis streaming, and Ask mode.

---

## Reasoning model support

Models that produce `<think>…</think>` reasoning blocks (DeepSeek R1, Gemma, and others) are handled transparently. While a reasoning block is incomplete, the output field shows **Thinking...** as a placeholder. Once the block closes, the resume text replaces it. The final output has all think blocks stripped — the user only sees the resume.

---

## Refresh granularity

Resume Output and Insights & Answers can each be refreshed independently:

- **↺ Refresh Resume** — re-runs the full resume generation (and then the analysis, since analysis must follow the resume).
- **↺ Refresh Insights** — re-runs only the analysis/summary or re-answers the question, without touching the resume.

This allows the user to get a new summary without waiting for another full resume generation.

---

## Window

- **Size:** 1100 × 1050 px
- **Server:** `127.0.0.1:7860` (Gradio, not accessible from other machines)
- **Window manager:** pywebview (native OS window, no visible browser chrome)
- **Favicon:** `src/image.png` (shown in the Gradio tab title bar)
