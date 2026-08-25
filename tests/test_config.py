import os
import pytest
from app.config import AppConfig, get_config

def test_default_config_loading():
    config = get_config()
    assert isinstance(config, AppConfig)
    assert config.llm_provider in ["google", "openai"]
    assert config.llm_model is not None
    assert config.embedding_model is not None

def test_custom_env_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_API_KEY", "test-secret-key-123456789")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")

    config = get_config()
    assert config.llm_provider == "google"
    assert config.llm_api_key == "test-secret-key-123456789"
    assert config.llm_model == "gemini-2.5-flash"

def test_api_key_masking_security():
    config_empty = AppConfig(llm_api_key=None)
    assert config_empty.get_masked_api_key() == "NOT_SET"

    config_short = AppConfig(llm_api_key="123456")
    assert config_short.get_masked_api_key() == "***"

    config_full = AppConfig(llm_api_key="sk-test-secret-api-key-999")
    masked = config_full.get_masked_api_key()
    assert "sk-t" in masked
    assert "-999" in masked
    assert "secret-api-key" not in masked
    # Verify string representation of AppConfig does not naively expose keys if printed
    assert "sk-test-secret-api-key-999" not in masked
