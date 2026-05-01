import re
from collections import Counter
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
ATS_TERM_LIMIT = 10
ATS_HIGH_VALUE_TERMS = {
    "accuracy", "analytical", "analyze", "clients", "databases", "decisions",
    "executives", "findings", "graphs", "improvement", "infographics",
    "integrity", "kpis", "patterns", "planning", "presentations",
    "recommendations", "reports", "research", "stakeholders", "strategic",
    "visualizations",
}
ATS_PRIORITY_TERMS = {
    "analytical", "analyze", "recommendations", "reports", "stakeholders",
    "visualizations",
}
ATS_SUPPORT_ALIASES = {
    "accuracy": {"accurate", "quality", "validation"},
    "analytical": {"analytics", "analysis", "data", "statistical"},
    "analysts": {"analyst", "analytics"},
    "analyze": {"analytics", "analysis", "data"},
    "clients": {"employees", "users", "stakeholders"},
    "collect": {"gather", "source", "intake"},
    "databases": {"sql", "database", "data"},
    "decisions": {"solutions", "strategy", "leadership"},
    "designing": {"designed", "redesigned", "built"},
    "executives": {"leadership", "leaders", "stakeholders"},
    "findings": {"insights", "analysis", "results"},
    "generate": {"built", "developed", "created", "designed"},
    "graphs": {"dashboards", "visualizations", "data viz", "power bi"},
    "identify": {"detect", "find", "insights"},
    "improvement": {"improved", "redesigned", "bottlenecks"},
    "infographics": {"visualizations", "data viz", "dashboards"},
    "integrity": {"governance", "quality", "security"},
    "kpis": {"metrics", "performance", "dashboards"},
    "measure": {"metrics", "track", "performance"},
    "organize": {"governance", "sharepoint", "processes"},
    "patterns": {"trends", "analytics", "insights"},
    "planning": {"strategy", "leadership", "solutions"},
    "presentations": {"present", "storytelling", "communication"},
    "processing": {"processes", "automation", "analytics"},
    "recommendations": {"solutions", "insights", "leadership", "storytelling", "present"},
    "reports": {"dashboards", "power bi", "analytics"},
    "research": {"study", "analysis", "bias"},
    "sales": {"business", "market"},
    "stakeholders": {"stakeholder", "leadership", "employees"},
    "strategic": {"strategy", "leadership", "solutions"},
    "techniques": {"methods", "modeling", "statistical"},
    "understand": {"analyze", "assess", "questions"},
    "visualizations": {"dashboards", "data viz", "power bi"},
    "visualizing": {"dashboards", "data viz", "power bi"},
}
STOP_WORDS = {
    # Articles & determiners
    "a", "an", "the", "this", "that", "these", "those", "each", "every",
    "any", "all", "both", "few", "more", "most", "other", "some", "such",
    "no", "none", "not", "own", "same", "so", "than", "too", "very",
    # Pronouns
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "whose",
    # Prepositions
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "up", "about", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "against", "among",
    "throughout", "despite", "towards", "upon", "within", "without",
    "along", "following", "across", "behind", "beyond", "plus",
    "except", "via", "per",
    # Conjunctions
    "and", "or", "but", "nor", "yet", "either", "neither",
    "although", "whereas", "though", "because", "since", "unless",
    "until", "whether", "if", "when", "where", "while", "however",
    # Auxiliary verbs
    "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "could", "should", "shall",
    "may", "might", "must", "can", "need", "used",
    # Generic verbs
    "get", "got", "take", "make", "made", "come", "go", "going", "goes",
    "know", "think", "look", "want", "give", "find", "tell", "ask",
    "seem", "feel", "try", "leave", "call", "keep", "let", "show",
    "hear", "play", "run", "move", "live", "hold", "bring", "happen",
    "write", "provide", "provides", "providing", "ensure", "ensuring",
    "work", "working", "works", "help", "helping", "helps",
    "support", "supporting", "supports",
    "develop", "developing", "drive", "driving",
    "manage", "managing", "build", "building",
    "create", "creating", "collaborate", "collaborating",
    "contribute", "contributing", "communicate", "communicating",
    # Generic adjectives
    "good", "new", "great", "little", "right", "high", "large",
    "big", "small", "long", "old", "early", "important",
    "public", "private", "real", "best", "next", "first", "last",
    "possible", "various", "strong", "excellent",
    # Generic adverbs
    "also", "just", "now", "well", "even", "back", "only", "still",
    "often", "always", "never", "sometimes", "already", "together",
    "rather", "really",
    # JD-specific filler
    "experience", "experiences", "experienced",
    "skill", "skills", "ability", "abilities",
    "knowledge", "understanding",
    "responsibilities", "responsibility",
    "qualifications", "qualification",
    "requirements", "requirement", "required", "preferred", "desired",
    "deep", "solid", "proven", "demonstrated",
    "years", "year", "month", "months",
    "degree", "bachelor", "master",
    "role", "position", "job", "opportunity", "opportunities",
    "team", "teams", "company", "organization", "business",
    "candidate", "candidates", "applicant", "applicants",
    "equal", "employer", "employment",
    "including", "etc", "ie", "eg",
    "apply", "submit", "send", "please", "join", "hire", "hiring",
    "seeking", "looking", "wanted", "open",
    "base", "based", "located", "location", "office", "remote",
    "full", "part", "time", "contract", "permanent",
    # Additional JD noise terms — generic words that inflate keyword counts without ATS signal
    "amount", "amounts",
    "associate", "associates",
    "companies",
    "craft", "crafting",
    "cross",
    "duties", "duty",
    "effectiveness",
    "encompasses", "encompass",
    "establishing",
    "external",
    "figures",
    "functional",
    "gleaned",
    "information", "informational",
    "informed",
    "internal",
    "maintaining",
    "member", "members",
    "method", "methods",
    "needs",
    "professional", "professionals",
    "relevant",
    "sets",
    "several",
    "skilled",
    "structuring",
    "usable",
    "using",
    "vast",
}
ATS_SECTION_HEADERS = frozenset({
    "PROFESSIONAL SUMMARY", "SUMMARY", "OBJECTIVE", "CAREER OBJECTIVE",
    "PROFESSIONAL OBJECTIVE", "PROFILE",
    "SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES", "KEY SKILLS",
    "COMPETENCIES", "AREAS OF EXPERTISE",
    "EDUCATION", "ACADEMIC BACKGROUND", "ACADEMIC HISTORY", "ACADEMIC CREDENTIALS",
    "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
    "EMPLOYMENT HISTORY", "EMPLOYMENT", "CAREER HISTORY",
    "PROJECTS", "PROJECT EXPERIENCE", "KEY PROJECTS", "PORTFOLIO",
    "CERTIFICATES", "CERTIFICATIONS", "LICENSES", "CREDENTIALS", "LICENSURE",
    "AWARDS", "ACHIEVEMENTS", "HONORS", "PUBLICATIONS",
    "VOLUNTEER", "VOLUNTEER EXPERIENCE", "COMMUNITY INVOLVEMENT",
    "LANGUAGES", "INTERESTS", "ACTIVITIES",
})
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


def _line_present(line, text):
    """True if `line` appears as a complete line in `text` (not merely a prefix of a longer line)."""
    return bool(re.search(r'(?:^|\n)' + re.escape(line) + r'[ \t]*(?:\n|$)', text))


def validate_resume_output(source_text, output_text):
    errors = []
    source = source_sections(source_text)
    output = extract_output_sections(output_text)

    for line in extract_header_lines(source_text):
        if not _line_present(line, output_text):
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
            if not _line_present(line, output_text):
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


def extract_jd_keywords(job_description):
    text = re.sub(r"[^a-z0-9\s]", " ", job_description.lower())
    tokens = text.split()

    seen_words = set()
    keywords = []
    for token in tokens:
        if token not in seen_words and len(token) >= 3 and token not in STOP_WORDS and not token.isdigit():
            seen_words.add(token)
            keywords.append(token)

    all_bigrams = []
    for i in range(len(tokens) - 1):
        w1, w2 = tokens[i], tokens[i + 1]
        if (len(w1) >= 3 and len(w2) >= 3
                and w1 not in STOP_WORDS and w2 not in STOP_WORDS
                and not w1.isdigit() and not w2.isdigit()):
            all_bigrams.append(f"{w1} {w2}")

    seen_bigrams = set()
    for bigram, count in Counter(all_bigrams).items():
        if count >= 2 and bigram not in seen_bigrams:
            seen_bigrams.add(bigram)
            keywords.append(bigram)

    return sorted(keywords)


def analyze_keyword_coverage(job_description, resume_text):
    keywords = extract_jd_keywords(job_description)
    resume_lower = re.sub(r"[^a-z0-9\s]", " ", resume_text.lower())
    found = [kw for kw in keywords if kw in resume_lower]
    missing = [kw for kw in keywords if kw not in resume_lower]
    return found, missing


def _normalized_keyword(text):
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


def _normalized_words(text):
    normalized = _normalized_keyword(text)
    return {
        word for word in normalized.split()
        if len(word) >= 3 and word not in STOP_WORDS and not word.isdigit()
    }


def _simple_stem(word):
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            return word[:-len(suffix)]
    return word


def _stemmed_words(text):
    return {_simple_stem(word) for word in _normalized_words(text)}


def _normalize_resume_for_comparison(text):
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    return "\n".join(lines).casefold()


def _split_job_sentences(job_description):
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", job_description)
        if sentence.strip()
    ]


def _keyword_context_words(job_description, keyword):
    normalized_keyword = _normalized_keyword(keyword)
    context = set()
    for sentence in _split_job_sentences(job_description):
        normalized_sentence = _normalized_keyword(sentence)
        if normalized_keyword in normalized_sentence:
            context.update(_normalized_words(sentence))
    return context


def _keyword_support_aliases(keyword):
    aliases = set()
    for word in _normalized_words(keyword):
        aliases.update(ATS_SUPPORT_ALIASES.get(word, set()))
    if keyword in ATS_SUPPORT_ALIASES:
        aliases.update(ATS_SUPPORT_ALIASES[keyword])
    return aliases


def _support_score(keyword, context_words, support_text):
    support_words = _normalized_words(support_text)
    support_stems = {_simple_stem(word) for word in support_words}
    keyword_words = _normalized_words(keyword)
    aliases = _keyword_support_aliases(keyword)

    score = len(context_words & support_words) * 3
    score += len({_simple_stem(word) for word in keyword_words} & support_stems) * 5
    score += sum(3 for alias in aliases if _normalized_keyword(alias) in _normalized_keyword(support_text))
    return score


def _line_edit_targets(prior_output):
    targets = []
    for line in prior_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper() in ATS_SECTION_HEADERS:
            continue
        if "@" in stripped or re.search(r"\(\d{3}\)", stripped):
            continue
        if "|" in stripped or ":" in stripped:
            continue
        targets.append(stripped)
    return targets


def _select_ats_terms(job_description, resume_text, prior_output, missing_keywords, limit=ATS_TERM_LIMIT):
    support_text = f"{resume_text}\n{prior_output}"
    scored = []
    for index, keyword in enumerate(missing_keywords):
        context_words = _keyword_context_words(job_description, keyword)
        word_count = len(_normalized_words(keyword))
        score = _support_score(keyword, context_words, support_text)
        score += 20 if word_count == 1 else 4
        if keyword in ATS_HIGH_VALUE_TERMS:
            score += 8
        if keyword in ATS_PRIORITY_TERMS:
            score += 6
        score -= index / 1000
        scored.append((score, word_count, index, keyword))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [keyword for _, _, _, keyword in scored[:limit]]


def _ats_line_term_groups(job_description, prior_output, selected_keywords):
    targets = _line_edit_targets(prior_output)
    if not targets:
        return {}

    guidance = []
    for keyword in selected_keywords:
        context_words = _keyword_context_words(job_description, keyword)
        aliases = _keyword_support_aliases(keyword)
        best_line = None
        best_score = -1
        for line in targets:
            line_score = _support_score(keyword, context_words, line)
            line_score += len(_stemmed_words(keyword) & _stemmed_words(line)) * 3
            line_score += sum(2 for alias in aliases if _normalized_keyword(alias) in _normalized_keyword(line))
            if line_score > best_score:
                best_line = line
                best_score = line_score
        if best_line and best_score > 0:
            guidance.append((best_line, keyword))

    grouped = {}
    for line, keyword in guidance:
        grouped.setdefault(line, [])
        if keyword not in grouped[line]:
            grouped[line].append(keyword)
    return grouped


def _build_ats_edit_guidance(job_description, resume_text, prior_output, selected_keywords):
    grouped = _ats_line_term_groups(job_description, prior_output, selected_keywords)
    support_text = f"{resume_text}\n{prior_output}"

    lines = []
    for line, keywords in grouped.items():
        terms = ", ".join(keywords)
        lines.append(f"- Existing line: {line}\n  Consider naturally adding: {terms}")

    if lines:
        return "\n".join(lines)

    fallback_terms = ", ".join(selected_keywords)
    if fallback_terms and _support_score(fallback_terms, set(), support_text) > 0:
        return f"- Consider naturally adding these supported terms where they fit: {fallback_terms}"
    return ""


def _append_before_period(line, phrase):
    if phrase.lower() in line.lower():
        return line
    if line.endswith("."):
        return f"{line[:-1]} {phrase}."
    return f"{line} {phrase}"


def _replace_once_case_insensitive(line, old, new):
    if new.lower() in line.lower():
        return line
    return re.sub(re.escape(old), new, line, count=1, flags=re.IGNORECASE)


def _term_missing(term, line):
    return _normalized_keyword(term) not in _normalized_keyword(line)


def _line_has_any(line, terms):
    normalized = _normalized_keyword(line)
    return any(_normalized_keyword(term) in normalized for term in terms)


def _apply_supported_term_templates(line, desired_terms):
    rewritten = line.strip()
    terms = set(desired_terms)
    normalized = _normalized_keyword(rewritten)

    if _line_has_any(rewritten, {"power bi", "dashboard", "dashboards", "data viz"}):
        if "reports" in terms and _term_missing("reports", rewritten):
            rewritten = _replace_once_case_insensitive(rewritten, "dashboards", "dashboards and reports")
        if "visualizations" in terms and _term_missing("visualizations", rewritten):
            if "dashboards and reports" in rewritten.lower():
                rewritten = _replace_once_case_insensitive(
                    rewritten, "dashboards and reports", "dashboards, reports, and visualizations"
                )
            else:
                rewritten = _replace_once_case_insensitive(rewritten, "dashboards", "dashboards and visualizations")
        if "stakeholders" in terms and _term_missing("stakeholders", rewritten):
            if re.search(r"\bfor insights into\b", rewritten, flags=re.IGNORECASE):
                rewritten = re.sub(
                    r"\bfor insights into\b",
                    "for stakeholders seeking insights into",
                    rewritten,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                rewritten = _append_before_period(rewritten, "for stakeholders")
        if "kpis" in terms and _term_missing("kpis", rewritten):
            rewritten = _append_before_period(rewritten, "tracking KPIs")
        if "patterns" in terms and _term_missing("patterns", rewritten):
            rewritten = _append_before_period(rewritten, "and identify patterns")
        if "trends" in terms and _term_missing("trends", rewritten):
            rewritten = _append_before_period(rewritten, "and trends")

    if _line_has_any(rewritten, {"analytics", "data", "statistical", "quant analysis", "modeling"}):
        if "analytical" in terms and _term_missing("analytical", rewritten):
            rewritten = _append_before_period(rewritten, "using analytical techniques")
        if "analyze" in terms and _term_missing("analyze", rewritten):
            rewritten = _append_before_period(rewritten, "to analyze data")
        if "analyze data" in terms and _term_missing("analyze data", rewritten):
            rewritten = _append_before_period(rewritten, "to analyze data")
        if "reports" in terms and _term_missing("reports", rewritten):
            rewritten = _append_before_period(rewritten, "and reports")
        if "visualizations" in terms and _term_missing("visualizations", rewritten):
            rewritten = _append_before_period(rewritten, "and visualizations")

    if _line_has_any(rewritten, {"leadership", "leaders", "solutions", "storytelling", "communication"}):
        if "recommendations" in terms and _term_missing("recommendations", rewritten):
            rewritten = _replace_once_case_insensitive(rewritten, "solutions", "recommendations and solutions")
        if "strategic" in terms and _term_missing("strategic", rewritten):
            rewritten = _append_before_period(rewritten, "for strategic planning")
        if "planning" in terms and _term_missing("planning", rewritten):
            rewritten = _append_before_period(rewritten, "for planning")
        if "decisions" in terms and _term_missing("decisions", rewritten):
            rewritten = _append_before_period(rewritten, "to support decisions")

    if _line_has_any(rewritten, {"governance", "process", "processes", "sharepoint", "bottlenecks", "redesigned"}):
        if "integrity" in terms and _term_missing("integrity", rewritten):
            rewritten = _append_before_period(rewritten, "and data integrity")
        if "organize" in terms and _term_missing("organize", rewritten):
            rewritten = _append_before_period(rewritten, "to organize information")
        if "improvement" in terms and _term_missing("improvement", rewritten):
            rewritten = _append_before_period(rewritten, "for process improvement")

    if _line_has_any(rewritten, {"stakeholder", "communication", "collaboration"}):
        if "stakeholders" in terms and _term_missing("stakeholders", rewritten):
            rewritten = _replace_once_case_insensitive(rewritten, "Stakeholder", "Stakeholders")

    if _line_has_any(rewritten, {"bias", "hate speech", "datasets", "research"}):
        if "research" in terms and _term_missing("research", rewritten):
            rewritten = _append_before_period(rewritten, "using research methods")
        if "findings" in terms and _term_missing("findings", rewritten):
            rewritten = _append_before_period(rewritten, "to surface findings")

    if normalized == _normalized_keyword(rewritten):
        return line
    return rewritten


def _rewrite_resume_line_for_terms(line, selected_terms):
    if not line.strip():
        return line
    if line.strip().upper() in ATS_SECTION_HEADERS:
        return line
    if "@" in line or re.search(r"\(\d{3}\)", line):
        return line
    if "|" in line or ":" in line:
        return line
    if not selected_terms:
        return line
    return _apply_supported_term_templates(line, selected_terms)


def _protected_source_lines(source_text):
    protected = set()
    source = source_sections(source_text)
    for section_name, lines in source.items():
        protected.update(extract_required_lines(section_name, lines))
    return protected


def _deterministic_ats_rewrite(job_description, resume_text, prior_output, protected_lines=None):
    prior_found, missing = analyze_keyword_coverage(job_description, prior_output)
    if not missing:
        return prior_output

    selected_terms = _select_ats_terms(job_description, resume_text, prior_output, missing)
    grouped_terms = _ats_line_term_groups(job_description, prior_output, selected_terms)
    protected = protected_lines or set()
    rewritten_lines = [
        line if line.strip() in protected else _rewrite_resume_line_for_terms(line, grouped_terms.get(line.strip(), []))
        for line in prior_output.splitlines()
    ]
    candidate = "\n".join(rewritten_lines)

    if _normalize_resume_for_comparison(candidate) == _normalize_resume_for_comparison(prior_output):
        return prior_output
    if not _preserves_resume_shape(prior_output, candidate, selected_terms):
        return prior_output

    final_found, _ = analyze_keyword_coverage(job_description, candidate)
    if len(final_found) <= len(prior_found):
        return prior_output
    return candidate


def _looks_like_keyword_dump(resume_text, candidate_keywords):
    keyword_set = {_normalized_keyword(keyword) for keyword in candidate_keywords}
    keyword_set.discard("")
    if not keyword_set:
        return False

    for line in resume_text.splitlines():
        parts = [_normalized_keyword(part) for part in line.split(",")]
        parts = [part for part in parts if part]
        if len(parts) < 5:
            continue
        keyword_parts = sum(1 for part in parts if part in keyword_set)
        if keyword_parts >= 5:
            return True
    return False


def _preserves_resume_shape(prior_output, candidate_output, candidate_keywords):
    prior_headers, _ = check_ats_structure(prior_output)
    candidate_headers, _ = check_ats_structure(candidate_output)

    if len(candidate_headers) < 2:
        return False
    if set(prior_headers) - set(candidate_headers):
        return False

    prior_lines = [line for line in prior_output.splitlines() if line.strip()]
    candidate_lines = [line for line in candidate_output.splitlines() if line.strip()]
    if prior_lines and len(candidate_lines) < max(2, int(len(prior_lines) * 0.8)):
        return False

    if _looks_like_keyword_dump(candidate_output, candidate_keywords):
        return False

    return True


def check_ats_format(resume_text):
    # Strip reasoning-model artifacts before checking — <think> tags are not formatting issues
    text = re.sub(r"</?think>", "", resume_text)
    issues = []
    for pattern in MARKDOWN_PATTERNS:
        if re.search(pattern, text, flags=re.MULTILINE):
            issues.append("markdown formatting")
            break
    if re.search(r"<[a-zA-Z][^>]*>", text):
        issues.append("HTML tags")
    return not bool(issues), issues


def check_ats_structure(resume_text):
    upper = resume_text.upper()
    detected = sorted(
        h for h in ATS_SECTION_HEADERS
        if re.search(rf"(?:^|\n){re.escape(h)}(?:\s*$|\s*\n)", upper)
    )
    core = {
        "summary": {"PROFESSIONAL SUMMARY", "SUMMARY", "OBJECTIVE", "CAREER OBJECTIVE",
                    "PROFESSIONAL OBJECTIVE", "PROFILE"},
        "skills": {"SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES", "KEY SKILLS",
                   "COMPETENCIES", "AREAS OF EXPERTISE"},
        "education": {"EDUCATION", "ACADEMIC BACKGROUND", "ACADEMIC HISTORY", "ACADEMIC CREDENTIALS"},
        "experience": {"EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
                       "EMPLOYMENT HISTORY", "EMPLOYMENT", "CAREER HISTORY"},
    }
    detected_set = set(detected)
    missing_core = [label for label, variants in core.items()
                    if not detected_set.intersection(variants)]
    return detected, missing_core


def format_ats_report(found, missing, resume_text):
    total = len(found) + len(missing)
    if total == 0:
        return ""

    fmt_clean, fmt_issues = check_ats_format(resume_text)
    detected, missing_core = check_ats_structure(resume_text)

    lines = ["---", "ATS Compatibility Report"]

    if fmt_clean:
        lines.append("Format:    ✓ No formatting issues detected")
    else:
        lines.append(f"Format:    ⚠ Formatting issues detected: {', '.join(fmt_issues)}")

    if detected:
        section_list = ", ".join(detected)
        if not missing_core:
            lines.append(f"Structure: ✓ {len(detected)} standard section(s) detected ({section_list})")
        else:
            lines.append(f"Structure: {len(detected)} standard section(s) detected ({section_list})")
            lines.append(f"           ⚠ Core section(s) not detected: {', '.join(missing_core)}")
    else:
        lines.append("Structure: ⚠ No standard ATS section headers detected")

    score = round(len(found) / total * 100)
    lines.append(f"Keywords:  {score}% ({len(found)}/{total} matched)")
    lines.append("")
    lines.append(f"Found ({len(found)}): {', '.join(found) if found else 'none'}")
    lines.append(f"Missing ({len(missing)}): {', '.join(missing) if missing else 'none'}")

    return "\n".join(lines)


def build_messages(resume_text, job_description, title=None, industry=None, specifications=None):
    system_prompt = (
        "You are a resume editor.\n"
        "- Output only the resume text.\n"
        "- Use only facts from the source resume.\n"
        "- Keep section names, section order, URLs, and contact details exactly as written.\n"
        "- Do not expand abbreviations, initials, acronyms, or short organization names.\n"
        "- Keep the same plain-text format. Do not use markdown, code fences, bullets, or commentary.\n"
        "- Do not add, remove, rename, merge, or invent entries.\n"
        "- Make only minimal wording edits to improve relevance to the job description.\n"
        "- Weave job-description keywords naturally into existing summary, skills, experience, and project wording when the source facts support them.\n"
        "- Prefer revising generic supported phrases into job-description language over adding new lines.\n"
        "- Do not add standalone keyword lists or comma-separated keyword lines."
    )
    user_prompt = (
        "Tailor this resume for the job description using only the resume facts below. "
        "Do not invent, correct, complete, or drop any information. "
        "Return the resume in the same plain-text structure and section order as the source. "
        "Keep URLs exactly as written in the resume. "
        "Keep each source entry on its own line rather than merging multiple entries together. "
        "If needed, make only minimal edits for relevance. "
        "When existing achievements already support job-description language, revise the wording to include that language naturally. "
        "Use the job description as context for natural phrasing, not as a list of terms to dump into the resume.\n\n"
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


def build_refine_messages(resume_text, prior_output, refinements, job_description=None):
    system_prompt = (
        "You are a resume editor.\n"
        "- Output only the resume text.\n"
        "- Use only facts from the source resume.\n"
        "- Keep section names, section order, URLs, and contact details exactly as written.\n"
        "- Do not expand abbreviations, initials, acronyms, or short organization names.\n"
        "- Keep the same plain-text format. Do not use markdown, code fences, bullets, or commentary.\n"
        "- Do not add, remove, rename, merge, or invent entries.\n"
        "- Apply only the requested refinements; preserve everything else exactly.\n"
        "- Preserve existing keyword alignment with the job description."
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
    if job_description and job_description.strip():
        user_prompt += (
            "\n\nJob Description (for keyword preservation — do not deviate from the requested refinements):"
            f"\n<<<JOB DESCRIPTION>>>\n{job_description}\n<<<END JOB DESCRIPTION>>>"
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


def build_ats_improve_messages(resume_text, prior_output, missing_keywords, edit_guidance=""):
    system_prompt = (
        "You are a resume editor. Your entire response must be the complete resume text only. "
        "Begin immediately with the candidate's name on the first line. "
        "Do not include any commentary, explanation, preamble, notes, or closing remarks before or after the resume. "
        "Do not acknowledge these instructions.\n"
        "- Treat the current tailored resume as the document to preserve and lightly edit.\n"
        "- Use the source resume only as the factual boundary for what may be claimed.\n"
        "- Keep section names, section order, URLs, contact details, and existing entries exactly as written unless a tiny wording edit is needed.\n"
        "- Do not expand abbreviations, initials, acronyms, or short organization names.\n"
        "- Keep the same plain-text format. Do not use markdown, code fences, bullets, or headings.\n"
        "- Do not add, remove, rename, merge, or invent entries.\n"
        "- Candidate terms are optional: use them only where they fit naturally and are truthfully supported.\n"
        "- Never add standalone keyword lists, comma-separated keyword lines, repeated keyword fragments, or a replacement skills dump.\n"
        "- Use the edit guidance to revise existing lines; do not add the guidance text itself to the resume.\n"
        "- Make no other changes beyond natural keyword-oriented wording edits."
    )
    user_prompt = (
        "The following job-description terms are absent from the current resume. "
        "They are candidate terms, not a mandatory checklist. "
        "Use only the terms that can be woven naturally into existing supported statements. "
        "Preserve the current resume's content and structure. "
        "Do not create new keyword-only lines or comma-separated term lists. "
        "Output the complete resume starting with the candidate's name. No preamble, no commentary.\n\n"
        f"Candidate terms: {', '.join(missing_keywords)}\n\n"
        f"Edit guidance:\n{edit_guidance or 'Use the candidate terms only where an existing line already supports them.'}\n\n"
        f"Current Tailored Resume (primary document to preserve):\n<<<CURRENT>>>\n{prior_output}\n<<<END CURRENT>>>\n\n"
        f"Source Resume (factual reference only):\n<<<RESUME>>>\n{resume_text}\n<<<END RESUME>>>"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def improve_ats_resume(pdf_source, model, prior_output, job_description, stop_event=None):
    if not prior_output or not prior_output.strip():
        yield "No resume output to improve. Run Improve mode first."
        return
    if not job_description or not job_description.strip():
        yield "No job description available for ATS analysis."
        return

    prior_found, missing = analyze_keyword_coverage(job_description, prior_output)
    if not missing:
        yield prior_output
        return

    try:
        resume_text = process_pdf(pdf_source)
    except ValueError as e:
        yield f"Could not read resume: {e}"
        return
    if resume_text is None:
        yield "No resume provided. Please upload a PDF file."
        return

    deterministic_output = _deterministic_ats_rewrite(job_description, resume_text, prior_output)
    if deterministic_output.strip() != prior_output.strip():
        yield deterministic_output
        return

    missing_to_integrate = _select_ats_terms(job_description, resume_text, prior_output, missing)
    edit_guidance = _build_ats_edit_guidance(
        job_description, resume_text, prior_output, missing_to_integrate
    )
    messages = build_ats_improve_messages(
        resume_text, prior_output, missing_to_integrate, edit_guidance=edit_guidance
    )

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

    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if _normalize_resume_for_comparison(cleaned) == _normalize_resume_for_comparison(prior_output):
        yield prior_output
        return

    if not _preserves_resume_shape(prior_output, cleaned, missing_to_integrate):
        # Model produced commentary, a keyword dump, or destructive changes — preserve the original
        yield prior_output
        return

    final_found, _ = analyze_keyword_coverage(job_description, cleaned)
    if len(final_found) <= len(prior_found):
        yield prior_output
        return
    yield cleaned


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

    chosen_output = choose_resume_output(resume_text, candidates)
    ats_output = _deterministic_ats_rewrite(
        job_description,
        resume_text,
        chosen_output,
        protected_lines=_protected_source_lines(resume_text),
    )
    if ats_output.strip() != chosen_output.strip():
        ats_errors = validate_resume_output(resume_text, ats_output)
        if not has_critical_errors(ats_errors):
            chosen_output = ats_output

    yield chosen_output


def refine_resume(pdf_source, model, prior_output, refinements, stop_event=None, job_description=None):
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

    messages = build_refine_messages(resume_text, prior_output, refinements, job_description=job_description)

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
