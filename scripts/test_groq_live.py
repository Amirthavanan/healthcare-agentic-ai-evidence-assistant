"""CLI diagnostic script for verifying live GroqCloud LLM integration."""
import os
import sys
from pathlib import Path
from pydantic import BaseModel, Field

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from llm.factory import get_llm_config, get_llm_provider
from llm.schemas import LLMMessage


class HarmlessVerificationSchema(BaseModel):
    system_name: str = Field(description="Name of the AI system")
    verified_clinical_domain: str = Field(description="Clinical domain (e.g. Patient Safety)")
    is_live_call_successful: bool = Field(description="True if live call succeeded")


def main():
    print("=== GroqCloud Live Integration Probe ===")
    cfg = get_llm_config()
    print(f"Provider: {cfg.provider}")
    print(f"Model: {cfg.model}")
    print(f"Temperature: {cfg.temperature}")
    print(f"Timeout: {cfg.timeout_seconds}s")
    print(f"API Key present: {'YES (hidden)' if cfg.api_key else 'NO'}")

    provider = get_llm_provider(cfg)
    health = provider.health_check()
    print(f"\nHealth Check Status: {health.status_code}")
    print(f"Message: {health.message}")
    print(f"Available: {health.available}")

    if not health.available:
        print("\n[BLOCKED] Real GroqCloud integration is currently BLOCKED pending provision of a valid GROQ_API_KEY.")
        print("To enable, set GROQ_API_KEY in your .env file or environment.")
        return 1

    print("\nAttempting live harmless structured generation test...")
    messages = [
        LLMMessage(
            role="system",
            content="You are a clinical decision support assistant verifier.",
        ),
        LLMMessage(
            role="user",
            content="Verify this system as 'Healthcare Agentic AI Evidence Assistant' focusing on 'Patient Safety'.",
        ),
    ]

    try:
        parsed, response = provider.generate_structured(messages, HarmlessVerificationSchema)
        print("\n[SUCCESS] Live GroqCloud call completed successfully!")
        print(f"Model used: {response.model}")
        print(f"Latency: {response.latency_seconds}s")
        print(f"Tokens: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
        print("Parsed Structured Output:")
        print(parsed.model_dump_json(indent=2))
        return 0
    except Exception as exc:
        print(f"\n[FAILED] Live call failed: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
