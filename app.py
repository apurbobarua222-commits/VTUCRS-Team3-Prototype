
import logging
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

from prompts import (
    BASE_SYSTEM_PROMPT,
    EXPERIMENTAL_SYSTEM_PROMPT,
    SCENARIOS,
)
from document_loader import extract_pdf_text
from vturcs_loader import (
    get_vturcs_project_records,
    format_projects_for_model,
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MAX_MESSAGES = 30
MAX_MESSAGE_LENGTH = 12000
MAX_RECOMMENDED_PROJECTS = 3


# --------------------------------------------------
# Load reference documents
# --------------------------------------------------

def load_reference_document(filename):
    """Load a PDF without preventing Flask from starting if it fails."""
    try:
        return extract_pdf_text(filename)
    except Exception:
        app.logger.exception(
            "Could not load reference document: %s", filename
        )
        return ""


HONOR_CODE_TEXT = load_reference_document("vt_honor_code.pdf")
RUBRIC_DOCUMENT_TEXT = load_reference_document(
    "research_readiness_rubric.pdf"
)


# --------------------------------------------------
# Response guidance
# --------------------------------------------------

CONCISE_RESPONSE_GUIDANCE = """
RESPONSE STYLE:
- Answer the user's question directly.
- Keep ordinary answers concise and easy to scan.
- Use headings and bullet points when helpful.
- Use normal Markdown without escaping Markdown characters.
- Do not provide a full rubric analysis unless explicitly requested.
- Do not invent facts that are not supported by available information.

VTURCS PROJECT RULES:
- Use only supplied VTURCS project records for project details.
- Never invent project names, faculty, skills, descriptions, or URLs.
- Never attach a URL to a different project.
- Use the exact official URL supplied for each project.
- If a field is missing, say "Not listed".
- A project listing does not guarantee that a professor is recruiting.
- Preserve the original meaning of project descriptions.
- Format multiple tasks as separate Markdown bullet points.
"""


# --------------------------------------------------
# Model client
# --------------------------------------------------

def get_client():
    """Create the OpenAI-compatible model client."""
    api_key = os.getenv("MODEL_API_KEY")
    base_url = os.getenv("MODEL_BASE_URL")

    if not api_key:
        raise RuntimeError(
            "MODEL_API_KEY is missing from the environment."
        )

    if not base_url:
        raise RuntimeError(
            "MODEL_BASE_URL is missing from the environment."
        )

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
        max_retries=0,
    )


def get_model_name():
    """Return the configured model name."""
    return os.getenv(
        "MODEL_NAME",
        "gpt-oss",
    )


# --------------------------------------------------
# Detect project-related questions
# --------------------------------------------------

def is_project_question(message):
    """Return True when current VTURCS project records are relevant."""
    message = message.lower().strip()

    keywords = [
        "vturcs",
        "project",
        "projects",
        "research opportunity",
        "research opportunities",
        "research opening",
        "research openings",
        "research position",
        "research positions",
        "available research",
        "available projects",
        "project fit",
        "which research",
        "which project",
        "best project",
        "best projects",
        "faculty advisor",
        "faculty adviser",
        "project advisor",
        "project adviser",
        "professor for",
        "join a lab",
        "join research",
        "get involved in research",
        "project link",
        "project links",
        "project url",
        "project urls",
        "project description",
        "describe the projects",
        "all projects",
        "every project",
        "list projects",
        "list all projects",
        "show all projects",
        "all opportunities",
        "what projects",
        "research can i join",
        "find research",
        "find projects",
    ]

    return any(keyword in message for keyword in keywords)


def assistant_asked_for_profile(messages):
    """Check whether the preceding assistant turn asked for a profile."""
    for item in reversed(messages[:-1]):
        if item.get("role") == "assistant":
            content = item.get("content", "").lower()
            return (
                "what research areas interest you most" in content
                or "what technical skills or tools do you know" in content
                or "project-matching questions" in content
            )

    return False


def asks_for_all_projects(message):
    """Recognize requests to list every available project."""
    message = message.lower().strip()

    phrases = [
        "all projects",
        "every project",
        "all available projects",
        "list all",
        "list every",
        "show all",
        "show me all",
        "every available opportunity",
        "all opportunities",
        "all research projects",
    ]

    return any(phrase in message for phrase in phrases)


def needs_official_project_formatting(
    message,
    profile_response=False,
):
    """Determine whether official project details should be appended."""
    if profile_response or asks_for_all_projects(message):
        return True

    message = message.lower().strip()

    phrases = [
        "which project",
        "which projects",
        "best project",
        "best projects",
        "recommend a project",
        "recommend projects",
        "recommend a research opportunity",
        "recommend research opportunities",
        "match my skills",
        "match projects",
        "project fit",
        "compare projects",
        "compare these projects",
        "which opportunity fits",
        "which opportunities fit",
        "what project fits",
        "what projects fit",
        "what project would fit",
        "what projects would fit",
    ]

    return any(phrase in message for phrase in phrases)


def is_profile_collection_request(message):
    """Recognize the prompt that starts the project-matching interview."""
    message = message.lower().strip()

    return (
        "ask me about my interests" in message
        or (
            "match projects to my skills" in message
            and "ask me" in message
        )
    )


def matching_flow_was_started(messages):
    """Check whether an earlier user turn started project matching."""
    starters = (
        "ask me about my interests",
        "match projects to my skills",
    )

    return any(
        item.get("role") == "user"
        and any(
            phrase in item.get("content", "").lower()
            for phrase in starters
        )
        for item in messages[:-1]
    )


# --------------------------------------------------
# Format project descriptions
# --------------------------------------------------

def format_project_description(description):
    """Turn source bullet characters into separate Markdown list items."""
    if not description:
        return "Not listed"

    description = str(description).strip()
    description = description.replace("\r\n", "\n")
    description = description.replace("\r", "\n")

    parts = [
        part.strip()
        for part in description.split("•")
        if part.strip()
    ]

    if len(parts) <= 1:
        return description

    introduction = parts[0]
    tasks = parts[1:]

    formatted_tasks = "\n".join(
        f"- {task}" for task in tasks
    )

    if introduction:
        return (
            f"{introduction}\n\n"
            "**Possible tasks include:**\n\n"
            f"{formatted_tasks}"
        )

    return formatted_tasks


# --------------------------------------------------
# Project formatting helpers
# --------------------------------------------------

def clean_field(value):
    """Convert a field into readable text without inventing missing data."""
    if value is None:
        return "Not listed"

    if isinstance(value, list):
        values = [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

        return ", ".join(values) if values else "Not listed"

    value = str(value).strip()
    return value if value else "Not listed"


def normalize_official_url(url):
    """Accept only absolute HTTP(S) URLs from project API records."""
    if not isinstance(url, str):
        return None

    url = url.strip()

    if re.match(r"^https?://", url, flags=re.IGNORECASE):
        return url

    return None


def format_official_project_matches(
    answer,
    projects,
    user_message,
):
    """
    Format official project details from API records.
    The model identifies relevant titles; the application supplies details.
    """
    if not projects:
        return (
            "I couldn't retrieve current VTURCS project records. "
            "Please try again later. I won't guess project names or links."
        )

    answer_lower = answer.lower()
    all_requested = asks_for_all_projects(user_message)

    if all_requested:
        selected = [
            project
            for project in projects
            if isinstance(project, dict)
        ]
    else:
        selected = [
            project
            for project in projects
            if (
                isinstance(project, dict)
                and clean_field(project.get("title")) != "Not listed"
                and clean_field(project.get("title")).lower()
                in answer_lower
            )
        ][:MAX_RECOMMENDED_PROJECTS]

    if not selected:
        return (
            "I couldn't confidently match the response to the official "
            "VTURCS project records. Try asking to list all available "
            "projects, or describe your interests and skills again."
        )

    output = []

    if answer.strip():
        output.extend([answer.strip(), ""])

    output.append("## Official VTURCS Project Details")

    for project in selected:
        title = clean_field(project.get("title"))
        faculty = clean_field(project.get("faculty"))
        skills = clean_field(project.get("skills"))

        description = format_project_description(
            project.get("description", "")
        )

        project_url = normalize_official_url(
            project.get("project_url")
        )

        output.append("")

        if project_url:
            output.append(f"### [{title}]({project_url})")
        else:
            output.append(f"### {title}")

        output.append(f"- **Professor:** {faculty}")
        output.append(f"- **Skills:** {skills}")
        output.append("- **Description:**")
        output.append("")
        output.append(description)

    output.append("")
    output.append(
        "*A project listing does not guarantee that the professor "
        "is currently recruiting.*"
    )

    return "\n".join(output)


# --------------------------------------------------
# Home page
# --------------------------------------------------

@app.get("/")
def index():
    return render_template(
        "index.html",
        scenarios=SCENARIOS,
    )


# --------------------------------------------------
# Frontend configuration status
# --------------------------------------------------

@app.get("/api/config")
def config():
    return jsonify({
        "model_configured": bool(
            os.getenv("MODEL_API_KEY")
            and os.getenv("MODEL_BASE_URL")
            and os.getenv("MODEL_NAME")
        ),
        "model_name": get_model_name(),
    })


# --------------------------------------------------
# Chat endpoint
# --------------------------------------------------

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}

    messages = data.get("messages", [])
    mode = data.get("mode", "experimental")
    scenario_id = data.get("scenario", "none")

    # Validate the conversation.
    if not isinstance(messages, list) or not messages:
        return jsonify({
            "error": "Send at least one message."
        }), 400

    messages = messages[-MAX_MESSAGES:]
    cleaned = []

    for item in messages:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        cleaned.append({
            "role": role,
            "content": content[:MAX_MESSAGE_LENGTH],
        })

    if not cleaned:
        return jsonify({
            "error": "No valid messages were provided."
        }), 400

    if cleaned[-1]["role"] != "user":
        return jsonify({
            "error": "The last message must be from the user."
        }), 400

    latest_message = cleaned[-1]["content"]
    latest_lower = latest_message.lower()

    # --------------------------------------------------
    # Choose assistant configuration
    # --------------------------------------------------

    if mode == "base":
        system_prompt = BASE_SYSTEM_PROMPT
    else:
        mode = "experimental"
        system_prompt = EXPERIMENTAL_SYSTEM_PROMPT

    # Detect when reference documents are relevant.
    asks_about_readiness = any(
        term in latest_lower
        for term in (
            "readiness score",
            "research readiness",
            "readiness assessment",
            "score my",
            "assess my",
            "assess readiness",
            "rubric",
            "dimension score",
        )
    )

    asks_about_integrity_or_ethics = any(
        term in latest_lower
        for term in (
            "honor code",
            "academic integrity",
            "plagiarism",
            "citation",
            "ethics",
            "ethical",
            "participant data",
            "privacy",
            "consent",
            "fabricat",
            "attribution",
            "disclose ai",
            "responsible ai",
        )
    )

    include_rubric = (
        mode == "experimental"
        or asks_about_readiness
    )

    include_honor_code = asks_about_integrity_or_ethics

    if include_rubric:
        if RUBRIC_DOCUMENT_TEXT:
            system_prompt += (
                "\n\nREFERENCE DOCUMENT: RESEARCH-READINESS RUBRIC\n"
                + RUBRIC_DOCUMENT_TEXT
            )
        else:
            system_prompt += (
                "\n\nREFERENCE DOCUMENT STATUS:\n"
                "The research-readiness rubric PDF could not be loaded. "
                "Do not pretend to have consulted it or invent its criteria."
            )

    if include_honor_code:
        if HONOR_CODE_TEXT:
            system_prompt += (
                "\n\nREFERENCE DOCUMENT: VIRGINIA TECH HONOR CODE\n"
                + HONOR_CODE_TEXT
            )
        else:
            system_prompt += (
                "\n\nREFERENCE DOCUMENT STATUS:\n"
                "The Virginia Tech Honor Code PDF could not be loaded. "
                "Do not pretend to have consulted its contents."
            )

    if include_rubric or include_honor_code:
        system_prompt += (
            "\n\nUse reference documents only for what they actually support. "
            "Do not invent rubric criteria or university policies. "
            "If a document does not answer a question, say so. "
            "Do not determine whether a student has committed an Honor Code violation."
        )

    # --------------------------------------------------
    # Add standardized scenario instructions
    # --------------------------------------------------

    if isinstance(scenario_id, str) and scenario_id in SCENARIOS:
        scenario = SCENARIOS[scenario_id]

        if isinstance(scenario, dict):
            scenario_prompt = scenario.get("prompt", "")

            if scenario_prompt:
                system_prompt += (
                    "\n\nACTIVE STANDARDIZED SCENARIO:\n"
                    + scenario_prompt
                )

    # --------------------------------------------------
    # Determine whether this is project matching
    # --------------------------------------------------

    profile_collection_request = is_profile_collection_request(
        latest_message
    )

    matching_flow_active = matching_flow_was_started(cleaned)

    profile_response = (
        matching_flow_active
        and not profile_collection_request
        and assistant_asked_for_profile(cleaned)
    )

    project_question = (
        is_project_question(latest_message)
        or profile_response
    )

    format_projects = needs_official_project_formatting(
        latest_message,
        profile_response=profile_response,
    )

    # --------------------------------------------------
    # Retrieve current VTURCS projects when relevant
    # --------------------------------------------------

    project_records = []

    if project_question:
        try:
            records = get_vturcs_project_records()

            if isinstance(records, list):
                project_records = records

            project_data = format_projects_for_model(project_records)

            if not project_data or not str(project_data).strip():
                project_data = (
                    "No VTURCS project data was returned. "
                    "Do not invent projects or project links."
                )

            system_prompt += (
                "\n\nCURRENT VTURCS PROJECT DATA\n"
                "The following data comes from the VTURCS project API.\n\n"
                "DATA RULES:\n"
                "- Use only these records for project-specific facts.\n"
                "- Keep every title, faculty member, skill list, description, "
                "and URL attached to its own record.\n"
                "- Do not invent or guess project details or links.\n"
                "- Never attach a URL to a different project.\n"
                "- Do not claim that a professor is recruiting unless the "
                "records explicitly establish that fact.\n"
                "- If a field is missing, say 'Not listed'.\n"
                "- For descriptions with multiple tasks, put each task on "
                "a separate Markdown bullet line.\n"
                "- Do not fabricate a project URL if one is missing.\n\n"
                "For recommendations, identify up to three relevant exact "
                "project titles. For a request to list all projects, mention "
                "the available titles from the supplied data.\n"
                "The final project details and links will be formatted from "
                "the official records by the application.\n\n"
                "PROJECT DATA STARTS HERE:\n"
                + str(project_data)
                + "\nPROJECT DATA ENDS HERE."
            )

        except Exception:
            app.logger.exception("VTURCS project retrieval failed")
            project_records = []

            system_prompt += (
                "\n\nVTURCS PROJECT DATA STATUS:\n"
                "Current project retrieval failed. Tell the user that "
                "project information could not be retrieved. Do not "
                "invent projects, details, or links."
            )

    system_prompt += "\n\n" + CONCISE_RESPONSE_GUIDANCE

    system_prompt += """
ADDITIONAL APPLICATION RULES:
- Answer general questions conversationally; do not force them into project matching.
- Use the conversation history to answer follow-up questions.
- For project listings or recommendations, name only exact project titles from the supplied records.
- Do not write or guess project URLs; the application will add official URLs from records.
- For readiness scoring, use the supplied seven-dimension framework and loaded rubric when available.
- If there is insufficient evidence for a score, say what evidence is missing rather than guessing.
"""

    # --------------------------------------------------
    # Guide the project-matching interview
    # --------------------------------------------------

    if profile_collection_request:
        system_prompt += """
PROJECT-MATCHING INTERVIEW — FIRST TURN:
The user has selected the option to match VTURCS projects to their skills.
Do not recommend or list projects yet. Ask for a short profile covering:
1. Research areas of interest.
2. Technical skills and tools.
3. Previous research, class projects, or other relevant experience.
4. What they hope to gain from a VTURCS project.
Let the user answer in one message and skip anything they do not know.
After they respond, compare their profile with official VTURCS project records.
"""
    elif matching_flow_active:
        system_prompt += """
PROJECT-MATCHING INTERVIEW — PROFILE PROVIDED:
The user is responding to the VTURCS project-matching questions.
Use their profile and official project records to recommend up to three relevant
projects. Mention each selected title exactly as it appears in the records so
the application can safely format official details and links.
"""

    # --------------------------------------------------
    # Call the model
    # --------------------------------------------------

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=get_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                *cleaned,
            ],
            temperature=0.3,

            # Nemotron uses this token budget for reasoning and final text.
            # Disabling thinking leaves more budget for the answer.
            max_tokens=4096,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            },
        )

        if not response.choices:
            app.logger.error(
                "Model returned no choices in its response."
            )
            return jsonify({
                "error": (
                    "The AI model returned no response. Please try again."
                )
            }), 502

        choice = response.choices[0]
        answer = choice.message.content or ""

        app.logger.info(
            "Model response received: finish_reason=%s, content_length=%s",
            choice.finish_reason,
            len(answer),
        )

        if not answer.strip():
            app.logger.error(
                "Model returned empty content: finish_reason=%s, usage=%s",
                choice.finish_reason,
                response.usage,
            )
            return jsonify({
                "error": (
                    "The AI model returned an empty answer. Please retry. "
                    "If the problem continues, check the Render logs."
                )
            }), 502

        # The first matching turn asks questions instead of recommending
        # projects before the user has provided their profile.
        if profile_collection_request:
            answer = (
                "Absolutely! I can help match you with VTURCS research projects.\n\n"
                "**1. What research areas interest you most?**\n"
                "For example, AI/ML, data analytics, NLP, cybersecurity, "
                "or web development.\n\n"
                "**2. What technical skills or tools do you know?**\n"
                "For example, Python, Java, SQL, or machine learning.\n\n"
                "**3. What relevant experience do you have?**\n"
                "You can mention research papers, class projects, personal "
                "projects, or teamwork.\n\n"
                "**4. What would you like to gain from research?**\n"
                "For example, hands-on experience, publishing, learning new "
                "methods, or working with a faculty advisor.\n\n"
                "Answer in one message, and I’ll compare your profile with "
                "official VTURCS listings and recommend up to three relevant "
                "projects."
            )

        # Only format official records for project listing or matching tasks.
        if format_projects and not profile_collection_request:
            answer = format_official_project_matches(
                answer=answer,
                projects=project_records,
                user_message=latest_message,
            )

        return jsonify({
            "reply": answer,
            "model": get_model_name(),
        })

    except Exception:
        app.logger.exception("Model request failed")

        return jsonify({
            "error": (
                "The model request failed. Check the Flask terminal "
                "and verify your provider URL, model name, and API key."
            )
        }), 502


# --------------------------------------------------
# Run Flask
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=True,
    )
