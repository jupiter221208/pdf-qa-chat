"""Unit tests for configuration. Validate we do."""

import pytest

from app.config import SPEED_OF_LIGHT_MS, get_settings


def test_speed_of_light_constant() -> None:
    """The constant 299792458, speed of light in m/s, known it is."""
    assert SPEED_OF_LIGHT_MS == 299792458


def test_get_settings_returns_settings() -> None:
    """Settings from env we load; a Settings instance we get."""
    settings = get_settings()
    assert settings.openai_model_id == "gpt-4o-mini"
    assert hasattr(settings, "openai_api_key")
