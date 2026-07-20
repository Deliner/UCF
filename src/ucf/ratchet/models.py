from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.codec import SEMANTIC_VERSION
from ucf.ir.models import (
    URI,
    Digest,
    EntityKind,
    Identifier,
    IRModel,
    NormalizedVersion,
    Producer,
    SafeInteger,
)
from ucf.ir.trust_models import BehaviorEntityRef
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    CandidateRef,
    CaptureContext,
)
from ucf.onboarding.models import DecisionId

RATCHET_VERSION = "1.0.0"
RATCHET_POLICY_SCHEMA_URI = "urn:ucf:ratchet:policy:1.0.0"
RATCHET_ASSESSMENT_SCHEMA_URI = "urn:ucf:ratchet:assessment:1.0.0"
RATCHET_BASELINE_SCHEMA_URI = "urn:ucf:ratchet:baseline:1.0.0"
RATCHET_EVALUATION_REPORT_SCHEMA_URI = (
    "urn:ucf:ratchet:evaluation-report:1.0.0"
)
RATCHET_EVALUATION_PROCEDURE_URI = "urn:ucf:ratchet:evaluate:1.0.0"
RATCHET_EVALUATOR_CAPABILITY = "org.ucf.ratchet.baseline"
SEMANTIC_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:behavior-subject:1.0.0"
)
OBSERVED_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:observed-subject:1.0.0"
)
MAX_RATCHET_RULES = 256
MAX_RATCHET_SUBJECTS = 256
MAX_RATCHET_VIOLATIONS = MAX_RATCHET_RULES * MAX_RATCHET_SUBJECTS

type PolicyId = Annotated[
    str,
    StringConstraints(pattern=r"^policy\.[0-9a-f]{64}$"),
]
type AssessmentId = Annotated[
    str,
    StringConstraints(pattern=r"^assessment\.[0-9a-f]{64}$"),
]
type BaselineId = Annotated[
    str,
    StringConstraints(pattern=r"^baseline\.[0-9a-f]{64}$"),
]
type BehaviorSubjectId = Annotated[
    str,
    StringConstraints(pattern=r"^subject\.[0-9a-f]{64}$"),
]
type ViolationId = Annotated[
    str,
    StringConstraints(pattern=r"^violation\.[0-9a-f]{64}$"),
]
type EvaluationId = Annotated[
    str,
    StringConstraints(pattern=r"^evaluation\.[0-9a-f]{64}$"),
]


class RatchetRule(IRModel):
    kind: Literal["ratchet_rule"]
    id: Identifier
    version: NormalizedVersion
    procedure_uri: URI
    producer: Producer
    summary: Annotated[str, StringConstraints(min_length=1, max_length=255)]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "ratchet rule procedure")


class RatchetPolicy(IRModel):
    kind: Literal["ratchet_policy"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_POLICY_SCHEMA_URI]
    id: PolicyId
    evaluator: CapabilitySelection
    rules: Annotated[
        tuple[RatchetRule, ...],
        Field(min_length=1, max_length=MAX_RATCHET_RULES),
    ]

    @model_validator(mode="after")
    def validate_evaluator(self) -> RatchetPolicy:
        if (
            self.evaluator.name != RATCHET_EVALUATOR_CAPABILITY
            or self.evaluator.version != RATCHET_VERSION
        ):
            raise ValueError(
                "ratchet policy requires the exact supported evaluator "
                "capability"
            )
        return self


class RatchetPolicyRef(IRModel):
    kind: Literal["ratchet_policy_ref"]
    schema_uri: Literal[RATCHET_POLICY_SCHEMA_URI]
    schema_version: Literal[RATCHET_VERSION]
    target_id: PolicyId
    canonical_digest: Digest


class OnboardingBundleRef(IRModel):
    kind: Literal["onboarding_bundle_ref"]
    schema_uri: Literal[ONBOARDING_BUNDLE_SCHEMA_URI]
    schema_version: Literal[ONBOARDING_VERSION]
    canonical_digest: Digest


class BehaviorSubjectKey(IRModel):
    kind: Literal["behavior_subject_key"]
    subject_uri: URI
    target_kind: EntityKind
    target_id: Identifier


class BehaviorSubjectRef(IRModel):
    kind: Literal["behavior_subject_ref"]
    target_id: BehaviorSubjectId


class RatchetRuleRef(IRModel):
    kind: Literal["ratchet_rule_ref"]
    target_id: Identifier
    version: NormalizedVersion


class SemanticFingerprint(IRModel):
    kind: Literal["semantic_fingerprint"]
    algorithm_uri: Literal[SEMANTIC_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class ObservedFingerprint(IRModel):
    kind: Literal["observed_fingerprint"]
    algorithm_uri: Literal[OBSERVED_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class SubjectTrace(IRModel):
    kind: Literal["ratchet_subject_trace"]
    onboarding_bundle: OnboardingBundleRef
    behavior: BehaviorEntityRef
    inventory_source_revision: Digest
    candidate: CandidateRef
    decision_id: DecisionId


class BehaviorSubjectSnapshot(IRModel):
    kind: Literal["behavior_subject_snapshot"]
    id: BehaviorSubjectId
    key: BehaviorSubjectKey
    semantic: SemanticFingerprint
    observed: ObservedFingerprint
    trace: SubjectTrace


class ViolationKey(IRModel):
    kind: Literal["violation_key"]
    rule: RatchetRuleRef
    subject: BehaviorSubjectRef
    slot: Identifier


class RatchetViolation(IRModel):
    kind: Literal["ratchet_violation"]
    id: ViolationId
    key: ViolationKey
    message: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class ViolationInput(IRModel):
    kind: Literal["ratchet_violation_input"]
    rule_id: Identifier
    subject: BehaviorSubjectKey
    slot: Identifier
    message: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class RuleCoverage(IRModel):
    kind: Literal["ratchet_rule_coverage"]
    rule: RatchetRuleRef
    status: Literal["complete", "partial"]
    subjects: Annotated[
        tuple[BehaviorSubjectRef, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]


class RatchetAssessment(IRModel):
    kind: Literal["ratchet_assessment"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_ASSESSMENT_SCHEMA_URI]
    id: AssessmentId
    policy: RatchetPolicyRef
    source: OnboardingBundleRef
    producer: Producer
    procedure_uri: URI
    capture_context: CaptureContext
    subject_coverage: Literal["complete", "partial"]
    subjects: Annotated[
        tuple[BehaviorSubjectSnapshot, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    coverage: Annotated[
        tuple[RuleCoverage, ...],
        Field(max_length=MAX_RATCHET_RULES),
    ]
    violations: Annotated[
        tuple[RatchetViolation, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "ratchet assessment procedure")


class RatchetAssessmentRef(IRModel):
    kind: Literal["ratchet_assessment_ref"]
    schema_uri: Literal[RATCHET_ASSESSMENT_SCHEMA_URI]
    schema_version: Literal[RATCHET_VERSION]
    target_id: AssessmentId
    canonical_digest: Digest


class RatchetBaselineRef(IRModel):
    kind: Literal["ratchet_baseline_ref"]
    schema_uri: Literal[RATCHET_BASELINE_SCHEMA_URI]
    schema_version: Literal[RATCHET_VERSION]
    target_id: BaselineId
    canonical_digest: Digest
    generation: Annotated[SafeInteger, Field(ge=0)]


class RatchetEvaluationReportRef(IRModel):
    kind: Literal["ratchet_evaluation_report_ref"]
    schema_uri: Literal[RATCHET_EVALUATION_REPORT_SCHEMA_URI]
    schema_version: Literal[RATCHET_VERSION]
    target_id: EvaluationId
    canonical_digest: Digest


class RatchetBaseline(IRModel):
    kind: Literal["ratchet_baseline"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_BASELINE_SCHEMA_URI]
    id: BaselineId
    generation: Annotated[SafeInteger, Field(ge=0)]
    policy: RatchetPolicyRef
    source_assessment: RatchetAssessmentRef
    source_evaluation: RatchetEvaluationReportRef | None
    predecessor: RatchetBaselineRef | None
    subjects: Annotated[
        tuple[BehaviorSubjectSnapshot, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    allowances: Annotated[
        tuple[ViolationKey, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]
    protected: Annotated[
        tuple[ViolationKey, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]

    @model_validator(mode="after")
    def validate_generation(self) -> RatchetBaseline:
        if self.generation == 0:
            if self.predecessor is not None:
                raise ValueError(
                    "initial ratchet baseline cannot have a predecessor"
                )
            if self.source_evaluation is not None:
                raise ValueError(
                    "initial ratchet baseline cannot have a source evaluation"
                )
        else:
            if self.predecessor is None:
                raise ValueError(
                    "successor ratchet baseline requires a predecessor"
                )
            if self.source_evaluation is None:
                raise ValueError(
                    "successor ratchet baseline requires a source evaluation"
                )
            if self.predecessor.generation != self.generation - 1:
                raise ValueError(
                    "successor generation must immediately follow its "
                    "predecessor"
                )
        return self


class SubjectChangeKind(StrEnum):
    UNCHANGED = "unchanged"
    SEMANTIC_CHANGED = "semantic_changed"
    OBSERVED_CHANGED = "observed_changed"
    SEMANTIC_AND_OBSERVED_CHANGED = "semantic_and_observed_changed"
    NEW_SUBJECT = "new_subject"
    REMOVED_SUBJECT = "removed_subject"
    UNKNOWN_SUBJECT = "unknown_subject"


class SubjectChange(IRModel):
    kind: Literal["ratchet_subject_change"]
    subject: BehaviorSubjectRef
    change: SubjectChangeKind


class ViolationClassificationKind(StrEnum):
    UNCHANGED_LEGACY = "unchanged_legacy"
    NEW_REGRESSION = "new_regression"
    TOUCHED_LEGACY = "touched_legacy"
    REINTRODUCED = "reintroduced"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class ViolationClassification(IRModel):
    kind: Literal["ratchet_violation_classification"]
    classification: ViolationClassificationKind
    key: ViolationKey


class WeakeningDeltaStatus(StrEnum):
    NONE = "none"
    TIGHTENING = "tightening"
    REVIEW_REQUIRED = "review_required"


class WeakeningDelta(IRModel):
    kind: Literal["weakening_delta"]
    status: WeakeningDeltaStatus
    added_allowances: Annotated[
        tuple[ViolationKey, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]
    removed_allowances: Annotated[
        tuple[ViolationKey, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]
    removed_protections: Annotated[
        tuple[ViolationKey, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS),
    ]


class EvaluationOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class RatchetEvaluationReport(IRModel):
    kind: Literal["ratchet_evaluation_report"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_EVALUATION_REPORT_SCHEMA_URI]
    id: EvaluationId
    policy: RatchetPolicyRef
    baseline: RatchetBaselineRef
    assessment: RatchetAssessmentRef
    procedure_uri: Literal[RATCHET_EVALUATION_PROCEDURE_URI]
    subject_changes: Annotated[
        tuple[SubjectChange, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS * 2),
    ]
    classifications: Annotated[
        tuple[ViolationClassification, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS * 2),
    ]
    outcome: EvaluationOutcome
    weakening_delta: WeakeningDelta


def _validate_versioned_uri(value: str, label: str) -> str:
    version = value.rsplit(":", maxsplit=1)[-1]
    if SEMANTIC_VERSION.fullmatch(version) is None:
        raise ValueError(f"{label} URI must end in a version")
    return value
