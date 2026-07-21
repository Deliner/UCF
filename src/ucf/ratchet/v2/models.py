from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    PATH_IDENTITY,
    InventoryRecordRef,
)
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
    DISCOVERY_RESULT_SCHEMA_URI,
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    CandidateRef,
    CaptureContext,
    DispositionKind,
)
from ucf.onboarding.models import DecisionId

RATCHET_VERSION = "2.0.0"
RATCHET_POLICY_SCHEMA_URI = "urn:ucf:ratchet:policy:2.0.0"
RATCHET_ASSESSMENT_SCHEMA_URI = "urn:ucf:ratchet:assessment:2.0.0"
RATCHET_BASELINE_SCHEMA_URI = "urn:ucf:ratchet:baseline:2.0.0"
RATCHET_EVALUATION_REPORT_SCHEMA_URI = (
    "urn:ucf:ratchet:evaluation-report:2.0.0"
)
RATCHET_EVALUATION_PROCEDURE_URI = "urn:ucf:ratchet:evaluate:2.0.0"
RATCHET_EVALUATOR_CAPABILITY = "org.ucf.ratchet.baseline"
BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:behavior-subject:2.0.0"
)
BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:observed-subject:2.0.0"
)
COVERAGE_SUBJECT_KEY_ALGORITHM_URI = (
    "urn:ucf:ratchet:coverage-subject-key:2.0.0"
)
COVERAGE_RECONCILIATION_ALGORITHM_URI = (
    "urn:ucf:ratchet:coverage-reconciliation:2.0.0"
)
COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:coverage-semantic:2.0.0"
)
COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI = (
    "urn:ucf:ratchet:fingerprint:coverage-observed:2.0.0"
)
COVERAGE_QUALIFICATION_ALGORITHM_URI = (
    "urn:ucf:ratchet:coverage-qualification:2.0.0"
)
MAX_RATCHET_RULES = 256
MAX_RATCHET_SUBJECTS = 10_000
MAX_RATCHET_VIOLATIONS = 100_000

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
type EvaluationId = Annotated[
    str,
    StringConstraints(pattern=r"^evaluation\.[0-9a-f]{64}$"),
]
type BehaviorSubjectId = Annotated[
    str,
    StringConstraints(pattern=r"^subject\.[0-9a-f]{64}$"),
]
type CoverageQualificationId = Annotated[
    str,
    StringConstraints(pattern=r"^domain\.[0-9a-f]{64}$"),
]
type CoverageSubjectId = Annotated[
    str,
    StringConstraints(pattern=r"^coverage\.[0-9a-f]{64}$"),
]
type CoverageDebtId = Annotated[
    str,
    StringConstraints(pattern=r"^debt\.[0-9a-f]{64}$"),
]
type ViolationId = Annotated[
    str,
    StringConstraints(pattern=r"^violation\.[0-9a-f]{64}$"),
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
        version = value.rsplit(":", maxsplit=1)[-1]
        if SEMANTIC_VERSION.fullmatch(version) is None:
            raise ValueError("ratchet rule procedure URI must end in a version")
        return value


class RatchetEvaluatorSelection(IRModel):
    kind: Literal["capability"]
    name: Literal[RATCHET_EVALUATOR_CAPABILITY]
    version: Literal[RATCHET_VERSION]


class RatchetPolicy(IRModel):
    kind: Literal["ratchet_policy"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_POLICY_SCHEMA_URI]
    id: PolicyId
    evaluator: RatchetEvaluatorSelection
    rules: Annotated[
        tuple[RatchetRule, ...],
        Field(min_length=1, max_length=MAX_RATCHET_RULES),
    ]

    @field_validator("evaluator", mode="before")
    @classmethod
    def normalize_evaluator(cls, value):
        if isinstance(value, CapabilitySelection):
            return value.model_dump(mode="json")
        return value


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


class BehaviorSemanticFingerprint(IRModel):
    kind: Literal["behavior_semantic_fingerprint"]
    algorithm_uri: Literal[BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class BehaviorObservedFingerprint(IRModel):
    kind: Literal["behavior_observed_fingerprint"]
    algorithm_uri: Literal[BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class BehaviorSubjectTrace(IRModel):
    kind: Literal["ratchet_behavior_subject_trace"]
    onboarding_bundle: OnboardingBundleRef
    behavior: BehaviorEntityRef
    inventory_source_revision: Digest
    candidate: CandidateRef
    decision_id: DecisionId


class BehaviorSubjectSnapshot(IRModel):
    kind: Literal["behavior_subject_snapshot"]
    id: BehaviorSubjectId
    key: BehaviorSubjectKey
    semantic: BehaviorSemanticFingerprint
    observed: BehaviorObservedFingerprint
    trace: BehaviorSubjectTrace


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


class BehaviorAssessmentLedger(IRModel):
    kind: Literal["ratchet_behavior_assessment"]
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


class CoverageQualification(IRModel):
    kind: Literal["coverage_qualification"]
    id: CoverageQualificationId
    algorithm_uri: Literal[COVERAGE_QUALIFICATION_ALGORITHM_URI]
    subject_uri: URI
    inventory_schema_uri: Literal[INVENTORY_SCHEMA_URI]
    inventory_version: Literal[INVENTORY_VERSION]
    inventory_producer: Producer
    inventory_capability: CapabilitySelection
    inventory_path_identity: Literal[PATH_IDENTITY]
    inventory_ignore_policy_digest: Digest
    inventory_procedure_uris: tuple[URI, ...]
    discovery_schema_uri: Literal[DISCOVERY_RESULT_SCHEMA_URI]
    discovery_version: Literal[ONBOARDING_VERSION]
    discovery_producer: Producer
    discovery_capability: CapabilitySelection
    discovery_procedure_uri: URI
    subject_key_algorithm_uri: Literal[COVERAGE_SUBJECT_KEY_ALGORITHM_URI]
    reconciliation_algorithm_uri: Literal[
        COVERAGE_RECONCILIATION_ALGORITHM_URI
    ]
    semantic_fingerprint_algorithm_uri: Literal[
        COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI
    ]
    observed_fingerprint_algorithm_uri: Literal[
        COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI
    ]


class CoverageSubjectKey(IRModel):
    kind: Literal["coverage_subject_key"]
    subject_uri: URI
    target_kind: Literal["public_interface"]
    interface_kind_uri: URI
    container: (
        Annotated[str, StringConstraints(min_length=1, max_length=255)] | None
    )
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class CoverageSubjectRef(IRModel):
    kind: Literal["coverage_subject_ref"]
    target_id: CoverageSubjectId


class CoverageSemanticFingerprint(IRModel):
    kind: Literal["coverage_semantic_fingerprint"]
    algorithm_uri: Literal[COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class CoverageObservedFingerprint(IRModel):
    kind: Literal["coverage_observed_fingerprint"]
    algorithm_uri: Literal[COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI]
    digest: Digest


class CoverageReconciliationTrace(IRModel):
    kind: Literal["coverage_reconciliation_trace"]
    candidate: CandidateRef
    decision_id: DecisionId


class CoverageReconciliationSnapshot(IRModel):
    kind: Literal["coverage_reconciliation_snapshot"]
    disposition: DispositionKind
    candidate_semantic_digest: Digest
    replacement_semantic_digest: Digest | None
    semantic: CoverageSemanticFingerprint
    observed: CoverageObservedFingerprint
    trace: CoverageReconciliationTrace

    @model_validator(mode="after")
    def validate_replacement(self) -> CoverageReconciliationSnapshot:
        if (self.disposition is DispositionKind.EDITED) != (
            self.replacement_semantic_digest is not None
        ):
            raise ValueError(
                "only edited reconciliation has a replacement digest"
            )
        return self


class CoverageSubjectState(StrEnum):
    UNCOVERED = "uncovered"
    RECONCILED = "reconciled"


class CoverageSubjectTrace(IRModel):
    kind: Literal["coverage_subject_trace"]
    onboarding_bundle: OnboardingBundleRef
    inventory_source_revision: Digest
    interface: InventoryRecordRef


class CoverageSubjectGroup(IRModel):
    kind: Literal["coverage_subject_group"]
    id: CoverageSubjectId
    key: CoverageSubjectKey
    state: CoverageSubjectState
    semantic: CoverageSemanticFingerprint
    observed: CoverageObservedFingerprint
    reconciliations: Annotated[
        tuple[CoverageReconciliationSnapshot, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    trace: CoverageSubjectTrace

    @model_validator(mode="after")
    def validate_state(self) -> CoverageSubjectGroup:
        if (self.state is CoverageSubjectState.UNCOVERED) != (
            not self.reconciliations
        ):
            raise ValueError(
                "coverage subject state differs from reconciliations"
            )
        return self


class CoverageDebtKind(StrEnum):
    UNCOVERED = "uncovered"
    UNCERTAIN = "uncertain"


class CoverageDebtKey(IRModel):
    kind: Literal["coverage_debt_key"]
    debt_kind: CoverageDebtKind
    subject: CoverageSubjectRef
    candidate_semantic_digest: Digest | None

    @model_validator(mode="after")
    def validate_candidate_coordinate(self) -> CoverageDebtKey:
        if (self.debt_kind is CoverageDebtKind.UNCERTAIN) != (
            self.candidate_semantic_digest is not None
        ):
            raise ValueError(
                "uncertain debt requires one candidate semantic digest"
            )
        return self


class CoverageDebtSnapshot(IRModel):
    kind: Literal["coverage_debt_snapshot"]
    id: CoverageDebtId
    key: CoverageDebtKey
    semantic: CoverageSemanticFingerprint
    observed: CoverageObservedFingerprint
    subject_trace: CoverageSubjectTrace
    reconciliation_trace: CoverageReconciliationTrace | None

    @model_validator(mode="after")
    def validate_trace(self) -> CoverageDebtSnapshot:
        if (self.key.debt_kind is CoverageDebtKind.UNCERTAIN) != (
            self.reconciliation_trace is not None
        ):
            raise ValueError(
                "uncertain debt requires one reconciliation trace"
            )
        return self


class CoverageAssessmentLedger(IRModel):
    kind: Literal["ratchet_coverage_assessment"]
    qualification: CoverageQualification
    inventory_coverage: Literal["complete", "partial"]
    discovery_coverage: Literal["complete", "partial"]
    groups: Annotated[
        tuple[CoverageSubjectGroup, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    debts: Annotated[
        tuple[CoverageDebtSnapshot, ...],
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
    behavior: BehaviorAssessmentLedger
    coverage: CoverageAssessmentLedger

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        version = value.rsplit(":", maxsplit=1)[-1]
        if SEMANTIC_VERSION.fullmatch(version) is None:
            raise ValueError(
                "ratchet assessment procedure URI must end in a version"
            )
        return value


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


class RatchetV1PolicyRef(IRModel):
    kind: Literal["ratchet_policy_ref"]
    schema_uri: Literal["urn:ucf:ratchet:policy:1.0.0"]
    schema_version: Literal["1.0.0"]
    target_id: PolicyId
    canonical_digest: Digest


class RatchetV1AssessmentRef(IRModel):
    kind: Literal["ratchet_assessment_ref"]
    schema_uri: Literal["urn:ucf:ratchet:assessment:1.0.0"]
    schema_version: Literal["1.0.0"]
    target_id: AssessmentId
    canonical_digest: Digest


class RatchetV1BaselineRef(IRModel):
    kind: Literal["ratchet_baseline_ref"]
    schema_uri: Literal["urn:ucf:ratchet:baseline:1.0.0"]
    schema_version: Literal["1.0.0"]
    target_id: BaselineId
    canonical_digest: Digest
    generation: Annotated[SafeInteger, Field(ge=0)]


class RatchetV1MigrationSource(IRModel):
    kind: Literal["ratchet_v1_migration_source"]
    policy: RatchetV1PolicyRef
    baseline: RatchetV1BaselineRef
    assessment: RatchetV1AssessmentRef
    onboarding_bundle: OnboardingBundleRef


class BehaviorBaselineLedger(IRModel):
    kind: Literal["ratchet_behavior_baseline"]
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


class CoverageBaselineLedger(IRModel):
    kind: Literal["ratchet_coverage_baseline"]
    qualification: CoverageQualification
    groups: Annotated[
        tuple[CoverageSubjectGroup, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    allowances: Annotated[
        tuple[CoverageDebtSnapshot, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    protected: Annotated[
        tuple[CoverageDebtKey, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]


class RatchetBaselineOrigin(StrEnum):
    INITIAL = "initial"
    SUCCESSOR = "successor"
    MIGRATED_V1 = "migrated_v1"


class RatchetBaseline(IRModel):
    kind: Literal["ratchet_baseline"]
    ratchet_version: Literal[RATCHET_VERSION]
    schema_uri: Literal[RATCHET_BASELINE_SCHEMA_URI]
    id: BaselineId
    origin: RatchetBaselineOrigin
    generation: Annotated[SafeInteger, Field(ge=0)]
    policy: RatchetPolicyRef
    source_assessment: RatchetAssessmentRef | RatchetV1AssessmentRef
    source_evaluation: RatchetEvaluationReportRef | None
    predecessor: RatchetBaselineRef | None
    migrated_from: RatchetV1MigrationSource | None
    behavior: BehaviorBaselineLedger
    coverage: CoverageBaselineLedger

    @model_validator(mode="after")
    def validate_origin(self) -> RatchetBaseline:
        if self.origin is RatchetBaselineOrigin.INITIAL:
            if (
                self.generation != 0
                or self.predecessor is not None
                or self.source_evaluation is not None
                or self.migrated_from is not None
                or not isinstance(self.source_assessment, RatchetAssessmentRef)
            ):
                raise ValueError("initial baseline has incompatible lineage")
            return self
        if self.origin is RatchetBaselineOrigin.MIGRATED_V1:
            if (
                self.predecessor is not None
                or self.source_evaluation is not None
                or self.migrated_from is None
                or not isinstance(
                    self.source_assessment,
                    RatchetV1AssessmentRef,
                )
                or self.generation != self.migrated_from.baseline.generation
            ):
                raise ValueError("migrated baseline has incompatible lineage")
            return self
        if (
            self.predecessor is None
            or self.source_evaluation is None
            or self.migrated_from is not None
            or not isinstance(self.source_assessment, RatchetAssessmentRef)
            or self.generation != self.predecessor.generation + 1
        ):
            raise ValueError("successor baseline has incompatible lineage")
        return self


class BehaviorSubjectChangeKind(StrEnum):
    UNCHANGED = "unchanged"
    SEMANTIC_CHANGED = "semantic_changed"
    OBSERVED_CHANGED = "observed_changed"
    SEMANTIC_AND_OBSERVED_CHANGED = "semantic_and_observed_changed"
    NEW_SUBJECT = "new_subject"
    REMOVED_SUBJECT = "removed_subject"
    UNKNOWN_SUBJECT = "unknown_subject"


class BehaviorSubjectChange(IRModel):
    kind: Literal["ratchet_behavior_subject_change"]
    subject: BehaviorSubjectRef
    change: BehaviorSubjectChangeKind


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


class CoverageSubjectChangeKind(StrEnum):
    UNCHANGED = "unchanged"
    SEMANTIC_CHANGED = "semantic_changed"
    OBSERVED_CHANGED = "observed_changed"
    SEMANTIC_AND_OBSERVED_CHANGED = "semantic_and_observed_changed"
    NEW_SUBJECT = "new_subject"
    UNKNOWN_SUBJECT = "unknown_subject"


class CoverageSubjectChange(IRModel):
    kind: Literal["ratchet_coverage_subject_change"]
    subject: CoverageSubjectRef
    change: CoverageSubjectChangeKind


class CoverageDebtClassificationKind(StrEnum):
    UNCHANGED_LEGACY = "unchanged_legacy"
    NEW_REGRESSION = "new_regression"
    CHANGED_REGRESSION = "changed_regression"
    REINTRODUCED = "reintroduced"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class CoverageDebtClassification(IRModel):
    kind: Literal["ratchet_coverage_debt_classification"]
    classification: CoverageDebtClassificationKind
    key: CoverageDebtKey


class WeakeningDeltaStatus(StrEnum):
    NONE = "none"
    TIGHTENING = "tightening"
    REVIEW_REQUIRED = "review_required"


class BehaviorWeakeningDelta(IRModel):
    kind: Literal["ratchet_behavior_delta"]
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


class CoverageWeakeningDelta(IRModel):
    kind: Literal["ratchet_coverage_delta"]
    status: WeakeningDeltaStatus
    added_allowances: Annotated[
        tuple[CoverageDebtKey, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    removed_allowances: Annotated[
        tuple[CoverageDebtKey, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]
    removed_protections: Annotated[
        tuple[CoverageDebtKey, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS),
    ]


class CoverageComparisonStatus(StrEnum):
    COMPARABLE = "comparable"
    INCOMPLETE_INVENTORY = "incomplete_inventory"
    NON_COMPARABLE_QUALIFICATION = "non_comparable_qualification"


class BehaviorOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class CoverageOutcome(StrEnum):
    PASS = "pass"
    PASS_WITH_LEGACY_COVERAGE_DEBT = "pass_with_legacy_coverage_debt"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class CombinedOutcome(StrEnum):
    PASS = "pass"
    PASS_WITH_LEGACY_COVERAGE_DEBT = "pass_with_legacy_coverage_debt"
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
    behavior_subject_changes: Annotated[
        tuple[BehaviorSubjectChange, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS * 2),
    ]
    behavior_classifications: Annotated[
        tuple[ViolationClassification, ...],
        Field(max_length=MAX_RATCHET_VIOLATIONS * 2),
    ]
    coverage_comparison: CoverageComparisonStatus
    coverage_subject_changes: Annotated[
        tuple[CoverageSubjectChange, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS * 2),
    ]
    coverage_classifications: Annotated[
        tuple[CoverageDebtClassification, ...],
        Field(max_length=MAX_RATCHET_SUBJECTS * 2),
    ]
    behavior_outcome: BehaviorOutcome
    coverage_outcome: CoverageOutcome
    combined_outcome: CombinedOutcome
    behavior_delta: BehaviorWeakeningDelta
    coverage_delta: CoverageWeakeningDelta
