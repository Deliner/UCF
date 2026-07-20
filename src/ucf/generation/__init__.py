"""Language-neutral deterministic generation request and result profile."""

from ucf.generation.client import generate_with_adapter
from ucf.generation.codec import (
    canonical_generation_digest,
    canonical_generation_json,
    parse_generation_request_json,
    parse_generation_result_json,
)
from ucf.generation.errors import (
    GenerationClientError,
    GenerationErrorCode,
    GenerationPublicationError,
    GenerationPublicationErrorCode,
    GenerationValidationError,
)
from ucf.generation.identity import (
    derive_generation_request_id,
    derive_generation_result_id,
)
from ucf.generation.models import (
    GENERATION_CAPABILITY,
    GENERATION_PROFILE_PROCEDURE_URI,
    GENERATION_PROFILE_VERSION,
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
    MAX_GENERATED_FILE_BYTES,
    MAX_GENERATED_FILES,
    MAX_GENERATED_TOTAL_BYTES,
    GeneratedFile,
    GenerationEnvironment,
    GenerationPortValue,
    GenerationRequest,
    GenerationResult,
    GenerationVerification,
)
from ucf.generation.publication import (
    GENERATION_RECEIPT_NAME,
    PublicationStatus,
    publish_generation_result,
)
from ucf.generation.validation import (
    validate_generation_request,
    validate_generation_result,
    validate_generation_result_structure,
)
from ucf.generation.wire import (
    generation_request_from_payload,
    generation_request_to_payload,
    generation_result_from_payload,
    generation_result_to_payload,
)

__all__ = [
    "GENERATION_CAPABILITY",
    "GENERATION_PROFILE_PROCEDURE_URI",
    "GENERATION_PROFILE_VERSION",
    "GENERATION_REQUEST_SCHEMA_URI",
    "GENERATION_RECEIPT_NAME",
    "GENERATION_RESULT_SCHEMA_URI",
    "MAX_GENERATED_FILE_BYTES",
    "MAX_GENERATED_FILES",
    "MAX_GENERATED_TOTAL_BYTES",
    "GeneratedFile",
    "GenerationClientError",
    "GenerationEnvironment",
    "GenerationErrorCode",
    "GenerationPublicationError",
    "GenerationPublicationErrorCode",
    "GenerationPortValue",
    "GenerationRequest",
    "GenerationResult",
    "GenerationValidationError",
    "GenerationVerification",
    "PublicationStatus",
    "canonical_generation_digest",
    "canonical_generation_json",
    "derive_generation_request_id",
    "derive_generation_result_id",
    "generation_request_from_payload",
    "generation_request_to_payload",
    "generation_result_from_payload",
    "generation_result_to_payload",
    "generate_with_adapter",
    "parse_generation_request_json",
    "parse_generation_result_json",
    "publish_generation_result",
    "validate_generation_request",
    "validate_generation_result",
    "validate_generation_result_structure",
]
