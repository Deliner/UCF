from __future__ import annotations

from ucf.inventory import FactKind
from ucf.onboarding import OnboardingBundle, OnboardingValidationError
from ucf.ratchet.errors import RatchetValidationError as V1ValidationError
from ucf.ratchet.models import (
    RatchetAssessment as V1Assessment,
)
from ucf.ratchet.models import (
    RatchetBaseline as V1Baseline,
)
from ucf.ratchet.models import (
    RatchetPolicy as V1Policy,
)
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.identity import derive_baseline_id
from ucf.ratchet.v2.models import (
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorBaselineLedger,
    CoverageBaselineLedger,
    RatchetBaseline,
    RatchetBaselineOrigin,
    RatchetPolicy,
    RatchetV1MigrationSource,
    ViolationKey,
)
from ucf.ratchet.v2.projection import (
    derive_behavior_subject_snapshots,
    derive_coverage_ledger,
)
from ucf.ratchet.v2.references import (
    onboarding_bundle_ref,
    policy_ref,
    v1_assessment_ref,
    v1_baseline_ref,
    v1_policy_ref,
)
from ucf.ratchet.v2.validation import (
    validate_migrated_ratchet_baseline,
    validate_ratchet_policy,
)
from ucf.ratchet.validation import (
    validate_initial_ratchet_baseline as validate_v1_initial_baseline,
)
from ucf.ratchet.validation import (
    validate_ratchet_assessment as validate_v1_assessment,
)
from ucf.ratchet.validation import (
    validate_ratchet_baseline_structure as validate_v1_baseline_structure,
)
from ucf.ratchet.validation import (
    validate_ratchet_policy as validate_v1_policy,
)


def migrate_ratchet_v1_baseline(
    target_policy: RatchetPolicy,
    source_policy: V1Policy,
    source_baseline: V1Baseline,
    source_assessment: V1Assessment,
    bundle: OnboardingBundle,
    *,
    accepted_source_baseline_id: str,
) -> RatchetBaseline:
    _validate_migration_sources(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
        accepted_source_baseline_id=accepted_source_baseline_id,
    )
    migrated = _derive_migrated_baseline(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
    )
    validate_migrated_ratchet_baseline(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
        migrated,
        accepted_source_baseline_id=accepted_source_baseline_id,
    )
    return migrated


def _validate_migration_sources(
    target_policy: RatchetPolicy,
    source_policy: V1Policy,
    source_baseline: V1Baseline,
    source_assessment: V1Assessment,
    bundle: OnboardingBundle,
    *,
    accepted_source_baseline_id: str,
) -> None:
    validate_ratchet_policy(target_policy)
    if source_baseline.id != accepted_source_baseline_id:
        _mismatch(
            "v1 source baseline differs from the independently accepted tip",
            "$.accepted_source_baseline_id",
        )
    try:
        validate_v1_policy(source_policy)
        validate_v1_assessment(source_policy, bundle, source_assessment)
        validate_v1_baseline_structure(source_baseline)
        if source_baseline.generation == 0:
            validate_v1_initial_baseline(
                source_policy,
                bundle,
                source_assessment,
                source_baseline,
            )
    except (V1ValidationError, OnboardingValidationError) as error:
        raise RatchetValidationError(
            RatchetErrorCode.MIGRATION_SOURCE_MISMATCH,
            "v1 source resources do not form a valid exact source",
            location="$.source",
        ) from error
    if source_baseline.policy.model_dump(mode="json") != v1_policy_ref(
        source_policy
    ).model_dump(mode="json"):
        _mismatch("baseline names a different v1 policy", "$.source.baseline.policy")
    if source_baseline.source_assessment.model_dump(
        mode="json"
    ) != v1_assessment_ref(source_assessment).model_dump(mode="json"):
        _mismatch(
            "baseline names a different v1 assessment",
            "$.source.baseline.source_assessment",
        )
    if source_baseline.subjects != source_assessment.subjects:
        _mismatch(
            "v1 baseline subjects differ from its source assessment",
            "$.source.baseline.subjects",
        )
    source_rules = {
        (rule.id, rule.version) for rule in source_policy.rules
    }
    for collection in ("allowances", "protected"):
        if any(
            (key.rule.target_id, key.rule.version) not in source_rules
            for key in getattr(source_baseline, collection)
        ):
            _mismatch(
                "v1 baseline names a rule outside its policy",
                f"$.source.baseline.{collection}",
            )
    if tuple(
        rule.model_dump(mode="json") for rule in target_policy.rules
    ) != tuple(rule.model_dump(mode="json") for rule in source_policy.rules):
        _mismatch(
            "target v2 policy rules differ from the v1 source policy",
            "$.target_policy.rules",
        )
    projected = derive_behavior_subject_snapshots(bundle)
    source_projection = tuple(
        (
            subject.id,
            subject.key.model_dump(mode="json"),
            subject.semantic.digest,
        )
        for subject in source_assessment.subjects
    )
    target_projection = tuple(
        (
            subject.id,
            subject.key.model_dump(mode="json"),
            subject.semantic.digest,
        )
        for subject in projected
    )
    if target_projection != source_projection:
        _mismatch(
            "v1 behavior projection cannot be represented exactly in v2",
            "$.source.assessment.subjects",
        )
    public_interface_coverage = next(
        item.status
        for item in bundle.inventory.coverage
        if item.fact_kind is FactKind.PUBLIC_INTERFACE
    )
    if public_interface_coverage != "complete":
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN,
            "v1 migration requires a complete public-interface inventory",
            location="$.source_assessment.coverage.inventory_coverage",
        )


def _derive_migrated_baseline(
    target_policy: RatchetPolicy,
    source_policy: V1Policy,
    source_baseline: V1Baseline,
    source_assessment: V1Assessment,
    bundle: OnboardingBundle,
) -> RatchetBaseline:
    coverage = derive_coverage_ledger(bundle)
    provisional = RatchetBaseline(
        kind="ratchet_baseline",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        id=f"baseline.{'0' * 64}",
        origin=RatchetBaselineOrigin.MIGRATED_V1,
        generation=source_baseline.generation,
        policy=policy_ref(target_policy),
        source_assessment=v1_assessment_ref(source_assessment),
        source_evaluation=None,
        predecessor=None,
        migrated_from=RatchetV1MigrationSource(
            kind="ratchet_v1_migration_source",
            policy=v1_policy_ref(source_policy),
            baseline=v1_baseline_ref(source_baseline),
            assessment=v1_assessment_ref(source_assessment),
            onboarding_bundle=onboarding_bundle_ref(bundle),
        ),
        behavior=BehaviorBaselineLedger(
            kind="ratchet_behavior_baseline",
            subjects=derive_behavior_subject_snapshots(bundle),
            allowances=_convert_violation_keys(source_baseline.allowances),
            protected=_convert_violation_keys(source_baseline.protected),
        ),
        coverage=CoverageBaselineLedger(
            kind="ratchet_coverage_baseline",
            qualification=coverage.qualification,
            groups=coverage.groups,
            allowances=coverage.debts,
            protected=(),
        ),
    )
    return provisional.model_copy(update={"id": derive_baseline_id(provisional)})


def _convert_violation_keys(values) -> tuple[ViolationKey, ...]:
    return tuple(
        ViolationKey.model_validate_json(value.model_dump_json())
        for value in values
    )


def _mismatch(message: str, location: str) -> None:
    raise RatchetValidationError(
        RatchetErrorCode.MIGRATION_SOURCE_MISMATCH,
        message,
        location=location,
    )
