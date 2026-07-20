from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from ucf.change_lifecycle import (
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    OPENSPEC_INTEROP_PROFILE,
    OPENSPEC_TESTED_AGAINST_VERSION,
    AddedBehavior,
    BehaviorDelta,
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ChangeProposal,
    ModifiedBehavior,
    OpenSpecArtifact,
    OpenSpecArtifactRole,
    OpenSpecManifest,
    RemovedBehavior,
    canonical_change_lifecycle_json,
    change_proposal_ref,
    derive_behavior_delta,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    validate_behavior_delta,
    validate_change_proposal,
)
from ucf.change_lifecycle.models import MAX_OPENSPEC_ARTIFACT_BYTES
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import BehaviorIR, Digest
from ucf.ir.trust_models import BehaviorDocumentRef

from ._fixture_factory import behavior_pair as _reviewed_behavior_pair

ROOT = Path(__file__).resolve().parents[2]
BEHAVIOR_FIXTURE = ROOT / "tests" / "fixtures" / "ir" / "v1" / "complete.json"


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def _behavior_ref(document: BehaviorIR) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=_digest(canonical_ir_json(document).encode("utf-8")),
    )


def _behavior_pair() -> tuple[BehaviorIR, BehaviorIR]:
    base_payload = json.loads(BEHAVIOR_FIXTURE.read_text(encoding="utf-8"))
    final_payload = deepcopy(base_payload)
    use_case = next(
        entity
        for entity in final_payload["entities"]
        if entity["kind"] == "use_case" and entity["id"] == "use-case.reserve-item"
    )
    use_case["output_ports"][0]["required"] = False
    return (
        parse_ir_json(json.dumps(base_payload)),
        parse_ir_json(json.dumps(final_payload)),
    )


def _artifact(
    path: str,
    role: OpenSpecArtifactRole,
    content: bytes,
    *,
    media_type: str = "text/markdown;charset=utf-8",
) -> OpenSpecArtifact:
    return OpenSpecArtifact(
        kind="openspec_artifact",
        path=path,
        role=role,
        media_type=media_type,
        content_base64=base64.b64encode(content).decode("ascii"),
        byte_digest=_digest(content),
    )


def _proposal(base: BehaviorIR) -> ChangeProposal:
    change_id = "allow-delayed-reservation-id"
    return ChangeProposal(
        kind="change_proposal",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=CHANGE_PROPOSAL_SCHEMA_URI,
        change_id=change_id,
        base_behavior=_behavior_ref(base),
        openspec=OpenSpecManifest(
            kind="openspec_manifest",
            profile=OPENSPEC_INTEROP_PROFILE,
            tested_against_version=OPENSPEC_TESTED_AGAINST_VERSION,
            change_path=f"changes/{change_id}",
            artifacts=(
                _artifact(
                    f"changes/{change_id}/.openspec.yaml",
                    OpenSpecArtifactRole.CHANGE_METADATA,
                    b"schema: spec-driven\n",
                    media_type="application/yaml;charset=utf-8",
                ),
                _artifact(
                    f"changes/{change_id}/proposal.md",
                    OpenSpecArtifactRole.PROPOSAL,
                    b"## Why\n\nReservation identifiers may be delayed.\n",
                ),
                _artifact(
                    f"changes/{change_id}/tasks.md",
                    OpenSpecArtifactRole.TASKS,
                    (
                        b"## 1. Contract\n\n"
                        b"- [ ] 1.1 Review the behavior delta\n"
                        b"- [ ] 1.2 Implement the change\n"
                        b"- [ ] 1.3 Run verification\n"
                    ),
                ),
            ),
        ),
    )


def test_proposal_and_delta_are_closed_canonical_and_exact() -> None:
    base, final = _behavior_pair()
    proposal = _proposal(base)
    validate_change_proposal(proposal, base)

    proposal_json = canonical_change_lifecycle_json(proposal)
    assert parse_change_proposal_json(proposal_json) == proposal
    assert (
        canonical_change_lifecycle_json(parse_change_proposal_json(proposal_json))
        == proposal_json
    )

    delta = derive_behavior_delta(proposal, base, final)
    validate_behavior_delta(delta, proposal, base, final)
    assert delta.proposal == change_proposal_ref(proposal)
    assert delta.base_behavior == _behavior_ref(base)
    assert delta.final_behavior == _behavior_ref(final)
    assert len(delta.entries) == 1
    modified = delta.entries[0]
    assert isinstance(modified, ModifiedBehavior)
    assert modified.base_subject.target_kind.value == "use_case"
    assert modified.base_subject.target_id == "use-case.reserve-item"
    assert modified.final_subject.target_id == "use-case.reserve-item"
    assert modified.aspects == ("definition",)
    assert modified.base_is_root is True
    assert modified.final_is_root is True

    delta_json = canonical_change_lifecycle_json(delta)
    assert parse_behavior_delta_json(delta_json) == delta
    assert (
        canonical_change_lifecycle_json(parse_behavior_delta_json(delta_json))
        == delta_json
    )


def test_proposal_rejects_artifact_role_path_mismatch() -> None:
    base, _ = _behavior_pair()
    payload = _proposal(base).model_dump(mode="json")
    task = next(
        artifact
        for artifact in payload["openspec"]["artifacts"]
        if artifact["role"] == "tasks"
    )
    task["path"] = f"changes/{payload['change_id']}/notes.txt"
    task["media_type"] = "text/plain;charset=utf-8"
    payload["openspec"]["artifacts"].sort(key=lambda artifact: artifact["path"])

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_proposal_rejects_binary_tasks_metadata_before_derivation() -> None:
    base, _ = _behavior_pair()
    payload = _proposal(base).model_dump(mode="json")
    task = next(
        artifact
        for artifact in payload["openspec"]["artifacts"]
        if artifact["role"] == "tasks"
    )
    content = b"\xffbinary-task"
    task["media_type"] = "application/octet-stream"
    task["content_base64"] = base64.b64encode(content).decode("ascii")
    task["byte_digest"]["value"] = hashlib.sha256(content).hexdigest()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_proposal_rejects_artifact_over_decoded_byte_bound() -> None:
    base, _ = _behavior_pair()
    payload = _proposal(base).model_dump(mode="json")
    proposal_artifact = next(
        artifact
        for artifact in payload["openspec"]["artifacts"]
        if artifact["role"] == "proposal"
    )
    content = b"x" * (MAX_OPENSPEC_ARTIFACT_BYTES + 1)
    proposal_artifact["content_base64"] = base64.b64encode(content).decode("ascii")
    proposal_artifact["byte_digest"]["value"] = hashlib.sha256(content).hexdigest()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize(
    ("document", "mutation"),
    [
        ("proposal", "unknown"),
        ("proposal", "version"),
        ("proposal", "schema"),
        ("proposal", "duplicate"),
        ("delta", "unknown"),
        ("delta", "version"),
        ("delta", "schema"),
        ("delta", "duplicate"),
    ],
)
def test_proposal_and_delta_reject_untrusted_json_boundaries(
    document: str,
    mutation: str,
) -> None:
    base, final = _behavior_pair()
    proposal = _proposal(base)
    value: ChangeProposal | BehaviorDelta = (
        proposal
        if document == "proposal"
        else derive_behavior_delta(proposal, base, final)
    )
    payload = value.model_dump(mode="json")
    if mutation == "unknown":
        payload["verified"] = True
    elif mutation == "version":
        payload["change_lifecycle_version"] = "2.0.0"
    elif mutation == "schema":
        payload["schema_uri"] = "urn:ucf:change-lifecycle:unknown:1.0.0"

    parser = (
        parse_change_proposal_json
        if document == "proposal"
        else parse_behavior_delta_json
    )
    if mutation == "duplicate":
        encoded = canonical_change_lifecycle_json(value).decode("utf-8")
        encoded = encoded.replace(
            '"kind":',
            '"kind":"duplicate","kind":',
            1,
        )
        with pytest.raises(ChangeLifecycleValidationError) as captured:
            parser(encoded)
        assert captured.value.code is (ChangeLifecycleErrorCode.DUPLICATE_JSON_MEMBER)
    else:
        with pytest.raises(ChangeLifecycleValidationError) as captured:
            parser(json.dumps(payload))
        assert captured.value.code is (ChangeLifecycleErrorCode.INVALID_STRUCTURE)


def test_delta_context_rejects_stale_or_incomplete_membership() -> None:
    base, final = _behavior_pair()
    proposal = _proposal(base)
    delta = derive_behavior_delta(proposal, base, final)

    wrong_proposal = proposal.model_copy(
        update={
            "base_behavior": proposal.base_behavior.model_copy(
                update={"canonical_digest": _digest(b"wrong")}
            )
        }
    )
    with pytest.raises(ChangeLifecycleValidationError) as stale:
        validate_change_proposal(wrong_proposal, base)
    assert stale.value.code is (ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH)

    incomplete = delta.model_copy(update={"entries": ()})
    with pytest.raises(ChangeLifecycleValidationError) as incomplete_error:
        validate_behavior_delta(incomplete, proposal, base, final)
    assert incomplete_error.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_delta_rejects_typed_behavior_with_a_broken_reference() -> None:
    base, final = _behavior_pair()
    removed_id = final.roots[0].target_id
    broken_final = final.model_copy(
        update={
            "entities": tuple(
                entity for entity in final.entities if entity.id != removed_id
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_behavior_delta(_proposal(base), base, broken_final)

    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE
    assert captured.value.location.startswith("$.final_behavior")


def test_delta_distinguishes_added_removed_and_root_membership_changes() -> None:
    _, reviewed = _reviewed_behavior_pair()
    reviewed_payload = json.loads(canonical_ir_json(reviewed))
    provenance = deepcopy(
        next(
            entity
            for entity in reviewed_payload["entities"]
            if entity["kind"] == "provenance"
        )
    )
    legacy = deepcopy(provenance)
    legacy["id"] = "provenance.lifecycle-legacy"
    replacement = deepcopy(provenance)
    replacement["id"] = "provenance.lifecycle-replacement"

    base_payload = deepcopy(reviewed_payload)
    base_payload["entities"].append(legacy)
    final_payload = deepcopy(reviewed_payload)
    final_payload["entities"].append(replacement)
    base = parse_ir_json(json.dumps(base_payload))
    final = parse_ir_json(json.dumps(final_payload))
    proposal = _proposal(base)

    delta = derive_behavior_delta(proposal, base, final)
    validate_behavior_delta(delta, proposal, base, final)
    assert tuple(type(entry) for entry in delta.entries) == (
        AddedBehavior,
        RemovedBehavior,
    )
    assert delta.entries[0].final_subject.target_id == (
        "provenance.lifecycle-replacement"
    )
    assert delta.entries[1].base_subject.target_id == ("provenance.lifecycle-legacy")

    root_final_payload = deepcopy(reviewed_payload)
    removed_root = root_final_payload["roots"].pop(0)
    root_final = parse_ir_json(json.dumps(root_final_payload))
    root_proposal = _proposal(reviewed)
    root_delta = derive_behavior_delta(
        root_proposal,
        reviewed,
        root_final,
    )
    validate_behavior_delta(
        root_delta,
        root_proposal,
        reviewed,
        root_final,
    )
    assert len(root_delta.entries) == 1
    changed = root_delta.entries[0]
    assert isinstance(changed, ModifiedBehavior)
    assert changed.final_subject.target_id == removed_root["target_id"]
    assert changed.aspects == ("root_membership",)
    assert changed.base_is_root is True
    assert changed.final_is_root is False
