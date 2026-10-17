
import logging
import re
from datetime import date
from html import unescape
from urllib.parse import urlparse

import requests

# --------------------------------------------------
# Configuration
# --------------------------------------------------

API_URL = "https://spring-vturcs-backend.endeavour.cs.vt.edu/opportunities"
REQUEST_TIMEOUT = 15
MAX_PROJECTS = 100
MAX_DESCRIPTION_LENGTH = 2500

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def clean_text(value):
    """Convert API values into readable plain text."""
    if value is None:
        return "Not listed"

    if isinstance(value, (dict, list)):
        value = str(value)

    text = unescape(str(value))
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    return text.strip() or "Not listed"


# --------------------------------------------------
# Official project URL
# --------------------------------------------------

def get_project_url(project):
    """
    Read the URL only from this project's projectURL field.
    Never substitute a URL from another source.
    """
    raw_url = project.get("projectURL")

    if not isinstance(raw_url, str) or not raw_url.strip():
        return None

    url = raw_url.strip()

    if any(character.isspace() for character in url):
        return None

    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("https://", "http://")):
        # Add a scheme only; do not invent a domain or path.
        url = "https://" + url

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return None

    if not parsed.hostname or "." not in parsed.hostname:
        return None

    return url


# --------------------------------------------------
# Project tags
# --------------------------------------------------

def get_project_tags(project):
    tags = project.get("tags", [])

    result = {
        "skills": [],
        "researchArea": [],
        "location": [],
        "jobType": [],
        "compensation": [],
    }

    if not isinstance(tags, list):
        return result

    for tag in tags:
        if not isinstance(tag, dict):
            continue

        category = tag.get("tagCategory")
        name = tag.get("tagName")

        if not category or not name:
            continue

        category = str(category).strip()
        name = clean_text(name)

        if category not in result:
            result[category] = []

        if name != "Not listed" and name not in result[category]:
            result[category].append(name)

    return result


def format_tags(values):
    return ", ".join(values) if values else "Not listed"


# --------------------------------------------------
# Listing status
# --------------------------------------------------

def is_expired(project):
    """Exclude projects whose end date has passed."""
    end_date = project.get("endDate")

    if not end_date:
        return False

    try:
        expiry_date = date.fromisoformat(str(end_date)[:10])
        return expiry_date < date.today()
    except (ValueError, TypeError):
        logger.warning(
            "Could not parse endDate for project %s: %r",
            project.get("researchTitle", "Unknown"),
            end_date,
        )
        return False


def is_draft(project):
    return project.get("draft") is True


# --------------------------------------------------
# Format one project
# --------------------------------------------------

def format_project(project):
    """Keep each project's details and URL together."""
    title = clean_text(project.get("researchTitle"))
    faculty = clean_text(project.get("facultyAdvisor"))
    description = clean_text(project.get("researchDescription"))

    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = (
            description[:MAX_DESCRIPTION_LENGTH].rstrip() + "..."
        )

    tags = get_project_tags(project)

    return {
        "title": title,
        "faculty": faculty,
        "description": description,
        "skills": tags.get("skills", []),
        "research_areas": tags.get("researchArea", []),
        "locations": tags.get("location", []),
        "work_arrangements": tags.get("jobType", []),
        "compensation": tags.get("compensation", []),
        "start_date": project.get("startDate") or "Not listed",
        "end_date": project.get("endDate") or "Not listed",
        "project_url": get_project_url(project),
        "position_id": project.get("positionId"),
    }


# --------------------------------------------------
# Retrieve structured project records
# --------------------------------------------------

def get_vturcs_project_records():
    """
    Return a list of structured API records.

    Returns:
        list: API request succeeded.
        None: API request or response parsing failed.
    """
    try:
        response = requests.get(
            API_URL,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            logger.error(
                "Unexpected VTURCS API response type: %s",
                type(data).__name__,
            )
            return None

        records = []

        for project in data:
            if not isinstance(project, dict):
                continue

            if is_draft(project) or is_expired(project):
                continue

            records.append(format_project(project))

        records = records[:MAX_PROJECTS]

        logger.info("Loaded %d VTURCS project listings", len(records))
        return records

    except requests.RequestException:
        logger.exception("Could not retrieve VTURCS projects")
        return None

    except (ValueError, TypeError):
        logger.exception("Could not parse VTURCS API response")
        return None


# --------------------------------------------------
# Format project data for the model
# --------------------------------------------------

def format_projects_for_model(projects):
    if projects is None:
        return (
            "ERROR: VTURCS project retrieval failed. "
            "Do not invent projects or links."
        )

    if not projects:
        return (
            "No eligible VTURCS project listings were returned. "
            "Do not invent projects."
        )

    sections = [
        f"Number of VTURCS project listings: {len(projects)}",
        (
            "Each project's title, description, faculty, tags, and URL "
            "belong to that exact record. Do not mix records."
        ),
    ]

    for index, project in enumerate(projects, start=1):
        sections.append(
            f"""PROJECT {index}
Title: {project["title"]}
Faculty advisor: {project["faculty"]}
Description from VTURCS: {project["description"]}
Skills: {format_tags(project["skills"])}
Research areas: {format_tags(project["research_areas"])}
Location: {format_tags(project["locations"])}
Work arrangement: {format_tags(project["work_arrangements"])}
Compensation: {format_tags(project["compensation"])}
Start date: {project["start_date"]}
End date: {project["end_date"]}
Project URL from VTURCS API: {project["project_url"] or "Not listed"}
Position ID: {project["position_id"] or "Not listed"}"""
        )

    return "\n\n--- NEXT PROJECT ---\n\n".join(sections)


# Backwards-compatible helper for any existing imports.
def get_vturcs_projects():
    return format_projects_for_model(get_vturcs_project_records())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = get_vturcs_project_records()
    print(format_projects_for_model(records))
