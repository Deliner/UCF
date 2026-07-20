from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ucf.evidence_status import (
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
    assess_verification_evidence,
    canonical_evidence_status_json,
    derive_verification_evidence_assessment_id,
    derive_verification_evidence_envelope_id,
    record_verification_evidence,
)
from ucf.ir.models import Digest

from ._support import (
    EvidenceContext,
    baseline_context,
    changed_environment_context,
    current_assessment_arguments,
    inventory_adapter_context,
    record_arguments,
    recorded_assessment_arguments,
    target_behavior_context,
    target_source_context,
    unrelated_behavior_context,
    unrelated_inventory_context,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "evidence_status" / "v1"
)


def generated_fixtures() -> dict[Path, bytes]:
    recorded = baseline_context()
    envelope = _record(recorded)
    fresh = _assess(envelope, recorded, recorded)
    indeterminate = _assess(envelope, recorded)
    unrelated_inventory = unrelated_inventory_context()
    unrelated_behavior = unrelated_behavior_context()
    target_behavior = target_behavior_context()
    target_source = target_source_context()
    changed_environment = changed_environment_context()
    changed_inventory_adapter = inventory_adapter_context()
    failed_result = baseline_context("failed")
    refreshed_envelope = _record(target_behavior)
    refreshed = _assess(
        refreshed_envelope,
        target_behavior,
        target_behavior,
    )
    positive_documents = {
        Path("positive/envelope.json"): envelope,
        Path("positive/assessment-fresh.json"): fresh,
        Path("positive/assessment-indeterminate.json"): indeterminate,
        Path("positive/assessment-unrelated-inventory-fresh.json"): _assess(
            envelope, recorded, unrelated_inventory
        ),
        Path("positive/assessment-unrelated-behavior-fresh.json"): _assess(
            envelope, recorded, unrelated_behavior
        ),
        Path("positive/assessment-stale-target-behavior.json"): _assess(
            envelope, recorded, target_behavior
        ),
        Path("positive/assessment-stale-target-source-mapping.json"): _assess(
            envelope, recorded, target_source
        ),
        Path("positive/assessment-stale-environment.json"): _assess(
            envelope, recorded, changed_environment
        ),
        Path("positive/assessment-stale-inventory-adapter.json"): _assess(
            envelope, recorded, changed_inventory_adapter
        ),
        Path("positive/assessment-stale-failed-result.json"): _assess(
            envelope, recorded, failed_result
        ),
        Path("positive/refreshed-envelope.json"): refreshed_envelope,
        Path("positive/refreshed-assessment-fresh.json"): refreshed,
    }
    positive = {
        path: canonical_evidence_status_json(document)
        for path, document in positive_documents.items()
    }

    envelope_payload = envelope.model_dump(mode="json")
    fresh_payload = fresh.model_dump(mode="json")
    stale_source = positive_documents[
        Path("positive/assessment-stale-target-source-mapping.json")
    ]
    stale_source_payload = stale_source.model_dump(mode="json")

    structural = _structural_negative_fixtures(
        envelope_payload=envelope_payload,
        envelope_bytes=positive[Path("positive/envelope.json")],
        fresh_payload=fresh_payload,
        fresh_bytes=positive[Path("positive/assessment-fresh.json")],
        stale_source_payload=stale_source_payload,
    )
    contextual = _contextual_negative_fixtures(
        envelope=envelope,
        fresh=fresh,
    )
    return {**positive, **structural, **contextual}


def _structural_negative_fixtures(
    *,
    envelope_payload: dict[str, object],
    envelope_bytes: bytes,
    fresh_payload: dict[str, object],
    fresh_bytes: bytes,
    stale_source_payload: dict[str, object],
) -> dict[Path, bytes]:
    unknown_envelope_root = _clone(envelope_payload)
    unknown_envelope_root["transport"] = "http"
    _identify_payload("envelope", unknown_envelope_root)

    unknown_envelope_nested = _clone(envelope_payload)
    unknown_envelope_nested["verification_result"]["framework"] = "spring"
    _identify_payload("envelope", unknown_envelope_nested)

    unknown_assessment_root = _clone(fresh_payload)
    unknown_assessment_root["future"] = True
    _identify_payload("assessment", unknown_assessment_root)

    unknown_assessment_nested = _clone(stale_source_payload)
    unknown_assessment_nested["reasons"][0]["transport"] = "event"
    _identify_payload("assessment", unknown_assessment_nested)

    unsupported_envelope_version = _clone(envelope_payload)
    unsupported_envelope_version["evidence_status_version"] = "2.0.0"
    _identify_payload("envelope", unsupported_envelope_version)

    wrong_envelope_schema = _clone(envelope_payload)
    wrong_envelope_schema["schema_uri"] = "urn:ucf:evidence-status:envelope:2.0.0"
    _identify_payload("envelope", wrong_envelope_schema)

    unsupported_result_ref_version = _clone(envelope_payload)
    unsupported_result_ref_version["verification_result"]["schema_version"] = "2.0.0"
    _identify_payload("envelope", unsupported_result_ref_version)

    wrong_mapping_ref_schema = _clone(envelope_payload)
    wrong_mapping_ref_schema["trace"]["mapping"]["schema_uri"] = (
        "urn:ucf:adapter:implementation-mapping-result:2.0.0"
    )
    _identify_payload("envelope", wrong_mapping_ref_schema)

    unsupported_assessment_version = _clone(fresh_payload)
    unsupported_assessment_version["evidence_status_version"] = "2.0.0"
    _identify_payload("assessment", unsupported_assessment_version)

    wrong_assessment_schema = _clone(fresh_payload)
    wrong_assessment_schema["schema_uri"] = "urn:ucf:evidence-status:assessment:2.0.0"
    _identify_payload("assessment", wrong_assessment_schema)

    unsupported_envelope_ref_version = _clone(fresh_payload)
    unsupported_envelope_ref_version["envelope"]["schema_version"] = "2.0.0"
    _identify_payload("assessment", unsupported_envelope_ref_version)

    wrong_envelope_ref_schema = _clone(fresh_payload)
    wrong_envelope_ref_schema["envelope"]["schema_uri"] = (
        "urn:ucf:evidence-status:envelope:2.0.0"
    )
    _identify_payload("assessment", wrong_envelope_ref_schema)

    duplicate_projection_member = _clone(envelope_payload)
    behavior = duplicate_projection_member["recorded"]["behavior"]
    behavior["members"][1] = _clone(behavior["members"][0])
    _identify_projection(behavior)
    _identify_payload("envelope", duplicate_projection_member)

    noncanonical_projection_members = _clone(envelope_payload)
    behavior = noncanonical_projection_members["recorded"]["behavior"]
    behavior["members"].reverse()
    _identify_projection(behavior)
    _identify_payload("envelope", noncanonical_projection_members)

    projection_digest_mismatch = _clone(envelope_payload)
    projection_digest_mismatch["recorded"]["source"]["digest"] = _digest("f")
    _identify_payload("envelope", projection_digest_mismatch)

    envelope_id_mismatch = _clone(envelope_payload)
    envelope_id_mismatch["id"] = f"envelope.{'f' * 64}"

    assessment_id_mismatch = _clone(fresh_payload)
    assessment_id_mismatch["id"] = f"assessment.{'f' * 64}"

    duplicate_reasons = _clone(stale_source_payload)
    duplicate_reasons["reasons"][1] = _clone(duplicate_reasons["reasons"][0])
    _identify_payload("assessment", duplicate_reasons)

    noncanonical_reasons = _clone(stale_source_payload)
    noncanonical_reasons["reasons"].reverse()
    _identify_payload("assessment", noncanonical_reasons)

    invalid_reason_shape = _clone(stale_source_payload)
    invalid_reason_shape["reasons"][0]["recorded"] = None
    _identify_payload("assessment", invalid_reason_shape)

    return {
        Path("invalid/duplicate-json-member-envelope.json"): _duplicate_member(
            envelope_bytes,
            b'"evidence_status_version":"1.0.0",',
        ),
        Path("invalid/duplicate-json-member-assessment.json"): _duplicate_member(
            fresh_bytes,
            b'"evidence_status_version":"1.0.0",',
        ),
        Path("invalid/unknown-envelope-root-field.json"): _canonical(
            unknown_envelope_root
        ),
        Path("invalid/unknown-envelope-nested-field.json"): _canonical(
            unknown_envelope_nested
        ),
        Path("invalid/unknown-assessment-root-field.json"): _canonical(
            unknown_assessment_root
        ),
        Path("invalid/unknown-assessment-nested-field.json"): _canonical(
            unknown_assessment_nested
        ),
        Path("invalid/unsupported-envelope-version.json"): _canonical(
            unsupported_envelope_version
        ),
        Path("invalid/wrong-envelope-schema-uri.json"): _canonical(
            wrong_envelope_schema
        ),
        Path("invalid/unsupported-result-ref-version.json"): _canonical(
            unsupported_result_ref_version
        ),
        Path("invalid/wrong-mapping-ref-schema-uri.json"): _canonical(
            wrong_mapping_ref_schema
        ),
        Path("invalid/unsupported-assessment-version.json"): _canonical(
            unsupported_assessment_version
        ),
        Path("invalid/wrong-assessment-schema-uri.json"): _canonical(
            wrong_assessment_schema
        ),
        Path("invalid/unsupported-envelope-ref-version.json"): _canonical(
            unsupported_envelope_ref_version
        ),
        Path("invalid/wrong-envelope-ref-schema-uri.json"): _canonical(
            wrong_envelope_ref_schema
        ),
        Path("invalid/duplicate-projection-member.json"): _canonical(
            duplicate_projection_member
        ),
        Path("invalid/noncanonical-projection-member-order.json"): _canonical(
            noncanonical_projection_members
        ),
        Path("invalid/projection-digest-mismatch.json"): _canonical(
            projection_digest_mismatch
        ),
        Path("invalid/envelope-id-mismatch.json"): _canonical(envelope_id_mismatch),
        Path("invalid/assessment-id-mismatch.json"): _canonical(assessment_id_mismatch),
        Path("invalid/duplicate-reason.json"): _canonical(duplicate_reasons),
        Path("invalid/noncanonical-reason-order.json"): _canonical(
            noncanonical_reasons
        ),
        Path("invalid/reason-shape.json"): _canonical(invalid_reason_shape),
    }


def _contextual_negative_fixtures(
    *,
    envelope: VerificationEvidenceEnvelope,
    fresh: VerificationEvidenceAssessment,
) -> dict[Path, bytes]:
    forged_result = envelope.model_copy(
        update={
            "verification_result": envelope.verification_result.model_copy(
                update={
                    "target_id": f"result.{'f' * 64}",
                    "canonical_digest": _digest_model("f"),
                }
            )
        }
    )
    forged_mapping = envelope.model_copy(
        update={
            "trace": envelope.trace.model_copy(
                update={
                    "mapping": envelope.trace.mapping.model_copy(
                        update={
                            "target_id": f"mapping.{'f' * 64}",
                            "canonical_digest": _digest_model("f"),
                        }
                    )
                }
            )
        }
    )
    forged_claim = envelope.model_copy(
        update={
            "claim": envelope.claim.model_copy(
                update={
                    "target_id": f"claim.tested.{'f' * 64}",
                    "canonical_digest": _digest_model("f"),
                }
            )
        }
    )
    forged_assessment_envelope = fresh.model_copy(
        update={
            "envelope": fresh.envelope.model_copy(
                update={
                    "target_id": f"envelope.{'f' * 64}",
                    "canonical_digest": _digest_model("f"),
                }
            )
        }
    )
    contextual_documents = {
        Path("invalid-context/forged-result-ref.json"): _reidentify_envelope(
            forged_result
        ),
        Path("invalid-context/forged-mapping-ref.json"): _reidentify_envelope(
            forged_mapping
        ),
        Path("invalid-context/forged-claim-ref.json"): _reidentify_envelope(
            forged_claim
        ),
        Path(
            "invalid-context/forged-assessment-envelope-ref.json"
        ): _reidentify_assessment(forged_assessment_envelope),
        Path("invalid-context/replayed-fresh-target-source.json"): fresh,
    }
    return {
        path: canonical_evidence_status_json(document)
        for path, document in contextual_documents.items()
    }


def _record(context: EvidenceContext) -> VerificationEvidenceEnvelope:
    return record_verification_evidence(
        context.result,
        **record_arguments(context),
    )


def _assess(
    envelope: VerificationEvidenceEnvelope,
    recorded: EvidenceContext,
    current: EvidenceContext | None = None,
) -> VerificationEvidenceAssessment:
    current_arguments = {} if current is None else current_assessment_arguments(current)
    return assess_verification_evidence(
        envelope,
        **recorded_assessment_arguments(recorded),
        **current_arguments,
    )


def _reidentify_envelope(
    document: VerificationEvidenceEnvelope,
) -> VerificationEvidenceEnvelope:
    return document.model_copy(
        update={"id": derive_verification_evidence_envelope_id(document)}
    )


def _reidentify_assessment(
    document: VerificationEvidenceAssessment,
) -> VerificationEvidenceAssessment:
    return document.model_copy(
        update={"id": derive_verification_evidence_assessment_id(document)}
    )


def _identify_projection(projection: dict[str, object]) -> None:
    projection["digest"] = _document_digest(
        {key: value for key, value in projection.items() if key != "digest"}
    )


def _identify_payload(prefix: str, payload: dict[str, object]) -> None:
    identity = {key: value for key, value in payload.items() if key != "id"}
    payload["id"] = f"{prefix}." + hashlib.sha256(_canonical(identity)).hexdigest()


def _document_digest(payload: object) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": hashlib.sha256(_canonical(payload)).hexdigest(),
    }


def _digest(fill: str) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": fill * 64,
    }


def _digest_model(fill: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=fill * 64,
    )


def _duplicate_member(payload: bytes, member: bytes) -> bytes:
    if member not in payload:
        raise AssertionError("duplicate-member fixture target is absent")
    return payload.replace(member, member + member, 1)


def _clone(value):
    return json.loads(json.dumps(value))


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check evidence-status wire fixtures."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _parse_args(arguments)
    expected = {
        options.output_directory / path: content
        for path, content in generated_fixtures().items()
    }
    if options.check:
        actual = {
            path
            for path in options.output_directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        stale = sorted(
            {
                path
                for path, content in expected.items()
                if path.is_symlink()
                or not path.is_file()
                or path.read_bytes() != content
            }
            | (actual - set(expected))
        )
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    options.output_directory.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
