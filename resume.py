import gradio as gr

from resume_core import tailor_resume


interface = gr.Interface(
    fn=tailor_resume,
    inputs=[
        gr.File(label="Upload Your PDF Resume"),
        gr.Textbox(label="Job Description", lines=18),
    ],
    outputs="text",
    title="Tailor your resume based on the job description",
    description="Use DeepSeek-R1 to tailor your resume based on the job description.",
)

interface.launch()
