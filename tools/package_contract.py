from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

if __package__:
    from .go_stdlib_adapter_contract import (
        GO_STDLIB_UPSTREAM_NOTICE_DIGESTS,
        copy_go_stdlib_adapter,
        copy_go_stdlib_fixture,
        go_stdlib_adapter_manifest,
        go_stdlib_fixture_manifest,
    )
    from .go_stdlib_adapter_contract import (
        SourceContractError as GoSourceContractError,
    )
    from .go_stdlib_platform_contract import (
        GO_STDLIB_PLATFORM_BINARY_SHA256,
        GO_STDLIB_PLATFORM_SOURCE_REVISION,
        copy_go_stdlib_platform_fixture,
        go_stdlib_platform_manifest,
        go_stdlib_platform_source_revision,
        validate_go_stdlib_platform_build_metadata,
    )
    from .go_stdlib_toolchain import (
        GO_STDLIB_VERSION_OUTPUT,
        GoStdlibToolchainError,
        resolve_go_stdlib_binary,
    )
    from .typescript_fastify_adapter_contract import (
        SourceContractError,
        SourceManifest,
        copy_typescript_fastify_adapter,
        copy_typescript_fastify_fixture,
        typescript_fastify_adapter_manifest,
        typescript_fastify_fixture_manifest,
    )
else:
    from go_stdlib_adapter_contract import (
        GO_STDLIB_UPSTREAM_NOTICE_DIGESTS,
        copy_go_stdlib_adapter,
        copy_go_stdlib_fixture,
        go_stdlib_adapter_manifest,
        go_stdlib_fixture_manifest,
    )
    from go_stdlib_adapter_contract import (
        SourceContractError as GoSourceContractError,
    )
    from go_stdlib_platform_contract import (
        GO_STDLIB_PLATFORM_BINARY_SHA256,
        GO_STDLIB_PLATFORM_SOURCE_REVISION,
        copy_go_stdlib_platform_fixture,
        go_stdlib_platform_manifest,
        go_stdlib_platform_source_revision,
        validate_go_stdlib_platform_build_metadata,
    )
    from go_stdlib_toolchain import (
        GO_STDLIB_VERSION_OUTPUT,
        GoStdlibToolchainError,
        resolve_go_stdlib_binary,
    )
    from typescript_fastify_adapter_contract import (
        SourceContractError,
        SourceManifest,
        copy_typescript_fastify_adapter,
        copy_typescript_fastify_fixture,
        typescript_fastify_adapter_manifest,
        typescript_fastify_fixture_manifest,
    )

EXPECTED_CONFORMANCE_KIT_ASSETS = {
    "ucf/adapter_conformance/assets/v1/fixtures/cancel-noop.json",
    "ucf/adapter_conformance/assets/v1/fixtures/capability-gate.json",
    "ucf/adapter_conformance/assets/v1/fixtures/duplicate-capability.json",
    "ucf/adapter_conformance/assets/v1/fixtures/duplicate-json-member.json",
    "ucf/adapter_conformance/assets/v1/fixtures/duplicate-request-id.json",
    "ucf/adapter_conformance/assets/v1/fixtures/incompatible-version.json",
    "ucf/adapter_conformance/assets/v1/fixtures/initialize-shutdown.json",
    "ucf/adapter_conformance/assets/v1/fixtures/invalid-message.json",
    "ucf/adapter_conformance/assets/v1/fixtures/invalid-params.json",
    "ucf/adapter_conformance/assets/v1/fixtures/lifecycle.json",
    "ucf/adapter_conformance/assets/v1/fixtures/operation-families.json",
    "ucf/adapter_conformance/assets/v1/fixtures/optional-capability.json",
    "ucf/adapter_conformance/assets/v1/fixtures/parse-error.json",
    "ucf/adapter_conformance/assets/v1/fixtures/shutdown-pending.json",
    "ucf/adapter_conformance/assets/v1/fixtures/targeted-cancellation.json",
    "ucf/adapter_conformance/assets/v1/fixtures/unknown-method.json",
    "ucf/adapter_conformance/assets/v1/fixtures/unsupported-required.json",
    "ucf/adapter_conformance/assets/v1/manifest.json",
    "ucf/adapter_conformance/assets/v1/samples/reference_adapter.mjs",
}
EXPECTED_SCHEMA_ASSETS = {
    "ucf/schemas/adapter_conformance/v1/schema.json",
    "ucf/schemas/adapter_protocol/v1/schema.json",
    "ucf/schemas/change_governance/v1/decision-assessment.schema.json",
    "ucf/schemas/change_governance/v1/decision-declaration.schema.json",
    "ucf/schemas/change_governance/v1/gate-evaluation.schema.json",
    "ucf/schemas/change_governance/v1/impact-report.schema.json",
    "ucf/schemas/change_lifecycle/v1/archive-record.schema.json",
    "ucf/schemas/change_lifecycle/v1/behavior-delta.schema.json",
    "ucf/schemas/change_lifecycle/v1/implementation-record.schema.json",
    "ucf/schemas/change_lifecycle/v1/proposal.schema.json",
    "ucf/schemas/change_lifecycle/v1/task-graph.schema.json",
    "ucf/schemas/change_lifecycle/v1/verification-record.schema.json",
    "ucf/schemas/evidence_status/v1/assessment.schema.json",
    "ucf/schemas/evidence_status/v1/envelope.schema.json",
    "ucf/schemas/generation/v1/request.schema.json",
    "ucf/schemas/generation/v1/result.schema.json",
    "ucf/schemas/inventory/v1/page.schema.json",
    "ucf/schemas/inventory/v1/request.schema.json",
    "ucf/schemas/inventory/v1/schema.json",
    "ucf/schemas/implementation_evidence/v1/mapping-request.schema.json",
    "ucf/schemas/implementation_evidence/v1/mapping-result.schema.json",
    "ucf/schemas/implementation_evidence/v1/verification-request.schema.json",
    "ucf/schemas/implementation_evidence/v1/verification-result.schema.json",
    "ucf/schemas/ir/v1/schema.json",
    "ucf/schemas/onboarding/v1/bundle.schema.json",
    "ucf/schemas/onboarding/v1/decision-set.schema.json",
    "ucf/schemas/onboarding/v1/discovery-request.schema.json",
    "ucf/schemas/onboarding/v1/discovery-result.schema.json",
    "ucf/schemas/ratchet/v1/assessment.schema.json",
    "ucf/schemas/ratchet/v1/baseline.schema.json",
    "ucf/schemas/ratchet/v1/evaluation-report.schema.json",
    "ucf/schemas/ratchet/v1/policy.schema.json",
    "ucf/schemas/ratchet/v2/assessment.schema.json",
    "ucf/schemas/ratchet/v2/baseline.schema.json",
    "ucf/schemas/ratchet/v2/evaluation-report.schema.json",
    "ucf/schemas/ratchet/v2/policy.schema.json",
    "ucf/schemas/runtime_evidence/v1/environment.schema.json",
    "ucf/schemas/runtime_evidence/v1/policy.schema.json",
    "ucf/schemas/runtime_evidence/v1/request.schema.json",
    "ucf/schemas/runtime_evidence/v1/result.schema.json",
    "ucf/schemas/spec/v1/schema.json",
    "ucf/schemas/trust/v1/schema.json",
}
EXPECTED_WHEEL_ASSETS = (
    {
        "ucf/generator/templates/impl_stub.py.j2",
        "ucf/generator/templates/interface.py.j2",
        "ucf/generator/templates/orchestrator.py.j2",
    }
    | EXPECTED_SCHEMA_ASSETS
    | EXPECTED_CONFORMANCE_KIT_ASSETS
)

TYPESCRIPT_FASTIFY_ADAPTER_NAME = "@ucf/typescript-fastify-adapter"
TYPESCRIPT_FASTIFY_ADAPTER_VERSION = "1.0.0"
TYPESCRIPT_FASTIFY_ADAPTER_BIN = "ucf-typescript-fastify-adapter"
TYPESCRIPT_FASTIFY_NODE_VERSION = "v22.22.3"
TYPESCRIPT_FASTIFY_NPM_VERSION = "10.9.8"
MAX_TYPESCRIPT_FASTIFY_TARBALL_BYTES = 2 * 1024 * 1024
MAX_INSTALLED_RATCHET_DOCUMENT_BYTES = 1024 * 1024
MAX_INSTALLED_REL001_EVIDENCE_BYTES = 16 * 1024 * 1024
REL001_LANE_EVIDENCE_KEYS = frozenset(
    {
        "kind",
        "evidence_version",
        "lane",
        "status",
        "source",
        "deterministic",
        "runtime",
        "metrics",
    }
)
REL001_DETERMINISTIC_EVIDENCE_KEYS = frozenset(
    {
        "inventory",
        "discovery",
        "decisions",
        "bundle",
        "mapping",
        "verification_requests",
    }
)
REL001_RUNTIME_EVIDENCE_KEYS = frozenset(
    {"verification_results", "successor_behaviors", "tested_trust"}
)
REL001_METRIC_KEYS = frozenset(
    {
        "inventory_record_count",
        "candidate_count",
        "dispositions",
        "eligible_interface_count",
        "uncovered_interface_count",
        "materialization_count",
        "mapping_binding_count",
        "tested_claim_count",
        "verified_claim_count",
        "verification_evidence_count",
        "transports",
    }
)
GO_STDLIB_BUILD_FLAGS = (
    "-mod=readonly",
    "-trimpath",
    "-buildvcs=false",
    "-ldflags=-buildid=",
)
GO_STDLIB_SUBJECT_URI = "urn:ucf:repository:go-stdlib-legacy-quote"
GO_STDLIB_SOURCE_REVISION = (
    "8c95d059aef410657d42e4544d34935c5f422efa9394f1242ee858e02a1c3ff8"
)
GO_STDLIB_NOTICE_DIGESTS = {
    PurePosixPath(relative).name: digest
    for relative, digest in GO_STDLIB_UPSTREAM_NOTICE_DIGESTS.items()
}

MINIMAL_SPEC = """\
kind: action
metadata:
  name: smoke-action
"""
MINIMAL_IR = """\
{
  "kind": "behavior_ir",
  "ir_version": "1.0.0",
  "document_id": "document.installed-smoke",
  "roots": [],
  "entities": []
}
"""
MINIMAL_TRUST_IR = """\
{
  "kind": "trust_ir",
  "trust_ir_version": "1.0.0",
  "document_id": "document.installed-trust-smoke",
  "subject_document": {
    "kind": "behavior_document_ref",
    "document_id": "document.installed-smoke",
    "ir_version": "1.0.0",
    "canonical_digest": {
      "kind": "digest",
      "algorithm": "sha-256",
      "value": "02161d0ad001bc08979cad27f909d69da360e793f1da4b516fb6c81445707327"
    }
  },
  "records": []
}
"""

INSTALLED_ONBOARDING_REVIEW = """\
import json
import sys
from pathlib import Path

from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateProposal,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    EditedDecision,
    RejectedDecision,
    UncertainDecision,
    canonical_onboarding_digest,
    canonical_onboarding_json,
    derive_candidate_semantic_digest,
    derive_decision_id,
    parse_discovery_result_json,
    validate_decision_set,
)

discovery_path = Path(sys.argv[1])
decision_path = Path(sys.argv[2])
discovery = parse_discovery_result_json(discovery_path.read_bytes())
discovery_digest = canonical_onboarding_digest(discovery)
base = DecisionSet(
    kind="decision_set_profile",
    onboarding_version=ONBOARDING_VERSION,
    schema_uri=DECISION_SET_SCHEMA_URI,
    discovery=DiscoveryDocumentRef(
        kind="discovery_document_ref",
        schema_uri=discovery.schema_uri,
        schema_version=discovery.onboarding_version,
        canonical_digest=discovery_digest,
    ),
    inventory_binding=discovery.inventory_binding,
    reviewer=Producer(
        kind="producer",
        name="org.ucf.installed-smoke-reviewer",
        version="1.0.0",
    ),
    capture_context=CaptureContext(
        kind="capture_context",
        captured_at="2026-07-19T12:00:00Z",
        environment=Digest(
            kind="digest",
            algorithm="sha-256",
            value="a" * 64,
        ),
    ),
    decisions=(),
)
provisional = []
for candidate in discovery.candidates:
    reference = CandidateRef(
        kind="candidate_ref",
        discovery_digest=discovery_digest,
        candidate_id=candidate.id,
        semantic_digest=candidate.semantic_digest,
    )
    common = {
        "id": "decision." + ("0" * 64),
        "candidate": reference,
    }
    root = candidate.proposal.root.target_id
    if root.endswith("quote-order"):
        decision = AcceptedDecision(
            kind="accepted_decision",
            reason="Matches the unchanged native behavior checks.",
            **common,
        )
    elif root.endswith("format-receipt"):
        serialized = json.dumps(
            candidate.proposal.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        replacement = CandidateProposal.model_validate_json(
            serialized.replace("format-receipt", "render-receipt")
        )
        decision = EditedDecision(
            kind="edited_decision",
            reason="Use the reviewed product vocabulary.",
            replacement_digest=derive_candidate_semantic_digest(replacement),
            replacement=replacement,
            **common,
        )
    elif root.endswith("normalize-coupon"):
        decision = RejectedDecision(
            kind="rejected_decision",
            reason="Internal helper, not reviewed product behavior.",
            **common,
        )
    else:
        decision = UncertainDecision(
            kind="uncertain_decision",
            reason="No executable check establishes intended semantics.",
            **common,
        )
    provisional.append(
        decision.model_copy(update={"id": derive_decision_id(decision, base)})
    )
decisions = base.model_copy(
    update={
        "decisions": tuple(
            sorted(
                provisional,
                key=lambda item: item.candidate.candidate_id,
            )
        )
    }
)
validate_decision_set(discovery, decisions)
decision_path.write_bytes(canonical_onboarding_json(decisions))
"""

INSTALLED_ONBOARDING_ASSERT = """\
import sys
from pathlib import Path

from ucf.ir import ClaimLevel
from ucf.onboarding import (
    DispositionKind,
    canonical_onboarding_json,
    parse_onboarding_bundle_json,
)

first_path = Path(sys.argv[1])
second_path = Path(sys.argv[2])
if first_path.read_bytes() != second_path.read_bytes():
    raise SystemExit("installed onboarding bundles differ")
bundle = parse_onboarding_bundle_json(first_path.read_bytes())
if canonical_onboarding_json(bundle) != first_path.read_bytes():
    raise SystemExit("installed onboarding bundle is not canonical")
dispositions = {
    summary.disposition: summary.candidate_ids
    for summary in bundle.baseline.dispositions
}
if set(dispositions) != set(DispositionKind):
    raise SystemExit("installed onboarding dispositions are incomplete")
if not all(len(dispositions[kind]) == 1 for kind in DispositionKind):
    raise SystemExit("installed onboarding dispositions are not distinguishable")
claims = {
    summary.level: summary.claim_ids
    for summary in bundle.baseline.claim_levels
}
for level in (ClaimLevel.MAPPED, ClaimLevel.TESTED, ClaimLevel.VERIFIED):
    if claims[level]:
        raise SystemExit(f"installed onboarding promoted {level.value}")
"""

INSTALLED_RATCHET_AUTHOR = """\
import sys
from pathlib import Path

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import Digest, EntityKind, Producer
from ucf.onboarding import CaptureContext, parse_onboarding_bundle_json
from ucf.ratchet import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorSubjectKey,
    RatchetPolicy,
    RatchetRule,
    ViolationInput,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_policy_id,
)

bundle = parse_onboarding_bundle_json(Path(sys.argv[1]).read_bytes())
rule = RatchetRule(
    kind="ratchet_rule",
    id="rule.missing-tested-evidence",
    version="1.0.0",
    procedure_uri="urn:ucf:ratchet-rule:missing-tested-evidence:1.0.0",
    producer=Producer(
        kind="producer",
        name="org.ucf.installed-smoke-rules",
        version="1.0.0",
    ),
    summary="Require one named tested-evidence check.",
)
provisional = RatchetPolicy(
    kind="ratchet_policy",
    ratchet_version=RATCHET_VERSION,
    schema_uri=RATCHET_POLICY_SCHEMA_URI,
    id="policy." + ("0" * 64),
    evaluator=CapabilitySelection(
        kind="capability",
        name=RATCHET_EVALUATOR_CAPABILITY,
        version=RATCHET_VERSION,
    ),
    rules=(rule,),
)
policy = provisional.model_copy(
    update={"id": derive_policy_id(provisional)}
)
subject = BehaviorSubjectKey(
    kind="behavior_subject_key",
    subject_uri=bundle.inventory.subject_uri,
    target_kind=EntityKind.USE_CASE,
    target_id="use-case.quote-order",
)
producer = Producer(
    kind="producer",
    name="org.ucf.installed-smoke-assessor",
    version="1.0.0",
)
capture_context = CaptureContext(
    kind="capture_context",
    captured_at="2026-07-19T13:00:00Z",
    environment=Digest(
        kind="digest",
        algorithm="sha-256",
        value="c" * 64,
    ),
)

def assessment(*slots):
    return build_ratchet_assessment(
        policy,
        bundle,
        producer=producer,
        procedure_uri="urn:ucf:ratchet-assessment:installed-smoke:1.0.0",
        capture_context=capture_context,
        violations=tuple(
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=rule.id,
                subject=subject,
                slot=slot,
                message=f"Installed smoke violation at {slot}.",
            )
            for slot in slots
        ),
    )

Path(sys.argv[2]).write_bytes(canonical_ratchet_json(policy))
Path(sys.argv[3]).write_bytes(
    canonical_ratchet_json(assessment("required-check"))
)
Path(sys.argv[4]).write_bytes(canonical_ratchet_json(assessment()))
Path(sys.argv[5]).write_bytes(
    canonical_ratchet_json(
        assessment("required-check", "second-check")
    )
)
"""

INSTALLED_RATCHET_ASSERT = """\
import sys
from pathlib import Path

from ucf.ratchet import (
    EvaluationOutcome,
    canonical_ratchet_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
)

baseline_path = Path(sys.argv[1])
pass_report_path = Path(sys.argv[2])
regression_report_path = Path(sys.argv[3])
successor_path = Path(sys.argv[4])
reintroduced_report_path = Path(sys.argv[5])
baseline = parse_ratchet_baseline_json(baseline_path.read_bytes())
pass_report = parse_ratchet_evaluation_report_json(
    pass_report_path.read_bytes()
)
regression = parse_ratchet_evaluation_report_json(
    regression_report_path.read_bytes()
)
successor = parse_ratchet_baseline_json(successor_path.read_bytes())
reintroduced = parse_ratchet_evaluation_report_json(
    reintroduced_report_path.read_bytes()
)
for path, document in (
    (baseline_path, baseline),
    (pass_report_path, pass_report),
    (regression_report_path, regression),
    (successor_path, successor),
    (reintroduced_report_path, reintroduced),
):
    if path.read_bytes() != canonical_ratchet_json(document):
        raise SystemExit(f"installed ratchet output is not canonical: {path}")
if pass_report.outcome is not EvaluationOutcome.PASS:
    raise SystemExit("unchanged installed legacy debt did not pass")
if regression.outcome is not EvaluationOutcome.FAIL:
    raise SystemExit("installed ratchet regression did not fail")
if not regression.weakening_delta.added_allowances:
    raise SystemExit("installed regression did not expose its allowance delta")
if successor.predecessor is None or successor.predecessor.target_id != baseline.id:
    raise SystemExit("installed successor does not bind its exact predecessor")
if successor.allowances or not successor.protected:
    raise SystemExit("installed successor did not protect the improvement")
if reintroduced.outcome is not EvaluationOutcome.FAIL:
    raise SystemExit("installed protected resolution did not block reintroduction")
"""

INSTALLED_RATCHET_V2_AUTHOR = """\
import sys
from pathlib import Path

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import Producer
from ucf.onboarding import parse_onboarding_bundle_json
from ucf.ratchet import parse_ratchet_policy_json as parse_v1_policy_json
from ucf.ratchet.v2 import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetPolicy,
    RatchetRule,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_policy_id,
)

bundle_path = Path(sys.argv[1])
source_policy_path = Path(sys.argv[2])
target_policy_path = Path(sys.argv[3])
assessment_path = Path(sys.argv[4])
bundle = parse_onboarding_bundle_json(bundle_path.read_bytes())
source_policy = parse_v1_policy_json(source_policy_path.read_bytes())
rules = tuple(
    RatchetRule.model_validate_json(rule.model_dump_json())
    for rule in source_policy.rules
)
provisional = RatchetPolicy(
    kind="ratchet_policy",
    ratchet_version=RATCHET_VERSION,
    schema_uri=RATCHET_POLICY_SCHEMA_URI,
    id="policy." + ("0" * 64),
    evaluator=CapabilitySelection(
        kind="capability",
        name=RATCHET_EVALUATOR_CAPABILITY,
        version=RATCHET_VERSION,
    ),
    rules=rules,
)
policy = provisional.model_copy(
    update={"id": derive_policy_id(provisional)}
)
assessment = build_ratchet_assessment(
    policy,
    bundle,
    producer=Producer(
        kind="producer",
        name="org.ucf.installed-smoke-assessor",
        version="2.0.0",
    ),
    procedure_uri="urn:ucf:ratchet-assessment:installed-smoke:2.0.0",
    capture_context=bundle.capture_context,
)
target_policy_path.write_bytes(canonical_ratchet_json(policy))
assessment_path.write_bytes(canonical_ratchet_json(assessment))
"""

INSTALLED_RATCHET_V2_ASSERT = """\
import stat
import sys
from pathlib import Path

from ucf.ratchet import (
    canonical_ratchet_json as canonical_v1_ratchet_json,
    parse_ratchet_baseline_json as parse_v1_baseline_json,
)
from ucf.ratchet.v2 import (
    CombinedOutcome,
    RatchetBaselineOrigin,
    canonical_ratchet_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
)

MAX_DOCUMENT_BYTES = 1024 * 1024

def read_bounded(path):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise SystemExit(f"installed ratchet v2 output is not regular: {path}")
    with path.open("rb") as stream:
        payload = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise SystemExit(f"installed ratchet v2 output is oversized: {path}")
    return payload

source_path = Path(sys.argv[1])
baseline_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])
successor_path = Path(sys.argv[4])
migrated_path = Path(sys.argv[5])
source = parse_v1_baseline_json(read_bounded(source_path))
baseline = parse_ratchet_baseline_json(read_bounded(baseline_path))
report = parse_ratchet_evaluation_report_json(read_bounded(report_path))
successor = parse_ratchet_baseline_json(read_bounded(successor_path))
migrated = parse_ratchet_baseline_json(read_bounded(migrated_path))

if read_bounded(source_path) != canonical_v1_ratchet_json(source):
    raise SystemExit("installed Ratchet v1 migration source is not canonical")
for path, document in (
    (baseline_path, baseline),
    (report_path, report),
    (successor_path, successor),
    (migrated_path, migrated),
):
    if read_bounded(path) != canonical_ratchet_json(document):
        raise SystemExit(f"installed Ratchet v2 output is not canonical: {path}")
if baseline.origin is not RatchetBaselineOrigin.INITIAL or baseline.generation != 0:
    raise SystemExit("installed Ratchet v2 establish has invalid lineage")
if report.baseline.target_id != baseline.id:
    raise SystemExit("installed Ratchet v2 report lost the accepted baseline ID")
if report.combined_outcome is not CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT:
    raise SystemExit("unchanged installed Ratchet v2 debt did not qualify its pass")
if (
    successor.origin is not RatchetBaselineOrigin.SUCCESSOR
    or successor.generation != baseline.generation + 1
    or successor.predecessor is None
    or successor.predecessor.target_id != baseline.id
    or successor.source_evaluation is None
    or successor.source_evaluation.target_id != report.id
):
    raise SystemExit("installed Ratchet v2 successor has invalid lineage")
if (
    migrated.origin is not RatchetBaselineOrigin.MIGRATED_V1
    or migrated.generation != source.generation
    or migrated.migrated_from is None
    or migrated.migrated_from.baseline.target_id != source.id
):
    raise SystemExit("installed v1-to-v2 migration has invalid lineage")
if len(migrated.behavior.allowances) != len(source.allowances):
    raise SystemExit("installed v1-to-v2 migration lost behavior debt")
if not migrated.coverage.allowances:
    raise SystemExit("installed v1-to-v2 migration lost uncertain coverage debt")
"""

INSTALLED_RUNTIME_EVIDENCE_ASSERT = """\
import hashlib
import sys
from pathlib import Path

from ucf.ir import canonical_trust_ir_json, parse_ir_json
from ucf.ir.trust_models import ObservedFact, SourceRecord
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_CAPABILITY,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEvidenceAcceptedResult,
    canonical_runtime_evidence_json,
    parse_runtime_environment_json,
    parse_runtime_evidence_result_json,
    project_runtime_evidence_to_trust,
)

result_path = Path(sys.argv[1])
behavior_path = Path(sys.argv[2])
environment_path = Path(sys.argv[3])
recording_path = Path(sys.argv[4])
result = parse_runtime_evidence_result_json(result_path.read_bytes())
if not isinstance(result, RuntimeEvidenceAcceptedResult):
    raise SystemExit("installed runtime evidence was not accepted")
if result_path.read_bytes() != canonical_runtime_evidence_json(result):
    raise SystemExit("installed runtime evidence result is not canonical")
if (
    result.capability.name != RUNTIME_EVIDENCE_CAPABILITY
    or result.capability.version != RUNTIME_EVIDENCE_VERSION
):
    raise SystemExit("installed runtime evidence capability is not exact")
if result.request.sampling.completeness != "partial":
    raise SystemExit("installed runtime evidence sampling is not partial")
if result.request.sampling.total_known is not False:
    raise SystemExit("installed runtime evidence total was inferred")
if result.request.environment.environment_uri != (
    "urn:ucf:fixture-environment:runtime-import:1.0.0"
):
    raise SystemExit("installed runtime evidence environment is not exact")
if result.request.adapter_procedure_uri != (
    "urn:ucf:fixture-adapter:runtime-evidence:1.0.0"
):
    raise SystemExit("installed runtime evidence procedure is not exact")
if result.producer.name != "org.ucf.fixture-runtime-adapter":
    raise SystemExit("installed runtime evidence producer is not exact")
recording_digest = hashlib.sha256(recording_path.read_bytes()).hexdigest()
if result.request.source.source_revision.value != recording_digest:
    raise SystemExit("installed runtime evidence source revision is not exact")

behavior = parse_ir_json(behavior_path.read_bytes())
environment = parse_runtime_environment_json(environment_path.read_bytes())
trust = project_runtime_evidence_to_trust(
    result,
    behavior=behavior,
    environment=environment,
)
if len(trust.records) != 2:
    raise SystemExit("installed runtime projection record count is not exact")
if {type(record) for record in trust.records} != {SourceRecord, ObservedFact}:
    raise SystemExit("installed runtime projection promoted evidence")
serialized = canonical_trust_ir_json(trust).lower()
for forbidden_kind in (
    '"claim"',
    '"declaration"',
    '"mapping"',
    '"behavior_candidate"',
    '"verification_evidence"',
):
    if forbidden_kind in serialized:
        raise SystemExit("installed runtime projection promoted evidence")
"""

INSTALLED_CHANGE_ASSERT = """\
import sys
from pathlib import Path

from ucf.change_lifecycle import (
    ExecutionEvidenceContext,
    canonical_change_lifecycle_json,
    parse_archive_record_json,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    parse_implementation_record_json,
    parse_task_graph_json,
    parse_verification_record_json,
    validate_archive_record,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    parse_execution_verification_result_json,
    parse_implementation_mapping_result_json,
)
from ucf.inventory import parse_inventory_snapshot_json
from ucf.ir import parse_ir_json
from ucf.onboarding import parse_onboarding_bundle_json

paths = tuple(Path(value) for value in sys.argv[1:])
if len(paths) != 12:
    raise SystemExit("installed change assertion received incomplete inputs")
(
    proposal_path,
    delta_path,
    tasks_path,
    implementation_path,
    verification_path,
    archive_path,
    base_path,
    final_path,
    result_path,
    mapping_path,
    bundle_path,
    inventory_path,
) = paths
parsers_and_paths = (
    (parse_change_proposal_json, proposal_path),
    (parse_behavior_delta_json, delta_path),
    (parse_task_graph_json, tasks_path),
    (parse_implementation_record_json, implementation_path),
    (parse_verification_record_json, verification_path),
    (parse_archive_record_json, archive_path),
)
documents = []
for parser, path in parsers_and_paths:
    document = parser(path.read_bytes())
    if canonical_change_lifecycle_json(document) != path.read_bytes():
        raise SystemExit(f"installed change output is not canonical: {path.name}")
    documents.append(document)
proposal, delta, graph, implementation, verification, archive = documents
if len({document.change_id for document in documents}) != 1:
    raise SystemExit("installed change outputs disagree on change ID")
if any(task.status != "completed" for task in graph.tasks):
    raise SystemExit("installed change archived incomplete tasks")
if verification.outcome != "accepted" or archive.status != "archived":
    raise SystemExit("installed change did not reach accepted archive state")

result = parse_execution_verification_result_json(result_path.read_bytes())
mapping = parse_implementation_mapping_result_json(mapping_path.read_bytes())
bundle = parse_onboarding_bundle_json(bundle_path.read_bytes())
inventory = parse_inventory_snapshot_json(inventory_path.read_bytes())
context = ExecutionEvidenceContext(
    result=result,
    mapping_result=mapping,
    bundle=bundle,
    current_inventory=inventory,
    mapping_initialized_adapter=mapping.producer,
    initialized_adapter=result.producer,
    negotiated_capabilities={
        IMPLEMENTATION_MAPPING_CAPABILITY: IMPLEMENTATION_EVIDENCE_VERSION,
        EXECUTION_VERIFICATION_CAPABILITY: IMPLEMENTATION_EVIDENCE_VERSION,
    },
)
validate_archive_record(
    archive,
    proposal,
    delta,
    graph,
    implementation,
    verification,
    parse_ir_json(base_path.read_bytes()),
    parse_ir_json(final_path.read_bytes()),
    evidence_contexts=(context,),
)
"""

INSTALLED_CHANGE_GOVERNANCE_ASSERT = """\
import sys
from pathlib import Path

from ucf.change_governance import (
    CompatibilityOutcome,
    GateStatus,
    canonical_change_governance_json,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    parse_impact_report_json,
    validate_decision_assessment,
    validate_decision_declaration,
    validate_gate_evaluation,
    validate_impact_report,
)
from ucf.change_lifecycle import (
    parse_behavior_delta_json,
    parse_change_proposal_json,
)
from ucf.ir import parse_ir_json

paths = tuple(Path(value) for value in sys.argv[1:])
if len(paths) != 13:
    raise SystemExit(
        "installed change governance assertion received incomplete inputs"
    )
(
    base_path,
    proposal_path,
    compatible_final_path,
    compatible_delta_path,
    compatible_impact_path,
    compatible_assessment_path,
    compatible_gate_path,
    breaking_final_path,
    breaking_delta_path,
    breaking_impact_path,
    breaking_assessment_path,
    breaking_declaration_path,
    breaking_gate_path,
) = paths
base = parse_ir_json(base_path.read_bytes())
proposal = parse_change_proposal_json(proposal_path.read_bytes())

def validate_profile(
    *,
    final_path,
    delta_path,
    impact_path,
    assessment_path,
    gate_path,
    declaration_path=None,
):
    final = parse_ir_json(final_path.read_bytes())
    delta = parse_behavior_delta_json(delta_path.read_bytes())
    impact = parse_impact_report_json(impact_path.read_bytes())
    assessment = parse_decision_assessment_json(assessment_path.read_bytes())
    declaration = (
        None
        if declaration_path is None
        else parse_decision_declaration_json(declaration_path.read_bytes())
    )
    gate = parse_gate_evaluation_json(gate_path.read_bytes())
    for document, path in (
        (impact, impact_path),
        (assessment, assessment_path),
        *((((declaration, declaration_path),) if declaration is not None else ())),
        (gate, gate_path),
    ):
        if canonical_change_governance_json(document) != path.read_bytes():
            raise SystemExit(
                f"installed change governance output is not canonical: {path.name}"
            )
    validate_impact_report(
        impact,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    validate_decision_assessment(
        assessment,
        impact,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    if declaration is not None:
        validate_decision_declaration(
            declaration,
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
    validate_gate_evaluation(
        gate,
        assessment,
        impact,
        declaration,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    return impact, gate

compatible_impact, compatible_gate = validate_profile(
    final_path=compatible_final_path,
    delta_path=compatible_delta_path,
    impact_path=compatible_impact_path,
    assessment_path=compatible_assessment_path,
    gate_path=compatible_gate_path,
)
breaking_impact, breaking_gate = validate_profile(
    final_path=breaking_final_path,
    delta_path=breaking_delta_path,
    impact_path=breaking_impact_path,
    assessment_path=breaking_assessment_path,
    declaration_path=breaking_declaration_path,
    gate_path=breaking_gate_path,
)
if (
    compatible_impact.compatibility.outcome is not CompatibilityOutcome.COMPATIBLE
    or compatible_gate.status is not GateStatus.PASS_NO_DECISION
):
    raise SystemExit("installed compatible change did not pass without a decision")
if (
    breaking_impact.compatibility.outcome is not CompatibilityOutcome.BREAKING
    or breaking_gate.status is not GateStatus.PASS_APPROVED
):
    raise SystemExit("installed breaking change did not require exact approval")
"""

INSTALLED_GENERATION_ASSERT = """\
import sys
from pathlib import Path

from ucf.generation import (
    GENERATION_RECEIPT_NAME,
    canonical_generation_json,
    parse_generation_request_json,
    parse_generation_result_json,
)

request = parse_generation_request_json(Path(sys.argv[1]).read_bytes())
results = tuple(
    parse_generation_result_json(
        (Path(root) / GENERATION_RECEIPT_NAME).read_bytes()
    )
    for root in sys.argv[2:]
)
if any(result.request != request for result in results):
    raise SystemExit("installed generation result changed its exact request")
if len({canonical_generation_json(result) for result in results}) != 1:
    raise SystemExit("installed generation results are not byte-deterministic")
expected_argv = (
    "python3",
    "-B",
    "-m",
    "pytest",
    "-q",
    "{generated_root}",
)
if any(result.verification.argv != expected_argv for result in results):
    raise SystemExit("installed generation verification command is not exact")
if any(
    tuple(file.path for file in result.files)
    != ("test_action_reserve_item.py",)
    for result in results
):
    raise SystemExit("installed generation result file inventory is not exact")
"""

INSTALLED_EVIDENCE_MUTATE = """\
import sys
from pathlib import Path

from ucf.implementation_evidence import (
    canonical_implementation_evidence_json,
    derive_execution_verification_result_id,
    parse_execution_verification_result_json,
)
from ucf.ir.models import Digest

source = parse_execution_verification_result_json(Path(sys.argv[1]).read_bytes())
environment = source.request.environment.model_copy(
    update={
        "identity_uri": (
            "urn:ucf:fixture-environment:node24-linux-loopback:2.0.0"
        ),
        "revision": Digest(
            kind="digest",
            algorithm="sha-256",
            value="f" * 64,
        ),
    }
)
request = source.request.model_copy(update={"environment": environment})
current = source.model_copy(update={"request": request})
current = current.model_copy(
    update={"id": derive_execution_verification_result_id(current)}
)
Path(sys.argv[2]).write_bytes(
    canonical_implementation_evidence_json(current)
)
failed = source.model_copy(update={"outcome": "failed"})
failed = failed.model_copy(
    update={"id": derive_execution_verification_result_id(failed)}
)
Path(sys.argv[3]).write_bytes(
    canonical_implementation_evidence_json(failed)
)
"""

INSTALLED_EVIDENCE_ASSERT = """\
import sys
from pathlib import Path

from ucf.evidence_status import (
    EvidenceStatus,
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
    validate_verification_evidence_assessment,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    parse_execution_verification_result_json,
    parse_implementation_mapping_result_json,
)
from ucf.inventory import parse_inventory_snapshot_json
from ucf.onboarding import parse_onboarding_bundle_json

(
    result_path,
    mapping_path,
    bundle_path,
    inventory_path,
    envelope_a_path,
    envelope_b_path,
    fresh_path,
    stale_path,
    indeterminate_path,
    current_result_path,
    refreshed_envelope_path,
    refreshed_assessment_path,
) = map(Path, sys.argv[1:])
result = parse_execution_verification_result_json(result_path.read_bytes())
mapping = parse_implementation_mapping_result_json(mapping_path.read_bytes())
bundle = parse_onboarding_bundle_json(bundle_path.read_bytes())
inventory = parse_inventory_snapshot_json(inventory_path.read_bytes())
current_result = parse_execution_verification_result_json(
    current_result_path.read_bytes()
)
envelope_a = parse_verification_evidence_envelope_json(
    envelope_a_path.read_bytes()
)
envelope_b = parse_verification_evidence_envelope_json(
    envelope_b_path.read_bytes()
)
refreshed_envelope = parse_verification_evidence_envelope_json(
    refreshed_envelope_path.read_bytes()
)
fresh = parse_verification_evidence_assessment_json(fresh_path.read_bytes())
stale = parse_verification_evidence_assessment_json(stale_path.read_bytes())
indeterminate = parse_verification_evidence_assessment_json(
    indeterminate_path.read_bytes()
)
refreshed = parse_verification_evidence_assessment_json(
    refreshed_assessment_path.read_bytes()
)
documents = (
    envelope_a,
    envelope_b,
    refreshed_envelope,
    fresh,
    stale,
    indeterminate,
    refreshed,
)
paths = (
    envelope_a_path,
    envelope_b_path,
    refreshed_envelope_path,
    fresh_path,
    stale_path,
    indeterminate_path,
    refreshed_assessment_path,
)
if any(
    canonical_evidence_status_json(document) != path.read_bytes()
    for document, path in zip(documents, paths, strict=True)
):
    raise SystemExit("installed evidence-status output is not canonical")
if envelope_a != envelope_b:
    raise SystemExit("installed evidence envelope is not deterministic")
if refreshed_envelope.id == envelope_a.id:
    raise SystemExit("installed evidence refresh did not bind the new result")
if b'"verified"' in b"".join(path.read_bytes() for path in paths):
    raise SystemExit("installed evidence loop promoted a verified claim")
if fresh.status is not EvidenceStatus.FRESH or fresh.reasons:
    raise SystemExit("installed unchanged evidence is not fresh")
if (
    stale.status is not EvidenceStatus.STALE
    or tuple(reason.code.value for reason in stale.reasons)
    != ("environment_changed",)
):
    raise SystemExit("installed changed evidence has the wrong stale reason")
if (
    indeterminate.status is not EvidenceStatus.INDETERMINATE
    or tuple(reason.code.value for reason in indeterminate.reasons)
    != ("current_context_unavailable",)
):
    raise SystemExit("installed absent context is not indeterminate")
if refreshed.status is not EvidenceStatus.FRESH or refreshed.reasons:
    raise SystemExit("installed refreshed evidence is not fresh")

capabilities = {
    IMPLEMENTATION_MAPPING_CAPABILITY: mapping.capability.version,
    EXECUTION_VERIFICATION_CAPABILITY: result.capability.version,
}
recorded = {
    "recorded_result": result,
    "recorded_request": result.request,
    "recorded_mapping_result": mapping,
    "recorded_bundle": bundle,
    "recorded_current_inventory": inventory,
    "recorded_mapping_initialized_adapter": mapping.producer,
    "recorded_initialized_adapter": result.producer,
    "recorded_negotiated_capabilities": capabilities,
}
current = {
    "current_result": result,
    "current_request": result.request,
    "current_mapping_result": mapping,
    "current_bundle": bundle,
    "current_inventory": inventory,
    "current_mapping_initialized_adapter": mapping.producer,
    "current_initialized_adapter": result.producer,
    "current_negotiated_capabilities": capabilities,
}
validate_verification_evidence_assessment(
    fresh,
    envelope_a,
    **recorded,
    **current,
)
validate_verification_evidence_assessment(
    indeterminate,
    envelope_a,
    **recorded,
)
current["current_result"] = current_result
current["current_request"] = current_result.request
validate_verification_evidence_assessment(
    stale,
    envelope_a,
    **recorded,
    **current,
)
recorded["recorded_result"] = current_result
recorded["recorded_request"] = current_result.request
validate_verification_evidence_assessment(
    refreshed,
    refreshed_envelope,
    **recorded,
    **current,
)
"""

INSTALLED_EVIDENCE_PUBLISH_RACE_ASSERT = """\
import os
import sys
from pathlib import Path

import ucf.cli as cli

output = Path(sys.argv[1])
winner = b"concurrent-winner"
original_link = os.link

def competing_link(source, destination, *, follow_symlinks=True):
    Path(destination).write_bytes(winner)
    return original_link(
        source,
        destination,
        follow_symlinks=follow_symlinks,
    )

cli.os.link = competing_link
try:
    cli._publish_exact_file(output, b"ucf-output")
except ValueError as error:
    if "output appeared before publication" not in str(error):
        raise
else:
    raise SystemExit(
        "installed evidence concurrent publication did not reject the loser"
    )
if output.read_bytes() != winner:
    raise SystemExit(
        "installed evidence concurrent publication replaced prior output"
    )
if tuple(output.parent.glob(f".{output.name}.*.tmp")):
    raise SystemExit(
        "installed evidence concurrent publication left temporary output"
    )
"""

INSTALLED_ASSET_SMOKE = """\
import hashlib
import json
import sys
from pathlib import Path

import ucf
from ucf.adapter_protocol import (
    AdapterDispatcher,
    AdapterProcess,
    Method,
    Request,
    ShutdownParams,
    decode_request_frame,
    encode_frame,
)
from ucf.adapter_conformance import (
    conformance_asset_names,
    conformance_kit_index,
    read_conformance_asset,
)
from ucf.change_lifecycle import (
    canonical_change_lifecycle_json,
    parse_archive_record_json,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    parse_implementation_record_json,
    parse_task_graph_json,
    parse_verification_record_json,
)
from ucf.change_governance import (
    canonical_change_governance_json,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    parse_impact_report_json,
)
from ucf.evidence_status import (
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
    validate_verification_evidence_assessment,
)
from ucf.generation import (
    canonical_generation_json,
    parse_generation_request_json,
    parse_generation_result_json,
)
from ucf.ir import (
    canonical_ir_json,
    canonical_trust_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import Producer
from ucf.inventory import (
    canonical_inventory_json,
    parse_inventory_request_json,
)
from ucf.implementation_evidence import (
    canonical_implementation_evidence_json,
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
    parse_implementation_mapping_request_json,
    parse_implementation_mapping_result_json,
)
from ucf.onboarding import (
    parse_decision_set_json,
    parse_discovery_request_json,
    parse_discovery_result_json,
    parse_onboarding_bundle_json,
)
from ucf.ratchet import (
    canonical_ratchet_json,
    parse_ratchet_assessment_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
    parse_ratchet_policy_json,
)
from ucf.ratchet.v2 import (
    RATCHET_EVALUATOR_CAPABILITY as RATCHET_EVALUATOR_CAPABILITY_V2,
    RATCHET_POLICY_SCHEMA_URI as RATCHET_POLICY_SCHEMA_URI_V2,
    RATCHET_VERSION as RATCHET_VERSION_V2,
    RatchetEvaluatorSelection as RatchetEvaluatorSelectionV2,
    RatchetPolicy as RatchetPolicyV2,
    RatchetRule as RatchetRuleV2,
    canonical_ratchet_json as canonical_ratchet_json_v2,
    derive_policy_id as derive_policy_id_v2,
    parse_ratchet_assessment_json as parse_ratchet_assessment_json_v2,
    parse_ratchet_baseline_json as parse_ratchet_baseline_json_v2,
    parse_ratchet_evaluation_report_json as parse_ratchet_evaluation_report_json_v2,
    parse_ratchet_policy_json as parse_ratchet_policy_json_v2,
)
from ucf.runtime_evidence import (
    canonical_runtime_evidence_json,
    parse_runtime_environment_json,
    parse_runtime_evidence_policy_json,
    parse_runtime_evidence_request_json,
    parse_runtime_evidence_result_json,
)

repository_root = Path(sys.argv[1]).resolve()
package_root = Path(ucf.__file__).resolve().parent
if package_root.is_relative_to(repository_root):
    raise SystemExit(f"source-tree import leaked into smoke test: {package_root}")

spec_schema_path = package_root / "schemas" / "spec" / "v1" / "schema.json"
spec_schema = json.loads(spec_schema_path.read_text())
if spec_schema.get("$id") != "urn:ucf:schema:spec:v1":
    raise SystemExit(
        f"unexpected packaged spec schema identity: {spec_schema.get('$id')!r}"
    )

ir_schema_path = package_root / "schemas" / "ir" / "v1" / "schema.json"
ir_schema = json.loads(ir_schema_path.read_text())
if ir_schema.get("$id") != "urn:ucf:schema:ir:1.0.0":
    raise SystemExit(
        f"unexpected packaged IR schema identity: {ir_schema.get('$id')!r}"
    )

trust_schema_path = package_root / "schemas" / "trust" / "v1" / "schema.json"
trust_schema = json.loads(trust_schema_path.read_text())
if trust_schema.get("$id") != "urn:ucf:schema:trust-ir:1.0.0":
    raise SystemExit(
        f"unexpected packaged trust schema identity: {trust_schema.get('$id')!r}"
    )

adapter_schema_path = (
    package_root / "schemas" / "adapter_protocol" / "v1" / "schema.json"
)
adapter_schema = json.loads(adapter_schema_path.read_text())
if adapter_schema.get("$id") != "urn:ucf:schema:adapter-protocol:1.0.0":
    raise SystemExit(
        "unexpected packaged adapter protocol schema identity: "
        f"{adapter_schema.get('$id')!r}"
    )

conformance_schema_path = (
    package_root / "schemas" / "adapter_conformance" / "v1" / "schema.json"
)
conformance_schema = json.loads(conformance_schema_path.read_text())
if (
    conformance_schema.get("$id")
    != "urn:ucf:schema:adapter-conformance:1.0.0"
):
    raise SystemExit(
        "unexpected packaged adapter conformance schema identity: "
        f"{conformance_schema.get('$id')!r}"
    )

generation_schema_directory = package_root / "schemas" / "generation" / "v1"
generation_resources = {
    generation_schema_directory / "request.schema.json": (
        "urn:ucf:generation:request:1.0.0",
        "generation_request",
    ),
    generation_schema_directory / "result.schema.json": (
        "urn:ucf:generation:result:1.0.0",
        "generation_result",
    ),
}
for generation_schema_path, coordinates in generation_resources.items():
    expected_id, expected_kind = coordinates
    generation_schema = json.loads(generation_schema_path.read_text())
    properties = generation_schema.get("properties", {})
    if generation_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged generation schema identity: "
            f"{generation_schema.get('$id')!r}"
        )
    if generation_schema.get("x-ucf-generation-version") != "1.0.0":
        raise SystemExit("unexpected packaged generation schema version")
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged generation document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged generation schema URI differs from its resource ID"
        )

generation_parsers = (
    parse_generation_request_json,
    parse_generation_result_json,
)
if len(generation_parsers) != len(generation_resources):
    raise SystemExit("installed generation parser surface is incomplete")
if not canonical_generation_json:
    raise SystemExit("installed generation serializer is unavailable")

evidence_status_schema_directory = (
    package_root / "schemas" / "evidence_status" / "v1"
)
evidence_status_resources = {
    evidence_status_schema_directory / "envelope.schema.json": (
        "urn:ucf:evidence-status:envelope:1.0.0",
        "verification_evidence_envelope",
    ),
    evidence_status_schema_directory / "assessment.schema.json": (
        "urn:ucf:evidence-status:assessment:1.0.0",
        "verification_evidence_assessment",
    ),
}
for evidence_schema_path, coordinates in evidence_status_resources.items():
    expected_id, expected_kind = coordinates
    evidence_schema = json.loads(evidence_schema_path.read_text())
    properties = evidence_schema.get("properties", {})
    if evidence_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged evidence-status schema identity: "
            f"{evidence_schema.get('$id')!r}"
        )
    if evidence_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit(
            "unexpected packaged evidence-status document kind: "
            f"{evidence_schema.get('x-ucf-document-kind')!r}"
        )
    if evidence_schema.get("x-ucf-evidence-status-version") != "1.0.0":
        raise SystemExit(
            "unexpected packaged evidence-status document version"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "packaged evidence-status schema kind differs from metadata"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged evidence-status schema URI differs from its resource ID"
        )

evidence_status_parsers = (
    parse_verification_evidence_envelope_json,
    parse_verification_evidence_assessment_json,
)
if len(evidence_status_parsers) != len(evidence_status_resources):
    raise SystemExit("installed evidence-status parser surface is incomplete")
if not canonical_evidence_status_json:
    raise SystemExit("installed evidence-status serializer is unavailable")
if not validate_verification_evidence_assessment:
    raise SystemExit(
        "installed evidence-status contextual validator is unavailable"
    )

inventory_schema_directory = package_root / "schemas" / "inventory" / "v1"
inventory_resources = {
    inventory_schema_directory / "schema.json": (
        "urn:ucf:schema:inventory:1.0.0",
        "inventory_snapshot",
    ),
    inventory_schema_directory / "request.schema.json": (
        "urn:ucf:adapter:inventory-request:1.0.0",
        "inventory_request_profile",
    ),
    inventory_schema_directory / "page.schema.json": (
        "urn:ucf:adapter:inventory-page:1.0.0",
        "inventory_page",
    ),
}
for inventory_schema_path, coordinates in inventory_resources.items():
    expected_id, expected_kind = coordinates
    inventory_schema = json.loads(inventory_schema_path.read_text())
    properties = inventory_schema.get("properties", {})
    if inventory_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged inventory schema identity: "
            f"{inventory_schema.get('$id')!r}"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged inventory document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged inventory schema URI differs from its resource ID"
        )

onboarding_schema_directory = package_root / "schemas" / "onboarding" / "v1"
onboarding_resources = {
    onboarding_schema_directory / "discovery-request.schema.json": (
        "urn:ucf:adapter:discovery-request:1.0.0",
        "discovery_request_profile",
    ),
    onboarding_schema_directory / "discovery-result.schema.json": (
        "urn:ucf:adapter:discovery-result:1.0.0",
        "discovery_result_profile",
    ),
    onboarding_schema_directory / "decision-set.schema.json": (
        "urn:ucf:onboarding:decision-set:1.0.0",
        "decision_set_profile",
    ),
    onboarding_schema_directory / "bundle.schema.json": (
        "urn:ucf:onboarding:bundle:1.0.0",
        "onboarding_bundle",
    ),
}
for onboarding_schema_path, coordinates in onboarding_resources.items():
    expected_id, expected_kind = coordinates
    onboarding_schema = json.loads(onboarding_schema_path.read_text())
    properties = onboarding_schema.get("properties", {})
    if onboarding_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged onboarding schema identity: "
            f"{onboarding_schema.get('$id')!r}"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged onboarding document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged onboarding schema URI differs from its resource ID"
        )

onboarding_parsers = (
    parse_discovery_request_json,
    parse_discovery_result_json,
    parse_decision_set_json,
    parse_onboarding_bundle_json,
)
if len(onboarding_parsers) != len(onboarding_resources):
    raise SystemExit("installed onboarding parser surface is incomplete")

ratchet_schema_directory = package_root / "schemas" / "ratchet" / "v1"
ratchet_resources = {
    ratchet_schema_directory / "policy.schema.json": (
        "urn:ucf:ratchet:policy:1.0.0",
        "ratchet_policy",
    ),
    ratchet_schema_directory / "assessment.schema.json": (
        "urn:ucf:ratchet:assessment:1.0.0",
        "ratchet_assessment",
    ),
    ratchet_schema_directory / "baseline.schema.json": (
        "urn:ucf:ratchet:baseline:1.0.0",
        "ratchet_baseline",
    ),
    ratchet_schema_directory / "evaluation-report.schema.json": (
        "urn:ucf:ratchet:evaluation-report:1.0.0",
        "ratchet_evaluation_report",
    ),
}
for ratchet_schema_path, coordinates in ratchet_resources.items():
    expected_id, expected_kind = coordinates
    ratchet_schema = json.loads(ratchet_schema_path.read_text())
    properties = ratchet_schema.get("properties", {})
    if ratchet_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged ratchet schema identity: "
            f"{ratchet_schema.get('$id')!r}"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged ratchet document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged ratchet schema URI differs from its resource ID"
        )

ratchet_parsers = (
    parse_ratchet_policy_json,
    parse_ratchet_assessment_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
)
if len(ratchet_parsers) != len(ratchet_resources):
    raise SystemExit("installed ratchet parser surface is incomplete")
if not canonical_ratchet_json:
    raise SystemExit("installed ratchet serializer is unavailable")

ratchet_v2_schema_directory = package_root / "schemas" / "ratchet" / "v2"
ratchet_v2_resources = {
    ratchet_v2_schema_directory / "policy.schema.json": (
        "urn:ucf:ratchet:policy:2.0.0",
        "ratchet_policy",
    ),
    ratchet_v2_schema_directory / "assessment.schema.json": (
        "urn:ucf:ratchet:assessment:2.0.0",
        "ratchet_assessment",
    ),
    ratchet_v2_schema_directory / "baseline.schema.json": (
        "urn:ucf:ratchet:baseline:2.0.0",
        "ratchet_baseline",
    ),
    ratchet_v2_schema_directory / "evaluation-report.schema.json": (
        "urn:ucf:ratchet:evaluation-report:2.0.0",
        "ratchet_evaluation_report",
    ),
}
for ratchet_v2_schema_path, coordinates in ratchet_v2_resources.items():
    expected_id, expected_kind = coordinates
    ratchet_v2_schema = json.loads(ratchet_v2_schema_path.read_text())
    properties = ratchet_v2_schema.get("properties", {})
    if ratchet_v2_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged ratchet v2 schema identity: "
            f"{ratchet_v2_schema.get('$id')!r}"
        )
    if ratchet_v2_schema.get("x-ucf-ratchet-version") != "2.0.0":
        raise SystemExit("unexpected packaged ratchet v2 version marker")
    if ratchet_v2_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit("unexpected packaged ratchet v2 kind marker")
    if ratchet_v2_schema.get("additionalProperties") is not False:
        raise SystemExit("packaged ratchet v2 root schema is not closed")
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit("unexpected packaged ratchet v2 document kind")
    if properties.get("ratchet_version", {}).get("const") != "2.0.0":
        raise SystemExit("unexpected packaged ratchet v2 document version")
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged ratchet v2 schema URI differs from its resource ID"
        )

ratchet_v2_rule = RatchetRuleV2(
    kind="ratchet_rule",
    id="installed-smoke",
    version="1.0.0",
    procedure_uri="urn:ucf:ratchet-rule:installed-smoke:1.0.0",
    producer=Producer(
        kind="producer",
        name="org.ucf.installed-smoke-rules",
        version="1.0.0",
    ),
    summary="Exercise the installed Ratchet 2.0.0 policy boundary.",
)
ratchet_v2_provisional = RatchetPolicyV2(
    kind="ratchet_policy",
    ratchet_version=RATCHET_VERSION_V2,
    schema_uri=RATCHET_POLICY_SCHEMA_URI_V2,
    id="policy." + ("0" * 64),
    evaluator=RatchetEvaluatorSelectionV2(
        kind="capability",
        name=RATCHET_EVALUATOR_CAPABILITY_V2,
        version=RATCHET_VERSION_V2,
    ),
    rules=(ratchet_v2_rule,),
)
ratchet_v2_policy = ratchet_v2_provisional.model_copy(
    update={"id": derive_policy_id_v2(ratchet_v2_provisional)}
)
ratchet_v2_encoded = canonical_ratchet_json_v2(ratchet_v2_policy)
if parse_ratchet_policy_json_v2(ratchet_v2_encoded) != ratchet_v2_policy:
    raise SystemExit("installed Ratchet 2.0.0 policy round-trip failed")
ratchet_v2_parsers = (
    parse_ratchet_policy_json_v2,
    parse_ratchet_assessment_json_v2,
    parse_ratchet_baseline_json_v2,
    parse_ratchet_evaluation_report_json_v2,
)
if len(ratchet_v2_parsers) != len(ratchet_v2_resources):
    raise SystemExit("installed ratchet v2 parser surface is incomplete")

runtime_evidence_schema_directory = (
    package_root / "schemas" / "runtime_evidence" / "v1"
)
runtime_evidence_resources = {
    runtime_evidence_schema_directory / "policy.schema.json": (
        "urn:ucf:runtime-evidence:policy:1.0.0",
        "runtime_evidence_policy",
    ),
    runtime_evidence_schema_directory / "environment.schema.json": (
        "urn:ucf:runtime-evidence:environment:1.0.0",
        "runtime_environment",
    ),
    runtime_evidence_schema_directory / "request.schema.json": (
        "urn:ucf:adapter:runtime-evidence-request:1.0.0",
        "runtime_evidence_import_request",
    ),
    runtime_evidence_schema_directory / "result.schema.json": (
        "urn:ucf:adapter:runtime-evidence-result:1.0.0",
        "runtime_evidence_result",
    ),
}
for runtime_schema_path, coordinates in runtime_evidence_resources.items():
    expected_id, expected_kind = coordinates
    runtime_schema = json.loads(runtime_schema_path.read_text())
    if runtime_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged runtime evidence schema identity: "
            f"{runtime_schema.get('$id')!r}"
        )
    if runtime_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit(
            "unexpected packaged runtime evidence document kind: "
            f"{runtime_schema.get('x-ucf-document-kind')!r}"
        )
    if expected_id not in json.dumps(runtime_schema, sort_keys=True):
        raise SystemExit(
            "packaged runtime evidence schema does not bind its URI"
        )

runtime_evidence_parsers = (
    parse_runtime_evidence_policy_json,
    parse_runtime_environment_json,
    parse_runtime_evidence_request_json,
    parse_runtime_evidence_result_json,
)
if len(runtime_evidence_parsers) != len(runtime_evidence_resources):
    raise SystemExit("installed runtime evidence parser surface is incomplete")
if not canonical_runtime_evidence_json:
    raise SystemExit("installed runtime evidence serializer is unavailable")

implementation_evidence_schema_directory = (
    package_root / "schemas" / "implementation_evidence" / "v1"
)
implementation_evidence_resources = {
    implementation_evidence_schema_directory / "mapping-request.schema.json": (
        "urn:ucf:adapter:implementation-mapping-request:1.0.0",
        "implementation_mapping_request",
    ),
    implementation_evidence_schema_directory / "mapping-result.schema.json": (
        "urn:ucf:adapter:implementation-mapping-result:1.0.0",
        "implementation_mapping_result",
    ),
    implementation_evidence_schema_directory
    / "verification-request.schema.json": (
        "urn:ucf:adapter:execution-verification-request:1.0.0",
        "execution_verification_request",
    ),
    implementation_evidence_schema_directory
    / "verification-result.schema.json": (
        "urn:ucf:adapter:execution-verification-result:1.0.0",
        "execution_verification_result",
    ),
}
for implementation_schema_path, coordinates in (
    implementation_evidence_resources.items()
):
    expected_id, expected_kind = coordinates
    implementation_schema = json.loads(
        implementation_schema_path.read_text()
    )
    if implementation_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged implementation evidence schema identity: "
            f"{implementation_schema.get('$id')!r}"
        )
    if implementation_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit(
            "unexpected packaged implementation evidence document kind: "
            f"{implementation_schema.get('x-ucf-document-kind')!r}"
        )
    if expected_id not in json.dumps(
        implementation_schema,
        sort_keys=True,
    ):
        raise SystemExit(
            "packaged implementation evidence schema does not bind its URI"
        )

implementation_evidence_parsers = (
    parse_implementation_mapping_request_json,
    parse_implementation_mapping_result_json,
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
)
if len(implementation_evidence_parsers) != len(
    implementation_evidence_resources
):
    raise SystemExit(
        "installed implementation evidence parser surface is incomplete"
    )
if not canonical_implementation_evidence_json:
    raise SystemExit(
        "installed implementation evidence serializer is unavailable"
    )

change_lifecycle_schema_directory = (
    package_root / "schemas" / "change_lifecycle" / "v1"
)
change_lifecycle_resources = {
    change_lifecycle_schema_directory / "proposal.schema.json": (
        "urn:ucf:change-lifecycle:proposal:1.0.0",
        "change_proposal",
    ),
    change_lifecycle_schema_directory / "behavior-delta.schema.json": (
        "urn:ucf:change-lifecycle:behavior-delta:1.0.0",
        "behavior_delta",
    ),
    change_lifecycle_schema_directory / "task-graph.schema.json": (
        "urn:ucf:change-lifecycle:task-graph:1.0.0",
        "task_graph",
    ),
    change_lifecycle_schema_directory / "implementation-record.schema.json": (
        "urn:ucf:change-lifecycle:implementation-record:1.0.0",
        "implementation_record",
    ),
    change_lifecycle_schema_directory / "verification-record.schema.json": (
        "urn:ucf:change-lifecycle:verification-record:1.0.0",
        "verification_record",
    ),
    change_lifecycle_schema_directory / "archive-record.schema.json": (
        "urn:ucf:change-lifecycle:archive-record:1.0.0",
        "archive_record",
    ),
}
for lifecycle_schema_path, coordinates in change_lifecycle_resources.items():
    expected_id, expected_kind = coordinates
    lifecycle_schema = json.loads(lifecycle_schema_path.read_text())
    properties = lifecycle_schema.get("properties", {})
    if lifecycle_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged change lifecycle schema identity: "
            f"{lifecycle_schema.get('$id')!r}"
        )
    if lifecycle_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit(
            "unexpected packaged change lifecycle schema metadata kind: "
            f"{lifecycle_schema.get('x-ucf-document-kind')!r}"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged change lifecycle document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged change lifecycle schema URI differs from its resource ID"
        )
    if (
        properties.get("change_lifecycle_version", {}).get("const")
        != "1.0.0"
    ):
        raise SystemExit(
            "unexpected packaged change lifecycle document version"
        )

change_lifecycle_parsers = (
    parse_change_proposal_json,
    parse_behavior_delta_json,
    parse_task_graph_json,
    parse_implementation_record_json,
    parse_verification_record_json,
    parse_archive_record_json,
)
if len(change_lifecycle_parsers) != len(change_lifecycle_resources):
    raise SystemExit("installed change lifecycle parser surface is incomplete")
if not canonical_change_lifecycle_json:
    raise SystemExit("installed change lifecycle serializer is unavailable")

change_governance_schema_directory = (
    package_root / "schemas" / "change_governance" / "v1"
)
change_governance_resources = {
    change_governance_schema_directory / "impact-report.schema.json": (
        "urn:ucf:change-governance:impact-report:1.0.0",
        "impact_report",
    ),
    change_governance_schema_directory / "decision-assessment.schema.json": (
        "urn:ucf:change-governance:decision-assessment:1.0.0",
        "decision_assessment",
    ),
    change_governance_schema_directory / "decision-declaration.schema.json": (
        "urn:ucf:change-governance:decision-declaration:1.0.0",
        "decision_declaration",
    ),
    change_governance_schema_directory / "gate-evaluation.schema.json": (
        "urn:ucf:change-governance:gate-evaluation:1.0.0",
        "gate_evaluation",
    ),
}
for governance_schema_path, coordinates in change_governance_resources.items():
    expected_id, expected_kind = coordinates
    governance_schema = json.loads(governance_schema_path.read_text())
    properties = governance_schema.get("properties", {})
    if governance_schema.get("$id") != expected_id:
        raise SystemExit(
            "unexpected packaged change governance schema identity: "
            f"{governance_schema.get('$id')!r}"
        )
    if governance_schema.get("x-ucf-document-kind") != expected_kind:
        raise SystemExit(
            "unexpected packaged change governance metadata kind: "
            f"{governance_schema.get('x-ucf-document-kind')!r}"
        )
    if governance_schema.get("x-ucf-change-governance-version") != "1.0.0":
        raise SystemExit(
            "unexpected packaged change governance metadata version"
        )
    if properties.get("kind", {}).get("const") != expected_kind:
        raise SystemExit(
            "unexpected packaged change governance document kind: "
            f"{properties.get('kind')!r}"
        )
    if properties.get("schema_uri", {}).get("const") != expected_id:
        raise SystemExit(
            "packaged change governance schema URI differs from its resource ID"
        )
    if (
        properties.get("change_governance_version", {}).get("const")
        != "1.0.0"
    ):
        raise SystemExit(
            "unexpected packaged change governance document version"
        )

change_governance_parsers = (
    parse_impact_report_json,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
)
if len(change_governance_parsers) != len(change_governance_resources):
    raise SystemExit("installed change governance parser surface is incomplete")
if not canonical_change_governance_json:
    raise SystemExit("installed change governance serializer is unavailable")

kit_index = conformance_kit_index()
if tuple(asset.name for asset in kit_index.assets) != conformance_asset_names():
    raise SystemExit("installed adapter conformance index is not exact")
for asset in kit_index.assets:
    content = read_conformance_asset(asset.name)
    if len(content) != asset.size:
        raise SystemExit(f"adapter conformance asset size mismatch: {asset.name}")
    if hashlib.sha256(content).hexdigest() != asset.sha256:
        raise SystemExit(
            f"adapter conformance asset digest mismatch: {asset.name}"
        )

protocol_frame = encode_frame(
    Request(
        jsonrpc="2.0",
        id="installed-smoke-1",
        method=Method.SHUTDOWN,
        params=ShutdownParams(kind="shutdown_request"),
    )
)
if decode_request_frame(protocol_frame).method is not Method.SHUTDOWN:
    raise SystemExit("installed adapter protocol codec smoke failed")
if not AdapterDispatcher or not AdapterProcess:
    raise SystemExit("installed adapter protocol APIs are unavailable")

minimal_ir = (
    '{"kind":"behavior_ir","ir_version":"1.0.0",'
    '"document_id":"document.installed-smoke","roots":[],"entities":[]}'
)
behavior = parse_ir_json(minimal_ir)
canonical_ir = canonical_ir_json(behavior)
if json.loads(canonical_ir)["document_id"] != "document.installed-smoke":
    raise SystemExit("installed IR parser/serializer smoke failed")

minimal_trust = (
    '{"kind":"trust_ir","trust_ir_version":"1.0.0",'
    '"document_id":"document.installed-trust-smoke",'
    '"subject_document":{"kind":"behavior_document_ref",'
    '"document_id":"document.installed-smoke","ir_version":"1.0.0",'
    '"canonical_digest":{"kind":"digest","algorithm":"sha-256",'
    '"value":"02161d0ad001bc08979cad27f909d69da360e793f1da4b516fb6c81445707327"}},'
    '"records":[]}'
)
trust = parse_trust_ir_json(minimal_trust)
validate_trust_against_behavior(trust, behavior)
canonical_trust = canonical_trust_ir_json(trust)
if json.loads(canonical_trust)["document_id"] != "document.installed-trust-smoke":
    raise SystemExit("installed trust IR parser/serializer smoke failed")

minimal_inventory_request = (
    '{"fact_kinds":["api_description","build_manifest","public_interface",'
    '"repository_entry","test_asset"],"ignore_policy":{"kind":"ignore_policy",'
    '"policy_version":"1.0.0","rules":[]},"inventory_version":"1.0.0",'
    '"kind":"inventory_request_profile","page":{"cursor":null,'
    '"kind":"inventory_page_request","record_limit":1},'
    '"root_path":".","schema_uri":'
    '"urn:ucf:adapter:inventory-request:1.0.0",'
    '"subject_uri":"urn:ucf:repository:installed-smoke"}'
)
inventory_request = parse_inventory_request_json(minimal_inventory_request)
canonical_inventory = canonical_inventory_json(inventory_request)
if parse_inventory_request_json(canonical_inventory) != inventory_request:
    raise SystemExit("installed inventory parser/serializer smoke failed")

template_dir = package_root / "generator" / "templates"
templates = sorted(path.name for path in template_dir.glob("*.j2"))
expected = ["impl_stub.py.j2", "interface.py.j2", "orchestrator.py.j2"]
if templates != expected:
    raise SystemExit(f"unexpected packaged templates: {templates!r}")

print(f"installed-package={package_root}")
print(f"spec-schema={spec_schema_path}")
print(f"ir-schema={ir_schema_path}")
print(f"trust-schema={trust_schema_path}")
print(f"adapter-protocol-schema={adapter_schema_path}")
print(f"adapter-conformance-schema={conformance_schema_path}")
print(f"generation-schemas={sorted(map(str, generation_resources))}")
print(
    "evidence-status-schemas="
    f"{sorted(map(str, evidence_status_resources))}"
)
print(f"inventory-schemas={sorted(map(str, inventory_resources))}")
print(f"onboarding-schemas={sorted(map(str, onboarding_resources))}")
print(f"ratchet-schemas={sorted(map(str, ratchet_resources))}")
print(f"ratchet-v2-schemas={sorted(map(str, ratchet_v2_resources))}")
print(
    "runtime-evidence-schemas="
    f"{sorted(map(str, runtime_evidence_resources))}"
)
print(
    "change-lifecycle-schemas="
    f"{sorted(map(str, change_lifecycle_resources))}"
)
print(
    "change-governance-schemas="
    f"{sorted(map(str, change_governance_resources))}"
)
print(f"adapter-conformance-assets={len(kit_index.assets)}")
print(f"templates={templates}")
"""


class PackageContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class _GoStdlibDistribution:
    adapter_root: Path
    adapter_entry: Path
    fixture_entry: Path
    fixture_root: Path
    platform_fixture_entry: Path
    platform_fixture_root: Path
    adapter_source_manifest: SourceManifest
    fixture_source_manifest: SourceManifest
    platform_fixture_source_manifest: SourceManifest


@dataclass(frozen=True)
class _GoStdlibBuildLane:
    adapter_root: Path
    fixture_root: Path
    platform_fixture_root: Path
    adapter_entry: Path
    fixture_entry: Path
    platform_fixture_entry: Path
    environment: dict[str, str]
    adapter_source_manifest: SourceManifest
    fixture_source_manifest: SourceManifest
    platform_fixture_source_manifest: SourceManifest


def _run(
    command: tuple[str, ...],
    cwd: Path,
    environment: dict[str, str],
    *,
    display_command: str | None = None,
    expected_returncode: int = 0,
) -> None:
    print(f"cwd: {cwd}", flush=True)
    print(f"command: {display_command or shlex.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
    )
    if completed.returncode != expected_returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
        )


def _run_text(
    command: tuple[str, ...],
    cwd: Path,
    environment: dict[str, str],
) -> str:
    print(f"cwd: {cwd}", flush=True)
    print(f"command: {shlex.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    if process.stdout is None:
        process.kill()
        process.wait()
        raise PackageContractError("observable command has no output stream")
    output: list[str] = []
    for line in process.stdout:
        print(line, end="", flush=True)
        output.append(line)
    returncode = process.wait()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, command)
    return "".join(output).strip()


def _wheel_in(directory: Path) -> Path:
    wheels = tuple(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise PackageContractError(
            f"expected one wheel in {directory}, found {len(wheels)}"
        )
    return wheels[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_reproducible(first: Path, second: Path) -> str:
    first_hash = _sha256(first)
    second_hash = _sha256(second)
    print(f"wheel-a-sha256={first_hash}", flush=True)
    print(f"wheel-b-sha256={second_hash}", flush=True)
    if first.read_bytes() != second.read_bytes():
        raise PackageContractError(
            f"wheel builds are not byte-reproducible: {first_hash} != {second_hash}"
        )
    return first_hash


def _assert_wheel_assets(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = sorted(EXPECTED_WHEEL_ASSETS - names)
    if missing:
        raise PackageContractError(f"wheel is missing runtime assets: {missing}")
    actual_runtime_assets = {
        name
        for name in names
        if name.startswith("ucf/")
        and not name.endswith("/")
        and not name.endswith(".py")
    }
    if actual_runtime_assets != EXPECTED_WHEEL_ASSETS:
        raise PackageContractError(
            "wheel runtime asset inventory differs from its closed contract: "
            f"{sorted(actual_runtime_assets)}"
        )
    actual_kit_assets = {
        name for name in names if name.startswith("ucf/adapter_conformance/assets/v1/")
    }
    if actual_kit_assets != EXPECTED_CONFORMANCE_KIT_ASSETS:
        raise PackageContractError(
            "wheel conformance kit inventory differs from its closed "
            f"contract: {sorted(actual_kit_assets)}"
        )
    actual_schema_assets = {name for name in names if name.startswith("ucf/schemas/")}
    if actual_schema_assets != EXPECTED_SCHEMA_ASSETS:
        raise PackageContractError(
            "wheel schema inventory differs from its closed contract: "
            f"{sorted(actual_schema_assets)}"
        )
    print(f"wheel-assets={sorted(EXPECTED_WHEEL_ASSETS)}", flush=True)


def _assert_go_stdlib_is_external(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    forbidden = [
        name
        for name in names
        if (
            name.endswith(".go")
            or name.endswith("/go.mod")
            or "go-stdlib" in name
            or "go_stdlib" in name
            or PurePosixPath(name).name
            in {
                "ucf-go-stdlib-adapter",
                "legacy-quote-server",
                "legacy-platforms",
            }
            or name.endswith("/third_party/go/LICENSE")
            or name.endswith("/third_party/go/PATENTS")
        )
    ]
    if forbidden:
        raise PackageContractError(
            "external Go source, binary, or notices leaked into the Python "
            f"wheel: {sorted(forbidden)}"
        )
    print("go-stdlib-assets-in-wheel=0", flush=True)


def _assert_python_pytest_is_external(
    wheel: Path,
    repository_root: Path,
) -> None:
    adapter = repository_root / "adapters" / "python-pytest" / "adapter.py"
    request_fixture = (
        repository_root
        / "tests"
        / "fixtures"
        / "generation"
        / "v1"
        / "positive"
        / "request.json"
    )
    external_payloads = {
        "adapter": adapter.read_bytes(),
        "request fixture": request_fixture.read_bytes(),
    }
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        forbidden_names = [
            name
            for name in names
            if "python-pytest" in name
            or "fixtures/generation" in name
            or "fixtures\\generation" in name
        ]
        if forbidden_names:
            raise PackageContractError(
                "external Python/pytest generation assets leaked into the "
                f"wheel: {sorted(forbidden_names)}"
            )
        for label, payload in external_payloads.items():
            if any(archive.read(name) == payload for name in names):
                raise PackageContractError(
                    f"external Python/pytest {label} leaked into the wheel"
                )
    print("python-pytest-generation-assets-in-wheel=0", flush=True)


def _assert_runtime_fixture_is_external(
    wheel: Path,
    repository_root: Path,
) -> None:
    fixture_directory = (
        repository_root
        / "tests"
        / "fixtures"
        / "runtime_evidence"
        / "recorded_trace_v1"
    )
    recording = json.loads(
        (fixture_directory / "recording.json").read_text(encoding="utf-8")
    )
    try:
        attributes = recording["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
            "attributes"
        ]
        values = {item["key"]: item["value"]["stringValue"] for item in attributes}
        forbidden = (
            values["fixture.secret"].encode(),
            values["fixture.personal"].encode(),
        )
    except (KeyError, TypeError, IndexError) as error:
        raise PackageContractError(
            "runtime privacy fixture structure is invalid"
        ) from error

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if any(
            "recorded_trace_v1" in name
            or name.endswith("runtime_evidence_reference_adapter.py")
            for name in names
        ):
            raise PackageContractError(
                "runtime recording or fixture adapter leaked into the wheel"
            )
        if any(value in archive.read(name) for name in names for value in forbidden):
            raise PackageContractError(
                "a forbidden runtime fixture value leaked into the wheel"
            )
    print("runtime-fixture-assets-in-wheel=0", flush=True)
    print("runtime-forbidden-values-in-wheel=0", flush=True)


def _isolated_environment(environment: dict[str, str]) -> dict[str, str]:
    isolated = environment.copy()
    isolated.pop("PYTHONHOME", None)
    isolated.pop("PYTHONPATH", None)
    isolated.pop("VIRTUAL_ENV", None)
    isolated["PYTHONNOUSERSITE"] = "1"
    return isolated


def _venv_executable(venv: Path, name: str) -> Path:
    bin_directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return venv / bin_directory / f"{name}{suffix}"


def _tree_manifest(root: Path) -> tuple[tuple[object, ...], ...]:
    pending = [root]
    entries: list[tuple[object, ...]] = []
    while pending:
        path = pending.pop()
        metadata = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISDIR(metadata.st_mode):
            kind = "directory"
            digest = None
            target = None
            children = sorted(path.iterdir(), key=lambda item: item.name)
            pending.extend(reversed(children))
        elif stat.S_ISREG(metadata.st_mode):
            kind = "file"
            digest = _sha256(path)
            target = None
        elif stat.S_ISLNK(metadata.st_mode):
            kind = "symlink"
            digest = None
            target = os.readlink(path)
        else:
            kind = "other"
            digest = None
            target = None
        entries.append(
            (
                relative,
                kind,
                mode,
                metadata.st_size,
                digest,
                target,
            )
        )
    return tuple(entries)


def _content_manifest(root: Path) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            _sha256(path),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _go_stdlib_build_environment(
    environment: dict[str, str],
    workspace: Path,
) -> dict[str, str]:
    isolated = environment.copy()
    directories = {
        "GOCACHE": workspace / "cache",
        "GOMODCACHE": workspace / "module-cache",
        "GOPATH": workspace / "gopath",
        "GOTMPDIR": workspace / "tmp",
    }
    for directory in directories.values():
        directory.mkdir(parents=True)
    isolated.update(
        {
            "CGO_ENABLED": "0",
            "GOARCH": "amd64",
            "GOAMD64": "v1",
            "GOENV": "off",
            "GOEXPERIMENT": "",
            "GOFLAGS": "",
            "GOOS": "linux",
            "GOSUMDB": "off",
            "GOTELEMETRY": "off",
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOPROXY": "off",
            **{name: str(directory) for name, directory in directories.items()},
        }
    )
    return isolated


def _validate_go_stdlib_module(
    *,
    go_bin: Path,
    module_root: Path,
    expected_module: str,
    environment: dict[str, str],
) -> None:
    _run(
        (str(go_bin), "mod", "tidy", "-diff"),
        module_root,
        environment,
    )
    _run((str(go_bin), "mod", "verify"), module_root, environment)
    modules = _run_text(
        (str(go_bin), "list", "-mod=readonly", "-m", "all"),
        module_root,
        environment,
    )
    if modules != expected_module:
        raise PackageContractError(
            f"Go module graph is not the exact zero-external-module graph: {modules!r}"
        )
    _run(
        (str(go_bin), "vet", "-mod=readonly", "./..."),
        module_root,
        environment,
    )
    _run(
        (
            str(go_bin),
            "test",
            "-count=1",
            "-mod=readonly",
            "-trimpath",
            "-buildvcs=false",
            "./...",
        ),
        module_root,
        environment,
    )


def _build_go_stdlib_binary(
    *,
    go_bin: Path,
    module_root: Path,
    target: str,
    output: Path,
    environment: dict[str, str],
) -> None:
    _run(
        (
            str(go_bin),
            "build",
            *GO_STDLIB_BUILD_FLAGS,
            "-o",
            str(output),
            target,
        ),
        module_root,
        environment,
    )
    try:
        metadata = output.lstat()
        resolved = output.resolve(strict=True)
    except OSError as error:
        raise PackageContractError(
            f"Go build output is unavailable: {output.name}"
        ) from error
    if (
        resolved != output
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size < 1
        or not metadata.st_mode & stat.S_IXUSR
    ):
        raise PackageContractError(
            f"Go build output is not one regular executable: {output.name}"
        )


def _assert_go_stdlib_build_info(
    *,
    go_bin: Path,
    entry: Path,
    module_path: str,
    package_path: str,
    environment: dict[str, str],
) -> None:
    output = _run_text(
        (str(go_bin), "version", "-m", str(entry)),
        entry.parent,
        environment,
    )
    lines = output.splitlines()
    expected_metadata = [
        f"\tpath\t{package_path}",
        f"\tmod\t{module_path}\t(devel)\t",
        "\tbuild\t-buildmode=exe",
        "\tbuild\t-compiler=gc",
        "\tbuild\t-trimpath=true",
        "\tbuild\tCGO_ENABLED=0",
        "\tbuild\tGOARCH=amd64",
        "\tbuild\tGOOS=linux",
        "\tbuild\tGOAMD64=v1",
    ]
    if (
        len(lines) != 10
        or lines[0] != f"{entry}: go1.26.5"
        or lines[1:] != expected_metadata
    ):
        raise PackageContractError(
            f"go version -m metadata is not exact for {entry.name}"
        )


def _copy_go_stdlib_notices(
    *,
    adapter_root: Path,
    distribution_root: Path,
) -> None:
    source_root = adapter_root / "third_party" / "go"
    destination_root = distribution_root / "third_party" / "go"
    destination_root.mkdir(parents=True)
    (distribution_root / "third_party").chmod(0o755)
    destination_root.chmod(0o755)
    for name, expected_digest in GO_STDLIB_NOTICE_DIGESTS.items():
        source = source_root / name
        if _sha256(source) != expected_digest:
            raise PackageContractError(f"Go upstream notice is not exact: {name}")
        destination = destination_root / name
        shutil.copyfile(source, destination)
        destination.chmod(0o644)
        if _sha256(destination) != expected_digest:
            raise PackageContractError(
                f"distributed Go upstream notice differs: {name}"
            )


def _assert_go_stdlib_distribution_tree(root: Path) -> None:
    manifest = _tree_manifest(root)
    actual = {entry[0]: (entry[1], entry[2], entry[4]) for entry in manifest}
    expected = {
        ".": ("directory", 0o755, None),
        "third_party": ("directory", 0o755, None),
        "third_party/go": ("directory", 0o755, None),
        "third_party/go/LICENSE": (
            "file",
            0o644,
            GO_STDLIB_NOTICE_DIGESTS["LICENSE"],
        ),
        "third_party/go/PATENTS": (
            "file",
            0o644,
            GO_STDLIB_NOTICE_DIGESTS["PATENTS"],
        ),
        "ucf-go-stdlib-adapter": (
            "file",
            0o755,
            _sha256(root / "ucf-go-stdlib-adapter"),
        ),
    }
    if actual != expected:
        raise PackageContractError(
            f"Go adapter distribution inventory is not exact: {sorted(actual.items())}"
        )


def _prepare_installed_go_stdlib_adapter(
    *,
    repository_root: Path,
    workspace: Path,
    environment: dict[str, str],
) -> _GoStdlibDistribution:
    go_bin = resolve_go_stdlib_binary(environment)
    source_adapter = repository_root / "adapters" / "go-stdlib"
    source_fixture = (
        repository_root / "tests" / "fixtures" / "brownfield" / "go_stdlib_legacy_quote"
    )
    source_platform_fixture = (
        repository_root
        / "tests"
        / "fixtures"
        / "brownfield"
        / "go_stdlib_legacy_platforms"
    )
    source_adapter_before = go_stdlib_adapter_manifest(source_adapter)
    source_fixture_before = go_stdlib_fixture_manifest(source_fixture)
    source_platform_fixture_before = go_stdlib_platform_manifest(
        source_platform_fixture
    )
    if (
        go_stdlib_platform_source_revision(source_platform_fixture_before)
        != GO_STDLIB_PLATFORM_SOURCE_REVISION
    ):
        raise PackageContractError("Go platform fixture source revision is not frozen")

    build_root = workspace / "go-stdlib-external-build"
    build_root.mkdir()
    lane_data: list[_GoStdlibBuildLane] = []
    for lane in ("a", "b"):
        adapter_root = build_root / f"adapter-{lane}"
        fixture_root = build_root / f"fixture-{lane}"
        platform_fixture_root = build_root / f"platform-fixture-{lane}"
        distribution_root = build_root / f"distribution-{lane}"
        verification_root = build_root / f"verification-{lane}"
        distribution_root.mkdir()
        distribution_root.chmod(0o755)
        verification_root.mkdir()
        copied_adapter = copy_go_stdlib_adapter(
            source_adapter,
            adapter_root,
        )
        copied_fixture = copy_go_stdlib_fixture(
            source_fixture,
            fixture_root,
        )
        copied_platform_fixture = copy_go_stdlib_platform_fixture(
            source_platform_fixture,
            platform_fixture_root,
        )
        if (
            go_stdlib_platform_source_revision(copied_platform_fixture)
            != GO_STDLIB_PLATFORM_SOURCE_REVISION
        ):
            raise PackageContractError(
                "copied Go platform fixture revision is not frozen"
            )
        go_environment = _go_stdlib_build_environment(
            environment,
            build_root / f"go-work-{lane}",
        )
        version = _run_text(
            (str(go_bin), "version"),
            adapter_root,
            go_environment,
        )
        if f"{version}\n" != GO_STDLIB_VERSION_OUTPUT:
            raise PackageContractError(
                f"Go distribution toolchain is incompatible: {version!r}"
            )
        for module_root, module_path in (
            (adapter_root, "ucf/adapters/go-stdlib"),
            (fixture_root, "example.com/legacyquotes"),
            (
                platform_fixture_root,
                "example.com/legacyplatforms",
            ),
        ):
            _validate_go_stdlib_module(
                go_bin=go_bin,
                module_root=module_root,
                expected_module=module_path,
                environment=go_environment,
            )

        adapter_entry = distribution_root / "ucf-go-stdlib-adapter"
        fixture_entry = verification_root / "legacy-quote-server"
        platform_fixture_entry = verification_root / "legacy-platforms"
        _build_go_stdlib_binary(
            go_bin=go_bin,
            module_root=adapter_root,
            target="./cmd/adapter",
            output=adapter_entry,
            environment=go_environment,
        )
        _build_go_stdlib_binary(
            go_bin=go_bin,
            module_root=fixture_root,
            target="./cmd/server",
            output=fixture_entry,
            environment=go_environment,
        )
        _build_go_stdlib_binary(
            go_bin=go_bin,
            module_root=platform_fixture_root,
            target="./cmd/platform",
            output=platform_fixture_entry,
            environment=go_environment,
        )
        adapter_entry.chmod(0o755)
        fixture_entry.chmod(0o755)
        platform_fixture_entry.chmod(0o755)
        _copy_go_stdlib_notices(
            adapter_root=adapter_root,
            distribution_root=distribution_root,
        )
        _assert_go_stdlib_distribution_tree(distribution_root)
        _assert_go_stdlib_build_info(
            go_bin=go_bin,
            entry=adapter_entry,
            module_path="ucf/adapters/go-stdlib",
            package_path="ucf/adapters/go-stdlib/cmd/adapter",
            environment=go_environment,
        )
        _assert_go_stdlib_build_info(
            go_bin=go_bin,
            entry=fixture_entry,
            module_path="example.com/legacyquotes",
            package_path="example.com/legacyquotes/cmd/server",
            environment=go_environment,
        )
        platform_metadata = _run_text(
            (
                str(go_bin),
                "version",
                "-m",
                str(platform_fixture_entry),
            ),
            verification_root,
            go_environment,
        )
        try:
            validate_go_stdlib_platform_build_metadata(
                platform_metadata,
                executable=platform_fixture_entry,
            )
        except GoSourceContractError as error:
            raise PackageContractError(
                "Go platform fixture build metadata is not exact"
            ) from error
        if _sha256(platform_fixture_entry) != GO_STDLIB_PLATFORM_BINARY_SHA256:
            raise PackageContractError(
                "Go platform fixture binary differs from the frozen build"
            )
        lane_data.append(
            _GoStdlibBuildLane(
                adapter_root=adapter_root,
                fixture_root=fixture_root,
                platform_fixture_root=platform_fixture_root,
                adapter_entry=adapter_entry,
                fixture_entry=fixture_entry,
                platform_fixture_entry=platform_fixture_entry,
                environment=go_environment,
                adapter_source_manifest=copied_adapter,
                fixture_source_manifest=copied_fixture,
                platform_fixture_source_manifest=(copied_platform_fixture),
            )
        )

    first = lane_data[0]
    second = lane_data[1]
    if first.adapter_entry.read_bytes() != second.adapter_entry.read_bytes():
        raise PackageContractError("Go adapter builds are not byte-identical")
    if first.fixture_entry.read_bytes() != second.fixture_entry.read_bytes():
        raise PackageContractError("Go fixture builds are not byte-identical")
    if (
        first.platform_fixture_entry.read_bytes()
        != second.platform_fixture_entry.read_bytes()
    ):
        raise PackageContractError("Go platform fixture builds are not byte-identical")
    first_distribution = first.adapter_entry.parent
    second_distribution = second.adapter_entry.parent
    first_distribution_manifest = {
        entry[0]: (entry[1], entry[2], entry[4], entry[5])
        for entry in _tree_manifest(first_distribution)
    }
    second_distribution_manifest = {
        entry[0]: (entry[1], entry[2], entry[4], entry[5])
        for entry in _tree_manifest(second_distribution)
    }
    if first_distribution_manifest != second_distribution_manifest:
        raise PackageContractError("Go adapter distributions are not byte-identical")

    for lane in lane_data:
        if (
            go_stdlib_adapter_manifest(lane.adapter_root)
            != lane.adapter_source_manifest
            or go_stdlib_fixture_manifest(lane.fixture_root)
            != lane.fixture_source_manifest
            or go_stdlib_platform_manifest(lane.platform_fixture_root)
            != lane.platform_fixture_source_manifest
        ):
            raise PackageContractError("Go copied source changed during external build")
    if (
        go_stdlib_adapter_manifest(source_adapter) != source_adapter_before
        or go_stdlib_fixture_manifest(source_fixture) != source_fixture_before
        or go_stdlib_platform_manifest(source_platform_fixture)
        != source_platform_fixture_before
    ):
        raise PackageContractError("Go repository source changed during external build")

    print(
        f"go-stdlib-adapter-sha256={_sha256(first.adapter_entry)}",
        flush=True,
    )
    print(
        f"go-stdlib-fixture-sha256={_sha256(first.fixture_entry)}",
        flush=True,
    )
    print(
        f"go-stdlib-platform-fixture-sha256={_sha256(first.platform_fixture_entry)}",
        flush=True,
    )
    return _GoStdlibDistribution(
        adapter_root=first.adapter_root,
        adapter_entry=first.adapter_entry,
        fixture_entry=first.fixture_entry,
        fixture_root=first.fixture_root,
        platform_fixture_entry=first.platform_fixture_entry,
        platform_fixture_root=first.platform_fixture_root,
        adapter_source_manifest=first.adapter_source_manifest,
        fixture_source_manifest=first.fixture_source_manifest,
        platform_fixture_source_manifest=(first.platform_fixture_source_manifest),
    )


def _one_local_npm_tarball(directory: Path) -> Path:
    tarballs = tuple(directory.glob("*.tgz"))
    if len(tarballs) != 1:
        raise PackageContractError(
            f"expected one local npm tarball in {directory}, found {len(tarballs)}"
        )
    return tarballs[0]


def _expected_typescript_fastify_tar_members(
    source_manifest: SourceManifest,
) -> frozenset[str]:
    generated = {
        "package/dist/" + relative.removeprefix("src/").removesuffix(".ts") + ".js"
        for relative, _, _ in source_manifest
        if relative.startswith("src/") and relative.endswith(".ts")
    }
    if "package/dist/main.js" not in generated:
        raise PackageContractError(
            "TypeScript/Fastify source manifest has no main entry"
        )
    return frozenset(
        {
            "package/README.md",
            "package/package.json",
            *generated,
        }
    )


def _read_typescript_fastify_tarball(
    tarball: Path,
    *,
    adapter_root: Path,
    source_manifest: SourceManifest,
) -> dict[str, bytes]:
    try:
        metadata = tarball.lstat()
        resolved = tarball.resolve(strict=True)
    except OSError as error:
        raise PackageContractError(
            "local TypeScript/Fastify tarball is unavailable"
        ) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or resolved != tarball
        or metadata.st_size > MAX_TYPESCRIPT_FASTIFY_TARBALL_BYTES
    ):
        raise PackageContractError(
            "local TypeScript/Fastify tarball is not one bounded regular file"
        )

    expected = _expected_typescript_fastify_tar_members(source_manifest)
    payloads: dict[str, bytes] = {}
    total_size = 0
    try:
        with tarfile.open(tarball, mode="r:gz") as archive:
            for member in archive.getmembers():
                portable = PurePosixPath(member.name)
                if (
                    portable.is_absolute()
                    or portable.as_posix() != member.name
                    or any(part in {"", ".", ".."} for part in portable.parts)
                    or not member.isreg()
                    or member.name in payloads
                ):
                    raise PackageContractError(
                        "local TypeScript/Fastify tarball has an unsafe member"
                    )
                total_size += member.size
                if (
                    member.size > MAX_TYPESCRIPT_FASTIFY_TARBALL_BYTES
                    or total_size > MAX_TYPESCRIPT_FASTIFY_TARBALL_BYTES
                ):
                    raise PackageContractError(
                        "local TypeScript/Fastify tarball is too large"
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise PackageContractError(
                        "local TypeScript/Fastify tar member is unreadable"
                    )
                payload = extracted.read(MAX_TYPESCRIPT_FASTIFY_TARBALL_BYTES + 1)
                if len(payload) != member.size:
                    raise PackageContractError(
                        "local TypeScript/Fastify tar member size changed"
                    )
                payloads[member.name] = payload
    except (OSError, tarfile.TarError) as error:
        raise PackageContractError(
            "local TypeScript/Fastify tarball is invalid"
        ) from error

    if frozenset(payloads) != expected:
        raise PackageContractError(
            f"local TypeScript/Fastify tar inventory is not exact: {sorted(payloads)}"
        )
    for member_name, payload in payloads.items():
        source_path = adapter_root.joinpath(
            *PurePosixPath(member_name.removeprefix("package/")).parts
        )
        try:
            built_payload = source_path.read_bytes()
        except OSError as error:
            raise PackageContractError(
                f"built npm input is unavailable: {member_name}"
            ) from error
        if payload != built_payload:
            raise PackageContractError(
                f"packed npm file differs from the external build: {member_name}"
            )

    try:
        package = json.loads(payloads["package/package.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PackageContractError(
            "packed TypeScript/Fastify package metadata is invalid"
        ) from error
    if (
        package.get("name") != TYPESCRIPT_FASTIFY_ADAPTER_NAME
        or package.get("version") != TYPESCRIPT_FASTIFY_ADAPTER_VERSION
        or package.get("private") is not True
        or package.get("files") != ["dist"]
        or package.get("bin") != {TYPESCRIPT_FASTIFY_ADAPTER_BIN: "dist/main.js"}
    ):
        raise PackageContractError(
            "packed TypeScript/Fastify package metadata is not exact"
        )
    for dependency_field in (
        "dependencies",
        "optionalDependencies",
        "peerDependencies",
        "bundledDependencies",
    ):
        if package.get(dependency_field):
            raise PackageContractError(
                "packed TypeScript/Fastify adapter has runtime dependencies"
            )
    return payloads


def _assert_installed_typescript_fastify_tree(
    consumer_root: Path,
    *,
    archive_payloads: dict[str, bytes],
) -> Path:
    node_modules = consumer_root / "node_modules"
    package_prefix = PurePosixPath("node_modules/@ucf/typescript-fastify-adapter")
    expected_files = {"node_modules/.package-lock.json"}
    expected_directories = {
        "node_modules",
        "node_modules/.bin",
        "node_modules/@ucf",
        package_prefix.as_posix(),
    }
    for archive_name in archive_payloads:
        relative = PurePosixPath(archive_name).relative_to("package")
        installed = package_prefix / relative
        expected_files.add(installed.as_posix())
        for parent in installed.parents:
            if parent.as_posix() in {".", "node_modules"}:
                break
            expected_directories.add(parent.as_posix())
    expected_links = {f"node_modules/.bin/{TYPESCRIPT_FASTIFY_ADAPTER_BIN}"}

    actual = {
        f"node_modules/{relative}" if relative != "." else "node_modules": (
            kind,
            target,
        )
        for relative, kind, _, _, _, target in _tree_manifest(node_modules)
    }
    actual_files = {path for path, (kind, _) in actual.items() if kind == "file"}
    actual_directories = {
        path for path, (kind, _) in actual.items() if kind == "directory"
    }
    actual_links = {path for path, (kind, _) in actual.items() if kind == "symlink"}
    actual_other = {
        path
        for path, (kind, _) in actual.items()
        if kind not in {"directory", "file", "symlink"}
    }
    if (
        actual_files != expected_files
        or actual_directories != expected_directories
        or actual_links != expected_links
        or actual_other
    ):
        raise PackageContractError(
            "offline-installed TypeScript/Fastify tree is not exact"
        )

    bin_path = node_modules / ".bin" / TYPESCRIPT_FASTIFY_ADAPTER_BIN
    expected_target = "../@ucf/typescript-fastify-adapter/dist/main.js"
    if os.readlink(bin_path) != expected_target:
        raise PackageContractError(
            "offline-installed TypeScript/Fastify bin target is not exact"
        )

    installed_package = node_modules / "@ucf" / "typescript-fastify-adapter"
    for archive_name, payload in archive_payloads.items():
        relative = PurePosixPath(archive_name).relative_to("package")
        installed_path = installed_package.joinpath(*relative.parts)
        if installed_path.read_bytes() != payload:
            raise PackageContractError(
                f"offline-installed npm file differs: {relative.as_posix()}"
            )

    try:
        hidden_lock = json.loads(
            (node_modules / ".package-lock.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise PackageContractError(
            "offline-installed npm lock metadata is invalid"
        ) from error
    if hidden_lock.get("lockfileVersion") != 3 or set(
        hidden_lock.get("packages", {})
    ) != {"node_modules/@ucf/typescript-fastify-adapter"}:
        raise PackageContractError(
            "offline install resolved packages outside the local adapter"
        )

    entry = installed_package / "dist" / "main.js"
    metadata = entry.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or not metadata.st_mode & stat.S_IXUSR
        or not entry.read_bytes().startswith(b"#!/usr/bin/env node\n")
    ):
        raise PackageContractError(
            "offline-installed TypeScript/Fastify entry is not executable"
        )
    return entry


def _prepare_installed_typescript_fastify_adapter(
    *,
    repository_root: Path,
    workspace: Path,
    environment: dict[str, str],
) -> tuple[Path, Path, SourceManifest]:
    source_adapter = repository_root / "adapters" / "typescript-fastify"
    source_fixture = (
        repository_root
        / "tests"
        / "fixtures"
        / "brownfield"
        / "typescript_fastify_legacy_quote"
    )
    source_adapter_before = typescript_fastify_adapter_manifest(source_adapter)
    source_fixture_before = typescript_fastify_fixture_manifest(source_fixture)

    distribution = workspace / "typescript-fastify-distribution"
    distribution.mkdir()
    adapter_root = distribution / "adapter-build"
    fixture_root = distribution / "legacy-fixture"
    copied_adapter = copy_typescript_fastify_adapter(
        source_adapter,
        adapter_root,
    )
    copied_fixture = copy_typescript_fastify_fixture(
        source_fixture,
        fixture_root,
    )

    node_version = _run_text(
        ("node", "--version"),
        adapter_root,
        environment,
    )
    npm_version = _run_text(
        ("npm", "--version"),
        adapter_root,
        environment,
    )
    if (
        node_version != TYPESCRIPT_FASTIFY_NODE_VERSION
        or npm_version != TYPESCRIPT_FASTIFY_NPM_VERSION
    ):
        raise PackageContractError(
            "TypeScript/Fastify distribution toolchain is incompatible: "
            f"node={node_version!r}, npm={npm_version!r}"
        )

    adapter_test_environment = environment.copy()
    adapter_test_environment["UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT"] = str(fixture_root)
    _run(
        ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
        adapter_root,
        adapter_test_environment,
    )
    _run(("npm", "run", "build"), adapter_root, adapter_test_environment)
    _run(("npm", "test"), adapter_root, adapter_test_environment)
    if (
        typescript_fastify_adapter_manifest(source_adapter) != source_adapter_before
        or typescript_fastify_adapter_manifest(adapter_root) != copied_adapter
    ):
        raise PackageContractError(
            "TypeScript/Fastify adapter source changed during external build"
        )

    tar_directories = (
        distribution / "npm-pack-a",
        distribution / "npm-pack-b",
    )
    for tar_directory in tar_directories:
        tar_directory.mkdir()
        _run(
            (
                "npm",
                "pack",
                "--ignore-scripts",
                "--pack-destination",
                str(tar_directory),
            ),
            adapter_root,
            adapter_test_environment,
            display_command=("npm pack --ignore-scripts --pack-destination <external>"),
        )
    tarballs = tuple(_one_local_npm_tarball(directory) for directory in tar_directories)
    first_payloads = _read_typescript_fastify_tarball(
        tarballs[0],
        adapter_root=adapter_root,
        source_manifest=copied_adapter,
    )
    second_payloads = _read_typescript_fastify_tarball(
        tarballs[1],
        adapter_root=adapter_root,
        source_manifest=copied_adapter,
    )
    if (
        tarballs[0].read_bytes() != tarballs[1].read_bytes()
        or first_payloads != second_payloads
    ):
        raise PackageContractError(
            "local TypeScript/Fastify npm tarballs are not reproducible"
        )
    print(
        f"typescript-fastify-tarball-sha256={_sha256(tarballs[0])}",
        flush=True,
    )

    if (
        typescript_fastify_fixture_manifest(source_fixture) != source_fixture_before
        or typescript_fastify_fixture_manifest(fixture_root) != copied_fixture
    ):
        raise PackageContractError(
            "TypeScript/Fastify fixture source changed during native build"
        )

    consumer_root = distribution / "offline-consumer"
    consumer_root.mkdir()
    (consumer_root / "package.json").write_text(
        json.dumps(
            {
                "name": "ucf-installed-adapter-smoke",
                "private": True,
                "version": "1.0.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    _run(
        (
            "npm",
            "install",
            "--offline",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "--omit=dev",
            str(tarballs[0]),
        ),
        consumer_root,
        environment,
    )
    installed_entry = _assert_installed_typescript_fastify_tree(
        consumer_root,
        archive_payloads=first_payloads,
    )
    return installed_entry, fixture_root, copied_fixture


def _onboarding_cli_command(
    *,
    ucf: Path,
    operation: str,
    root: Path,
    policy: Path,
    output: Path,
    python: Path,
    adapter: Path,
    page_record_limit: int,
    decisions: Path | None = None,
    mode: str = "normal",
) -> tuple[str, ...]:
    command = [
        str(ucf),
        "adapter",
        operation,
        str(root),
        "--policy",
        str(policy),
    ]
    if decisions is not None:
        command.extend(("--decisions", str(decisions)))
    command.extend(
        (
            "--output",
            str(output),
            "--subject-uri",
            "urn:ucf:repository:installed-python-legacy-quote",
            "--page-record-limit",
            str(page_record_limit),
            "--operation-timeout",
            "5",
            "--",
            str(python),
            "-B",
            "-X",
            "utf8",
            str(adapter),
            "--mode",
            mode,
        )
    )
    return tuple(command)


def _ratchet_cli_command(
    *,
    ucf: Path,
    operation: str,
    policy: Path,
    bundle: Path,
    assessment: Path,
    output: Path,
    baseline: Path | None = None,
    evaluation: Path | None = None,
) -> tuple[str, ...]:
    command = [
        str(ucf),
        "ratchet",
        operation,
        "--policy",
        str(policy),
        "--onboarding-bundle",
        str(bundle),
        "--assessment",
        str(assessment),
    ]
    if baseline is not None:
        command.extend(("--baseline", str(baseline)))
    if evaluation is not None:
        command.extend(("--evaluation", str(evaluation)))
    command.extend(("--output", str(output)))
    return tuple(command)


def _ratchet_v2_cli_command(
    *,
    ucf: Path,
    operation: str,
    policy: Path,
    bundle: Path,
    assessment: Path,
    output: Path,
    baseline: Path | None = None,
    accepted_baseline_id: str | None = None,
    evaluation: Path | None = None,
) -> tuple[str, ...]:
    command = [
        str(ucf),
        "ratchet",
        "v2",
        operation,
        "--policy",
        str(policy),
        "--onboarding-bundle",
        str(bundle),
        "--assessment",
        str(assessment),
    ]
    if baseline is not None:
        command.extend(("--baseline", str(baseline)))
    if accepted_baseline_id is not None:
        command.extend(
            ("--accepted-baseline-id", accepted_baseline_id)
        )
    if evaluation is not None:
        command.extend(("--evaluation", str(evaluation)))
    command.extend(("--output", str(output)))
    return tuple(command)


def _read_bounded_ratchet_document(path: Path, *, label: str) -> bytes:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise PackageContractError(f"{label} is not a regular file")
        with path.open("rb") as stream:
            payload = stream.read(MAX_INSTALLED_RATCHET_DOCUMENT_BYTES + 1)
    except OSError as error:
        raise PackageContractError(f"{label} is unavailable") from error
    if len(payload) > MAX_INSTALLED_RATCHET_DOCUMENT_BYTES:
        raise PackageContractError(f"{label} exceeds the document limit")
    return payload


def _bounded_ratchet_document_id(path: Path, *, label: str) -> str:
    payload = _read_bounded_ratchet_document(path, label=label)
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageContractError(f"{label} is not valid JSON") from error
    identifier = document.get("id") if isinstance(document, dict) else None
    if (
        not isinstance(identifier, str)
        or not identifier.startswith("baseline.")
        or len(identifier) != len("baseline.") + 64
        or any(character not in "0123456789abcdef" for character in identifier[9:])
    ):
        raise PackageContractError(f"{label} has an invalid baseline ID")
    return identifier


def _runtime_evidence_cli_command(
    *,
    ucf: Path,
    python: Path,
    adapter: Path,
    adapter_cwd: Path,
    recording: Path,
    policy: Path,
    environment: Path,
    behavior: Path,
    output: Path,
    mode: str = "normal",
) -> tuple[str, ...]:
    return (
        str(ucf),
        "adapter",
        "import-runtime-evidence",
        "--recording",
        str(recording),
        "--policy",
        str(policy),
        "--environment",
        str(environment),
        "--behavior-ir",
        str(behavior),
        "--source-uri",
        "urn:ucf:runtime-recording:fixture-v1",
        "--captured-at",
        "2026-07-19T08:30:00Z",
        "--sampling-procedure-uri",
        "urn:ucf:runtime-sampling:recorded-partial:1.0.0",
        "--adapter-procedure-uri",
        "urn:ucf:fixture-adapter:runtime-evidence:1.0.0",
        "--adapter-cwd",
        str(adapter_cwd),
        "--output",
        str(output),
        "--operation-timeout",
        "5",
        "--",
        str(python),
        "-I",
        "-B",
        "-X",
        "utf8",
        str(adapter),
        str(recording),
        "--mode",
        mode,
    )


def _smoke_installed_ratchet(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    bundle: Path,
    environment: dict[str, str],
) -> None:
    policy = run_directory / "ratchet-policy.json"
    initial = run_directory / "ratchet-assessment-initial.json"
    resolved = run_directory / "ratchet-assessment-resolved.json"
    regression = run_directory / "ratchet-assessment-regression.json"
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_RATCHET_AUTHOR,
            str(bundle),
            str(policy),
            str(initial),
            str(resolved),
            str(regression),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-ratchet-author> "
            f"{shlex.quote(str(bundle))} <ratchet-documents>"
        ),
    )

    baseline_a = run_directory / "ratchet-baseline-a.json"
    baseline_b = run_directory / "ratchet-baseline-b.json"
    for baseline in (baseline_a, baseline_b):
        _run(
            _ratchet_cli_command(
                ucf=ucf,
                operation="establish",
                policy=policy,
                bundle=bundle,
                assessment=initial,
                output=baseline,
            ),
            run_directory,
            environment,
        )
    if baseline_a.read_bytes() != baseline_b.read_bytes():
        raise PackageContractError(
            "installed ratchet baseline is not byte-deterministic"
        )
    accepted_baseline = baseline_a.read_bytes()

    pass_report_a = run_directory / "ratchet-pass-report-a.json"
    pass_report_b = run_directory / "ratchet-pass-report-b.json"
    for report in (pass_report_a, pass_report_b):
        _run(
            _ratchet_cli_command(
                ucf=ucf,
                operation="evaluate",
                policy=policy,
                bundle=bundle,
                baseline=baseline_a,
                assessment=initial,
                output=report,
            ),
            run_directory,
            environment,
        )
    if pass_report_a.read_bytes() != pass_report_b.read_bytes():
        raise PackageContractError("installed ratchet report is not byte-deterministic")

    regression_report = run_directory / "ratchet-regression-report.json"
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="evaluate",
            policy=policy,
            bundle=bundle,
            baseline=baseline_a,
            assessment=regression,
            output=regression_report,
        ),
        run_directory,
        environment,
        expected_returncode=1,
    )
    blocked_successor = run_directory / "ratchet-successor-sentinel.json"
    blocked_successor.write_bytes(b"preserve-me")
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="advance",
            policy=policy,
            bundle=bundle,
            baseline=baseline_a,
            assessment=regression,
            evaluation=regression_report,
            output=blocked_successor,
        ),
        run_directory,
        environment,
        expected_returncode=1,
    )
    if blocked_successor.read_bytes() != b"preserve-me":
        raise PackageContractError(
            "blocked installed ratchet advance changed its output"
        )

    resolved_report = run_directory / "ratchet-resolved-report.json"
    successor = run_directory / "ratchet-successor.json"
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="evaluate",
            policy=policy,
            bundle=bundle,
            baseline=baseline_a,
            assessment=resolved,
            output=resolved_report,
        ),
        run_directory,
        environment,
    )
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="advance",
            policy=policy,
            bundle=bundle,
            baseline=baseline_a,
            assessment=resolved,
            evaluation=resolved_report,
            output=successor,
        ),
        run_directory,
        environment,
    )

    reintroduced_report = run_directory / "ratchet-reintroduced-report.json"
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="evaluate",
            policy=policy,
            bundle=bundle,
            baseline=successor,
            assessment=initial,
            output=reintroduced_report,
        ),
        run_directory,
        environment,
        expected_returncode=1,
    )

    invalid_policy = run_directory / "ratchet-invalid-policy.json"
    invalid_policy.write_text(
        policy.read_text(encoding="utf-8").replace(
            '"kind":"ratchet_policy"',
            '"kind":"ratchet_policy","kind":"ratchet_policy"',
            1,
        ),
        encoding="utf-8",
    )
    invalid_output = run_directory / "ratchet-invalid-sentinel.json"
    invalid_output.write_bytes(b"preserve-me")
    _run(
        _ratchet_cli_command(
            ucf=ucf,
            operation="evaluate",
            policy=invalid_policy,
            bundle=bundle,
            baseline=baseline_a,
            assessment=initial,
            output=invalid_output,
        ),
        run_directory,
        environment,
        expected_returncode=3,
    )
    if invalid_output.read_bytes() != b"preserve-me":
        raise PackageContractError("invalid installed ratchet changed its output")
    if baseline_a.read_bytes() != accepted_baseline:
        raise PackageContractError("installed ratchet mutated its accepted baseline")

    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_RATCHET_ASSERT,
            str(baseline_a),
            str(pass_report_a),
            str(regression_report),
            str(successor),
            str(reintroduced_report),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-ratchet-assert> <ratchet-outputs>"
        ),
    )
    _smoke_installed_ratchet_v2(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        bundle=bundle,
        source_policy=policy,
        source_assessment=initial,
        source_baseline=baseline_a,
        environment=environment,
    )
    if baseline_a.read_bytes() != accepted_baseline:
        raise PackageContractError(
            "installed Ratchet v2 smoke mutated its v1 source baseline"
        )
    if tuple(run_directory.glob(".ratchet-*.tmp")):
        raise PackageContractError("failed installed ratchet left temporary output")


def _smoke_installed_ratchet_v2(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    bundle: Path,
    source_policy: Path,
    source_assessment: Path,
    source_baseline: Path,
    environment: dict[str, str],
) -> None:
    source_baseline_before = _read_bounded_ratchet_document(
        source_baseline,
        label="installed Ratchet v1 source baseline",
    )
    target_policy = run_directory / "ratchet-v2-policy.json"
    assessment = run_directory / "ratchet-v2-assessment.json"
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_RATCHET_V2_AUTHOR,
            str(bundle),
            str(source_policy),
            str(target_policy),
            str(assessment),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-ratchet-v2-author> <ratchet-v2-documents>"
        ),
    )

    baseline = run_directory / "ratchet-v2-baseline.json"
    _run(
        _ratchet_v2_cli_command(
            ucf=ucf,
            operation="establish",
            policy=target_policy,
            bundle=bundle,
            assessment=assessment,
            output=baseline,
        ),
        run_directory,
        environment,
    )
    accepted_baseline_id = _bounded_ratchet_document_id(
        baseline,
        label="installed Ratchet v2 baseline",
    )

    report = run_directory / "ratchet-v2-unchanged-report.json"
    _run(
        _ratchet_v2_cli_command(
            ucf=ucf,
            operation="evaluate",
            policy=target_policy,
            bundle=bundle,
            assessment=assessment,
            baseline=baseline,
            accepted_baseline_id=accepted_baseline_id,
            output=report,
        ),
        run_directory,
        environment,
    )
    successor = run_directory / "ratchet-v2-successor.json"
    _run(
        _ratchet_v2_cli_command(
            ucf=ucf,
            operation="advance",
            policy=target_policy,
            bundle=bundle,
            assessment=assessment,
            baseline=baseline,
            accepted_baseline_id=accepted_baseline_id,
            evaluation=report,
            output=successor,
        ),
        run_directory,
        environment,
    )

    accepted_source_id = _bounded_ratchet_document_id(
        source_baseline,
        label="installed Ratchet v1 source baseline",
    )
    migrated = run_directory / "ratchet-v2-migrated-from-v1.json"
    _run(
        (
            str(ucf),
            "ratchet",
            "v2",
            "migrate-from-v1",
            "--target-policy",
            str(target_policy),
            "--source-policy",
            str(source_policy),
            "--source-baseline",
            str(source_baseline),
            "--source-assessment",
            str(source_assessment),
            "--onboarding-bundle",
            str(bundle),
            "--accepted-source-baseline-id",
            accepted_source_id,
            "--output",
            str(migrated),
        ),
        run_directory,
        environment,
    )

    outputs = {
        "target policy": target_policy,
        "assessment": assessment,
        "baseline": baseline,
        "evaluation": report,
        "successor": successor,
        "migration": migrated,
    }
    for label, path in outputs.items():
        _read_bounded_ratchet_document(
            path,
            label=f"installed Ratchet v2 {label}",
        )
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_RATCHET_V2_ASSERT,
            str(source_baseline),
            str(baseline),
            str(report),
            str(successor),
            str(migrated),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-ratchet-v2-assert> <ratchet-v2-outputs>"
        ),
    )
    if _read_bounded_ratchet_document(
        source_baseline,
        label="installed Ratchet v1 source baseline",
    ) != source_baseline_before:
        raise PackageContractError(
            "installed Ratchet v2 transaction mutated its v1 source"
        )


def _smoke_installed_runtime_evidence(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    fixture_directory = run_directory / "runtime-evidence-fixture"
    shutil.copytree(
        repository_root
        / "tests"
        / "fixtures"
        / "runtime_evidence"
        / "recorded_trace_v1",
        fixture_directory,
    )
    behavior = fixture_directory / "behavior.json"
    shutil.copy2(
        repository_root / "tests" / "fixtures" / "ir" / "v1" / "complete.json",
        behavior,
    )
    adapter_directory = run_directory / "external-runtime-adapter"
    adapter_directory.mkdir()
    adapter = adapter_directory / "runtime_evidence_reference_adapter.py"
    shutil.copy2(
        repository_root
        / "tests"
        / "fixtures"
        / "adapters"
        / "runtime_evidence_reference_adapter.py",
        adapter,
    )
    recording = fixture_directory / "recording.json"
    policy = fixture_directory / "policy.json"
    runtime_environment = fixture_directory / "environment.json"
    initial_fixture = _tree_manifest(fixture_directory)
    initial_adapter = _tree_manifest(adapter_directory)

    outputs = (
        run_directory / "runtime-evidence-result-a.json",
        run_directory / "runtime-evidence-result-b.json",
    )
    for output, seed in zip(outputs, ("1", "777"), strict=True):
        _run(
            _runtime_evidence_cli_command(
                ucf=ucf,
                python=python,
                adapter=adapter,
                adapter_cwd=run_directory,
                recording=recording,
                policy=policy,
                environment=runtime_environment,
                behavior=behavior,
                output=output,
            ),
            run_directory,
            {**environment, "PYTHONHASHSEED": seed},
        )
    if outputs[0].read_bytes() != outputs[1].read_bytes():
        raise PackageContractError(
            "installed runtime evidence is not hash-seed deterministic"
        )

    recording_payload = json.loads(recording.read_text(encoding="utf-8"))
    try:
        attributes = recording_payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
            "attributes"
        ]
        attribute_values = {
            item["key"]: item["value"]["stringValue"] for item in attributes
        }
        forbidden = (
            attribute_values["fixture.secret"].encode(),
            attribute_values["fixture.personal"].encode(),
        )
    except (KeyError, TypeError, IndexError) as error:
        raise PackageContractError(
            "installed runtime fixture structure is invalid"
        ) from error
    if any(value in outputs[0].read_bytes() for value in forbidden):
        raise PackageContractError(
            "installed runtime evidence retained a forbidden fixture value"
        )

    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_RUNTIME_EVIDENCE_ASSERT,
            str(outputs[0]),
            str(behavior),
            str(runtime_environment),
            str(recording),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-runtime-evidence-assert> "
            "<runtime-evidence-inputs-and-output>"
        ),
    )

    unsafe_policy = run_directory / "runtime-evidence-selected-secret-policy.json"
    unsafe_payload = json.loads(policy.read_text(encoding="utf-8"))
    unsafe_payload["rules"][0]["selector_uri"] = (
        "urn:ucf:fixture-selector:selected-secret:1.0.0"
    )
    unsafe_policy.write_text(
        json.dumps(
            unsafe_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    rejected_output = run_directory / "runtime-evidence-rejection-sentinel.json"
    rejected_output.write_bytes(b"preserve-me")
    _run(
        _runtime_evidence_cli_command(
            ucf=ucf,
            python=python,
            adapter=adapter,
            adapter_cwd=run_directory,
            recording=recording,
            policy=unsafe_policy,
            environment=runtime_environment,
            behavior=behavior,
            output=rejected_output,
        ),
        run_directory,
        environment,
        expected_returncode=1,
    )
    if rejected_output.read_bytes() != b"preserve-me":
        raise PackageContractError(
            "installed runtime rejection changed its prior output"
        )
    if tuple(run_directory.glob(".runtime-evidence-*.tmp")):
        raise PackageContractError("installed runtime evidence left temporary output")
    if _tree_manifest(fixture_directory) != initial_fixture:
        raise PackageContractError(
            "installed runtime evidence changed its input fixture"
        )
    if _tree_manifest(adapter_directory) != initial_adapter:
        raise PackageContractError(
            "installed runtime evidence changed its external adapter"
        )


def _smoke_installed_onboarding(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    legacy_root = run_directory / "python_legacy_quote"
    adapter_directory = run_directory / "external-python-adapter"
    adapter_directory.mkdir()
    shutil.copytree(
        repository_root / "tests" / "fixtures" / "brownfield" / "python_legacy_quote",
        legacy_root,
    )
    adapter_source = repository_root / "tests" / "fixtures" / "adapters"
    adapter = adapter_directory / "inventory_reference_adapter.py"
    shutil.copy2(
        adapter_source / "inventory_reference_adapter.py",
        adapter,
    )
    shutil.copytree(
        adapter_source / "inventory_reference",
        adapter_directory / "inventory_reference",
    )
    policy = run_directory / "onboarding-policy.json"
    policy.write_text(
        json.dumps(
            {
                "kind": "ignore_policy",
                "policy_version": "1.0.0",
                "rules": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    initial_manifest = _tree_manifest(legacy_root)
    native_environment = {
        **environment,
        "PYTHONPATH": str(legacy_root / "src"),
    }
    native_command = (
        str(python),
        "-B",
        "tests/behavior_checks.py",
    )
    _run(native_command, legacy_root, native_environment)
    if _tree_manifest(legacy_root) != initial_manifest:
        raise PackageContractError(
            "native pre-onboarding behavior changed the legacy fixture"
        )

    discovery_a = run_directory / "onboarding-discovery-a.json"
    discovery_b = run_directory / "onboarding-discovery-b.json"
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="discover",
            root=legacy_root,
            policy=policy,
            output=discovery_a,
            python=python,
            adapter=adapter,
            page_record_limit=3,
        ),
        run_directory,
        environment,
    )
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="discover",
            root=legacy_root,
            policy=policy,
            output=discovery_b,
            python=python,
            adapter=adapter,
            page_record_limit=1,
        ),
        run_directory,
        environment,
    )
    if discovery_a.read_bytes() != discovery_b.read_bytes():
        raise PackageContractError(
            "installed discovery output is not byte-deterministic"
        )

    decisions = run_directory / "onboarding-decisions.json"
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_ONBOARDING_REVIEW,
            str(discovery_a),
            str(decisions),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-onboarding-review> "
            f"{shlex.quote(str(discovery_a))} "
            f"{shlex.quote(str(decisions))}"
        ),
    )

    bundle_a = run_directory / "onboarding-bundle-a.json"
    bundle_b = run_directory / "onboarding-bundle-b.json"
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="onboard",
            root=legacy_root,
            policy=policy,
            decisions=decisions,
            output=bundle_a,
            python=python,
            adapter=adapter,
            page_record_limit=3,
        ),
        run_directory,
        environment,
    )
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="onboard",
            root=legacy_root,
            policy=policy,
            decisions=decisions,
            output=bundle_b,
            python=python,
            adapter=adapter,
            page_record_limit=1,
        ),
        run_directory,
        environment,
    )
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_ONBOARDING_ASSERT,
            str(bundle_a),
            str(bundle_b),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-onboarding-assert> "
            f"{shlex.quote(str(bundle_a))} "
            f"{shlex.quote(str(bundle_b))}"
        ),
    )

    stale_payload = json.loads(decisions.read_text(encoding="utf-8"))
    stale_payload["discovery"]["canonical_digest"]["value"] = "f" * 64
    stale_decisions = run_directory / "onboarding-stale-decisions.json"
    stale_decisions.write_text(
        json.dumps(
            stale_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    failure_output = run_directory / "onboarding-failure-sentinel.json"
    failure_output.write_bytes(b"preserve-me")
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="onboard",
            root=legacy_root,
            policy=policy,
            decisions=stale_decisions,
            output=failure_output,
            python=python,
            adapter=adapter,
            page_record_limit=3,
        ),
        run_directory,
        environment,
        expected_returncode=3,
    )
    if failure_output.read_bytes() != b"preserve-me":
        raise PackageContractError(
            "stale installed onboarding changed an existing output"
        )
    _run(
        _onboarding_cli_command(
            ucf=ucf,
            operation="onboard",
            root=legacy_root,
            policy=policy,
            decisions=decisions,
            output=failure_output,
            python=python,
            adapter=adapter,
            page_record_limit=3,
            mode="fail-discovery",
        ),
        run_directory,
        environment,
        expected_returncode=3,
    )
    if failure_output.read_bytes() != b"preserve-me":
        raise PackageContractError(
            "failed installed adapter changed an existing output"
        )
    if tuple(run_directory.glob(".onboarding-*.tmp")):
        raise PackageContractError("failed installed onboarding left temporary output")

    _smoke_installed_ratchet(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        bundle=bundle_a,
        environment=environment,
    )

    _run(native_command, legacy_root, native_environment)
    if _tree_manifest(legacy_root) != initial_manifest:
        raise PackageContractError("installed onboarding changed the legacy fixture")


def _copy_stable_driver(
    *,
    source: Path,
    destination: Path,
    label: str,
) -> None:
    try:
        before = source.lstat()
        payload = source.read_bytes()
        after = source.lstat()
    except OSError as error:
        raise PackageContractError(
            f"installed {label} smoke driver is unavailable"
        ) from error
    if not stat.S_ISREG(before.st_mode) or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise PackageContractError(f"installed {label} smoke driver is not stable")
    destination.write_bytes(payload)
    if destination.read_bytes() != payload:
        raise PackageContractError(f"external installed {label} driver copy differs")


def _read_installed_rel001_lane_evidence(
    path: Path,
    *,
    expected_lane: str,
    expected_transports: tuple[str, ...],
) -> dict[str, object]:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise PackageContractError(
                "installed REL-001 evidence is not a regular file"
            )
        with path.open("rb") as stream:
            payload = stream.read(MAX_INSTALLED_REL001_EVIDENCE_BYTES + 1)
    except OSError as error:
        raise PackageContractError(
            "installed REL-001 evidence is unavailable"
        ) from error
    if len(payload) > MAX_INSTALLED_REL001_EVIDENCE_BYTES:
        raise PackageContractError("installed REL-001 evidence is oversized")
    try:
        evidence = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageContractError(
            "installed REL-001 evidence is invalid JSON"
        ) from error
    if type(evidence) is not dict:
        raise PackageContractError("installed REL-001 evidence is not an object")
    canonical = (
        json.dumps(
            evidence,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    if payload != canonical:
        raise PackageContractError("installed REL-001 evidence is not canonical")
    if set(evidence) != REL001_LANE_EVIDENCE_KEYS or (
        evidence["kind"] != "rel001_lane_evidence"
        or evidence["evidence_version"] != "1.0.0"
        or evidence["lane"] != expected_lane
        or evidence["status"] != "passed"
    ):
        raise PackageContractError(
            "installed REL-001 evidence has incompatible coordinates"
        )

    source = evidence["source"]
    deterministic = evidence["deterministic"]
    runtime = evidence["runtime"]
    metrics = evidence["metrics"]
    if (
        type(source) is not dict
        or set(source) != {"file_count", "byte_count", "manifest_digest"}
        or type(deterministic) is not dict
        or set(deterministic) != REL001_DETERMINISTIC_EVIDENCE_KEYS
        or type(runtime) is not dict
        or set(runtime) != REL001_RUNTIME_EVIDENCE_KEYS
        or type(metrics) is not dict
        or set(metrics) != REL001_METRIC_KEYS
    ):
        raise PackageContractError(
            "installed REL-001 evidence has an incompatible shape"
        )
    digest = source["manifest_digest"]
    if (
        type(source["file_count"]) is not int
        or source["file_count"] <= 0
        or type(source["byte_count"]) is not int
        or source["byte_count"] <= 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise PackageContractError(
            "installed REL-001 evidence has invalid source identity"
        )
    if any(
        type(deterministic[name]) is not dict
        for name in REL001_DETERMINISTIC_EVIDENCE_KEYS
        if name != "verification_requests"
    ) or not _nonempty_document_array(deterministic["verification_requests"]):
        raise PackageContractError(
            "installed REL-001 deterministic evidence is incomplete"
        )
    if any(
        not _nonempty_document_array(runtime[name])
        for name in REL001_RUNTIME_EVIDENCE_KEYS
    ):
        raise PackageContractError(
            "installed REL-001 runtime evidence is incomplete"
        )

    dispositions = metrics["dispositions"]
    integer_metrics = REL001_METRIC_KEYS - {"dispositions", "transports"}
    if (
        type(dispositions) is not dict
        or set(dispositions) != {"accepted", "edited", "rejected", "uncertain"}
        or any(type(value) is not int or value < 0 for value in dispositions.values())
        or any(
            type(metrics[name]) is not int or metrics[name] < 0
            for name in integer_metrics
        )
        or metrics["transports"] != list(expected_transports)
        or metrics["tested_claim_count"] <= 0
        or metrics["verification_evidence_count"] <= 0
        or metrics["verified_claim_count"] != 0
    ):
        raise PackageContractError(
            "installed REL-001 evidence metrics are invalid or overclaimed"
        )
    print(
        f"rel001-{expected_lane}-evidence-sha256="
        f"{hashlib.sha256(payload).hexdigest()}",
        flush=True,
    )
    return evidence


def _nonempty_document_array(value: object) -> bool:
    return (
        type(value) is list
        and bool(value)
        and all(type(document) is dict for document in value)
    )


def _smoke_installed_evidence_status(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    recorded_result_source = (
        repository_root
        / "tests/fixtures/change_lifecycle/v1/context/execution-result.json"
    )
    context_source = recorded_result_source.parent
    sources = {
        "result": recorded_result_source,
        "mapping": context_source / "mapping-result.json",
        "bundle": context_source / "onboarding-bundle.json",
        "inventory": context_source / "current-inventory.json",
    }
    paths = {
        name: run_directory / f"evidence-{name}.json"
        for name in sources
    }
    for name, source in sources.items():
        _copy_stable_driver(
            source=source,
            destination=paths[name],
            label=f"evidence-status {name}",
        )
    current_result = run_directory / "evidence-current-result.json"
    failed_result = run_directory / "evidence-failed-result.json"
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_EVIDENCE_MUTATE,
            str(paths["result"]),
            str(current_result),
            str(failed_result),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-evidence-mutate> "
            "<result> <current-result> <failed-result>"
        ),
    )
    immutable_inputs = {
        **paths,
        "current_result": current_result,
        "failed_result": failed_result,
    }

    def input_snapshot(path: Path) -> tuple[int, int, int, int, str]:
        metadata = path.lstat()
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            _sha256(path),
        )

    input_snapshots = {
        name: input_snapshot(path)
        for name, path in immutable_inputs.items()
    }

    def record_command(
        result: Path,
        output: Path,
        *,
        verification_capability_version: str = "1.0.0",
    ) -> tuple[str, ...]:
        return (
            str(ucf),
            "evidence",
            "record",
            "--result",
            str(result),
            "--mapping-result",
            str(paths["mapping"]),
            "--onboarding-bundle",
            str(paths["bundle"]),
            "--inventory",
            str(paths["inventory"]),
            "--mapping-adapter-name",
            "org.ucf.fixture-adapter",
            "--mapping-adapter-version",
            "1.0.0",
            "--verification-adapter-name",
            "org.ucf.fixture-adapter",
            "--verification-adapter-version",
            "1.0.0",
            "--mapping-capability-version",
            "1.0.0",
            "--verification-capability-version",
            verification_capability_version,
            "--output",
            str(output),
        )

    def context_options(prefix: str, result: Path) -> tuple[str, ...]:
        return (
            f"--{prefix}-result",
            str(result),
            f"--{prefix}-mapping-result",
            str(paths["mapping"]),
            f"--{prefix}-onboarding-bundle",
            str(paths["bundle"]),
            f"--{prefix}-inventory",
            str(paths["inventory"]),
            f"--{prefix}-mapping-adapter-name",
            "org.ucf.fixture-adapter",
            f"--{prefix}-mapping-adapter-version",
            "1.0.0",
            f"--{prefix}-verification-adapter-name",
            "org.ucf.fixture-adapter",
            f"--{prefix}-verification-adapter-version",
            "1.0.0",
            f"--{prefix}-mapping-capability-version",
            "1.0.0",
            f"--{prefix}-verification-capability-version",
            "1.0.0",
        )

    def assessment_command(
        envelope: Path,
        output: Path,
        *,
        recorded_result: Path,
        current: Path | None,
    ) -> tuple[str, ...]:
        command = (
            str(ucf),
            "evidence",
            "assess",
            "--envelope",
            str(envelope),
            *context_options("recorded", recorded_result),
            "--output",
            str(output),
        )
        if current is not None:
            command += context_options("current", current)
        return command

    envelopes = (
        run_directory / "envelope-seed-1.json",
        run_directory / "envelope-seed-777.json",
    )
    lanes = []
    for seed in ("1", "777"):
        lane = environment.copy()
        lane["PYTHONHASHSEED"] = seed
        lanes.append(lane)
    for envelope, lane in zip(envelopes, lanes, strict=True):
        _run(
            record_command(paths["result"], envelope),
            run_directory,
            lane,
        )
    if envelopes[0].read_bytes() != envelopes[1].read_bytes():
        raise PackageContractError(
            "installed evidence envelope changed across PYTHONHASHSEED"
        )
    retry_before = (
        envelopes[0].stat().st_ino,
        envelopes[0].stat().st_mtime_ns,
        _sha256(envelopes[0]),
    )
    _run(
        record_command(paths["result"], envelopes[0]),
        run_directory,
        lanes[1],
    )
    retry_after = (
        envelopes[0].stat().st_ino,
        envelopes[0].stat().st_mtime_ns,
        _sha256(envelopes[0]),
    )
    if retry_after != retry_before:
        raise PackageContractError(
            "installed evidence record retry was not an exact no-op"
        )

    def reproducible_output(
        name: str,
        command_for: Callable[[Path], tuple[str, ...]],
        *,
        expected_returncode: int = 0,
    ) -> Path:
        outputs = tuple(
            run_directory / f"{name}-seed-{seed}.json"
            for seed in ("1", "777")
        )
        for output, lane in zip(outputs, lanes, strict=True):
            _run(
                command_for(output),
                run_directory,
                lane,
                expected_returncode=expected_returncode,
            )
        if outputs[0].read_bytes() != outputs[1].read_bytes():
            raise PackageContractError(
                "installed evidence output changed across PYTHONHASHSEED: "
                f"{name}"
            )
        return outputs[0]

    assessment_fresh = reproducible_output(
        "assessment-fresh",
        lambda output: assessment_command(
            envelopes[0],
            output,
            recorded_result=paths["result"],
            current=paths["result"],
        ),
    )
    assessment_stale = reproducible_output(
        "assessment-stale",
        lambda output: assessment_command(
            envelopes[0],
            output,
            recorded_result=paths["result"],
            current=current_result,
        ),
        expected_returncode=1,
    )
    assessment_indeterminate = reproducible_output(
        "assessment-indeterminate",
        lambda output: assessment_command(
            envelopes[0],
            output,
            recorded_result=paths["result"],
            current=None,
        ),
        expected_returncode=1,
    )

    refreshed_envelope = reproducible_output(
        "refreshed-envelope",
        lambda output: record_command(current_result, output),
    )
    refreshed_assessment = reproducible_output(
        "refreshed-assessment-fresh",
        lambda output: assessment_command(
            refreshed_envelope,
            output,
            recorded_result=current_result,
            current=current_result,
        ),
    )

    invalid_output = run_directory / "invalid-evidence-output.json"
    invalid_output.write_bytes(b"preserve-me")
    _run(
        record_command(
            paths["result"],
            invalid_output,
            verification_capability_version="2.0.0",
        ),
        run_directory,
        environment,
        expected_returncode=3,
    )
    if invalid_output.read_bytes() != b"preserve-me":
        raise PackageContractError(
            "installed evidence invalid publication changed prior output"
        )
    if tuple(run_directory.glob(".invalid-evidence-output.json.*.tmp")):
        raise PackageContractError(
            "installed evidence invalid publication left temporary output"
        )

    failed_output = run_directory / "failed-evidence-output.json"
    failed_output.write_bytes(b"preserve-failed")
    _run(
        record_command(failed_result, failed_output),
        run_directory,
        environment,
        expected_returncode=3,
    )
    if failed_output.read_bytes() != b"preserve-failed":
        raise PackageContractError(
            "installed evidence failed verification publication changed prior output"
        )
    if tuple(run_directory.glob(".failed-evidence-output.json.*.tmp")):
        raise PackageContractError(
            "installed evidence failed verification publication left "
            "temporary output"
        )

    partial_output = run_directory / "partial-current-output.json"
    partial_output.write_bytes(b"preserve-partial")
    partial_command = assessment_command(
        envelopes[0],
        partial_output,
        recorded_result=paths["result"],
        current=None,
    ) + ("--current-result", str(paths["result"]))
    _run(
        partial_command,
        run_directory,
        environment,
        expected_returncode=3,
    )
    if partial_output.read_bytes() != b"preserve-partial":
        raise PackageContractError(
            "installed evidence partial current context changed prior output"
        )
    if tuple(run_directory.glob(".partial-current-output.json.*.tmp")):
        raise PackageContractError(
            "installed evidence partial current context left temporary output"
        )

    race_output = run_directory / "concurrent-evidence-output.json"
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_EVIDENCE_PUBLISH_RACE_ASSERT,
            str(race_output),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-evidence-publish-race-assert> <output>"
        ),
    )

    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_EVIDENCE_ASSERT,
            str(paths["result"]),
            str(paths["mapping"]),
            str(paths["bundle"]),
            str(paths["inventory"]),
            str(envelopes[0]),
            str(envelopes[1]),
            str(assessment_fresh),
            str(assessment_stale),
            str(assessment_indeterminate),
            str(current_result),
            str(refreshed_envelope),
            str(refreshed_assessment),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-evidence-assert> <evidence-loop>"
        ),
    )
    if {
        name: input_snapshot(path)
        for name, path in immutable_inputs.items()
    } != input_snapshots:
        raise PackageContractError(
            "installed evidence loop changed immutable context inputs"
        )


def _smoke_installed_generation(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    source_adapter = repository_root / "adapters/python-pytest/adapter.py"
    source_request = (
        repository_root
        / "tests/fixtures/generation/v1/positive/request.json"
    )
    external_adapter = run_directory / "python-pytest-adapter.py"
    request = run_directory / "generation-request.json"
    _copy_stable_driver(
        source=source_adapter,
        destination=external_adapter,
        label="Python/pytest generation adapter",
    )
    _copy_stable_driver(
        source=source_request,
        destination=request,
        label="Python/pytest generation request",
    )

    implementation = run_directory / "legacy_inventory.py"
    implementation.write_text(
        """\
def reserve_item(*, item_id: str) -> str:
    if item_id != "sku-123":
        raise ValueError("unexpected item")
    return "reservation-456"
""",
        encoding="utf-8",
    )
    implementation_digest = _sha256(implementation)
    request_digest = _sha256(request)

    _run(
        (
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "pytest==9.1.1",
        ),
        run_directory,
        environment,
    )

    destinations = (
        run_directory / "generated-seed-1",
        run_directory / "generated-seed-777",
    )

    def generation_command(destination: Path) -> tuple[str, ...]:
        return (
            str(ucf),
            "generation",
            "run",
            str(request),
            "--destination",
            str(destination),
            "--adapter-cwd",
            str(run_directory),
            "--operation-timeout",
            "5",
            "--",
            str(python),
            "-I",
            "-B",
            "-X",
            "utf8",
            str(external_adapter),
        )

    lane_environments = []
    for seed in ("1", "777"):
        lane = environment.copy()
        lane["PYTHONHASHSEED"] = seed
        lane_environments.append(lane)

    for destination, lane in zip(
        destinations,
        lane_environments,
        strict=True,
    ):
        status = _run_text(
            generation_command(destination),
            run_directory,
            lane,
        )
        if status != "created":
            raise PackageContractError(
                "installed generation did not create its exact managed tree"
            )

    if _content_manifest(destinations[0]) != _content_manifest(
        destinations[1]
    ):
        raise PackageContractError(
            "generated tree changed across Python hash seeds"
        )
    if _sha256(implementation) != implementation_digest:
        raise PackageContractError(
            "installed generation changed user implementation code"
        )
    if _sha256(request) != request_digest:
        raise PackageContractError(
            "installed generation changed its immutable request"
        )

    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_GENERATION_ASSERT,
            str(request),
            *(str(destination) for destination in destinations),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-generation-assert> <request> <generated-roots>"
        ),
    )
    _run(
        (
            str(python),
            "-B",
            "-m",
            "pytest",
            "-q",
            str(destinations[0]),
        ),
        run_directory,
        environment,
    )

    before_retry = _tree_manifest(destinations[0])
    status = _run_text(
        generation_command(destinations[0]),
        run_directory,
        lane_environments[1],
    )
    if status != "unchanged":
        raise PackageContractError(
            "installed generation retry was not an exact no-op"
        )
    if _tree_manifest(destinations[0]) != before_retry:
        raise PackageContractError(
            "installed generation retry changed its managed tree"
        )

    generated_test = destinations[0] / "test_action_reserve_item.py"
    generated_test.write_bytes(generated_test.read_bytes() + b"# local edit\n")
    dirty_before = _tree_manifest(destinations[0])
    _run(
        generation_command(destinations[0]),
        run_directory,
        lane_environments[0],
        expected_returncode=3,
    )
    if _tree_manifest(destinations[0]) != dirty_before:
        raise PackageContractError("dirty generated tree was overwritten")
    if _sha256(implementation) != implementation_digest:
        raise PackageContractError(
            "dirty-tree rejection changed user implementation code"
        )
    if _sha256(request) != request_digest:
        raise PackageContractError(
            "dirty-tree rejection changed its immutable request"
        )


def _smoke_installed_python_legacy_quote(
    *,
    python: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    fixture_root = run_directory / "rel001-python-legacy-quote"
    adapter_root = run_directory / "rel001-python-adapter"
    shutil.copytree(
        repository_root
        / "tests"
        / "fixtures"
        / "brownfield"
        / "python_legacy_quote",
        fixture_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    adapter_root.mkdir()
    source_adapter_root = repository_root / "tests" / "fixtures" / "adapters"
    adapter = adapter_root / "inventory_reference_adapter.py"
    shutil.copy2(source_adapter_root / adapter.name, adapter)
    shutil.copytree(
        source_adapter_root / "inventory_reference",
        adapter_root / "inventory_reference",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    fixture_before = _tree_manifest(fixture_root)
    adapter_before = _tree_manifest(adapter_root)

    source_driver = (
        repository_root / "tools" / "installed_python_legacy_quote_smoke.py"
    )
    external_driver = run_directory / "installed_python_legacy_quote_smoke.py"
    _copy_stable_driver(
        source=source_driver,
        destination=external_driver,
        label="Python legacy quote",
    )
    evidence_output = run_directory / "rel001-python-lane-evidence.json"
    _run(
        (
            str(python),
            "-I",
            str(external_driver),
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture_root),
            "--evidence-output",
            str(evidence_output),
        ),
        run_directory,
        environment,
    )
    _read_installed_rel001_lane_evidence(
        evidence_output,
        expected_lane="python",
        expected_transports=(),
    )
    if (
        _tree_manifest(fixture_root) != fixture_before
        or _tree_manifest(adapter_root) != adapter_before
    ):
        raise PackageContractError(
            "installed Python REL-001 workflow changed its fixture or adapter"
        )


def _smoke_installed_typescript_fastify(
    *,
    python: Path,
    run_directory: Path,
    repository_root: Path,
    workspace: Path,
    environment: dict[str, str],
) -> None:
    adapter_entry, fixture_root, fixture_source_manifest = (
        _prepare_installed_typescript_fastify_adapter(
            repository_root=repository_root,
            workspace=workspace,
            environment=environment,
        )
    )
    source_driver = repository_root / "tools" / "installed_typescript_fastify_smoke.py"
    external_driver = run_directory / "installed_typescript_fastify_smoke.py"
    _copy_stable_driver(
        source=source_driver,
        destination=external_driver,
        label="TypeScript/Fastify",
    )
    evidence_output = run_directory / "rel001-typescript-lane-evidence.json"

    _run(
        (
            str(python),
            "-I",
            str(external_driver),
            "--adapter",
            str(adapter_entry),
            "--fixture",
            str(fixture_root),
            "--evidence-output",
            str(evidence_output),
        ),
        fixture_root,
        environment,
    )
    _read_installed_rel001_lane_evidence(
        evidence_output,
        expected_lane="typescript_fastify",
        expected_transports=("http",),
    )
    if typescript_fastify_fixture_manifest(fixture_root) != fixture_source_manifest:
        raise PackageContractError(
            "installed TypeScript/Fastify smoke changed fixture source"
        )


def _smoke_installed_go_stdlib(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    workspace: Path,
    environment: dict[str, str],
) -> None:
    distribution = _prepare_installed_go_stdlib_adapter(
        repository_root=repository_root,
        workspace=workspace,
        environment=environment,
    )
    distribution_before = _tree_manifest(distribution.adapter_entry.parent)
    fixture_binary_digest = _sha256(distribution.fixture_entry)

    conformance_reports = (
        run_directory / "conformance-go-stdlib-a.json",
        run_directory / "conformance-go-stdlib-b.json",
    )
    for report in conformance_reports:
        _run(
            (
                str(ucf),
                "adapter",
                "conformance",
                "--cwd",
                str(run_directory),
                "--report",
                str(report),
                "--",
                str(distribution.adapter_entry),
                "--conformance",
            ),
            run_directory,
            environment,
        )
    first_report = conformance_reports[0].read_bytes()
    if first_report != conformance_reports[1].read_bytes():
        raise PackageContractError("installed Go adapter conformance reports differ")
    try:
        conformance = json.loads(first_report)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PackageContractError(
            "installed Go adapter conformance report is invalid"
        ) from error
    canonical_report = (
        json.dumps(
            conformance,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    if (
        first_report != canonical_report
        or conformance.get("kind") != "adapter_conformance_report"
        or conformance.get("kit_version") != "1.0.0"
        or conformance.get("protocol_version") != "1.0.0"
        or conformance.get("profile") != "org.ucf.adapter-conformance.full"
        or conformance.get("status") != "conformant"
        or len(conformance.get("cases", ())) != 17
        or any(case.get("status") != "passed" for case in conformance.get("cases", ()))
    ):
        raise PackageContractError(
            "installed Go adapter did not produce the exact canonical "
            "conformance report"
        )
    print(
        f"go-stdlib-conformance-sha256={hashlib.sha256(first_report).hexdigest()}",
        flush=True,
    )

    source_driver = repository_root / "tools" / "installed_go_stdlib_smoke.py"
    external_driver = run_directory / "installed_go_stdlib_smoke.py"
    _copy_stable_driver(
        source=source_driver,
        destination=external_driver,
        label="Go standard-library",
    )
    evidence_output = run_directory / "rel001-go-http-lane-evidence.json"
    _run(
        (
            str(python),
            "-I",
            str(external_driver),
            "--adapter",
            str(distribution.adapter_entry),
            "--fixture",
            str(distribution.fixture_root),
            "--fixture-executable",
            str(distribution.fixture_entry),
            "--evidence-output",
            str(evidence_output),
        ),
        distribution.fixture_root,
        environment,
    )
    _read_installed_rel001_lane_evidence(
        evidence_output,
        expected_lane="go_http",
        expected_transports=("http",),
    )

    _smoke_installed_go_stdlib_platform(
        python=python,
        run_directory=run_directory,
        repository_root=repository_root,
        distribution=distribution,
        environment=environment,
    )

    if (
        go_stdlib_adapter_manifest(distribution.adapter_root)
        != distribution.adapter_source_manifest
        or go_stdlib_fixture_manifest(distribution.fixture_root)
        != distribution.fixture_source_manifest
        or _tree_manifest(distribution.adapter_entry.parent) != distribution_before
        or _sha256(distribution.fixture_entry) != fixture_binary_digest
    ):
        raise PackageContractError(
            "installed Go vertical slice changed source or distribution inputs"
        )


def _smoke_installed_go_stdlib_platform(
    *,
    python: Path,
    run_directory: Path,
    repository_root: Path,
    distribution: _GoStdlibDistribution,
    environment: dict[str, str],
) -> None:
    distribution_before = _tree_manifest(distribution.adapter_entry.parent)
    legacy_fixture_binary_digest = _sha256(distribution.fixture_entry)
    platform_fixture_binary_digest = _sha256(distribution.platform_fixture_entry)
    source_driver = repository_root / "tools" / "installed_go_stdlib_platform_smoke.py"
    external_driver = run_directory / "installed_go_stdlib_platform_smoke.py"
    _copy_stable_driver(
        source=source_driver,
        destination=external_driver,
        label="Go standard-library platform",
    )
    evidence_output = run_directory / "rel001-go-platform-lane-evidence.json"
    _run(
        (
            str(python),
            "-I",
            str(external_driver),
            "--adapter",
            str(distribution.adapter_entry),
            "--fixture",
            str(distribution.platform_fixture_root),
            "--platform-fixture-executable",
            str(distribution.platform_fixture_entry),
            "--evidence-output",
            str(evidence_output),
        ),
        run_directory,
        environment,
    )
    _read_installed_rel001_lane_evidence(
        evidence_output,
        expected_lane="go_platform",
        expected_transports=("cli", "event"),
    )
    if (
        go_stdlib_adapter_manifest(distribution.adapter_root)
        != distribution.adapter_source_manifest
        or go_stdlib_fixture_manifest(distribution.fixture_root)
        != distribution.fixture_source_manifest
        or go_stdlib_platform_manifest(distribution.platform_fixture_root)
        != distribution.platform_fixture_source_manifest
        or _tree_manifest(distribution.adapter_entry.parent) != distribution_before
        or _sha256(distribution.fixture_entry) != legacy_fixture_binary_digest
        or _sha256(distribution.platform_fixture_entry)
        != platform_fixture_binary_digest
        or platform_fixture_binary_digest != GO_STDLIB_PLATFORM_BINARY_SHA256
    ):
        raise PackageContractError(
            "installed Go platform smoke changed source, binaries, "
            "or distribution inputs"
        )


def _smoke_installed_change(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    fixture_root = (
        repository_root
        / "tests"
        / "fixtures"
        / "change_lifecycle"
        / "v1"
    )
    source_workspace = run_directory / "change-openspec-source"
    context_directory = run_directory / "change-context"
    shutil.copytree(
        fixture_root / "openspec-spec-driven-1",
        source_workspace,
    )
    shutil.copytree(fixture_root / "context", context_directory)
    source_before = _tree_manifest(source_workspace)
    context_before = _tree_manifest(context_directory)
    change_directory = (
        source_workspace
        / "changes"
        / "require-quote-order-total"
    )
    base_behavior = context_directory / "base-behavior.json"
    final_behavior = context_directory / "final-behavior.json"
    result_path = context_directory / "execution-result.json"
    mapping_path = context_directory / "mapping-result.json"
    bundle_path = context_directory / "onboarding-bundle.json"
    inventory_path = context_directory / "current-inventory.json"
    try:
        mapping_producer = json.loads(mapping_path.read_bytes())["producer"]
        verification_producer = json.loads(result_path.read_bytes())["producer"]
        producer_coordinates = (
            mapping_producer["name"],
            mapping_producer["version"],
            verification_producer["name"],
            verification_producer["version"],
        )
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise PackageContractError(
            "change lifecycle context producer coordinates are invalid"
        ) from error
    if not all(
        isinstance(value, str) and value
        for value in producer_coordinates
    ):
        raise PackageContractError(
            "change lifecycle context producer coordinates are incomplete"
        )

    evidence_arguments = (
        "--result",
        str(result_path),
        "--mapping-result",
        str(mapping_path),
        "--onboarding-bundle",
        str(bundle_path),
        "--current-inventory",
        str(inventory_path),
        "--mapping-adapter-name",
        producer_coordinates[0],
        "--mapping-adapter-version",
        producer_coordinates[1],
        "--verification-adapter-name",
        producer_coordinates[2],
        "--verification-adapter-version",
        producer_coordinates[3],
    )
    lane_outputs: list[dict[str, Path]] = []
    for seed in ("1", "777"):
        lane = run_directory / f"change-seed-{seed}"
        lane.mkdir()
        seeded_environment = environment.copy()
        seeded_environment["PYTHONHASHSEED"] = seed
        proposal = lane / "change-proposal.json"
        exported = lane / "exported-openspec"
        delta = lane / "behavior-delta.json"
        pending_tasks = lane / "tasks-pending.json"
        first_tasks = lane / "tasks-1.json"
        second_tasks = lane / "tasks-2.json"
        completed_tasks = lane / "tasks-completed.json"
        implementation = lane / "implementation-record.json"
        verification = lane / "verification-record.json"
        archive = lane / "change-archive.json"

        _run(
            (
                str(ucf),
                "change",
                "import-openspec",
                str(change_directory),
                "--base-behavior",
                str(base_behavior),
                "--output",
                str(proposal),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "export-openspec",
                str(proposal),
                "--destination",
                str(exported),
            ),
            lane,
            seeded_environment,
        )
        exported_before = _content_manifest(exported)
        if exported_before != _content_manifest(source_workspace):
            raise PackageContractError(
                "installed change export differs from imported OpenSpec bytes"
            )
        _run(
            (
                str(ucf),
                "change",
                "export-openspec",
                str(proposal),
                "--destination",
                str(exported),
            ),
            lane,
            seeded_environment,
        )
        if _content_manifest(exported) != exported_before:
            raise PackageContractError(
                "installed exact OpenSpec re-export changed its destination"
            )
        conflicting_export = lane / "conflicting-openspec"
        shutil.copytree(exported, conflicting_export)
        conflict_sentinel = conflicting_export / "user-owned.txt"
        conflict_sentinel.write_bytes(b"preserve-me")
        conflict_before = _content_manifest(conflicting_export)
        _run(
            (
                str(ucf),
                "change",
                "export-openspec",
                str(proposal),
                "--destination",
                str(conflicting_export),
            ),
            lane,
            seeded_environment,
            expected_returncode=3,
        )
        if _content_manifest(conflicting_export) != conflict_before:
            raise PackageContractError(
                "conflicting installed change export changed user content"
            )

        _run(
            (
                str(ucf),
                "change",
                "derive-delta",
                "--proposal",
                str(proposal),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                "--output",
                str(delta),
            ),
            lane,
            seeded_environment,
        )
        subject = "modified:use_case:use-case.quote-order"
        _run(
            (
                str(ucf),
                "change",
                "derive-tasks",
                "--proposal",
                str(proposal),
                "--delta",
                str(delta),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                "--subject",
                f"task.1-1={subject}",
                "--subject",
                f"task.1-2={subject}",
                "--subject",
                f"task.1-3={subject}",
                "--depends",
                "task.1-2=task.1-1",
                "--depends",
                "task.1-3=task.1-2",
                "--output",
                str(pending_tasks),
            ),
            lane,
            seeded_environment,
        )

        blocked_output = lane / "blocked-task-sentinel.json"
        blocked_output.write_bytes(b"preserve-me")
        _run(
            (
                str(ucf),
                "change",
                "complete-task",
                "--proposal",
                str(proposal),
                "--delta",
                str(delta),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                "--tasks",
                str(pending_tasks),
                "--task-id",
                "task.1-3",
                "--output",
                str(blocked_output),
            ),
            lane,
            seeded_environment,
            expected_returncode=1,
        )
        if blocked_output.read_bytes() != b"preserve-me":
            raise PackageContractError(
                "blocked installed task transition changed its output"
            )

        predecessor = pending_tasks
        for task_id, successor in (
            ("task.1-1", first_tasks),
            ("task.1-2", second_tasks),
            ("task.1-3", completed_tasks),
        ):
            _run(
                (
                    str(ucf),
                    "change",
                    "complete-task",
                    "--proposal",
                    str(proposal),
                    "--delta",
                    str(delta),
                    "--base-behavior",
                    str(base_behavior),
                    "--final-behavior",
                    str(final_behavior),
                    "--tasks",
                    str(predecessor),
                    "--task-id",
                    task_id,
                    "--output",
                    str(successor),
                ),
                lane,
                seeded_environment,
            )
            predecessor = successor

        _run(
            (
                str(ucf),
                "change",
                "record-implementation",
                "--proposal",
                str(proposal),
                "--delta",
                str(delta),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                "--tasks",
                str(completed_tasks),
                *evidence_arguments,
                "--output",
                str(implementation),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "verify",
                "--proposal",
                str(proposal),
                "--delta",
                str(delta),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                "--tasks",
                str(completed_tasks),
                "--implementation",
                str(implementation),
                *evidence_arguments,
                "--output",
                str(verification),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "archive",
                "--proposal",
                str(proposal),
                "--delta",
                str(delta),
                "--tasks",
                str(completed_tasks),
                "--implementation",
                str(implementation),
                "--verification",
                str(verification),
                "--base-behavior",
                str(base_behavior),
                "--final-behavior",
                str(final_behavior),
                *evidence_arguments,
                "--output",
                str(archive),
            ),
            lane,
            seeded_environment,
        )
        lane_outputs.append(
            {
                "root": lane,
                "proposal": proposal,
                "delta": delta,
                "tasks": completed_tasks,
                "implementation": implementation,
                "verification": verification,
                "archive": archive,
            }
        )

    if _content_manifest(lane_outputs[0]["root"]) != _content_manifest(
        lane_outputs[1]["root"]
    ):
        raise PackageContractError(
            "installed change workflow differs across Python hash seeds"
        )
    if (
        _tree_manifest(source_workspace) != source_before
        or _tree_manifest(context_directory) != context_before
    ):
        raise PackageContractError(
            "installed change workflow changed its immutable inputs"
        )

    accepted = lane_outputs[0]
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_CHANGE_ASSERT,
            str(accepted["proposal"]),
            str(accepted["delta"]),
            str(accepted["tasks"]),
            str(accepted["implementation"]),
            str(accepted["verification"]),
            str(accepted["archive"]),
            str(base_behavior),
            str(final_behavior),
            str(result_path),
            str(mapping_path),
            str(bundle_path),
            str(inventory_path),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-change-assert> <change-chain>"
        ),
    )


def _smoke_installed_change_governance(
    *,
    python: Path,
    ucf: Path,
    run_directory: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    fixture_root = (
        repository_root
        / "tests"
        / "fixtures"
        / "change_governance"
        / "v1"
    )
    context_directory = run_directory / "change-governance-context"
    shutil.copytree(fixture_root, context_directory)
    context_before = _tree_manifest(context_directory)
    base = context_directory / "context" / "base-behavior.json"
    proposal = context_directory / "context" / "proposal.json"

    lane_outputs: list[dict[str, Path]] = []
    for seed in ("1", "777"):
        lane = run_directory / f"change-governance-seed-{seed}"
        lane.mkdir()
        seeded_environment = environment.copy()
        seeded_environment["PYTHONHASHSEED"] = seed
        compatible_final = (
            context_directory
            / "context"
            / "compatible-final-behavior.json"
        )
        compatible_delta = (
            context_directory / "context" / "compatible-delta.json"
        )
        breaking_final = (
            context_directory
            / "context"
            / "breaking-final-behavior.json"
        )
        breaking_delta = (
            context_directory / "context" / "breaking-delta.json"
        )
        compatible_impact = lane / "compatible-impact.json"
        compatible_assessment = lane / "compatible-assessment.json"
        compatible_gate = lane / "compatible-gate.json"
        breaking_impact = lane / "breaking-impact.json"
        breaking_assessment = lane / "breaking-assessment.json"
        breaking_declaration = lane / "breaking-declaration.json"
        breaking_gate = lane / "breaking-gate.json"

        compatible_context = (
            "--proposal",
            str(proposal),
            "--delta",
            str(compatible_delta),
            "--base-behavior",
            str(base),
            "--final-behavior",
            str(compatible_final),
        )
        breaking_context = (
            "--proposal",
            str(proposal),
            "--delta",
            str(breaking_delta),
            "--base-behavior",
            str(base),
            "--final-behavior",
            str(breaking_final),
        )
        _run(
            (
                str(ucf),
                "change",
                "impact",
                *compatible_context,
                "--output",
                str(compatible_impact),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "assess",
                *compatible_context,
                "--impact",
                str(compatible_impact),
                "--assessment",
                str(
                    context_directory
                    / "positive"
                    / "compatible-assessment.json"
                ),
                "--output",
                str(compatible_assessment),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "gate",
                *compatible_context,
                "--impact",
                str(compatible_impact),
                "--assessment",
                str(compatible_assessment),
                "--output",
                str(compatible_gate),
            ),
            lane,
            seeded_environment,
        )

        _run(
            (
                str(ucf),
                "change",
                "impact",
                *breaking_context,
                "--output",
                str(breaking_impact),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "assess",
                *breaking_context,
                "--impact",
                str(breaking_impact),
                "--assessment",
                str(
                    context_directory
                    / "positive"
                    / "breaking-assessment.json"
                ),
                "--output",
                str(breaking_assessment),
            ),
            lane,
            seeded_environment,
        )
        blocked_gate = lane / "blocked-gate-sentinel.json"
        blocked_gate.write_bytes(b"preserve-blocked")
        _run(
            (
                str(ucf),
                "change",
                "gate",
                *breaking_context,
                "--impact",
                str(breaking_impact),
                "--assessment",
                str(breaking_assessment),
                "--output",
                str(blocked_gate),
            ),
            lane,
            seeded_environment,
            expected_returncode=1,
        )
        if blocked_gate.read_bytes() != b"preserve-blocked":
            raise PackageContractError(
                "blocked installed change gate changed its output"
            )
        _run(
            (
                str(ucf),
                "change",
                "decide",
                *breaking_context,
                "--impact",
                str(breaking_impact),
                "--assessment",
                str(breaking_assessment),
                "--declaration",
                str(
                    context_directory
                    / "positive"
                    / "breaking-approved-declaration.json"
                ),
                "--output",
                str(breaking_declaration),
            ),
            lane,
            seeded_environment,
        )
        _run(
            (
                str(ucf),
                "change",
                "gate",
                *breaking_context,
                "--impact",
                str(breaking_impact),
                "--assessment",
                str(breaking_assessment),
                "--declaration",
                str(breaking_declaration),
                "--output",
                str(breaking_gate),
            ),
            lane,
            seeded_environment,
        )
        lane_outputs.append(
            {
                "root": lane,
                "compatible_final": compatible_final,
                "compatible_delta": compatible_delta,
                "compatible_impact": compatible_impact,
                "compatible_assessment": compatible_assessment,
                "compatible_gate": compatible_gate,
                "breaking_final": breaking_final,
                "breaking_delta": breaking_delta,
                "breaking_impact": breaking_impact,
                "breaking_assessment": breaking_assessment,
                "breaking_declaration": breaking_declaration,
                "breaking_gate": breaking_gate,
            }
        )

    if _content_manifest(lane_outputs[0]["root"]) != _content_manifest(
        lane_outputs[1]["root"]
    ):
        raise PackageContractError(
            "installed change governance workflow differs across "
            "Python hash seeds"
        )
    if _tree_manifest(context_directory) != context_before:
        raise PackageContractError(
            "installed change governance workflow changed immutable inputs"
        )

    accepted = lane_outputs[0]
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_CHANGE_GOVERNANCE_ASSERT,
            str(base),
            str(proposal),
            str(accepted["compatible_final"]),
            str(accepted["compatible_delta"]),
            str(accepted["compatible_impact"]),
            str(accepted["compatible_assessment"]),
            str(accepted["compatible_gate"]),
            str(accepted["breaking_final"]),
            str(accepted["breaking_delta"]),
            str(accepted["breaking_impact"]),
            str(accepted["breaking_assessment"]),
            str(accepted["breaking_declaration"]),
            str(accepted["breaking_gate"]),
        ),
        run_directory,
        environment,
        display_command=(
            f"{shlex.quote(str(python))} -I -c "
            "<installed-change-governance-assert> <governance-chain>"
        ),
    )


def _smoke_installed_wheel(
    wheel: Path,
    workspace: Path,
    repository_root: Path,
    environment: dict[str, str],
) -> None:
    venv = workspace / "venv"
    run_directory = workspace / "external-run"
    specs_directory = run_directory / "specs"
    specs_directory.mkdir(parents=True)
    (specs_directory / "smoke-action.yaml").write_text(MINIMAL_SPEC)
    ir_path = run_directory / "behavior-ir.json"
    ir_path.write_text(MINIMAL_IR)
    trust_ir_path = run_directory / "trust-ir.json"
    trust_ir_path.write_text(MINIMAL_TRUST_IR)

    _run(("uv", "venv", "--python", "3.12", str(venv)), workspace, environment)
    python = _venv_executable(venv, "python")
    ucf = _venv_executable(venv, "ucf")
    _run(
        ("uv", "pip", "install", "--python", str(python), str(wheel)),
        workspace,
        environment,
    )

    isolated = _isolated_environment(environment)
    _run(
        (str(ucf), "generation", "run", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "evidence", "record", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "evidence", "assess", "--help"),
        run_directory,
        isolated,
    )
    _smoke_installed_evidence_status(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_generation(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_python_legacy_quote(
        python=python,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_typescript_fastify(
        python=python,
        run_directory=run_directory,
        repository_root=repository_root,
        workspace=workspace,
        environment=isolated,
    )
    _smoke_installed_go_stdlib(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        workspace=workspace,
        environment=isolated,
    )
    _run((str(ucf), "--help"), run_directory, isolated)
    _run(
        (str(ucf), "adapter", "inventory", "--help"),
        run_directory,
        isolated,
    )
    _run((str(ucf), "adapter", "discover", "--help"), run_directory, isolated)
    _run((str(ucf), "adapter", "onboard", "--help"), run_directory, isolated)
    _run(
        (str(ucf), "adapter", "import-runtime-evidence", "--help"),
        run_directory,
        isolated,
    )
    _run((str(ucf), "ratchet", "establish", "--help"), run_directory, isolated)
    _run((str(ucf), "ratchet", "evaluate", "--help"), run_directory, isolated)
    _run((str(ucf), "ratchet", "advance", "--help"), run_directory, isolated)
    _run(
        (str(ucf), "change", "import-openspec", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "export-openspec", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "derive-delta", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "derive-tasks", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "complete-task", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "record-implementation", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "verify", "--help"),
        run_directory,
        isolated,
    )
    _run(
        (str(ucf), "change", "archive", "--help"),
        run_directory,
        isolated,
    )
    for command in ("impact", "assess", "decide", "gate"):
        _run(
            (str(ucf), "change", command, "--help"),
            run_directory,
            isolated,
        )
    _run(
        (
            str(python),
            "-I",
            "-c",
            INSTALLED_ASSET_SMOKE,
            str(repository_root),
        ),
        run_directory,
        isolated,
        display_command=(
            f"{shlex.quote(str(python))} -I -c <installed-asset-smoke> "
            f"{shlex.quote(str(repository_root))}"
        ),
    )
    _smoke_installed_runtime_evidence(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_onboarding(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_change(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _smoke_installed_change_governance(
        python=python,
        ucf=ucf,
        run_directory=run_directory,
        repository_root=repository_root,
        environment=isolated,
    )
    _run((str(ucf), "validate", "specs"), run_directory, isolated)
    _run((str(ucf), "ir", "validate", str(ir_path)), run_directory, isolated)
    _run(
        (
            str(ucf),
            "trust",
            "validate",
            str(trust_ir_path),
            "--behavior-ir",
            str(ir_path),
        ),
        run_directory,
        isolated,
    )
    kit_directory = run_directory / "adapter-conformance-kit"
    _run(
        (
            str(ucf),
            "adapter",
            "kit",
            "--extract",
            str(kit_directory),
        ),
        run_directory,
        isolated,
    )
    node = shutil.which("node", path=isolated.get("PATH"))
    if node is None:
        raise PackageContractError(
            "Node is required to execute the packaged sample adapter"
        )
    manifest = json.loads((kit_directory / "manifest.json").read_text(encoding="utf-8"))
    reference_adapter = kit_directory.joinpath(*manifest["sample_adapter"].split("/"))
    reference_reports = (
        run_directory / "conformance-reference-a.json",
        run_directory / "conformance-reference-b.json",
    )
    for report in reference_reports:
        _run(
            (
                str(ucf),
                "adapter",
                "conformance",
                "--cwd",
                str(run_directory),
                "--report",
                str(report),
                "--",
                node,
                str(reference_adapter),
            ),
            run_directory,
            isolated,
        )
    if reference_reports[0].read_bytes() != reference_reports[1].read_bytes():
        raise PackageContractError(
            "packaged sample produced non-deterministic conformance reports"
        )
    reference_result = json.loads(reference_reports[0].read_text(encoding="utf-8"))
    if reference_result.get("status") != "conformant":
        raise PackageContractError(
            "packaged sample did not produce a conformant report"
        )

    fault_adapter = kit_directory.joinpath(*manifest["fault_adapter"].split("/"))
    for index, profile in enumerate(manifest["fault_profiles"]):
        report = run_directory / f"conformance-fault-{index}.json"
        _run(
            (
                str(ucf),
                "adapter",
                "conformance",
                "--cwd",
                str(run_directory),
                "--report",
                str(report),
                "--",
                node,
                str(fault_adapter),
                *profile["arguments"],
            ),
            run_directory,
            isolated,
            expected_returncode=1,
        )
        result = json.loads(report.read_text(encoding="utf-8"))
        failed_cases = {
            case["case_id"] for case in result["cases"] if case["status"] == "failed"
        }
        if result.get("status") != "non_conformant" or failed_cases != {
            profile["expected_case_id"]
        }:
            raise PackageContractError(
                "packaged fault profile did not fail exactly its named "
                f"case: {profile['fault_id']}"
            )


def run_contract(repository_root: Path) -> None:
    if shutil.which("uv") is None:
        raise PackageContractError("uv is required to build and smoke-test the wheel")

    environment = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="ucf-package-contract-") as temporary:
        workspace = Path(temporary).resolve()
        if workspace.is_relative_to(repository_root):
            raise PackageContractError(
                f"package smoke workspace must be outside the checkout: {workspace}"
            )

        first_directory = workspace / "wheel-a"
        second_directory = workspace / "wheel-b"
        first_build_environment = environment.copy()
        first_build_environment["PYTHONHASHSEED"] = "1"
        second_build_environment = environment.copy()
        second_build_environment["PYTHONHASHSEED"] = "777"
        _run(
            (
                "uv",
                "build",
                "--wheel",
                "--out-dir",
                str(first_directory),
            ),
            repository_root,
            first_build_environment,
        )
        _run(
            (
                "uv",
                "build",
                "--wheel",
                "--out-dir",
                str(second_directory),
            ),
            repository_root,
            second_build_environment,
        )

        first_wheel = _wheel_in(first_directory)
        second_wheel = _wheel_in(second_directory)
        wheel_hash = _assert_reproducible(first_wheel, second_wheel)
        _assert_wheel_assets(first_wheel)
        _assert_go_stdlib_is_external(first_wheel)
        _assert_python_pytest_is_external(first_wheel, repository_root)
        _assert_runtime_fixture_is_external(first_wheel, repository_root)
        _smoke_installed_wheel(
            first_wheel,
            workspace,
            repository_root,
            environment,
        )
        print(
            json.dumps(
                {
                    "package_contract": "PASS",
                    "wheel": first_wheel.name,
                    "sha256": wheel_hash,
                },
                sort_keys=True,
            ),
            flush=True,
        )


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    try:
        run_contract(repository_root)
    except (
        PackageContractError,
        GoSourceContractError,
        GoStdlibToolchainError,
        SourceContractError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"package contract failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
