from __future__ import annotations

import hashlib
import json

from ucf.implementation_evidence.models import (
    ExecutionVerificationResult,
    ImplementationMappingResult,
)


def derive_implementation_mapping_result_id(
    result: ImplementationMappingResult,
) -> str:
    projection = result.model_dump(mode="json", exclude={"id"})
    encoded = (
        json.dumps(
            projection,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return "mapping." + hashlib.sha256(encoded).hexdigest()


def derive_execution_verification_result_id(
    result: ExecutionVerificationResult,
) -> str:
    projection = result.model_dump(mode="json", exclude={"id"})
    encoded = (
        json.dumps(
            projection,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return "result." + hashlib.sha256(encoded).hexdigest()
