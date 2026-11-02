"""Abstract Base Class for LLM Providers in Healthcare Agentic AI."""
from abc import ABC, abstractmethod
from typing import TypeVar
from pydantic import BaseModel

from llm.schemas import LLMConfig, LLMHealthStatus, LLMMessage, LLMResponse

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Common interface for all LLM providers (GroqCloud, local, etc.)."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Execute a text generation call with bounded retries and timeout."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[T, LLMResponse]:
        """Execute a structured-output call and validate against a Pydantic schema."""
        pass

    @abstractmethod
    def health_check(self) -> LLMHealthStatus:
        """Verify provider availability and configuration without exposing secrets."""
        pass
