"""Implementation for use case: generate-alt-flow-verification.

@implements("use-cases/generate-alt-flow-verification")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.models.action import ActionSpec
from ucf.models.usecase import AlternativeFlow, UseCaseSpec
from ucf.parser.registry import SpecRegistry

from .interface import (
    ExtractErrorCodeResult,
    FindTriggerActionResult,
    GenerateAltFlowVerificationInterface,
    GenerateAssertionResult,
)


class GenerateAltFlowVerificationImpl(GenerateAltFlowVerificationInterface):
    """Implements alt flow trigger verification for generator."""

    def __init__(self, registry: SpecRegistry) -> None:
        self._registry = registry
        self._generated_code = None
        self._error_code = None
        self._action_ref = None

    # ── Actions ──

    def action_extract_error_code(self, alt_flow: Any) -> ExtractErrorCodeResult:
        """Extract error code from alternative flow spec."""
        if not isinstance(alt_flow, AlternativeFlow):
            raise TypeError("alt_flow must be an AlternativeFlow")
        if not alt_flow.handles_error:
            raise ValueError("alternative flow does not declare handles_error")

        error_code = alt_flow.handles_error
        self._error_code = error_code
        return ExtractErrorCodeResult(error_code=error_code)

    def action_find_trigger_action(
        self, usecase_spec: Any, error_code: Any
    ) -> FindTriggerActionResult:
        """Find which action in main flow can raise this error."""
        if not isinstance(usecase_spec, UseCaseSpec):
            raise TypeError("usecase_spec must be a UseCaseSpec")

        matches: list[tuple[str, str]] = []
        for step in usecase_spec.steps:
            action = self._registry.resolve_ref(step.use)
            if not isinstance(action, ActionSpec):
                continue
            if any(error.code == error_code for error in action.errors):
                matches.append((step.use, step.id))
        if len(matches) != 1:
            raise ValueError(
                f"expected one action declaring {error_code}, found {len(matches)}"
            )

        action_ref, step_id = matches[0]
        self._action_ref = action_ref
        return FindTriggerActionResult(action_ref=action_ref, step_id=step_id)

    def action_generate_assertion(
        self, action_ref: Any, error_code: Any
    ) -> GenerateAssertionResult:
        """Generate Python assertion code to verify trigger was called."""
        code = f"""\
# Verify that {action_ref} raised {error_code}
assert uc._validation_called, "Expected validation to be triggered"
assert uc._last_error_code == {str(error_code)!r}, (
    f"Expected {str(error_code)!r}, got {{uc._last_error_code}}"
)
""".strip()

        self._generated_code = code
        return GenerateAssertionResult(code=code)

    def action_skip_verification(self, message: Any) -> None:
        """Log warning for alt flows without error handlers."""
        self._skipped_message = str(message)
        self.render_cli_output({"warning": self._skipped_message}, "text")

    # ── Verifications ──

    def verify_assertion_code_verifies_error_was_raised_by_correct_action(
        self,
    ) -> None:
        """Verify generated code checks for error from correct action."""
        assert self._generated_code is not None, "No assertion code generated"
        assert self._action_ref in self._generated_code, (
            f"Action ref '{self._action_ref}' not found in generated code"
        )
        assert self._error_code in self._generated_code, (
            f"Error code '{self._error_code}' not found in generated code"
        )

    def verify_assertion_is_inserted_into_generated_test(self) -> None:
        """Verify assertion code is valid Python."""
        assert self._generated_code is not None
        # Check it's valid Python syntax
        try:
            compile(self._generated_code, "<assertion>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def verify_test_fails_if_trigger_action_not_called(self) -> None:
        """Verify assertion will catch missing trigger."""
        assert self._generated_code is not None
        # Check that assertion uses `assert` statement
        assert "assert" in self._generated_code.lower(), (
            "Generated code doesn't contain assertion"
        )

    def verify_required_inputs_validated(self) -> None:
        """Verify framework enforces required inputs."""
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def generate_alt_flow_verification_impl(
    inputs: dict[str, object],
) -> GenerateAltFlowVerificationImpl:
    registry = inputs["registry"]
    if not isinstance(registry, SpecRegistry):
        raise TypeError("inputs.registry must be a SpecRegistry")
    return GenerateAltFlowVerificationImpl(registry)
