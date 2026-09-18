"""
tests/test_config.py — Unit tests for configuration loading.

WHAT: Verifies that Settings loads correctly from environment variables.
WHY:  If config loading is broken, nothing else works. Testing it ensures
      we catch issues like typos in field names or wrong defaults early.
"""

import os
from unittest.mock import patch

from copilot.config import Settings, LLMProvider, PROJECT_ROOT


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_defaults(self):
        """Default values should be sensible."""
        # LEARN: We create a fresh Settings() to test defaults, ignoring
        # any .env file that might exist. We patch env vars to be empty.
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)  # Skip .env file
            assert s.llm_provider == LLMProvider.OPENAI
            assert s.openai_model == "gpt-4o-mini"
            assert s.llm_temperature == 0.1
            assert s.api_port == 8000

    def test_env_override(self):
        """Environment variables should override defaults."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "google",
            "GOOGLE_API_KEY": "test-key-123",
            "LLM_TEMPERATURE": "0.5",
        }, clear=True):
            s = Settings(_env_file=None)
            assert s.llm_provider == LLMProvider.GOOGLE
            assert s.google_api_key == "test-key-123"
            assert s.llm_temperature == 0.5

    def test_project_root_exists(self):
        """PROJECT_ROOT should point to an actual directory."""
        assert PROJECT_ROOT.exists()
        assert (PROJECT_ROOT / "pyproject.toml").exists()
