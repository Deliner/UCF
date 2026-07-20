from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ucf._typed_boundary import (
    TypedBoundaryError,
    reject_noncanonical_typed_values,
)
from ucf.change_governance.errors import (
    ChangeGovernanceErrorCode,
    ChangeGovernanceValidationError,
)
from ucf.change_governance.models import (
    CHANGE_GOVERNANCE_VERSION,
    DECISION_ASSESSMENT_SCHEMA_URI,
    DECISION_DECLARATION_SCHEMA_URI,
    IMPACT_REPORT_SCHEMA_URI,
    DecisionAssessment,
    DecisionAssessmentRef,
    DecisionDeclaration,
    DecisionDeclarationRef,
    GateEvaluation,
    ImpactReport,
    ImpactReportRef,
)
from ucf.ir import (
    IRErrorCode,
    IRValidationError,
    decode_strict_json_object,
)
from ucf.ir.codec import MAX_JSON_NESTING
from ucf.ir.models import Digest

type ChangeGovernanceDocument = (
    ImpactReport | DecisionAssessment | DecisionDeclaration | GateEvaluation
)
_CHANGE_GOVERNANCE_DOCUMENT_TYPES = (
    ImpactReport,
    DecisionAssessment,
    DecisionDeclaration,
    GateEvaluation,
)


def canonical_change_governance_json(
    document: ChangeGovernanceDocument,
) -> bytes:
    model = type(document)
    if model not in _CHANGE_GOVERNANCE_DOCUMENT_TYPES:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "governance resource must use one exact canonical document type",
            location="$",
        )
    try:
        reject_noncanonical_typed_values(
            document,
            declared_type=model,
            max_depth=MAX_JSON_NESTING,
        )
    except TypedBoundaryError as error:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            str(error),
            location=error.location,
        ) from error
    try:
        encoded = (
            json.dumps(
                document.model_dump(
                    mode="json",
                    serialize_as_any=True,
                ),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError) as error:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            f"governance resource cannot be serialized: {error}",
            location="$",
        ) from error
    _parse_governance_document(encoded, model)
    return encoded


def parse_impact_report_json(payload: str | bytes) -> ImpactReport:
    return _parse_governance_document(payload, ImpactReport)


def parse_decision_assessment_json(
    payload: str | bytes,
) -> DecisionAssessment:
    return _parse_governance_document(payload, DecisionAssessment)


def parse_decision_declaration_json(
    payload: str | bytes,
) -> DecisionDeclaration:
    return _parse_governance_document(payload, DecisionDeclaration)


def parse_gate_evaluation_json(payload: str | bytes) -> GateEvaluation:
    return _parse_governance_document(payload, GateEvaluation)


def canonical_change_governance_digest(
    document: ChangeGovernanceDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(canonical_change_governance_json(document)).hexdigest(),
    )


def impact_report_ref(report: ImpactReport) -> ImpactReportRef:
    if type(report) is not ImpactReport:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "impact reference source must use exact ImpactReport type",
            location="$.impact",
        )
    return ImpactReportRef(
        kind="impact_report_ref",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=IMPACT_REPORT_SCHEMA_URI,
        change_id=report.change_id,
        canonical_digest=canonical_change_governance_digest(report),
    )


def decision_assessment_ref(
    assessment: DecisionAssessment,
) -> DecisionAssessmentRef:
    if type(assessment) is not DecisionAssessment:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "assessment reference source must use exact DecisionAssessment type",
            location="$.assessment",
        )
    return DecisionAssessmentRef(
        kind="decision_assessment_ref",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=DECISION_ASSESSMENT_SCHEMA_URI,
        change_id=assessment.change_id,
        canonical_digest=canonical_change_governance_digest(assessment),
    )


def decision_declaration_ref(
    declaration: DecisionDeclaration,
) -> DecisionDeclarationRef:
    if type(declaration) is not DecisionDeclaration:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "declaration reference source must use exact DecisionDeclaration type",
            location="$.declaration",
        )
    return DecisionDeclarationRef(
        kind="decision_declaration_ref",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=DECISION_DECLARATION_SCHEMA_URI,
        change_id=declaration.change_id,
        canonical_digest=canonical_change_governance_digest(declaration),
    )


def _parse_governance_document(
    payload: str | bytes,
    model: Any,
):
    if not isinstance(payload, (str, bytes)):
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_JSON,
            "governance JSON payload must be str or bytes; "
            f"got {type(payload).__name__}",
            location="$",
        )
    try:
        decoded = decode_strict_json_object(payload)
    except IRValidationError as error:
        code = (
            ChangeGovernanceErrorCode.DUPLICATE_JSON_MEMBER
            if error.code is IRErrorCode.DUPLICATE_JSON_MEMBER
            else ChangeGovernanceErrorCode.INVALID_JSON
        )
        raise ChangeGovernanceValidationError(
            code,
            str(error),
            location="$",
        ) from error
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    try:
        return model.model_validate_json(normalized)
    except PydanticValidationError as error:
        detail = error.errors(
            include_context=False,
            include_input=False,
            include_url=False,
        )[0]
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            detail["msg"],
            location=_pydantic_location(detail["loc"]),
        ) from error


def _pydantic_location(components: tuple[Any, ...]) -> str:
    location = "$"
    for component in components:
        if isinstance(component, int):
            location += f"[{component}]"
        else:
            location += f".{component}"
    return location
