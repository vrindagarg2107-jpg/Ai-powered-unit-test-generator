# CodeCrafters — AI-Powered Unit Test Generator

## Deploy on Render

This folder is arranged with the Flask application at the repository root.

1. Upload **the contents of this folder** to the root of your GitHub repository (not the ZIP file itself).
2. In Render, choose **New + → Web Service**, connect that GitHub repository, and select the `main` branch.
3. Use these settings:

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Root Directory | Leave blank |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Health Check Path | `/` |

4. To enable real Gemini generation, add these Render Environment Variables:
   - `GEMINI_API_KEY` = your Google AI Studio API key
   - `GEMINI_MODEL` = `gemini-2.5-flash` (optional; this is the app default)
5. Click **Create Web Service** and wait for the deploy to finish.

Do not commit your real API key to GitHub. Add it only in Render's Environment settings.

## Important deployment notes

- Demo mode works without an API key. It is heuristic function detection and a test-plan template, not real AI-generated verified tests.
- Gemini mode requires a valid `GEMINI_API_KEY` and available API quota.
- The local Python test-validation endpoint runs submitted source code. It is intentionally hidden and disabled on Render because the current implementation is not a secure sandbox. Do not enable public execution of untrusted code.
- The homepage is served by Flask; `templates/index.html` must remain in the `templates/` folder.
- Python is pinned to 3.12 to avoid Render selecting a newer interpreter that may not match all dependencies.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.
