from __future__ import annotations

from collections.abc import Collection

from ucf.ir.models import Producer
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    CaptureContext,
    OnboardingBundle,
    canonical_onboarding_digest,
)
from ucf.ratchet.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.identity import (
    derive_assessment_id,
    derive_violation_id,
)
from ucf.ratchet.models import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorSubjectRef,
    OnboardingBundleRef,
    RatchetAssessment,
    RatchetPolicy,
    RatchetRuleRef,
    RatchetViolation,
    RuleCoverage,
    ViolationInput,
    ViolationKey,
)
from ucf.ratchet.projection import derive_subject_snapshots
from ucf.ratchet.references import policy_ref
from ucf.ratchet.validation import (
    validate_ratchet_assessment,
    validate_ratchet_policy,
)


def build_ratchet_assessment(
    policy: RatchetPolicy,
    bundle: OnboardingBundle,
    *,
    producer: Producer,
    procedure_uri: str,
    capture_context: CaptureContext,
    violations: tuple[ViolationInput, ...] = (),
    partial_rule_ids: Collection[str] = (),
) -> RatchetAssessment:
    validate_ratchet_policy(policy)
    unknown_partial = set(partial_rule_ids) - {
        rule.id for rule in policy.rules
    }
    if unknown_partial:
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "partial coverage names an unknown policy rule",
            location="$.coverage",
        )
    subjects = derive_subject_snapshots(bundle)
    subject_by_key = {subject.key: subject for subject in subjects}
    rules = {rule.id: rule for rule in policy.rules}
    subject_refs = tuple(
        sorted(
            (
                BehaviorSubjectRef(
                    kind="behavior_subject_ref",
                    target_id=subject.id,
                )
                for subject in subjects
            ),
            key=lambda item: item.target_id,
        )
    )
    coverage = tuple(
        RuleCoverage(
            kind="ratchet_rule_coverage",
            rule=_rule_ref(rule),
            status=(
                "partial" if rule.id in partial_rule_ids else "complete"
            ),
            subjects=subject_refs,
        )
        for rule in policy.rules
    )
    violation_records = []
    for item in violations:
        rule = rules.get(item.rule_id)
        if rule is None:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names an unknown policy rule",
                location="$.violations",
            )
        subject = subject_by_key.get(item.subject)
        if subject is None:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names an unknown behavior subject",
                location="$.violations",
            )
        key = ViolationKey(
            kind="violation_key",
            rule=_rule_ref(rule),
            subject=BehaviorSubjectRef(
                kind="behavior_subject_ref",
                target_id=subject.id,
            ),
            slot=item.slot,
        )
        violation_records.append(
            RatchetViolation(
                kind="ratchet_violation",
                id=derive_violation_id(key),
                key=key,
                message=item.message,
            )
        )
    provisional = RatchetAssessment(
        kind="ratchet_assessment",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_ASSESSMENT_SCHEMA_URI,
        id=f"assessment.{'0' * 64}",
        policy=policy_ref(policy),
        source=OnboardingBundleRef(
            kind="onboarding_bundle_ref",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        producer=producer,
        procedure_uri=procedure_uri,
        capture_context=capture_context,
        subject_coverage=bundle.discovery.coverage.status,
        subjects=subjects,
        coverage=coverage,
        violations=tuple(
            sorted(violation_records, key=lambda item: item.id)
        ),
    )
    assessment = provisional.model_copy(
        update={"id": derive_assessment_id(provisional)}
    )
    validate_ratchet_assessment(policy, bundle, assessment)
    return assessment
def _rule_ref(rule) -> RatchetRuleRef:
    return RatchetRuleRef(
        kind="ratchet_rule_ref",
        target_id=rule.id,
        version=rule.version,
    )
