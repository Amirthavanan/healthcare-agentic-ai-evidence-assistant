"""Exceptions for LLM provider operations in Healthcare Agentic AI."""

class LLMError(Exception):
    """Base exception for all LLM errors."""
    def __init__(self, message: str, provider: str = "unknown", error_code: str = "LLM_ERROR"):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.error_code = error_code


class LLMAuthenticationError(LLMError):
    """Raised when authentication fails (missing, invalid, or expired API key)."""
    def __init__(self, message: str = "LLM authentication failed: invalid or missing API key", provider: str = "groq"):
        super().__init__(message, provider=provider, error_code="AUTH_FAILED")


class LLMRateLimitError(LLMError):
    """Raised when provider rate limits are exceeded (HTTP 429)."""
    def __init__(self, message: str = "LLM provider rate limit exceeded", provider: str = "groq", retry_after: float | None = None):
        super().__init__(message, provider=provider, error_code="RATE_LIMITED")
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """Raised when an LLM invocation exceeds the configured timeout budget."""
    def __init__(self, message: str = "LLM request timed out", provider: str = "groq", timeout_seconds: float = 30.0):
        super().__init__(message, provider=provider, error_code="TIMEOUT")
        self.timeout_seconds = timeout_seconds


class LLMProviderUnavailableError(LLMError):
    """Raised when the LLM provider cannot be reached (network/server failure or unconfigured)."""
    def __init__(self, message: str = "LLM provider is currently unavailable", provider: str = "groq"):
        super().__init__(message, provider=provider, error_code="PROVIDER_UNAVAILABLE")


class LLMStructuredOutputError(LLMError):
    """Raised when LLM output cannot be parsed as valid JSON or fails Pydantic schema validation."""
    def __init__(self, message: str, raw_output: str = "", provider: str = "groq"):
        super().__init__(message, provider=provider, error_code="SCHEMA_VALIDATION_FAILED")
        self.raw_output = raw_output


class LLMModelNotFoundError(LLMError):
    """Raised when the requested model name is not recognized or decommissioned."""
    def __init__(self, model_name: str, provider: str = "groq"):
        super().__init__(f"Requested model '{model_name}' is not recognized or available on {provider}", provider=provider, error_code="MODEL_NOT_FOUND")
        self.model_name = model_name
