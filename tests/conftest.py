"""Pytest configuration. Load .env so integration tests see OPENAI_API_KEY."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root so os.getenv("OPENAI_API_KEY") works in tests
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")
