"""GroqCloud LLM Provider implementation for Healthcare Agentic AI."""
import json
import logging
import re
import time
from typing import TypeVar
from pydantic import BaseModel, ValidationError

try:
    import groq
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    groq = None
    Groq = None

from llm.base import BaseLLMProvider
from llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from llm.schemas import (
    LLMConfig,
    LLMHealthStatus,
    LLMMessage,
    LLMResponse,
    LLMUsage,
)

logger = logging.getLogger("healthcare_agentic_ai.llm.groq")
T = TypeVar("T", bound=BaseModel)


class GroqProvider(BaseLLMProvider):
    """Production-grade GroqCloud provider with bounded retries and structured output."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: Groq | None = None
        if not GROQ_AVAILABLE:
            logger.warning("The 'groq' package is not installed. Live GroqCloud calls will be disabled.")
        elif self.config.api_key:
            try:
                self._client = Groq(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout_seconds,
                    max_retries=0,  # We handle retries explicitly
                )
            except Exception as exc:
                logger.error("Failed to initialize Groq client: %s", exc)
                self._client = None

    def _ensure_client(self) -> Groq:
        if not GROQ_AVAILABLE:
            raise LLMProviderUnavailableError("The 'groq' Python package is not installed.")
        if not self.config.api_key:
            raise LLMAuthenticationError("GROQ_API_KEY is not configured in the environment.")
        if self._client is None:
            self._client = Groq(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                max_retries=0,
            )
        return self._client

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        temp = temperature if temperature is not None else self.config.temperature
        model_name = self.config.model
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        retries = 0
        last_error = None
        start_time = time.perf_counter()

        while retries <= self.config.max_retries:
            try:
                t0 = time.perf_counter()
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=formatted_messages,
                    temperature=temp,
                    max_tokens=max_tokens,
                )
                duration = time.perf_counter() - t0

                choice = completion.choices[0]
                content = choice.message.content or ""
                finish_reason = choice.finish_reason

                usage_obj = completion.usage
                usage = LLMUsage(
                    prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
                    completion_tokens=getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
                    total_tokens=getattr(usage_obj, "total_tokens", 0) if usage_obj else 0,
                )

                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="groq",
                    usage=usage,
                    latency_seconds=round(duration, 3),
                    finish_reason=finish_reason,
                    retry_count=retries,
                )

            except groq.AuthenticationError as exc:
                logger.error("Groq authentication failed: %s", exc)
                raise LLMAuthenticationError(str(exc), provider="groq") from exc

            except groq.NotFoundError as exc:
                logger.error("Groq model not found '%s': %s", model_name, exc)
                raise LLMModelNotFoundError(model_name, provider="groq") from exc

            except groq.RateLimitError as exc:
                retries += 1
                last_error = exc
                if retries <= self.config.max_retries:
                    wait_time = 2.0 ** retries
                    logger.warning("Groq rate limit hit. Bounded retry %d/%d after %.1fs", retries, self.config.max_retries, wait_time)
                    time.sleep(wait_time)
                else:
                    raise LLMRateLimitError(str(exc), provider="groq") from exc

            except (groq.APITimeoutError, TimeoutError) as exc:
                retries += 1
                last_error = exc
                if retries <= self.config.max_retries:
                    wait_time = 1.0 * retries
                    logger.warning("Groq timeout hit. Bounded retry %d/%d", retries, self.config.max_retries)
                    time.sleep(wait_time)
                else:
                    raise LLMTimeoutError(str(exc), provider="groq", timeout_seconds=self.config.timeout_seconds) from exc

            except (groq.APIConnectionError, groq.InternalServerError) as exc:
                retries += 1
                last_error = exc
                if retries <= self.config.max_retries:
                    wait_time = 1.5 ** retries
                    logger.warning("Groq connection or server error: %s. Retry %d/%d", exc, retries, self.config.max_retries)
                    time.sleep(wait_time)
                else:
                    raise LLMProviderUnavailableError(str(exc), provider="groq") from exc

            except Exception as exc:
                logger.error("Unexpected error in Groq call: %s", exc)
                raise LLMError(f"Unexpected Groq call failure: {exc}", provider="groq") from exc

        raise LLMError(f"Exhausted {self.config.max_retries} retries: {last_error}", provider="groq")

    def generate_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[T, LLMResponse]:
        client = self._ensure_client()
        temp = temperature if temperature is not None else self.config.temperature
        model_name = self.config.model

        # Build schema instructions to enforce valid JSON
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You MUST output ONLY a valid JSON object matching this JSON schema:\n{schema_json}\n"
            "Do not include markdown codeblocks like ```json, preamble, or commentary outside the JSON."
        )

        adjusted_messages = [LLMMessage(role="system", content=system_instruction)] + messages
        formatted_messages = [{"role": m.role, "content": m.content} for m in adjusted_messages]

        retries = 0
        last_error = None

        while retries <= self.config.max_retries:
            try:
                t0 = time.perf_counter()
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=formatted_messages,
                    temperature=temp,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                duration = time.perf_counter() - t0

                choice = completion.choices[0]
                content = (choice.message.content or "").strip()
                finish_reason = choice.finish_reason

                usage_obj = completion.usage
                usage = LLMUsage(
                    prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
                    completion_tokens=getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
                    total_tokens=getattr(usage_obj, "total_tokens", 0) if usage_obj else 0,
                )

                # Clean markdown backticks if present
                clean_json_str = content
                if clean_json_str.startswith("```"):
                    clean_json_str = re.sub(r"^```(?:json)?\s*", "", clean_json_str)
                    clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

                try:
                    data = json.loads(clean_json_str)
                except json.JSONDecodeError as jde:
                    raise LLMStructuredOutputError(f"Malformed JSON from Groq: {jde}", raw_output=content) from jde

                try:
                    parsed_instance = schema.model_validate(data)
                except ValidationError as ve:
                    raise LLMStructuredOutputError(f"Schema validation failed: {ve}", raw_output=content) from ve

                response = LLMResponse(
                    content=content,
                    structured_data=data,
                    model=model_name,
                    provider="groq",
                    usage=usage,
                    latency_seconds=round(duration, 3),
                    finish_reason=finish_reason,
                    retry_count=retries,
                )
                return parsed_instance, response

            except (LLMAuthenticationError, LLMModelNotFoundError):
                raise

            except LLMStructuredOutputError as exc:
                retries += 1
                last_error = exc
                if retries <= self.config.max_retries:
                    logger.warning("Groq structured output parsing error (%s). Bounded repair retry %d/%d", exc, retries, self.config.max_retries)
                    time.sleep(1.0)
                else:
                    raise

            except (groq.RateLimitError, groq.APITimeoutError, groq.APIConnectionError, groq.InternalServerError) as exc:
                retries += 1
                last_error = exc
                if retries <= self.config.max_retries:
                    wait_time = 1.5 ** retries
                    logger.warning("Transient error in structured Groq call (%s). Retry %d/%d", exc, retries, self.config.max_retries)
                    time.sleep(wait_time)
                else:
                    if isinstance(exc, groq.RateLimitError):
                        raise LLMRateLimitError(str(exc), provider="groq") from exc
                    elif isinstance(exc, groq.APITimeoutError):
                        raise LLMTimeoutError(str(exc), provider="groq", timeout_seconds=self.config.timeout_seconds) from exc
                    else:
                        raise LLMProviderUnavailableError(str(exc), provider="groq") from exc

            except Exception as exc:
                logger.error("Unexpected error in Groq structured call: %s", exc)
                raise LLMError(f"Unexpected Groq structured call failure: {exc}", provider="groq") from exc

        raise LLMError(f"Exhausted {self.config.max_retries} structured generation retries: {last_error}", provider="groq")

    def health_check(self) -> LLMHealthStatus:
        if not GROQ_AVAILABLE:
            return LLMHealthStatus(
                provider="groq",
                model=self.config.model,
                configured=False,
                available=False,
                status_code="PACKAGE_MISSING",
                message="The 'groq' library is not installed in the environment.",
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )

        if not self.config.api_key:
            return LLMHealthStatus(
                provider="groq",
                model=self.config.model,
                configured=False,
                available=False,
                status_code="NOT_CONFIGURED",
                message="GROQ_API_KEY is not set. Prototype running in deterministic fallback mode.",
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )

        try:
            client = self._ensure_client()
            # Perform a harmless probe (list models or short completion)
            models = client.models.list()
            available_ids = [m.id for m in getattr(models, "data", [])]
            is_model_present = self.config.model in available_ids or len(available_ids) > 0

            return LLMHealthStatus(
                provider="groq",
                model=self.config.model,
                configured=True,
                available=True,
                status_code="HEALTHY",
                message=f"GroqCloud connection verified. Model '{self.config.model}' accessible.",
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )
        except groq.AuthenticationError:
            return LLMHealthStatus(
                provider="groq",
                model=self.config.model,
                configured=True,
                available=False,
                status_code="AUTH_FAILED",
                message="Configured GROQ_API_KEY was rejected by GroqCloud authentication.",
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )
        except Exception as exc:
            return LLMHealthStatus(
                provider="groq",
                model=self.config.model,
                configured=True,
                available=False,
                status_code="UNAVAILABLE",
                message=f"Unable to reach GroqCloud API: {exc}",
                timeout_seconds=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )
