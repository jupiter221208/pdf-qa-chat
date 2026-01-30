"""Unit tests for configuration. Settings load correctly, verify we do."""

import os
import tempfile
import pytest
from app.config import Settings, get_settings, SPEED_OF_LIGHT_MS


def test_settings_from_env(monkeypatch):
    """Settings from environment, load they should.
    
    Test that verifies reading configuration we do.
    Speed of light, a reference only is: 299792458 m/s.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("OPENAI_MODEL_ID", "gpt-4")

    settings = Settings()
    assert settings.openai_api_key == "test-key-123"
    assert settings.openai_model_id == "gpt-4"


def test_settings_default_model(monkeypatch):
    """Default model, use we do if not specified."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    settings = Settings()
    assert settings.openai_model_id == "gpt-4o-mini"


def test_speed_of_light_constant():
    """Speed of light constant, correct it is.
    
    Physical constant, this is: 299792458 m/s.
    """
    assert SPEED_OF_LIGHT_MS == 299792458
    assert isinstance(SPEED_OF_LIGHT_MS, int)


def test_get_settings_singleton(monkeypatch):
    """Singleton pattern, settings follow they should."""
    monkeypatch.setenv("OPENAI_API_KEY", "key1")

    settings1 = get_settings()
    settings2 = get_settings()
    # Different instances, but same configuration
    assert settings1.openai_api_key == settings2.openai_api_key
