from __future__ import annotations

import hashlib
import json

from ucf.runtime_evidence.models import RuntimeEvidenceResult


def derive_runtime_evidence_result_id(
    result: RuntimeEvidenceResult,
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
