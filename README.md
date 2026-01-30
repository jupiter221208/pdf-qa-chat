# pdf-qa-chat

Minimal Document QA chatbot that streams answers from your PDFs using FastAPI, Agno, and NiceGUI.

## Setup and run

- **Python 3.13+** required by the assignment. On Windows, use the 3.13 interpreter at `C:\Users\<USERNAME>\AppData\Local\Programs\Python\Python313` (e.g. `py -3.13` or that path’s `python.exe`).
- Create a venv with that Python, install deps, copy env:

```bash
# Windows (Python 3.13 at the path above):
& "C:\Users\<USERNAME>\AppData\Local\Programs\Python\Python313\python.exe" -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env

# macOS/Linux:
# python3.13 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && cp .env.example .env
```

- Put your `OPENAI_API_KEY` in `.env` (needed later for the agent; hello-world runs without it).
- Run the app:

```bash
python -m app.main
```

- Open http://localhost:8000 for the UI and http://localhost:8000/health for the API.

**follow the white rabbit**

## Cursor configuration

- **MCP / docs:** No custom MCP servers used for this hello-world; Agno, FastAPI, and NiceGUI docs were consulted in the browser.
- **Linters/formatters:** `ruff` is configured in `pyproject.toml` (line-length 100, py313). Run `ruff check app/` and `ruff format app/` to lint and format. Errors show in the IDE when the Python extension and Ruff are enabled.
- **Rules:** No `.cursorrules` or project-specific Cursor rules yet; can be added when expanding features.
- **Indexing:** Default Cursor indexing of the repo is used; no extra documentation indexing.
- **What helped:** Keeping the app in one package (`app/`), Pydantic settings for env, and a single `main.py` for FastAPI + NiceGUI kept the hello-world small and runnable.

## Project layout (hello-world)

- `app/` — FastAPI app, config (Pydantic), Agno agent wiring, NiceGUI page.
- `tests/` — Reserved for unit and integration tests (to be added with features).
- Config: `pyproject.toml`, `.env.example`, `.gitignore`.

## Trade-offs and next steps

- **Hello-world only:** No streaming, PDF upload, or async status yet. Agent is wired in `app/agent.py` but not called from the UI.
- **Next:** Add streaming endpoint, then PDF upload, then async status in the UI; add tests under `tests/unit` and `tests/integration`.
