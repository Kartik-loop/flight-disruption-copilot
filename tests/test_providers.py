"""Verify provider selection and schema binding without external requests or real credentials.

Provider constructors are replaced here. Workflow tests separately exercise the
real LangGraph with a controlled extractor; live API quality is not claimed.
"""

import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("langchain_core")
from copilot.agents.llm import create_extractor  # noqa: E402
from copilot.config import Settings  # noqa: E402
from copilot.schemas.requests import IntakeFacts  # noqa: E402


@pytest.mark.parametrize(
    "provider,module,class_name,key_name",
    [
        ("openai", "langchain_openai", "ChatOpenAI", "api_key"),
        ("google", "langchain_google_genai", "ChatGoogleGenerativeAI", "google_api_key"),
    ],
)
def test_provider_and_structured_contract(monkeypatch, provider, module, class_name, key_name):
    """Both adapters must preserve configured models and bind the same fact-only schema."""
    calls = {}

    class FakeChat:
        """Capture constructor and schema options without opening a connection."""

        def __init__(self, **kwargs):
            """Keep provider options visible to assertions without handling real credentials."""
            calls.update(kwargs)

        def with_structured_output(self, schema, **kwargs):
            """Record the tool-call schema selection independently of a provider response."""
            calls.update(schema=schema, **kwargs)
            return "bound-extractor"

    monkeypatch.setitem(sys.modules, module, SimpleNamespace(**{class_name: FakeChat}))
    config = Settings(
        _env_file=None,
        llm_provider=provider,
        openai_api_key="test-not-a-key",
        google_api_key="test-not-a-key",
        openai_model="test-openai-model",
        google_model="test-google-model",
    )
    assert create_extractor(config) == "bound-extractor"
    assert calls["schema"] is IntakeFacts
    assert calls["method"] == "function_calling"
    assert calls["model"] == f"test-{provider}-model"
    assert calls[key_name] == "test-not-a-key"


@pytest.mark.parametrize("provider", ["openai", "google"])
def test_missing_keys_are_actionable(provider):
    """Do not silently switch providers or pretend free-text extraction works without a key."""
    config = Settings(
        _env_file=None, llm_provider=provider, openai_api_key=None, google_api_key=None
    )
    with pytest.raises(ValueError, match="structured input"):
        create_extractor(config)
