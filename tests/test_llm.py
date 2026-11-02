"""Tests for the LLM subsystem: configuration, Groq provider, structured output, and health checks."""
import os
import unittest
from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from llm.factory import get_llm_config, get_llm_provider
from llm.groq_provider import GroqProvider
from llm.schemas import LLMConfig, LLMHealthStatus, LLMMessage, LLMResponse


class SampleClinicalExtract(BaseModel):
    finding: str = Field(description="Clinical finding excerpt")
    severity: str = Field(description="Documented severity level")


def test_llm_config_defaults():
    cfg = get_llm_config()
    assert cfg.provider == "groq"
    assert cfg.temperature == 0.1
    assert cfg.timeout_seconds == 30.0
    assert cfg.max_retries == 2


def test_llm_health_check_without_api_key():
    cfg = LLMConfig(provider="groq", api_key=None)
    provider = GroqProvider(cfg)
    status = provider.health_check()
    assert isinstance(status, LLMHealthStatus)
    assert status.configured is False
    assert status.available is False
    assert status.status_code == "NOT_CONFIGURED"
    assert "GROQ_API_KEY is not set" in status.message


def test_llm_health_check_with_invalid_api_key():
    cfg = LLMConfig(provider="groq", api_key="gsk_invalid_test_key_12345")
    provider = GroqProvider(cfg)
    status = provider.health_check()
    assert isinstance(status, LLMHealthStatus)
    assert status.configured is True
    assert status.available is False
    assert status.status_code in ("AUTH_FAILED", "UNAVAILABLE")


def test_generate_raises_auth_error_without_key():
    cfg = LLMConfig(provider="groq", api_key=None)
    provider = GroqProvider(cfg)
    with pytest.raises(LLMAuthenticationError) as exc_info:
        provider.generate([LLMMessage(role="user", content="Hello")])
    assert "GROQ_API_KEY is not configured" in str(exc_info.value)


def test_structured_parsing_success_mocked():
    cfg = LLMConfig(provider="groq", api_key="dummy_key")
    provider = GroqProvider(cfg)

    # Mock the internal client response
    mock_choice = MagicMock()
    mock_choice.message.content = '{"finding": "Acute wheezing", "severity": "moderate"}'
    mock_choice.finish_reason = "stop"

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 25
    mock_usage.completion_tokens = 12
    mock_usage.total_tokens = 37

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    provider._client = mock_client

    parsed, response = provider.generate_structured(
        messages=[LLMMessage(role="user", content="Extract finding")],
        schema=SampleClinicalExtract,
    )

    assert isinstance(parsed, SampleClinicalExtract)
    assert parsed.finding == "Acute wheezing"
    assert parsed.severity == "moderate"
    assert response.usage.total_tokens == 37
    assert response.provider == "groq"


def test_structured_parsing_malformed_json_raises_error():
    cfg = LLMConfig(provider="groq", api_key="dummy_key", max_retries=0)
    provider = GroqProvider(cfg)

    mock_choice = MagicMock()
    mock_choice.message.content = 'THIS IS NOT JSON AT ALL'
    mock_choice.finish_reason = "stop"

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    provider._client = mock_client

    with pytest.raises(LLMStructuredOutputError):
        provider.generate_structured(
            messages=[LLMMessage(role="user", content="Extract finding")],
            schema=SampleClinicalExtract,
        )


def test_timeout_behavior_raises_timeout_error():
    import groq
    cfg = LLMConfig(provider="groq", api_key="dummy_key", max_retries=0, timeout_seconds=1.0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    # Create request object for APITimeoutError
    mock_request = MagicMock()
    mock_client.chat.completions.create.side_effect = groq.APITimeoutError(request=mock_request)
    provider._client = mock_client

    with pytest.raises(LLMTimeoutError):
        provider.generate([LLMMessage(role="user", content="Hello")])


def test_rate_limit_behavior_raises_rate_limit_error():
    import groq
    cfg = LLMConfig(provider="groq", api_key="dummy_key", max_retries=0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_response = MagicMock(status_code=429, headers={})
    mock_client.chat.completions.create.side_effect = groq.RateLimitError(
        message="Rate limit reached",
        response=mock_response,
        body={},
    )
    provider._client = mock_client

    with pytest.raises(LLMRateLimitError):
        provider.generate([LLMMessage(role="user", content="Hello")])


@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="Live GroqCloud test requires real GROQ_API_KEY")
def test_live_groq_api_call():
    """Live call to GroqCloud API verifying real authentication and structured parsing."""
    provider = get_llm_provider()
    health = provider.health_check()
    assert health.available is True, f"GroqCloud health check failed: {health.message}"

    messages = [
        LLMMessage(role="system", content="You are a clinical NLP extractor."),
        LLMMessage(role="user", content="The patient has mild intermittent asthma documented in record."),
    ]
    parsed, response = provider.generate_structured(messages=messages, schema=SampleClinicalExtract)
    assert isinstance(parsed, SampleClinicalExtract)
    assert len(parsed.finding) > 0
    assert response.usage.total_tokens > 0
