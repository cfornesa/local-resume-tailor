import threading
import time
from pathlib import Path

import gradio as gr
import ollama
import webview

from resume_core import tailor_resume


EMBEDDING_NAME_KEYWORDS = ["embed"]
EMBEDDING_FAMILIES = ["bert", "nomic-bert"]

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


def run_tailor(pdf_source, model, job_description):
    _stop_event.clear()
    yield from tailor_resume(pdf_source, model, job_description, _stop_event)


with gr.Blocks(title="Resume Tailor") as interface:
    gr.Markdown(
        "# Resume Tailor\n\n"
        "Select a model, upload your resume, and paste the job description to get a customized resume."
    )
    with gr.Row():
        with gr.Column():
            pdf_input = gr.File(label="Upload Your PDF Resume")
            model_input = gr.Dropdown(
                choices=models, label="Model", value=models[0] if models else None
            )
            job_input = gr.Textbox(label="Job Description", lines=18)
        output = gr.Textbox(label="Output", lines=25)
    with gr.Row():
        submit_btn = gr.Button("Submit", variant="primary")
        stop_btn = gr.Button("Stop")

    submit_btn.click(
        fn=run_tailor,
        inputs=[pdf_input, model_input, job_input],
        outputs=output,
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

webview.create_window("Resume Tailor", "http://127.0.0.1:7860", width=1100, height=800)
webview.start()
