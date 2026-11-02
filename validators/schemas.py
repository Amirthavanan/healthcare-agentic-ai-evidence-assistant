"""Schemas for deterministic validation results."""
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class ValidationResult(BaseModel):
    """Detailed result of deterministic clinical output validation."""
    model_config = ConfigDict(extra="ignore")

    passed: bool = Field(description="True if output satisfied all validation rules")
    error_codes: list[str] = Field(default_factory=list, description="Specific error codes if validation failed")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
    rules_checked: list[str] = Field(default_factory=list, description="List of the 12 validation rules evaluated")
    citation_ids_checked: int = Field(default=0, description="Count of citations verified")
    can_retry: bool = Field(default=False, description="True if a bounded repair retry is permitted")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic breakdown per rule")
