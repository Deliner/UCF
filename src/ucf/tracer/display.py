"""Display helpers for tracer output (CLI tree formatting)."""

from __future__ import annotations

from ucf.models.component import StepDef


def format_step_label(step: StepDef) -> str:
    """Format a step label for CLI tree output, marking conditional steps with [?]."""
    if step.when:
        return f"[?] {step.id}  (when: {step.when})"
    if step.skip_if:
        return f"[?] {step.id}  (skip_if: {step.skip_if})"
    return step.id
