"""Factory and configuration loader for LLM providers."""
import os
from dotenv import load_dotenv

from llm.base import BaseLLMProvider
from llm.groq_provider import GroqProvider
from llm.schemas import LLMConfig

# Load environment configuration
load_dotenv()


def get_llm_config() -> LLMConfig:
    """Load LLM configuration from environment variables with safe defaults."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        api_key = api_key.strip()
        if not api_key:
            api_key = None

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    except ValueError:
        temperature = 0.1

    try:
        timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "30.0"))
    except ValueError:
        timeout_seconds = 30.0

    try:
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    except ValueError:
        max_retries = 2

    return LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


def get_llm_provider(config: LLMConfig | None = None) -> BaseLLMProvider:
    """Factory function returning the configured LLM provider instance."""
    cfg = config or get_llm_config()
    if cfg.provider == "groq":
        return GroqProvider(cfg)
    raise ValueError(f"Unsupported LLM provider: {cfg.provider}")
