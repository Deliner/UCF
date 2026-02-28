"""Component primitive — a reusable block of steps (function analog)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ucf.models.base import FieldDef, Metadata


class RetryConfig(BaseModel):
    """Retry configuration for a step."""
    
    max_attempts: int = Field(ge=1, le=100, description="Maximum retry attempts")
    on_error: str | list[str] = Field(description="Error code(s) that trigger retry")
    backoff: Literal["constant", "linear", "exponential"] = Field(default="constant")
    initial_delay_ms: int = Field(default=1000, ge=0, description="Initial delay before retry")


class StepDef(BaseModel):
    id: str
    use: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, str] = Field(default_factory=dict)
    when: str | None = Field(default=None, description="Expression to evaluate. Step runs if true.")
    skip_if: str | None = Field(default=None, description="Expression to evaluate. Step is skipped if true.")
    depends_on: list[str] = Field(default_factory=list)
    postcondition: str | None = None
    retry: RetryConfig | None = None

    @field_validator("when", "skip_if", mode="before")
    @classmethod
    def _reject_empty_expression(cls, v: str | None) -> str | None:
        """Reject empty or whitespace-only strings; they are not valid expressions."""
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        if not v.strip():
            raise ValueError("Expression cannot be empty or whitespace-only")
        return v

    @model_validator(mode="after")
    def check_mutually_exclusive_conditions(self) -> StepDef:
        if self.when is not None and self.skip_if is not None:
            raise ValueError("Cannot specify both 'when' and 'skip_if' on the same step.")
        return self


class ComponentSpec(BaseModel):
    kind: Literal["component"] = "component"
    metadata: Metadata
    parameters: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    provides: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    steps: list[StepDef] = Field(default_factory=list)
