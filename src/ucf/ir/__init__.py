"""Versioned, language-neutral UCF behavior IR."""

from ucf.ir.codec import (
    CURRENT_IR_VERSION,
    canonical_ir_json,
    decode_ir_json,
    decode_strict_json_object,
    parse_ir_json,
)
from ucf.ir.errors import IRErrorCode, IRValidationError
from ucf.ir.models import BehaviorIR, EntityKind
from ucf.ir.trust_codec import (
    canonical_trust_ir_json,
    decode_trust_ir_json,
    parse_trust_ir_json,
)
from ucf.ir.trust_models import (
    CURRENT_TRUST_IR_VERSION,
    ClaimLevel,
    RecordRef,
    TrustIR,
    TrustMapping,
    TrustRecordKind,
)
from ucf.ir.trust_validation import (
    reconcile_mapping,
    supported_claim_levels,
    validate_trust_against_behavior,
)
from ucf.ir.validation import validate_ir_value, validate_required_capabilities

__all__ = [
    "BehaviorIR",
    "CURRENT_IR_VERSION",
    "CURRENT_TRUST_IR_VERSION",
    "ClaimLevel",
    "EntityKind",
    "IRErrorCode",
    "IRValidationError",
    "RecordRef",
    "TrustIR",
    "TrustMapping",
    "TrustRecordKind",
    "canonical_ir_json",
    "canonical_trust_ir_json",
    "decode_ir_json",
    "decode_strict_json_object",
    "decode_trust_ir_json",
    "parse_ir_json",
    "parse_trust_ir_json",
    "reconcile_mapping",
    "supported_claim_levels",
    "validate_required_capabilities",
    "validate_ir_value",
    "validate_trust_against_behavior",
]
