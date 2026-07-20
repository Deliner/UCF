from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError
from pydantic_core import PydanticSerializationError

from ucf.change_lifecycle.errors import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
)
from ucf.ir import (
    IRErrorCode,
    IRValidationError,
    canonical_ir_json,
    parse_ir_json,
)
from ucf.ir.models import BehaviorIR

_IR_ERROR_CODES = {
    IRErrorCode.BROKEN_REFERENCE: ChangeLifecycleErrorCode.BROKEN_REFERENCE,
    IRErrorCode.DOCUMENT_IDENTITY_MISMATCH: (
        ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH
    ),
    IRErrorCode.DUPLICATE_CAPABILITY: (ChangeLifecycleErrorCode.DUPLICATE_IDENTITY),
    IRErrorCode.DUPLICATE_IDENTITY: (ChangeLifecycleErrorCode.DUPLICATE_IDENTITY),
    IRErrorCode.DUPLICATE_REFERENCE: (ChangeLifecycleErrorCode.DUPLICATE_IDENTITY),
    IRErrorCode.WRONG_TARGET_KIND: ChangeLifecycleErrorCode.WRONG_TARGET_KIND,
}


def validate_behavior_document(
    document: BehaviorIR,
    *,
    location: str,
) -> None:
    """Revalidate typed Behavior IR at a lifecycle trust boundary."""

    try:
        parse_ir_json(canonical_ir_json(document))
    except IRValidationError as error:
        code = _IR_ERROR_CODES.get(
            error.code,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        )
        nested_location = (
            location + error.location[1:]
            if error.location.startswith("$")
            else location
        )
        raise ChangeLifecycleValidationError(
            code,
            f"invalid Behavior IR ({error.code.value}): {error.message}",
            location=nested_location,
        ) from error
    except (
        PydanticSerializationError,
        PydanticValidationError,
        TypeError,
        AttributeError,
    ) as error:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            f"invalid Behavior IR structure: {error}",
            location=location,
        ) from error


__all__ = ["validate_behavior_document"]
