"""Reliability and fault-injection test suite for LLM and Multi-Agent Orchestration.

All tests in this file use controlled mocks for fault injection to evaluate resilience
against transient external provider failures without consuming live API tokens.
These tests are clearly distinguished from live API tests.
"""
from unittest.mock import MagicMock, patch
import pytest
import groq
from pydantic import BaseModel, Field

from llm.exceptions import (
    LLMAuthenticationError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from llm.groq_provider import GroqProvider
from llm.schemas import LLMConfig, LLMMessage
from agents.summary_agent import SummaryAgent
from agents.schemas import (
    EvidenceClaim,
    EvidenceQualityResult,
    PatientContextResult,
    RetrievedPassage,
    SafetyResult,
)


class MockClinicalSchema(BaseModel):
    finding: str = Field(description="Clinical finding text")
    confidence: float = Field(default=0.9, description="Confidence score")


# =========================================================================
# 1. Groq HTTP 429 Rate Limiting (Mocked)
# =========================================================================
def test_groq_http_429_rate_limiting_mocked():
    """Verify provider correctly identifies HTTP 429 rate limit errors from GroqCloud."""
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_resp = MagicMock(status_code=429, headers={"retry-after": "5"})
    mock_client.chat.completions.create.side_effect = groq.RateLimitError(
        message="Rate limit reached: Limit 8000 TPM",
        response=mock_resp,
        body={"error": {"message": "Rate limit reached", "type": "tokens", "code": "rate_limit_exceeded"}},
    )
    provider._client = mock_client

    with pytest.raises(LLMRateLimitError) as exc_info:
        provider.generate([LLMMessage(role="user", content="Test query")])

    assert "rate limit" in str(exc_info.value).lower() or "429" in str(exc_info.value)


# =========================================================================
# 2. Provider Timeout (Mocked)
# =========================================================================
def test_provider_timeout_mocked():
    """Verify provider wraps APITimeoutError in LLMTimeoutError with clear message."""
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=0, timeout_seconds=1.0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_req = MagicMock()
    mock_client.chat.completions.create.side_effect = groq.APITimeoutError(request=mock_req)
    provider._client = mock_client

    with pytest.raises(LLMTimeoutError):
        provider.generate([LLMMessage(role="user", content="Timeout query")])


# =========================================================================
# 3. Provider Unavailable / Connection Error (Mocked)
# =========================================================================
def test_provider_unavailable_mocked():
    """Verify connection refusal or unreachable provider raises LLMProviderUnavailableError."""
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_req = MagicMock()
    mock_client.chat.completions.create.side_effect = groq.APIConnectionError(
        message="Could not reach GroqCloud endpoint",
        request=mock_req,
    )
    provider._client = mock_client

    with pytest.raises(LLMProviderUnavailableError) as exc_info:
        provider.generate([LLMMessage(role="user", content="Unreachable query")])

    assert "unavailable" in str(exc_info.value).lower() or "reach" in str(exc_info.value).lower()


# =========================================================================
# 4. Malformed Structured Output (Mocked)
# =========================================================================
def test_malformed_structured_output_mocked():
    """Verify unparseable JSON or schema non-conformance raises LLMStructuredOutputError."""
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=0)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_choice = MagicMock()
    # Unquoted keys and broken JSON syntax
    mock_choice.message.content = "{finding: unquoted, confidence: NOT_A_NUMBER}"
    mock_choice.finish_reason = "stop"
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice], usage=None)
    provider._client = mock_client

    with pytest.raises(LLMStructuredOutputError):
        provider.generate_structured(
            messages=[LLMMessage(role="user", content="Extract")],
            schema=MockClinicalSchema,
        )


# =========================================================================
# 5. Bounded Retry Exhaustion (Mocked)
# =========================================================================
def test_bounded_retry_exhaustion_mocked():
    """Verify provider retries exactly max_retries times and does not loop indefinitely."""
    max_retries = 2
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=max_retries, timeout_seconds=0.1)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_req = MagicMock()
    # Always time out
    mock_client.chat.completions.create.side_effect = groq.APITimeoutError(request=mock_req)
    provider._client = mock_client

    with patch("time.sleep", return_value=None):  # Fast test without sleeping
        with pytest.raises(LLMTimeoutError):
            provider.generate([LLMMessage(role="user", content="Retry test")])

    # Initial attempt + 2 retries = 3 calls total
    assert mock_client.chat.completions.create.call_count == max_retries + 1


# =========================================================================
# 6. Deterministic Fallback in SummaryAgent (Mocked)
# =========================================================================
def test_deterministic_fallback_in_summary_agent_mocked():
    """Verify that when GroqCloud fails, SummaryAgent safely degrades to extractive mode."""
    mock_provider = MagicMock()
    mock_provider.generate_structured.side_effect = LLMRateLimitError("Simulated Groq 429 rate limit exceeded")

    agent = SummaryAgent(llm_provider=mock_provider)

    ctx_res = PatientContextResult(documented_facts=["Patient has asthma"], missing_information=[])
    qual_res = EvidenceQualityResult(
        evidence_quality_status="acceptable",
        accepted_evidence=[
            RetrievedPassage(
                source_id="who_global_patient_safety_001",
                document_title="WHO Patient Safety Guide",
                section="Section 1",
                page_number=4,
                excerpt="Patient safety is a global healthcare priority requiring systematic medication verification.",
                retrieval_score=0.92,
            )
        ],
    )
    safety_res = SafetyResult(safety_status="safe", escalation_reason=None)

    res = agent.execute(
        question="What are medication safety priorities for asthma?",
        context_result=ctx_res,
        quality_result=qual_res,
        safety_result=safety_res,
    )

    # Must produce grounded answer via extractive fallback
    assert res.direct_answer is not None
    assert len(res.direct_answer) > 20
    assert "deterministic_grounded_extractive" in res.generation_mode
    assert len(res.citations) > 0
    assert res.citations[0].source_id == "who_global_patient_safety_001"
    assert len(res.limitations) > 0
    assert any("educational" in lim.lower() for lim in res.limitations)


# =========================================================================
# 7. Recovery After Provider Availability Returns (Mocked)
# =========================================================================
def test_recovery_after_provider_availability_returns_mocked():
    """Verify provider recovers cleanly when transient errors resolve on subsequent calls."""
    cfg = LLMConfig(provider="groq", api_key="dummy_mock_key", max_retries=1)
    provider = GroqProvider(cfg)

    mock_client = MagicMock()
    mock_req = MagicMock()
    
    # Successful mock completion
    mock_choice = MagicMock()
    mock_choice.message.content = '{"finding": "Transient asthma resolved", "confidence": 0.95}'
    mock_choice.finish_reason = "stop"
    mock_success = MagicMock(choices=[mock_choice], usage=MagicMock(total_tokens=28, prompt_tokens=20, completion_tokens=8))

    # First call times out, retry succeeds!
    mock_client.chat.completions.create.side_effect = [
        groq.APITimeoutError(request=mock_req),
        mock_success,
    ]
    provider._client = mock_client

    with patch("time.sleep", return_value=None):
        parsed, resp = provider.generate_structured(
            messages=[LLMMessage(role="user", content="Extract clinical finding")],
            schema=MockClinicalSchema,
        )

    assert isinstance(parsed, MockClinicalSchema)
    assert parsed.finding == "Transient asthma resolved"
    assert parsed.confidence == 0.95
    assert resp.usage.total_tokens == 28
    assert mock_client.chat.completions.create.call_count == 2
