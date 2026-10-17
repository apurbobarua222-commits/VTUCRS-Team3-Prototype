
# VTURCS Research Opportunities Chatbot

**Live Website:**
https://vtucrs-team3-prototype.onrender.com/

## Overview

The VTURCS Research Opportunities Chatbot is a web-based application designed to help students explore research opportunities available through Virginia Tech's Undergraduate Research in Computer Science (VTURCS) program.

The application provides a conversational interface through which students can discover research projects, understand project requirements, review faculty advisors, and identify opportunities aligned with their academic interests, technical skills, and experience.

The chatbot retrieves project information from the official VTURCS opportunities API and uses a language model to support natural-language interactions.

## Objectives

- Make VTURCS research opportunities easier for students to discover and understand.
- Help students identify research projects aligned with their interests and technical background.
- Present project descriptions, faculty advisors, required skills, and official project links in a clear format.
- Support exploration and comparison of research opportunities through a conversational interface.
- Provide a centralized interface for accessing official VTURCS project information.

## Features

### Research Project Discovery

Students can request information about available VTURCS research projects and review the opportunities returned by the official project data source.

### Personalized Project Exploration

Students can describe their interests, skills, coursework, and previous experience to explore research opportunities that may be relevant to their backgrounds.

Recommendations are intended to support exploration and do not guarantee project acceptance or faculty availability.

### Project Details

Where the official project records provide the information, the application presents:

- Project title
- Faculty advisor
- Project description
- Required or relevant skills
- Research areas and tags
- Project dates
- Official project link

Information is limited to the fields available in the source records. Missing details should not be treated as confirmed.

### Project Comparison

Students can compare research opportunities based on their research focus, skills, faculty advisor, and project descriptions.

### Conversational Interface

The application provides a chat-based interface for asking questions and exploring opportunities using natural language.

### Reference Documents

The application can load reference documents, including the Virginia Tech Honor Code and research-readiness rubric, for use in the relevant application mode.

## Technology Stack

### Frontend

- HTML5
- CSS3
- JavaScript
- Marked.js for Markdown rendering

### Backend

- Python
- Flask
- OpenAI-compatible API client
- Requests for retrieving project data
- pypdf for extracting text from PDF documents

### Language Model

The application is configured to use an NVIDIA-hosted language model through an OpenAI-compatible API.

The model endpoint, model name, and API key are configured through environment variables.

### Data Source

- Official VTURCS opportunities API:
  https://spring-vturcs-backend.endeavour.cs.vt.edu/opportunities

### Deployment

- GitHub for source code management
- Render for web application hosting

## Project Structure

```text
VTUCRS-Team3-Prototype/
├── app.py
├── prompts.py
├── rubric.py
├── document_loader.py
├── vturcs_loader.py
├── nvidia.py
├── requirements.txt
├── .gitignore
├── documents/
│   ├── vt_honor_code.pdf
│   └── research_readiness_rubric.pdf
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── chat.js
```

The structure above describes the expected application layout. Keep only files and folders that actually exist in the repository, and ensure that imports match their locations.

## Getting Started

### Prerequisites

- Python 3.10 or a compatible version supported by the dependencies
- pip
- An NVIDIA API key with access to the configured model
- Internet access for retrieving VTURCS project records

## Deployment

The application is hosted on Render.

Live application:
https://vtucrs-team3-prototype.onrender.com/


## Limitations

- Available project information depends on the official VTURCS API and the completeness of its records.
- Project availability and details may change over time.
- Personalized recommendations depend on the information students provide and the model's interpretation of it.
- Access to the chatbot depends on the availability of the hosted application and the configured language-model API.
- The application does not guarantee project eligibility, faculty approval, or research placement.

## Acknowledgments

This project is intended to make Virginia Tech undergraduate computer science research opportunities more accessible to students through a conversational interface.
