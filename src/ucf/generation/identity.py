from __future__ import annotations

import hashlib
import json

from ucf.generation.models import GenerationRequest, GenerationResult


def derive_generation_request_id(request: GenerationRequest) -> str:
    return "generation-request." + _projection_digest(request)


def derive_generation_result_id(result: GenerationResult) -> str:
    return "generation-result." + _projection_digest(result)


def _projection_digest(document: object) -> str:
    projection = document.model_dump(mode="json", exclude={"id"})
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
    return hashlib.sha256(encoded).hexdigest()
