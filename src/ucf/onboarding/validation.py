from __future__ import annotations

from ucf.inventory import InventoryRecordKind, PublicInterfaceFact
from ucf.onboarding.codec import canonical_onboarding_digest
from ucf.onboarding.errors import (
    OnboardingErrorCode,
    OnboardingValidationError,
)
from ucf.onboarding.identity import (
    derive_candidate_semantic_digest,
    derive_decision_id,
    derive_discovery_candidate_id,
)
from ucf.onboarding.models import (
    CandidateProposal,
    DecisionSet,
    DiscoveryRequest,
    DiscoveryResult,
    EditedDecision,
    ProposalEntityKind,
    ProposalEntityRef,
    ProposalPortRef,
    ProposedAction,
    ProposedBinding,
    ProposedStep,
    ProposedUseCase,
)


def validate_discovery_exchange(
    request: DiscoveryRequest,
    result: DiscoveryResult,
) -> None:
    for field in (
        "subject_uri",
        "source_revision",
        "canonical_digest",
    ):
        if getattr(request.inventory_binding, field) != getattr(
            result.inventory_binding,
            field,
        ):
            raise OnboardingValidationError(
                OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                "discovery result names a different inventory snapshot",
                location=f"$.inventory_binding.{field}",
            )
    _validate_diagnostics(request, result)
    _validate_candidates(request, result)


def _validate_diagnostics(
    request: DiscoveryRequest,
    result: DiscoveryResult,
) -> None:
    diagnostic_ids = tuple(
        diagnostic.id for diagnostic in result.diagnostics
    )
    if len(diagnostic_ids) != len(set(diagnostic_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "discovery diagnostic IDs must be unique",
            location="$.diagnostics",
        )
    if diagnostic_ids != tuple(sorted(diagnostic_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.NON_CANONICAL_ORDER,
            "discovery diagnostics must be sorted by ID",
            location="$.diagnostics",
        )

    records_by_id = {
        record.id: record for record in request.inventory.records
    }
    for position, diagnostic in enumerate(result.diagnostics):
        reference = diagnostic.evidence
        if reference is None:
            continue
        location = f"$.diagnostics[{position}].evidence"
        target = records_by_id.get(reference.target_id)
        if target is None:
            raise OnboardingValidationError(
                OnboardingErrorCode.BROKEN_REFERENCE,
                "diagnostic evidence target does not exist",
                location=location,
            )
        if InventoryRecordKind(target.kind) is not reference.target_kind:
            raise OnboardingValidationError(
                OnboardingErrorCode.WRONG_TARGET_KIND,
                "diagnostic evidence target has a different kind",
                location=location,
            )


def _validate_candidates(
    request: DiscoveryRequest,
    result: DiscoveryResult,
) -> None:
    candidate_ids = tuple(candidate.id for candidate in result.candidates)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "discovery candidate IDs must be unique",
            location="$.candidates",
        )
    if candidate_ids != tuple(sorted(candidate_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.NON_CANONICAL_ORDER,
            "discovery candidates must be sorted by content identity",
            location="$.candidates",
        )
    semantic_digests = tuple(
        candidate.semantic_digest.value for candidate in result.candidates
    )
    if len(semantic_digests) != len(set(semantic_digests)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "discovery candidates must have unique semantic proposals",
            location="$.candidates",
        )

    records_by_id = {
        record.id: record for record in request.inventory.records
    }
    for position, candidate in enumerate(result.candidates):
        location = f"$.candidates[{position}]"
        validate_candidate_proposal(
            candidate.proposal,
            location=f"{location}.proposal",
        )
        expected_semantic_digest = derive_candidate_semantic_digest(
            candidate.proposal
        )
        if candidate.semantic_digest != expected_semantic_digest:
            raise OnboardingValidationError(
                OnboardingErrorCode.CONTENT_IDENTITY_MISMATCH,
                "candidate semantic digest does not match its proposal",
                location=f"{location}.semantic_digest",
            )
        if candidate.id != derive_discovery_candidate_id(candidate, result):
            raise OnboardingValidationError(
                OnboardingErrorCode.CONTENT_IDENTITY_MISMATCH,
                "candidate ID does not match its exact content and context",
                location=f"{location}.id",
            )
        evidence_keys = tuple(
            (reference.target_kind.value, reference.target_id)
            for reference in candidate.evidence
        )
        if (
            len(evidence_keys) != len(set(evidence_keys))
            or evidence_keys != tuple(sorted(evidence_keys))
        ):
            raise OnboardingValidationError(
                OnboardingErrorCode.NON_CANONICAL_ORDER,
                "candidate evidence must be unique and canonically sorted",
                location=f"{location}.evidence",
            )
        for evidence_position, reference in enumerate(candidate.evidence):
            reference_location = (
                f"{location}.evidence[{evidence_position}]"
            )
            target = records_by_id.get(reference.target_id)
            if target is None:
                raise OnboardingValidationError(
                    OnboardingErrorCode.BROKEN_REFERENCE,
                    "candidate evidence target does not exist",
                    location=reference_location,
                )
            if InventoryRecordKind(target.kind) is not reference.target_kind:
                raise OnboardingValidationError(
                    OnboardingErrorCode.WRONG_TARGET_KIND,
                    "candidate evidence target has a different kind",
                    location=reference_location,
                )
        subject_location = f"{location}.subject"
        subject_target = records_by_id.get(candidate.subject.target_id)
        if subject_target is None:
            raise OnboardingValidationError(
                OnboardingErrorCode.BROKEN_REFERENCE,
                "candidate subject target does not exist",
                location=subject_location,
            )
        if (
            candidate.subject.target_kind
            is not InventoryRecordKind.PUBLIC_INTERFACE
            or not isinstance(subject_target, PublicInterfaceFact)
        ):
            raise OnboardingValidationError(
                OnboardingErrorCode.WRONG_TARGET_KIND,
                "candidate subject must resolve to a public interface",
                location=subject_location,
            )
        if candidate.subject not in candidate.evidence:
            raise OnboardingValidationError(
                OnboardingErrorCode.SUMMARY_MISMATCH,
                "candidate evidence must include its subject",
                location=f"{location}.evidence",
            )

    _validate_coverage(request, result)


def _validate_coverage(
    request: DiscoveryRequest,
    result: DiscoveryResult,
) -> None:
    coverage = result.coverage
    eligible_keys = tuple(
        (reference.target_kind.value, reference.target_id)
        for reference in coverage.eligible_subjects
    )
    uncovered_keys = tuple(
        (reference.target_kind.value, reference.target_id)
        for reference in coverage.uncovered_subjects
    )
    for location, keys in (
        ("$.coverage.eligible_subjects", eligible_keys),
        ("$.coverage.uncovered_subjects", uncovered_keys),
    ):
        if len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
            raise OnboardingValidationError(
                OnboardingErrorCode.NON_CANONICAL_ORDER,
                "coverage references must be unique and canonically sorted",
                location=location,
            )
    expected_eligible = {
        (
            InventoryRecordKind.PUBLIC_INTERFACE.value,
            record.id,
        )
        for record in request.inventory.records
        if isinstance(record, PublicInterfaceFact)
    }
    if set(eligible_keys) != expected_eligible:
        raise OnboardingValidationError(
            OnboardingErrorCode.SUMMARY_MISMATCH,
            "eligible subjects do not match inventory public interfaces",
            location="$.coverage.eligible_subjects",
        )
    if not set(uncovered_keys).issubset(expected_eligible):
        raise OnboardingValidationError(
            OnboardingErrorCode.BROKEN_REFERENCE,
            "uncovered subjects must be eligible public interfaces",
            location="$.coverage.uncovered_subjects",
        )
    candidate_subjects = {
        (
            candidate.subject.target_kind.value,
            candidate.subject.target_id,
        )
        for candidate in result.candidates
    }
    covered_subjects = expected_eligible - set(uncovered_keys)
    if candidate_subjects != covered_subjects:
        raise OnboardingValidationError(
            OnboardingErrorCode.SUMMARY_MISMATCH,
            "candidate subjects do not match declared discovery coverage",
            location="$.coverage",
        )


def validate_decision_set(
    discovery: DiscoveryResult,
    decision_set: DecisionSet,
) -> None:
    discovery_digest = canonical_onboarding_digest(discovery)
    if decision_set.discovery.canonical_digest != discovery_digest:
        _stale_decision(
            "decision set names a different discovery document",
            location="$.discovery.canonical_digest",
        )
    for field in (
        "subject_uri",
        "source_revision",
        "canonical_digest",
    ):
        if getattr(decision_set.inventory_binding, field) != getattr(
            discovery.inventory_binding,
            field,
        ):
            _stale_decision(
                "decision set names a different inventory snapshot",
                location=f"$.inventory_binding.{field}",
            )

    candidates_by_id = {
        candidate.id: candidate for candidate in discovery.candidates
    }
    decision_candidate_ids = tuple(
        decision.candidate.candidate_id
        for decision in decision_set.decisions
    )
    if (
        len(decision_candidate_ids) != len(candidates_by_id)
        or len(decision_candidate_ids) != len(set(decision_candidate_ids))
        or set(decision_candidate_ids) != set(candidates_by_id)
    ):
        _stale_decision(
            "decisions must cover every current candidate exactly once",
            location="$.decisions",
        )

    for position, decision in enumerate(decision_set.decisions):
        location = f"$.decisions[{position}]"
        candidate = candidates_by_id[decision.candidate.candidate_id]
        if decision.candidate.discovery_digest != discovery_digest:
            _stale_decision(
                "candidate reference names a different discovery document",
                location=f"{location}.candidate.discovery_digest",
            )
        if decision.candidate.semantic_digest != candidate.semantic_digest:
            _stale_decision(
                "candidate semantic digest is stale",
                location=f"{location}.candidate.semantic_digest",
            )
        if isinstance(decision, EditedDecision):
            validate_candidate_proposal(
                decision.replacement,
                location=f"{location}.replacement",
            )
            if (
                decision.replacement_digest
                != derive_candidate_semantic_digest(decision.replacement)
            ):
                _stale_decision(
                    "edited replacement digest is stale",
                    location=f"{location}.replacement_digest",
                )
        if decision.id != derive_decision_id(decision, decision_set):
            raise OnboardingValidationError(
                OnboardingErrorCode.CONTENT_IDENTITY_MISMATCH,
                "decision ID does not match its exact content and context",
                location=f"{location}.id",
            )

    if decision_candidate_ids != tuple(sorted(decision_candidate_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.NON_CANONICAL_ORDER,
            "decisions must be sorted by candidate ID",
            location="$.decisions",
        )


def _stale_decision(message: str, *, location: str) -> None:
    raise OnboardingValidationError(
        OnboardingErrorCode.STALE_DECISION,
        message,
        location=location,
    )


def validate_candidate_proposal(
    proposal: CandidateProposal,
    *,
    location: str = "$",
) -> None:
    entity_ids = tuple(entity.id for entity in proposal.entities)
    if len(entity_ids) != len(set(entity_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "proposal entity IDs must be globally unique",
            location=f"{location}.entities",
        )
    entity_keys = tuple(
        (str(entity.kind), entity.id) for entity in proposal.entities
    )
    if entity_keys != tuple(sorted(entity_keys)):
        raise OnboardingValidationError(
            OnboardingErrorCode.NON_CANONICAL_ORDER,
            "proposal entities must be in canonical kind and ID order",
            location=f"{location}.entities",
        )
    by_id = {entity.id: entity for entity in proposal.entities}
    root = _resolve_proposal_ref(
        proposal.root,
        by_id,
        location=f"{location}.root",
    )
    if not isinstance(root, ProposedUseCase):
        raise OnboardingValidationError(
            OnboardingErrorCode.WRONG_TARGET_KIND,
            "proposal root must resolve to a proposed use case",
            location=f"{location}.root",
        )

    for position, entity in enumerate(proposal.entities):
        entity_location = f"{location}.entities[{position}]"
        if isinstance(entity, (ProposedAction, ProposedUseCase)):
            _validate_proposal_ports(
                entity.input_ports,
                location=f"{entity_location}.input_ports",
            )
            _validate_proposal_ports(
                entity.output_ports,
                location=f"{entity_location}.output_ports",
            )

    reachable = {root.id}
    step_positions: dict[str, int] = {}
    for step_position, step_ref in enumerate(root.steps):
        step = _resolve_proposal_ref(
            step_ref,
            by_id,
            location=f"{location}.root.steps[{step_position}]",
        )
        if not isinstance(step, ProposedStep):
            raise OnboardingValidationError(
                OnboardingErrorCode.WRONG_TARGET_KIND,
                "use-case steps must resolve to proposed steps",
                location=f"{location}.root.steps[{step_position}]",
            )
        reachable.add(step.id)
        step_positions.setdefault(step.id, step_position)
        action = _resolve_proposal_ref(
            step.action,
            by_id,
            location=f"{location}.entities[{entity_ids.index(step.id)}].action",
        )
        if not isinstance(action, ProposedAction):
            raise OnboardingValidationError(
                OnboardingErrorCode.WRONG_TARGET_KIND,
                "step action must resolve to a proposed action",
                location=f"{location}.entities[{entity_ids.index(step.id)}].action",
            )
        reachable.add(action.id)
        _validate_step_bindings(
            root,
            step,
            action,
            by_id,
            reachable,
            step_positions,
            location=f"{location}.entities[{entity_ids.index(step.id)}]",
        )

    if reachable != set(entity_ids):
        raise OnboardingValidationError(
            OnboardingErrorCode.UNREACHABLE_ENTITY,
            "proposal contains an entity unreachable from its root",
            location=f"{location}.entities",
        )


def _validate_step_bindings(
    root: ProposedUseCase,
    step: ProposedStep,
    action: ProposedAction,
    by_id: dict[str, object],
    reachable: set[str],
    step_positions: dict[str, int],
    *,
    location: str,
) -> None:
    binding_ids = tuple(reference.target_id for reference in step.bindings)
    if len(binding_ids) != len(set(binding_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "step binding references must be unique",
            location=f"{location}.bindings",
        )
    bound_inputs: list[str] = []
    for position, reference in enumerate(step.bindings):
        binding = _resolve_proposal_ref(
            reference,
            by_id,
            location=f"{location}.bindings[{position}]",
        )
        if not isinstance(binding, ProposedBinding):
            raise OnboardingValidationError(
                OnboardingErrorCode.WRONG_TARGET_KIND,
                "step bindings must resolve to proposed bindings",
                location=f"{location}.bindings[{position}]",
            )
        reachable.add(binding.id)
        if (
            binding.target.owner.target_kind
            is not ProposalEntityKind.STEP
            or binding.target.owner.target_id != step.id
            or binding.target.direction != "input"
        ):
            _invalid_proposal(
                "binding target must be an input on its owning step",
                location=f"{location}.bindings[{position}]",
            )
        target_port = _find_port(
            action.input_ports,
            binding.target,
            location=f"{location}.bindings[{position}].target",
        )
        source_port = _resolve_binding_source(
            binding.source,
            root,
            by_id,
            step,
            step_positions,
            location=f"{location}.bindings[{position}].source",
        )
        if source_port.value_kind is not target_port.value_kind:
            _invalid_proposal(
                "binding source and target value kinds differ",
                location=f"{location}.bindings[{position}]",
            )
        bound_inputs.append(target_port.name)
    required_inputs = tuple(
        port.name for port in action.input_ports if port.required
    )
    if (
        len(bound_inputs) != len(set(bound_inputs))
        or any(name not in bound_inputs for name in required_inputs)
    ):
        _invalid_proposal(
            "each required action input needs exactly one binding",
            location=f"{location}.bindings",
        )


def _resolve_binding_source(
    source: ProposalPortRef,
    root: ProposedUseCase,
    by_id: dict[str, object],
    target_step: ProposedStep,
    step_positions: dict[str, int],
    *,
    location: str,
):
    owner = _resolve_proposal_ref(source.owner, by_id, location=location)
    if isinstance(owner, ProposedUseCase):
        if owner.id != root.id or source.direction != "input":
            _invalid_proposal(
                "binding source use case must be the root input",
                location=location,
            )
        return _find_port(owner.input_ports, source, location=location)
    if isinstance(owner, ProposedStep):
        if (
            source.direction != "output"
            or owner.id not in step_positions
            or step_positions[owner.id] >= step_positions[target_step.id]
        ):
            _invalid_proposal(
                "binding source step must be a prior step output",
                location=location,
            )
        action = _resolve_proposal_ref(
            owner.action,
            by_id,
            location=location,
        )
        assert isinstance(action, ProposedAction)
        return _find_port(action.output_ports, source, location=location)
    _invalid_proposal(
        "binding source owner must be a use case or prior step",
        location=location,
    )


def _resolve_proposal_ref(
    reference: ProposalEntityRef,
    by_id: dict[str, object],
    *,
    location: str,
):
    target = by_id.get(reference.target_id)
    if target is None:
        raise OnboardingValidationError(
            OnboardingErrorCode.BROKEN_REFERENCE,
            "proposal reference target does not exist",
            location=location,
        )
    if target.kind is not reference.target_kind:
        raise OnboardingValidationError(
            OnboardingErrorCode.WRONG_TARGET_KIND,
            "proposal reference target has a different kind",
            location=location,
        )
    return target


def _validate_proposal_ports(ports, *, location: str) -> None:
    names = tuple(port.name for port in ports)
    if len(names) != len(set(names)) or names != tuple(sorted(names)):
        raise OnboardingValidationError(
            OnboardingErrorCode.NON_CANONICAL_ORDER,
            "proposal ports must be unique and sorted by name",
            location=location,
        )


def _find_port(ports, reference: ProposalPortRef, *, location: str):
    for port in ports:
        if port.name == reference.name:
            return port
    _invalid_proposal(
        "proposal port reference does not resolve",
        location=location,
    )


def _invalid_proposal(message: str, *, location: str) -> None:
    raise OnboardingValidationError(
        OnboardingErrorCode.INVALID_PROPOSAL,
        message,
        location=location,
    )
