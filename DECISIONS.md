# Architectural Decisions

## Stack: Gradio + pywebview instead of a native GUI framework

**Decision:** Use Gradio (`gr.Blocks`) as the UI layer, wrapped in a pywebview native window, rather than a framework like tkinter, PyQt, or Electron.

**Rationale:** Gradio provides built-in streaming output, file upload, dropdowns, and a queue system for free — all of which would require significant custom implementation in a native GUI framework. pywebview turns the Gradio web server into a borderless desktop window with no visible browser chrome, preserving the native app feel. The tradeoff is that Gradio's versioning is fast-moving and some parameters (e.g. `show_copy_button`) may appear or disappear between minor versions.

---

## Local inference via Ollama, no cloud APIs

**Decision:** All LLM inference runs through a locally installed Ollama server. No cloud API keys, no network calls to external services.

**Rationale:** The primary use case is resume tailoring, which involves highly sensitive personal data (contact info, employment history, education). Keeping inference fully local means the user's resume never leaves their machine. The tradeoff is that model quality depends on what the user has pulled into Ollama, and smaller models may produce lower-quality output.

---

## Three interaction modes: Improve, Refine, Ask

**Decision:** Split the interaction surface into three named modes rather than a single prompt field.

**Rationale:** Each mode has a fundamentally different intent and therefore different prompt design, validation rules, and output handling:
- **Improve** — broad AI-driven tailoring from scratch. Needs validation/retry to catch hallucinations.
- **Refine** — surgical user-specified edits applied to a prior output. Should yield directly without validation interference.
- **Ask** — conversational Q&A about the resume. Output is prose, not a resume, so resume validation is irrelevant.

Merging these into one field would require the user to communicate intent implicitly and would make it impossible to apply the right post-processing per mode.

---

## Validation and retry only in Improve mode

**Decision:** `validate_resume_output` and the retry/fallback cycle run only in `tailor_resume` (Improve mode). `refine_resume` and `ask_about_resume` yield LLM output directly.

**Rationale:** Validation against the original PDF source is designed to catch unprompted hallucinations and structural drift in a broad tailoring pass. In Refine mode, the user has written explicit instructions — running validation against the original PDF would likely flag legitimate refinements as errors, and the fallback (`resume_text`, the raw PDF) would erase all prior tailoring work. In Ask mode, the output is prose and has no resume structure to validate.

---

## Two output fields: Resume Output + Insights & Answers

**Decision:** Separate the resume text and the commentary into two distinct output textboxes.

**Rationale:** Mixing resume output with change summaries or Q&A answers in a single field forces the user to manually separate them before using the resume elsewhere. Two fields also enable independent refresh: the user can regenerate only the insights without re-running the (much slower) resume generation, and vice versa.

---

## Sequential generation: resume first, then analysis

**Decision:** In Improve and Refine modes, the resume streams to completion (including validation/retry if applicable) before the analysis/summary begins streaming into the Insights field.

**Rationale:** The analysis prompt asks the model to compare the source and the tailored resume — it needs the final resume text to do this meaningfully. Running them in parallel would require the analysis to reason about a partially streamed or pre-validation resume, producing inaccurate commentary.

---

## Resume state persists across mode switches; only the specs field clears

**Decision:** Switching modes does not clear the PDF upload, model selection, Title, Industry, Job Description, or output fields. Only the Specifications/Refinements/Question field clears and relabels.

**Rationale:** The natural workflow is: run Improve → review the resume → switch to Refine to make a targeted change → switch to Ask to ask a question. Clearing inputs on mode switch would force the user to re-enter data on every transition. The specs field is the exception because a "specification" for Improve mode is semantically different from a "refinement" in Refine mode or a "question" in Ask mode — carrying the text forward would be confusing.

---

## Fallback in Improve mode returns original resume, not an error

**Decision:** When both the first answer and the retry have critical validation errors, `choose_resume_output` returns the original source resume text rather than an error message.

**Rationale:** An error message would force the user to start over with nothing. Returning the original resume means the user at minimum has their unchanged source text in the output field and can read it, copy it, or try a different model. The tradeoff is that the returned text may not look "tailored" — but this is always recoverable.

---

## Copy buttons implemented as explicit buttons with JS, not `show_copy_button`

**Decision:** Copy-to-clipboard is implemented via `gr.Button` + a client-side JS handler (`navigator.clipboard.writeText`), rather than Gradio's `show_copy_button` parameter on `gr.Textbox`.

**Rationale:** `show_copy_button` does not exist in Gradio 6.13.0. Using an explicit button with JS is the only way to provide clipboard access in this version.

---

## PDF is passed to Refine mode as LLM context even without validation

**Decision:** `refine_resume` still reads the PDF and passes `resume_text` to `build_refine_messages`, even though it does not run `validate_resume_output`.

**Rationale:** The source resume text serves as a factual boundary for the LLM — it can see what the original said and is instructed not to invent new information. Removing the PDF from the Refine prompt would remove this constraint and increase the risk of the model drifting from the original facts during refinement.

---

## Inputs above outputs in the layout

**Decision:** All input fields (PDF, model, title, industry, job description, specifications) appear above the output fields (Resume Output, Insights & Answers).

**Rationale:** Standard top-to-bottom form flow — the user fills in what they have, clicks Submit, and the results appear below. Having outputs above inputs (an earlier layout iteration) was counter-intuitive: the user had to scroll past empty output fields to reach the inputs.
