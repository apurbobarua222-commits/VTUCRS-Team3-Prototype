# VTURCS Research-Readiness Chatbot Prototype

A Flask-based prototype for exploring undergraduate research readiness, responsible AI use, and feedback across seven rubric dimensions.

## Features

- Interactive browser-based chat interface.
- Base and experimental prompt configurations.
- Three standardized hypothetical scenarios.
- Seven research-readiness rubric dimensions.
- Provider-configurable API connection using an OpenAI-compatible endpoint.
- API credentials kept on the server, not in browser code.

## Important research limitations

This is an experimental prototype. Its scores, if requested from the model, are **model-generated scores**, not independently validated measures of student readiness. Do not use them as admissions decisions or as proof of competence. The base/experimental comparison changes the full prompt configuration, so it does not isolate the effect of any single prompt component. The scenarios are hypothetical and cannot establish real-world validity.

Before using this with real participants, obtain appropriate research/ethics guidance, explain data collection, minimize retention of personal data, and do not enter identifiable or confidential participant data.

## Requirements

- Python 3.10 or later
- API access from a provider that hosts GPT-OSS and offers an OpenAI-compatible chat-completions endpoint

A standard OpenAI API key should not be assumed to provide access to a separately hosted GPT-OSS model. Confirm the provider's endpoint and model identifier.

## Run locally

1. Open this folder in VS Code.
2. Create and activate a virtual environment:

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in the actual provider values:
   - `MODEL_API_KEY`
   - `MODEL_BASE_URL`
   - `MODEL_NAME`

5. Start the server:
   ```bash
   python app.py
   ```

6. Visit http://127.0.0.1:5000

If the provider does not support the OpenAI-compatible chat-completions API, adapt the client call to its documented API.

## Push to GitHub

Check that `.env` is not staged:
```bash
git status
```

Then:
```bash
git init
git add .
git commit -m "Build research-readiness chatbot prototype"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Do not replace `YOUR_GITHUB_REPOSITORY_URL` until you have created your own repository.

## Deploy

Deploy to a Python-compatible host. Set the API variables in the host's secret/environment settings, and use a production server such as:
```bash
gunicorn app:app
```

Do not put the API key in HTML, CSS, JavaScript, a public README, or GitHub Actions logs.
