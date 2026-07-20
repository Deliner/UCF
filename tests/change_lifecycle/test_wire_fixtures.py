from __future__ import annotations

from collections.abc import Callable

import pytest

from ucf.change_lifecycle import (
    ArchiveRecord,
    BehaviorDelta,
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ChangeProposal,
    ImplementationRecord,
    TaskGraph,
    VerificationRecord,
    derive_verification_record,
    parse_archive_record_json,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    parse_implementation_record_json,
    parse_task_graph_json,
    parse_verification_record_json,
    validate_archive_record,
    validate_behavior_delta,
    validate_change_proposal,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
)

from ._fixture_factory import (
    DEFAULT_FIXTURE_DIRECTORY,
    behavior_pair,
    evidence_context,
    render_wire_fixtures,
)

type Parser = Callable[
    [str | bytes],
    (
        ChangeProposal
        | BehaviorDelta
        | TaskGraph
        | ImplementationRecord
        | VerificationRecord
        | ArchiveRecord
    ),
]


def _fixture(relative_path: str) -> bytes:
    return (DEFAULT_FIXTURE_DIRECTORY / relative_path).read_bytes()


def _positive_chain() -> tuple[
    ChangeProposal,
    BehaviorDelta,
    TaskGraph,
    ImplementationRecord,
    VerificationRecord,
    ArchiveRecord,
]:
    return (
        parse_change_proposal_json(_fixture("positive/proposal.json")),
        parse_behavior_delta_json(_fixture("positive/behavior-delta.json")),
        parse_task_graph_json(_fixture("positive/task-graph.json")),
        parse_implementation_record_json(
            _fixture("positive/implementation-record.json")
        ),
        parse_verification_record_json(_fixture("positive/verification-record.json")),
        parse_archive_record_json(_fixture("positive/archive-record.json")),
    )


def test_committed_wire_fixtures_are_current_and_positive_chain_is_exact() -> None:
    rendered = render_wire_fixtures()
    assert len(rendered) == 37
    for path, content in rendered.items():
        assert path.read_text(encoding="utf-8") == content

    base, final = behavior_pair()
    proposal, delta, graph, implementation, verification, archive = _positive_chain()
    contexts = (evidence_context(delta),)
    validate_change_proposal(proposal, base)
    validate_behavior_delta(delta, proposal, base, final)
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
    )
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    validate_archive_record(
        archive,
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base,
        final,
        evidence_contexts=contexts,
    )


@pytest.mark.parametrize(
    ("relative_path", "parser", "expected_code"),
    [
        (
            "invalid/duplicate-json-member.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.DUPLICATE_JSON_MEMBER,
        ),
        (
            "invalid/unknown-root-field.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unknown-nested-field.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unsupported-version.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unsupported-openspec-profile.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/invalid-artifact-utf8.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/noncanonical-artifact-base64.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/mismatched-artifact-digest.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unsafe-artifact-path.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/artifact-role-path-mismatch.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/binary-tasks-media-mismatch.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/noncanonical-delta-spec-layout.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/orphan-base-spec.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unsupported-profile-metadata.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/missing-profile-declaration.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/excessive-profile-nesting.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/file-directory-prefix-collision.json",
            parse_change_proposal_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/archive-missing-verification.json",
            parse_archive_record_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/unsupported-evidence-capability.json",
            parse_implementation_record_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
        (
            "invalid/stale-validation-receipt.json",
            parse_implementation_record_json,
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        ),
    ],
)
def test_model_invalid_wire_fixtures_are_rejected(
    relative_path: str,
    parser: Parser,
    expected_code: ChangeLifecycleErrorCode,
) -> None:
    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parser(_fixture(relative_path))
    assert captured.value.code is expected_code


@pytest.mark.parametrize(
    ("relative_path", "expected_code"),
    [
        (
            "invalid/stale-delta-proposal-reference.json",
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            "invalid/cyclic-task-dependency.json",
            ChangeLifecycleErrorCode.CYCLIC_DEPENDENCY,
        ),
        (
            "invalid/stale-verification-reference.json",
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            "invalid/stale-archive-reference.json",
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
    ],
)
def test_context_invalid_wire_fixtures_are_rejected(
    relative_path: str,
    expected_code: ChangeLifecycleErrorCode,
) -> None:
    base, final = behavior_pair()
    proposal, delta, graph, implementation, verification, _ = _positive_chain()
    contexts = (evidence_context(delta),)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        if relative_path.startswith("invalid/stale-delta"):
            invalid_delta = parse_behavior_delta_json(_fixture(relative_path))
            validate_behavior_delta(
                invalid_delta,
                proposal,
                base,
                final,
            )
        elif relative_path.startswith("invalid/cyclic"):
            invalid_graph = parse_task_graph_json(_fixture(relative_path))
            validate_task_graph(
                invalid_graph,
                delta,
                proposal,
                base_behavior=base,
                final_behavior=final,
            )
        elif relative_path.startswith("invalid/stale-verification"):
            invalid_verification = parse_verification_record_json(
                _fixture(relative_path)
            )
            validate_verification_record(
                invalid_verification,
                implementation,
                graph,
                delta,
                proposal,
                base_behavior=base,
                final_behavior=final,
                evidence_contexts=contexts,
            )
        else:
            invalid_archive = parse_archive_record_json(_fixture(relative_path))
            validate_archive_record(
                invalid_archive,
                proposal,
                delta,
                graph,
                implementation,
                verification,
                base,
                final,
                evidence_contexts=contexts,
            )
    assert captured.value.code is expected_code


def test_nonpassing_implementation_fixture_cannot_be_verified() -> None:
    base, final = behavior_pair()
    proposal, delta, graph, _, _, _ = _positive_chain()
    implementation = parse_implementation_record_json(
        _fixture("invalid/nonpassing-implementation.json")
    )
    contexts = (evidence_context(delta, "failed"),)
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_verification_record(
            implementation,
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
            evidence_contexts=contexts,
        )
    assert captured.value.code is ChangeLifecycleErrorCode.EVIDENCE_NOT_PASSED
