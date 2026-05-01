import re
from pathlib import Path

import ollama
from langchain_community.document_loaders import PyMuPDFLoader

SECTION_HEADERS = [
    "PROFESSIONAL SUMMARY",
    "SKILLS",
    "EDUCATION",
    "EXPERIENCE",
    "PROJECTS",
    "CERTIFICATES",
]
MARKDOWN_PATTERNS = [
    r"^\s*#",
    r"^\s*[-*]\s+",
    r"\*\*",
    r"^\s*---\s*$",
    r"```",
]
INDUSTRIES = [
    "Technology/Software",
    "Healthcare/Medical",
    "Finance/Banking",
    "Education",
    "Marketing/Advertising",
    "Engineering",
    "Sales/Business Development",
    "Consulting",
    "Legal",
    "Manufacturing",
    "Retail/E-commerce",
    "Nonprofit/Government",
    "Media/Entertainment",
    "Real Estate",
    "Human Resources",
    "Cybersecurity",
    "Data/Analytics",
    "Research/Academia",
    "Logistics/Supply Chain",
    "Architecture/Design",
]


def resolve_pdf_source(pdf_source):
    if pdf_source is None:
        return None

    if isinstance(pdf_source, (str, Path)):
        return str(pdf_source)

    if hasattr(pdf_source, "name") and pdf_source.name:
        return pdf_source.name

    if hasattr(pdf_source, "path") and pdf_source.path:
        return pdf_source.path

    raise ValueError("Unsupported PDF input. Provide a file path or uploaded file.")


def process_pdf(pdf_source):
    pdf_path = resolve_pdf_source(pdf_source)
    if pdf_path is None:
        return None

    loader = PyMuPDFLoader(pdf_path)
    data = loader.load()
    full_text = "\n\n".join([doc.page_content for doc in data])

    if not full_text.strip():
        raise ValueError(
            "Could not extract any text from the PDF. Make sure it is a valid, non-empty PDF."
        )

    return full_text


def source_sections(text):
    sections = {}
    current = "HEADER"
    sections[current] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped in SECTION_HEADERS:
            current = stripped
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)

    return sections


def extract_urls(text):
    pattern = r"\b(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?"
    return set(re.findall(pattern, text))


def extract_required_lines(section_name, lines):
    required = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if section_name == "HEADER":
            required.append(stripped)
        elif section_name == "SKILLS" and ":" in stripped:
            required.append(stripped)
        elif section_name == "EDUCATION" and "|" in stripped:
            required.append(stripped)
        elif section_name == "EXPERIENCE" and ("|" in stripped or stripped.endswith(".")):
            required.append(stripped)
        elif section_name == "PROJECTS" and "|" in stripped:
            required.append(stripped)
        elif section_name == "CERTIFICATES":
            required.append(stripped)

    return required


def extract_header_lines(source_text):
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    header_lines = []

    for line in lines:
        if line in SECTION_HEADERS:
            break
        header_lines.append(line)

    return header_lines


def normalize_lines(lines):
    return [line.strip() for line in lines if line.strip()]


def section_line_counts(sections):
    counts = {}
    for name, lines in sections.items():
        counts[name] = len(normalize_lines(lines))
    return counts


def extract_output_sections(text):
    return source_sections(text)


def validate_resume_output(source_text, output_text):
    errors = []
    source = source_sections(source_text)
    output = extract_output_sections(output_text)

    for line in extract_header_lines(source_text):
        if line not in output_text:
            errors.append(f"Missing or changed header/contact line: {line}")

    for pattern in MARKDOWN_PATTERNS:
        if re.search(pattern, output_text, flags=re.MULTILINE):
            errors.append("Output introduced markdown formatting that is not present in the source resume.")
            break

    last_index = -1
    for header in SECTION_HEADERS:
        index = output_text.find(header)
        if index == -1:
            errors.append(f"Missing required section header: {header}")
            continue
        if index < last_index:
            errors.append(f"Section order changed for: {header}")
        last_index = index

    for section_name, lines in source.items():
        required_lines = extract_required_lines(section_name, lines)
        for line in required_lines:
            if line not in output_text:
                errors.append(f"Missing or changed source line: {line}")

    source_counts = section_line_counts(source)
    output_counts = section_line_counts(output)
    for section_name in SECTION_HEADERS:
        if section_name not in output:
            continue
        source_count = source_counts.get(section_name, 0)
        output_count = output_counts.get(section_name, 0)
        if output_count < source_count:
            errors.append(
                f"Section {section_name} has fewer non-empty lines than the source resume."
            )

    for section_name in ("EDUCATION", "EXPERIENCE", "PROJECTS", "CERTIFICATES"):
        source_lines = normalize_lines(source.get(section_name, []))
        output_lines = normalize_lines(output.get(section_name, []))
        source_multiline_entries = sum(1 for line in source_lines if "|" in line)
        output_multiline_entries = sum(1 for line in output_lines if "|" in line)
        if output_multiline_entries < source_multiline_entries:
            errors.append(f"Section {section_name} collapsed or removed entry title lines.")

    for section_name in SECTION_HEADERS:
        output_lines = normalize_lines(output.get(section_name, []))
        for line in output_lines:
            if line.count("|") > 2:
                errors.append(
                    f"Section {section_name} contains a collapsed line with multiple merged entries: {line}"
                )
                break

    source_urls = extract_urls(source_text)
    output_urls = extract_urls(output_text)
    if source_urls != output_urls:
        missing = sorted(source_urls - output_urls)
        added = sorted(output_urls - source_urls)
        if missing:
            errors.append(f"Missing or changed URLs: {', '.join(missing)}")
        if added:
            errors.append(f"Unexpected URLs added: {', '.join(added)}")

    return errors


def is_critical_validation_error(error):
    if error.startswith("Missing or changed header/contact line:"):
        return True
    if error.startswith("Missing required section header:"):
        return True
    if error.startswith("Section order changed for:"):
        return True
    if error.startswith("Missing or changed URLs:"):
        return True
    if error.startswith("Unexpected URLs added:"):
        return True
    if error.startswith("Missing or changed source line:"):
        return True
    return False


def has_critical_errors(errors):
    return any(is_critical_validation_error(error) for error in errors)


def choose_resume_output(resume_text, candidate_outputs):
    ranked = sorted(candidate_outputs, key=lambda item: (has_critical_errors(item[1]), len(item[1])))
    best_output, best_errors = ranked[0]

    if not has_critical_errors(best_errors):
        return best_output

    return resume_text


def strip_think_streaming(text):
    # Remove complete think blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Show placeholder while still inside an incomplete think block
    if "<think>" in text:
        return "Thinking..."
    return text.strip()


def build_messages(resume_text, job_description, title=None, industry=None, specifications=None):
    system_prompt = (
        "You are a resume editor.\n"
        "- Output only the resume text.\n"
        "- Use only facts from the source resume.\n"
        "- Keep section names, section order, URLs, and contact details exactly as written.\n"
        "- Do not expand abbreviations, initials, acronyms, or short organization names.\n"
        "- Keep the same plain-text format. Do not use markdown, code fences, bullets, or commentary.\n"
        "- Do not add, remove, rename, merge, or invent entries.\n"
        "- Make only minimal wording edits to improve relevance to the job description."
    )
    user_prompt = (
        "Tailor this resume for the job description using only the resume facts below. "
        "Do not invent, correct, complete, or drop any information. "
        "Return the resume in the same plain-text structure and section order as the source. "
        "Keep URLs exactly as written in the resume. "
        "Keep each source entry on its own line rather than merging multiple entries together. "
        "If needed, make only minimal edits for relevance.\n\n"
        f"Resume:\n<<<RESUME>>>\n{resume_text}\n<<<END RESUME>>>\n\n"
        f"Job Description:\n<<<JOB DESCRIPTION>>>\n{job_description}\n<<<END JOB DESCRIPTION>>>"
    )

    extras = []
    if title and title.strip():
        extras.append(f"Target Job Title: {title.strip()}")
    if industry and industry.strip():
        extras.append(f"Target Industry: {industry.strip()}")
    if specifications and specifications.strip():
        extras.append(f"Additional Preferences: {specifications.strip()}")
    if extras:
        user_prompt += "\n\n" + "\n".join(extras)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_refine_messages(resume_text, prior_output, refinements):
    system_prompt = (
        "You are a resume editor.\n"
        "- Output only the resume text.\n"
        "- Use only facts from the source resume.\n"
        "- Keep section names, section order, URLs, and contact details exactly as written.\n"
        "- Do not expand abbreviations, initials, acronyms, or short organization names.\n"
        "- Keep the same plain-text format. Do not use markdown, code fences, bullets, or commentary.\n"
        "- Do not add, remove, rename, merge, or invent entries.\n"
        "- Apply only the requested refinements; preserve everything else exactly."
    )
    user_prompt = (
        "Apply the requested refinements to the current tailored resume below. "
        "Do not invent, correct, complete, or drop any information. "
        "Return the resume in the same plain-text structure and section order. "
        "Keep URLs exactly as written. Keep each entry on its own line.\n\n"
        f"Source Resume (validation reference):\n<<<RESUME>>>\n{resume_text}\n<<<END RESUME>>>\n\n"
        f"Current Tailored Resume:\n<<<CURRENT>>>\n{prior_output}\n<<<END CURRENT>>>\n\n"
        f"Requested Refinements:\n<<<REFINEMENTS>>>\n{refinements}\n<<<END REFINEMENTS>>>"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_ask_messages(prior_output, question):
    system_prompt = (
        "You are a resume consultant. "
        "Answer the user's question about the resume clearly and concisely. "
        "Do not rewrite the full resume unless specifically asked."
    )
    user_prompt = (
        f"Resume:\n<<<RESUME>>>\n{prior_output}\n<<<END RESUME>>>\n\n"
        f"Question: {question}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_summary_messages(source_resume, tailored_resume, context_note=""):
    system_prompt = "You are a resume consultant. Be concise and specific."
    request = "Compare the original and tailored resumes below and list 3-5 key changes made. Focus on what changed, not what stayed the same."
    if context_note:
        request = f"{context_note}\n\n{request}"
    user_prompt = (
        f"{request}\n\n"
        f"Original:\n<<<ORIGINAL>>>\n{source_resume}\n<<<END ORIGINAL>>>\n\n"
        f"Tailored:\n<<<TAILORED>>>\n{tailored_resume}\n<<<END TAILORED>>>"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_resume(messages, model):
    try:
        response = ollama.chat(model=model, messages=messages)
    except ollama.ResponseError:
        raise ValueError(
            f"'{model}' does not support text generation. Please select a different model."
        )

    response_content = response.message.content
    return re.sub(r"<think>.*?</think>", "", response_content, flags=re.DOTALL).strip()


def _stream_ollama(model, messages, stop_event):
    """Stream Ollama chat, yielding text chunks. Raises ValueError on model error."""
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
    except ollama.ResponseError:
        raise ValueError(f"'{model}' does not support text generation. Please select a different model.")

    raw = ""
    streaming_done = False
    stream_error = None
    try:
        for chunk in stream:
            if stop_event and stop_event.is_set():
                break
            raw += (chunk.message.content if chunk.message else "") or ""
            yield strip_think_streaming(raw)
        else:
            streaming_done = True
    except GeneratorExit:
        pass
    except Exception as e:
        stream_error = e
    finally:
        try:
            stream.close()
        except Exception:
            pass

    if not streaming_done:
        if stream_error:
            raise RuntimeError(f"Generation failed: {stream_error}")


def tailor_resume(pdf_source, model, job_description, stop_event=None, title=None, industry=None, specifications=None):
    try:
        resume_text = process_pdf(pdf_source)
    except ValueError as e:
        yield f"Could not read resume: {e}"
        return
    if resume_text is None:
        yield "No resume provided. Please upload a PDF file."
        return

    messages = build_messages(resume_text, job_description, title=title, industry=industry, specifications=specifications)

    raw = ""
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
    except ollama.ResponseError:
        yield f"'{model}' does not support text generation. Please select a different model."
        return
    except Exception as e:
        yield f"Could not connect to Ollama: {e}\n\nMake sure Ollama is running and try again."
        return

    streaming_done = False
    stream_error = None
    try:
        for chunk in stream:
            if stop_event and stop_event.is_set():
                break
            raw += (chunk.message.content if chunk.message else "") or ""
            yield strip_think_streaming(raw)
        else:
            streaming_done = True
    except GeneratorExit:
        pass
    except Exception as e:
        stream_error = e
    finally:
        try:
            stream.close()
        except Exception:
            pass

    if not streaming_done:
        if stream_error:
            yield f"Generation failed: {stream_error}\n\nOllama may still be loading the model. Wait a moment and try again."
        return

    first_answer = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    errors = validate_resume_output(resume_text, first_answer)
    candidates = [(first_answer, errors)]

    if errors:
        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    "Your previous draft violated required constraints. Regenerate the resume and fix every issue below. "
                    "Preserve the source text exactly wherever possible.\n\n"
                    f"Validation errors:\n- " + "\n- ".join(errors)
                ),
            }
        ]
        try:
            retry_answer = generate_resume(retry_messages, model)
            retry_errors = validate_resume_output(resume_text, retry_answer)
            candidates.append((retry_answer, retry_errors))
        except ValueError:
            pass

    yield choose_resume_output(resume_text, candidates)


def refine_resume(pdf_source, model, prior_output, refinements, stop_event=None):
    if not prior_output or not prior_output.strip():
        yield "No resume output to refine. Run Improve mode first, then switch to Refine."
        return
    if not refinements or not refinements.strip():
        yield "Please enter refinement instructions before submitting."
        return

    try:
        resume_text = process_pdf(pdf_source)
    except ValueError as e:
        yield f"Could not read resume: {e}"
        return
    if resume_text is None:
        yield "No resume provided. Please upload a PDF file."
        return

    messages = build_refine_messages(resume_text, prior_output, refinements)

    raw = ""
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
    except ollama.ResponseError:
        yield f"'{model}' does not support text generation. Please select a different model."
        return
    except Exception as e:
        yield f"Could not connect to Ollama: {e}\n\nMake sure Ollama is running and try again."
        return

    streaming_done = False
    stream_error = None
    try:
        for chunk in stream:
            if stop_event and stop_event.is_set():
                break
            raw += (chunk.message.content if chunk.message else "") or ""
            yield strip_think_streaming(raw)
        else:
            streaming_done = True
    except GeneratorExit:
        pass
    except Exception as e:
        stream_error = e
    finally:
        try:
            stream.close()
        except Exception:
            pass

    if not streaming_done:
        if stream_error:
            yield f"Generation failed: {stream_error}\n\nOllama may still be loading the model. Wait a moment and try again."
        return

    yield re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def ask_about_resume(model, prior_output, question, stop_event=None):
    if not prior_output or not prior_output.strip():
        yield "No resume output to ask about. Run Improve mode first, then switch to Ask."
        return
    if not question or not question.strip():
        yield "Please enter a question before submitting."
        return

    messages = build_ask_messages(prior_output, question)

    raw = ""
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
    except ollama.ResponseError:
        yield f"'{model}' does not support text generation. Please select a different model."
        return
    except Exception as e:
        yield f"Could not connect to Ollama: {e}\n\nMake sure Ollama is running and try again."
        return

    streaming_done = False
    stream_error = None
    try:
        for chunk in stream:
            if stop_event and stop_event.is_set():
                break
            raw += (chunk.message.content if chunk.message else "") or ""
            yield strip_think_streaming(raw)
        else:
            streaming_done = True
    except GeneratorExit:
        pass
    except Exception as e:
        stream_error = e
    finally:
        try:
            stream.close()
        except Exception:
            pass

    if not streaming_done:
        if stream_error:
            yield f"Generation failed: {stream_error}"
        return

    yield re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def summarize_changes(model, source_resume, tailored_resume, context_note=""):
    if not source_resume or not source_resume.strip():
        messages = build_summary_messages("(not available)", tailored_resume, context_note)
    else:
        messages = build_summary_messages(source_resume, tailored_resume, context_note)

    raw = ""
    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
    except Exception:
        yield "Could not generate analysis."
        return

    try:
        for chunk in stream:
            raw += (chunk.message.content if chunk.message else "") or ""
            yield strip_think_streaming(raw)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass

    final = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if final:
        yield final
