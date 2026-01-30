"""Agno agent wiring. OpenAI model we use; from config, key we take."""

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from app.config import get_settings


def get_agent() -> Agent:
    """Build and return the agent. Once per app, reuse we should."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not set. In .env put it, you must.")
    model = OpenAIChat(
        id=settings.openai_model_id,
        api_key=settings.openai_api_key,
    )
    return Agent(model=model)
