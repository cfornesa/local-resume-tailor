import threading
import time
from pathlib import Path

import gradio as gr
import ollama
import webview

from resume_core import (
    tailor_resume,
    refine_resume,
    ask_about_resume,
    summarize_changes,
    improve_ats_resume,
    analyze_keyword_coverage,
    format_ats_report,
    INDUSTRIES,
)


EMBEDDING_NAME_KEYWORDS = ["embed"]
EMBEDDING_FAMILIES = ["bert", "nomic-bert"]

MODE_LABELS = {
    "Improve": "Specifications (Optional)",
    "Refine":  "What refinements would you like to make?",
    "Ask":     "Ask a question about your resume",
}
MODE_PLACEHOLDERS = {
    "Improve": "e.g. Emphasize leadership, keep bullets concise, tailor for a senior role...",
    "Refine":  "e.g. Make the summary shorter, emphasize Python more in the Skills section...",
    "Ask":     "e.g. How well does this resume match the job description?",
}

_stop_event = threading.Event()


def get_installed_models():
    response = ollama.list()
    models = []
    for m in response.models:
        if any(kw in m.model.lower() for kw in EMBEDDING_NAME_KEYWORDS):
            continue
        family = (m.details.family or "").lower() if m.details else ""
        if any(f in family for f in EMBEDDING_FAMILIES):
            continue
        models.append(m.model)
    return models


models = get_installed_models()


def stop_generation():
    _stop_event.set()


def on_mode_change(mode):
    is_improve = mode == "Improve"
    return (
        gr.update(visible=is_improve),
        gr.update(visible=is_improve),
        gr.update(visible=is_improve),
        gr.update(label=MODE_LABELS[mode], placeholder=MODE_PLACEHOLDERS[mode], value=""),
    )


def run_tailor(mode, pdf_source, model, prior_resume, title, industry, job_description, user_input):
    _stop_event.clear()

    if mode == "Improve":
        last_chunk = ""
        for chunk in tailor_resume(
            pdf_source, model, job_description, _stop_event,
            title=title, industry=industry, specifications=user_input,
        ):
            last_chunk = chunk
            yield chunk, gr.update(), gr.update()

        if not last_chunk:
            return

        final_resume = last_chunk
        yield final_resume, "Analyzing changes...", final_resume

        final_insights = ""
        for chunk in summarize_changes(model, prior_resume or "", final_resume):
            if _stop_event.is_set():
                break
            final_insights = chunk
            yield gr.update(), chunk, gr.update()

        if job_description and job_description.strip() and not _stop_event.is_set():
            found, missing = analyze_keyword_coverage(job_description, final_resume)
            report = format_ats_report(found, missing, final_resume)
            if report:
                yield gr.update(), final_insights + "\n\n" + report, gr.update()

    elif mode == "Refine":
        last_chunk = ""
        for chunk in refine_resume(pdf_source, model, prior_resume, user_input, _stop_event, job_description=job_description):
            last_chunk = chunk
            yield chunk, gr.update(), gr.update()

        if not last_chunk:
            return

        final_resume = last_chunk
        context = f"The user requested: {user_input}" if user_input and user_input.strip() else ""
        yield final_resume, "Analyzing refinements...", final_resume

        final_insights = ""
        for chunk in summarize_changes(model, prior_resume or "", final_resume, context_note=context):
            if _stop_event.is_set():
                break
            final_insights = chunk
            yield gr.update(), chunk, gr.update()

        if job_description and job_description.strip() and not _stop_event.is_set():
            found, missing = analyze_keyword_coverage(job_description, final_resume)
            report = format_ats_report(found, missing, final_resume)
            if report:
                yield gr.update(), final_insights + "\n\n" + report, gr.update()

    else:  # Ask
        for chunk in ask_about_resume(model, prior_resume, user_input, _stop_event):
            yield gr.update(), chunk, gr.update()


def refresh_resume_fn(mode, pdf_source, model, prior_resume, title, industry, job_description, user_input):
    _stop_event.clear()
    if mode == "Ask":
        yield "Resume refresh is not available in Ask mode.", gr.update(), gr.update()
        return

    gen = (
        tailor_resume(
            pdf_source, model, job_description, _stop_event,
            title=title, industry=industry, specifications=user_input,
        )
        if mode == "Improve"
        else refine_resume(pdf_source, model, prior_resume, user_input, _stop_event, job_description=job_description)
    )
    last_chunk = ""
    for chunk in gen:
        last_chunk = chunk
        yield chunk, gr.update(), gr.update()

    if not last_chunk:
        return

    final_resume = last_chunk
    context = f"The user requested: {user_input}" if mode == "Refine" and user_input and user_input.strip() else ""
    yield final_resume, "Analyzing changes...", final_resume

    final_insights = ""
    for chunk in summarize_changes(model, prior_resume or "", final_resume, context_note=context):
        if _stop_event.is_set():
            break
        final_insights = chunk
        yield gr.update(), chunk, gr.update()

    if job_description and job_description.strip() and not _stop_event.is_set():
        found, missing = analyze_keyword_coverage(job_description, final_resume)
        report = format_ats_report(found, missing, final_resume)
        if report:
            yield gr.update(), final_insights + "\n\n" + report, gr.update()


def refresh_insights_fn(mode, model, resume_state, user_input, job_description):
    _stop_event.clear()
    if mode == "Ask":
        for chunk in ask_about_resume(model, resume_state, user_input, _stop_event):
            yield chunk
    else:
        if not resume_state or not resume_state.strip():
            yield "No resume generated yet. Run Submit first."
            return
        context = f"The user requested: {user_input}" if mode == "Refine" and user_input and user_input.strip() else ""
        final_insights = ""
        for chunk in summarize_changes(model, "", resume_state, context_note=context):
            if _stop_event.is_set():
                break
            final_insights = chunk
            yield chunk
        if job_description and job_description.strip() and not _stop_event.is_set():
            found, missing = analyze_keyword_coverage(job_description, resume_state)
            report = format_ats_report(found, missing, resume_state)
            if report:
                yield final_insights + "\n\n" + report


def improve_ats_fn(pdf_source, model, resume_state, job_description):
    _stop_event.clear()
    yield gr.update(), "Integrating ATS keywords...", gr.update()

    last_chunk = ""
    for chunk in improve_ats_resume(pdf_source, model, resume_state, job_description, _stop_event):
        last_chunk = chunk

    if _stop_event.is_set() or not last_chunk:
        yield resume_state or gr.update(), "Generation stopped. Resume unchanged.", gr.update()
        return

    final_resume = last_chunk
    if final_resume.strip() == (resume_state or "").strip():
        found, missing = analyze_keyword_coverage(job_description, final_resume)
        report = format_ats_report(found, missing, final_resume)
        note = "⚠ No supported ATS improvement was accepted — the resume is unchanged. Try Refine with specific keyword instructions.\n\n"
        yield final_resume, note + (report or ""), final_resume
        return

    found, missing = analyze_keyword_coverage(job_description, final_resume)
    report = format_ats_report(found, missing, final_resume)
    yield final_resume, report or "ATS analysis complete.", final_resume


with gr.Blocks(title="Resume Tailor") as interface:
    resume_state = gr.State(value=None)

    gr.Markdown(
        "# Resume Tailor\n\n"
        "Upload your resume, choose a mode, and let the model tailor it for you."
    )

    mode_input = gr.Radio(
        choices=["Improve", "Refine", "Ask"],
        value="Improve",
        label="Mode",
        interactive=True,
    )

    pdf_input = gr.File(label="Upload Your PDF Resume")
    model_input = gr.Dropdown(
        choices=models, label="Model", value=models[0] if models else None
    )

    with gr.Row() as title_row:
        title_input = gr.Textbox(
            label="Job Title (Optional)",
            placeholder="e.g. Senior Software Engineer",
            lines=1,
        )

    with gr.Row() as industry_row:
        industry_input = gr.Dropdown(
            choices=INDUSTRIES,
            label="Industry (Optional)",
            value=None,
            allow_custom_value=True,
        )

    with gr.Row() as job_row:
        job_input = gr.Textbox(label="Job Description", lines=10)

    user_input = gr.Textbox(
        label=MODE_LABELS["Improve"],
        placeholder=MODE_PLACEHOLDERS["Improve"],
        lines=4,
    )

    with gr.Row():
        submit_btn = gr.Button("Submit", variant="primary")
        stop_btn = gr.Button("Stop")

    with gr.Row():
        gr.Markdown("### Resume Output")
        copy_resume_btn = gr.Button("⧉ Copy", size="sm", variant="secondary")
        refresh_resume_btn = gr.Button("↺ Refresh Resume", size="sm", variant="secondary")
        improve_ats_btn = gr.Button("↑ Improve ATS", size="sm", variant="secondary")

    resume_output = gr.Textbox(
        label=None,
        show_label=False,
        lines=20,
        interactive=False,
    )

    with gr.Row():
        gr.Markdown("### Insights & Answers")
        copy_insights_btn = gr.Button("⧉ Copy", size="sm", variant="secondary")
        refresh_insights_btn = gr.Button("↺ Refresh Insights", size="sm", variant="secondary")

    insights_output = gr.Textbox(
        label=None,
        show_label=False,
        lines=8,
        interactive=False,
    )

    mode_input.change(
        fn=on_mode_change,
        inputs=[mode_input],
        outputs=[title_row, industry_row, job_row, user_input],
    )

    submit_btn.click(
        fn=run_tailor,
        inputs=[mode_input, pdf_input, model_input, resume_state,
                title_input, industry_input, job_input, user_input],
        outputs=[resume_output, insights_output, resume_state],
    )

    refresh_resume_btn.click(
        fn=refresh_resume_fn,
        inputs=[mode_input, pdf_input, model_input, resume_state,
                title_input, industry_input, job_input, user_input],
        outputs=[resume_output, insights_output, resume_state],
    )

    refresh_insights_btn.click(
        fn=refresh_insights_fn,
        inputs=[mode_input, model_input, resume_state, user_input, job_input],
        outputs=[insights_output],
    )

    improve_ats_btn.click(
        fn=improve_ats_fn,
        inputs=[pdf_input, model_input, resume_state, job_input],
        outputs=[resume_output, insights_output, resume_state],
    )

    copy_resume_btn.click(
        fn=None,
        inputs=[resume_output],
        outputs=[],
        js="(text) => { navigator.clipboard.writeText(text); }",
    )

    copy_insights_btn.click(
        fn=None,
        inputs=[insights_output],
        outputs=[],
        js="(text) => { navigator.clipboard.writeText(text); }",
    )

    stop_btn.click(fn=stop_generation, inputs=[], outputs=[], queue=False)


def run_gradio():
    interface.launch(
        server_name="127.0.0.1",
        server_port=7860,
        prevent_thread_lock=True,
        inbrowser=False,
        quiet=True,
        favicon_path=str(Path(__file__).parent / "image.png"),
    )


threading.Thread(target=run_gradio, daemon=True).start()
time.sleep(2)

webview.create_window("Resume Tailor", "http://127.0.0.1:7860", width=1100, height=1050)
webview.start()
