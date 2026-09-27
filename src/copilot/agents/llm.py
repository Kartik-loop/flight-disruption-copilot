"""Create the configured structured extractor only when a text request needs it.

Lazy construction keeps structured-form requests and unit tests independent of
API keys. The provider wrappers share LangChain's structured-output interface;
the rest of the workflow does not depend on a vendor SDK.
"""

from langchain_core.runnables import Runnable

from copilot.config import LLMProvider, Settings, get_settings
from copilot.schemas.requests import IntakeFacts


class MissingProviderKeyError(ValueError):
    """Separate safe configuration guidance from potentially sensitive provider failures."""


def create_extractor(config: Settings | None = None) -> Runnable:
    """Keep credentials out of prompts and fail clearly when the selected provider lacks a key."""
    config = config or get_settings()
    if config.llm_provider == LLMProvider.OPENAI:
        if not config.openai_api_key or config.openai_api_key.startswith("your-"):
            raise MissingProviderKeyError("Configure OPENAI_API_KEY or use structured input.")
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            api_key=config.openai_api_key,
            model=config.openai_model,
            temperature=config.llm_temperature,
            timeout=30,
            max_retries=1,
        )
    else:
        if not config.google_api_key or config.google_api_key.startswith("your-"):
            raise MissingProviderKeyError("Configure GOOGLE_API_KEY or use structured input.")
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(
            google_api_key=config.google_api_key,
            model=config.google_model,
            temperature=config.llm_temperature,
            timeout=30,
            max_retries=1,
        )
    # LEARN: Tool calling constrains the shape of extracted facts, not their truth.
    # Nullable fields allow honest omissions. Pydantic validates again after the
    # call, and deterministic code decides which missing facts require a question.
    # https://developers.openai.com/api/docs/guides/structured-outputs
    return model.with_structured_output(IntakeFacts, method="function_calling")
