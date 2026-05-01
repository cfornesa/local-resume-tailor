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

## ATS keyword coverage is deterministic Python, not LLM-reported

**Decision:** Keyword gap analysis (`extract_jd_keywords`, `analyze_keyword_coverage`, `format_ats_report` in `resume_core.py`) uses pure Python stop-word filtering and substring matching rather than asking the LLM to identify keyword coverage. The composite ATS report also checks formatting and section structure directly from the output text.

**Rationale:** Local LLM quality varies widely. A 3B model may miss important keywords, hallucinate matches, or produce vague qualitative commentary instead of a structured found/missing list. A deterministic function always produces the same result for a given JD + resume pair, regardless of which model is selected. The format and structure dimensions are computed from the actual output text — not assumed from the app's internal constraints — because users bring resumes with different section counts, section names, and formatting. The LLM handles the qualitative change summary; Python handles the quantitative ATS audit.

---

## ATS keyword integration is Python-first

**Decision:** `improve_ats_resume` first runs a deterministic ATS rewrite (`_deterministic_ats_rewrite`) before calling the LLM. The rewrite selects supported missing JD terms, maps them to plausible existing lines, and applies small template-based edits such as adding `reports`, `visualizations`, `stakeholders`, `analytical techniques`, or `recommendations` to already-supported claims. The LLM path remains a fallback only if the deterministic pass cannot improve keyword coverage.

**Rationale:** The application is intended to work on consumer-grade machines with small local models. Weak models often fail targeted keyword integration by doing nothing, rewriting too broadly, or dumping keywords. A Python-first pass makes the common ATS improvement path deterministic, local, fast, and independent of model capability while still preserving the LLM fallback for cases the templates cannot handle.

---

## ATS section detection uses a broad header set, not the hardcoded validation list

**Decision:** `check_ats_structure` (used in `format_ats_report`) scans the output against `ATS_SECTION_HEADERS` — a frozenset of 35+ recognized section name variants — rather than `SECTION_HEADERS` (the 6-header list used by `validate_resume_output`).

**Rationale:** The validation layer enforces the specific 6-section structure expected by the example resume. The ATS report must work honestly for all users, including those whose resumes have different sections (e.g., "WORK EXPERIENCE" instead of "EXPERIENCE", or no PROJECTS section). `ATS_SECTION_HEADERS` covers common variants across resume styles without imposing a single format.

---

## Improve ATS buffers output and surfaces failure explicitly

**Decision:** `improve_ats_fn` does not stream intermediate chunks to Resume Output. It buffers the entire generator output, then after the loop: (a) if `_stop_event` is set, restores the prior resume; (b) if the result equals the prior resume, shows `⚠ No supported ATS improvement was accepted — the resume is unchanged. Try Refine with specific keyword instructions.` followed by the current ATS report; (c) otherwise shows the improved resume with a fresh ATS report.

**Rationale:** Streaming intermediate tokens directly to Resume Output meant the user watched garbage accumulate live whenever a weak model produced hallucinated word-salad. Buffering prevents this. A returned prior resume can now mean either no deterministic rewrite was supported or every model fallback candidate was rejected. The message avoids blaming model size and points users toward specific Refine instructions when the safe automatic path cannot improve coverage.

---

## `improve_ats_resume` fallback gates

**Decision:** If deterministic ATS rewriting cannot improve coverage and the LLM fallback runs, the cleaned LLM output must preserve ATS section shape, differ from the prior resume beyond whitespace, avoid keyword dumps, and increase keyword match count. Otherwise `prior_output` is yielded instead.

**Rationale:** Weak models frequently "break character" when given a list of keywords to integrate — they produce meta-commentary (`"The revised resume integrates **extract**..."`) or keyword dumps instead of an actual resume. The fallback gates prevent broken, unchanged, or equal-score output from overwriting a valid resume. The score can never regress, and `↑ Improve ATS` only shows changed output when coverage actually improves.

---

## Improve mode does NOT inject an explicit keyword list into the prompt

**Decision:** `build_messages` does not extract or inject a list of JD keywords into the user prompt. The full JD text is provided, and after validation the selected candidate may receive a validation-aware deterministic ATS rewrite that protects source-required lines and revalidates before acceptance.

**Rationale:** Injecting an explicit keyword list (e.g. "incorporate these verbatim: recommendations, visualizations, databases, ...") was tried and caused catastrophic failures with weak models. The model treated the list as an enumeration task: it dumped all terms into the SKILLS section as a comma-separated blob, then entered a repetition loop on words it had exhausted. The deterministic post-validation rewrite gives small models ATS help without exposing the initial broad-generation prompt to a keyword list.

---

## Validation requires complete-line matches, not substring presence

**Decision:** `validate_resume_output` uses `_line_present(line, text)` — a regex that requires the line to appear bounded by `\n` (or start/end of text) on both sides — rather than the Python `in` operator (substring match).

**Rationale:** The original `if line not in output_text` check was a substring search. A weak model could append arbitrary content to a required line (e.g., append a keyword dump after `ML & DS: Python...`) and the required line would still be "found" as a prefix substring, passing validation. This allowed garbage output to reach the user. The `_line_present` regex (`(?:^|\n){escaped_line}[ \t]*(?:\n|$)`) requires the line to occupy its own line. Trailing horizontal whitespace is tolerated (to handle trailing spaces) but any non-whitespace content on the same line fails the check, triggering a retry or fallback.

---

## STOP_WORDS covers JD boilerplate, not just English function words

**Decision:** `STOP_WORDS` in `resume_core.py` was extended with ~30 additional JD filler terms beyond the original set: `amount`, `associates`, `companies`, `crafting`, `cross`, `duties`, `effectiveness`, `encompasses`, `establishing`, `external`, `figures`, `functional`, `gleaned`, `information`, `informational`, `informed`, `internal`, `maintaining`, `members`, `methods`, `needs`, `professionals`, `relevant`, `sets`, `several`, `skilled`, `structuring`, `usable`, `using`, `vast`, and similar.

**Rationale:** Without these additions, a single paragraph of JD boilerplate ("encompasses a vast amount of cross-functional duties...") produced 10–15 noise keywords that inflated the denominator. A JD that should yield ~25 genuine ATS keywords was returning 80+, making the keyword match percentage artificially low (11% vs a realistic 30–40%) and giving the model an impossible list to integrate. The additions filter prose fragments that have no standalone ATS value. If a term is being incorrectly filtered, check `STOP_WORDS` first.

---

## Job description is passed to Refine mode for keyword preservation

**Decision:** `build_refine_messages` now accepts `job_description` as an optional parameter and appends it to the user prompt with an explicit instruction to preserve existing keyword alignment — not to broaden the edit.

**Rationale:** Without the job description, a surgical Refine pass (e.g. "shorten the summary to two sentences") gives the model no signal to preserve the keyword alignment established during the Improve pass. The model may silently drop ATS-relevant terms while following the refinement instruction. Passing the JD with a preservation-only note fixes this without widening the scope of the edit.

---

## Inputs above outputs in the layout

**Decision:** All input fields (PDF, model, title, industry, job description, specifications) appear above the output fields (Resume Output, Insights & Answers).

**Rationale:** Standard top-to-bottom form flow — the user fills in what they have, clicks Submit, and the results appear below. Having outputs above inputs (an earlier layout iteration) was counter-intuitive: the user had to scroll past empty output fields to reach the inputs.
