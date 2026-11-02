"""Pydantic schemas for LLM provider configuration, requests, responses, and health status."""
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class LLMConfig(BaseModel):
    """Centralized configuration for LLM provider operations."""
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(default="groq", description="Provider identifier (e.g. 'groq')")
    api_key: str | None = Field(default=None, description="API credential (must never be logged)")
    model: str = Field(default="llama-3.3-70b-versatile", description="Model name supported by provider")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=120.0, description="Per-request timeout budget")
    max_retries: int = Field(default=2, ge=0, le=5, description="Maximum bounded retry attempts")


class LLMMessage(BaseModel):
    """Standard message representation for chat completions."""
    role: Literal["system", "user", "assistant"]
    content: str


class LLMUsage(BaseModel):
    """Token usage tracking for observability and efficiency monitoring."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Standardized response from an LLM invocation."""
    content: str
    structured_data: dict[str, Any] | None = None
    model: str
    provider: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    latency_seconds: float = 0.0
    finish_reason: str | None = None
    retry_count: int = 0


class LLMHealthStatus(BaseModel):
    """Safe, non-credential-leaking status representation for UI/API health checks."""
    provider: str
    model: str
    configured: bool
    available: bool
    status_code: str
    message: str
    timeout_seconds: float
    max_retries: int
