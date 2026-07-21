"""UCF CLI — validate, trace, graph, generate, drift, and completeness from specs.

@implements("actions/render-cli-output")
@implements("use-cases/validate-spec-directory")
@implements("use-cases/trace-data-flow")
@implements("use-cases/detect-conflicts")
@implements("use-cases/analyze-dependency-impact")
@implements("use-cases/generate-test-code")
@implements("use-cases/detect-spec-code-drift")
@implements("use-cases/scaffold-specs-from-code")
@implements("use-cases/browse-spec-catalog")
@implements("use-cases/inspect-spec-detail")
@implements("use-cases/explore-dependency-graph")
@implements("use-cases/check-spec-completeness")
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ucf import __version__

app = typer.Typer(
    name="ucf",
    help="Use Case-Driven Development Framework",
    no_args_is_help=True,
)
console = Console()
ir_app = typer.Typer(help="Versioned behavior IR operations")
app.add_typer(ir_app, name="ir")
trust_app = typer.Typer(help="Versioned intent and evidence trust IR operations")
app.add_typer(trust_app, name="trust")
adapter_app = typer.Typer(help="Out-of-process adapter protocol operations")
app.add_typer(adapter_app, name="adapter")
ratchet_app = typer.Typer(help="Versioned brownfield baseline-and-ratchet operations")
app.add_typer(ratchet_app, name="ratchet")
ratchet_v2_app = typer.Typer(help="Ratchet 2.0.0 dual-ledger operations")
ratchet_app.add_typer(ratchet_v2_app, name="v2")
change_app = typer.Typer(
    help="Versioned OpenSpec-compatible change lifecycle operations"
)
app.add_typer(change_app, name="change")
generation_app = typer.Typer(
    help="Versioned deterministic generation operations"
)
app.add_typer(generation_app, name="generation")
evidence_app = typer.Typer(
    help="Versioned verification-evidence freshness operations"
)
app.add_typer(evidence_app, name="evidence")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ucf {__version__}")
        raise typer.Exit()


@app.callback()
def root_options(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed UCF package version and exit.",
    ),
) -> None:
    """Apply root-level diagnostic options."""


@evidence_app.command("record")
def evidence_record(
    result_path: Path = typer.Option(..., "--result"),
    mapping_result_path: Path = typer.Option(..., "--mapping-result"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    inventory_path: Path = typer.Option(..., "--inventory"),
    mapping_adapter_name: str = typer.Option(
        ...,
        "--mapping-adapter-name",
    ),
    mapping_adapter_version: str = typer.Option(
        ...,
        "--mapping-adapter-version",
    ),
    verification_adapter_name: str = typer.Option(
        ...,
        "--verification-adapter-name",
    ),
    verification_adapter_version: str = typer.Option(
        ...,
        "--verification-adapter-version",
    ),
    mapping_capability_version: str = typer.Option(
        ...,
        "--mapping-capability-version",
    ),
    verification_capability_version: str = typer.Option(
        ...,
        "--verification-capability-version",
    ),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Record one exact passed verification without promoting it to verified."""
    from ucf.evidence_status import (
        canonical_evidence_status_json,
        record_verification_evidence,
    )

    try:
        context, inputs = _read_evidence_status_context(
            result_path=result_path,
            mapping_result_path=mapping_result_path,
            onboarding_bundle_path=onboarding_bundle_path,
            inventory_path=inventory_path,
            mapping_adapter_name=mapping_adapter_name,
            mapping_adapter_version=mapping_adapter_version,
            verification_adapter_name=verification_adapter_name,
            verification_adapter_version=verification_adapter_version,
            mapping_capability_version=mapping_capability_version,
            verification_capability_version=(
                verification_capability_version
            ),
        )
        envelope = record_verification_evidence(
            context["result"],
            request=context["result"].request,
            mapping_result=context["mapping_result"],
            bundle=context["bundle"],
            current_inventory=context["inventory"],
            mapping_initialized_adapter=context["mapping_adapter"],
            initialized_adapter=context["verification_adapter"],
            negotiated_capabilities=context["capabilities"],
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="verification evidence output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="verification evidence",
            )

        _publish_exact_file(
            destination,
            canonical_evidence_status_json(envelope),
            before_publish=validate_source,
        )
    except (OSError, TypeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@evidence_app.command("assess")
def evidence_assess(
    envelope_path: Path = typer.Option(..., "--envelope"),
    recorded_result_path: Path = typer.Option(..., "--recorded-result"),
    recorded_mapping_result_path: Path = typer.Option(
        ...,
        "--recorded-mapping-result",
    ),
    recorded_onboarding_bundle_path: Path = typer.Option(
        ...,
        "--recorded-onboarding-bundle",
    ),
    recorded_inventory_path: Path = typer.Option(
        ...,
        "--recorded-inventory",
    ),
    recorded_mapping_adapter_name: str = typer.Option(
        ...,
        "--recorded-mapping-adapter-name",
    ),
    recorded_mapping_adapter_version: str = typer.Option(
        ...,
        "--recorded-mapping-adapter-version",
    ),
    recorded_verification_adapter_name: str = typer.Option(
        ...,
        "--recorded-verification-adapter-name",
    ),
    recorded_verification_adapter_version: str = typer.Option(
        ...,
        "--recorded-verification-adapter-version",
    ),
    recorded_mapping_capability_version: str = typer.Option(
        ...,
        "--recorded-mapping-capability-version",
    ),
    recorded_verification_capability_version: str = typer.Option(
        ...,
        "--recorded-verification-capability-version",
    ),
    output: Path = typer.Option(..., "--output"),
    current_result_path: Path | None = typer.Option(
        None,
        "--current-result",
    ),
    current_mapping_result_path: Path | None = typer.Option(
        None,
        "--current-mapping-result",
    ),
    current_onboarding_bundle_path: Path | None = typer.Option(
        None,
        "--current-onboarding-bundle",
    ),
    current_inventory_path: Path | None = typer.Option(
        None,
        "--current-inventory",
    ),
    current_mapping_adapter_name: str | None = typer.Option(
        None,
        "--current-mapping-adapter-name",
    ),
    current_mapping_adapter_version: str | None = typer.Option(
        None,
        "--current-mapping-adapter-version",
    ),
    current_verification_adapter_name: str | None = typer.Option(
        None,
        "--current-verification-adapter-name",
    ),
    current_verification_adapter_version: str | None = typer.Option(
        None,
        "--current-verification-adapter-version",
    ),
    current_mapping_capability_version: str | None = typer.Option(
        None,
        "--current-mapping-capability-version",
    ),
    current_verification_capability_version: str | None = typer.Option(
        None,
        "--current-verification-capability-version",
    ),
) -> None:
    """Assess exact evidence as fresh, stale, or indeterminate."""
    from ucf.evidence_status import (
        EvidenceStatus,
        assess_verification_evidence,
        canonical_evidence_status_json,
        parse_verification_evidence_envelope_json,
    )

    try:
        envelope_payload, envelope_snapshot = _read_runtime_input(
            envelope_path
        )
        envelope = parse_verification_evidence_envelope_json(
            envelope_payload
        )
        recorded, inputs = _read_evidence_status_context(
            result_path=recorded_result_path,
            mapping_result_path=recorded_mapping_result_path,
            onboarding_bundle_path=recorded_onboarding_bundle_path,
            inventory_path=recorded_inventory_path,
            mapping_adapter_name=recorded_mapping_adapter_name,
            mapping_adapter_version=recorded_mapping_adapter_version,
            verification_adapter_name=(
                recorded_verification_adapter_name
            ),
            verification_adapter_version=(
                recorded_verification_adapter_version
            ),
            mapping_capability_version=(
                recorded_mapping_capability_version
            ),
            verification_capability_version=(
                recorded_verification_capability_version
            ),
        )
        inputs[envelope_path] = (
            envelope_payload,
            envelope_snapshot,
        )
        current, current_inputs = _read_optional_evidence_status_context(
            result_path=current_result_path,
            mapping_result_path=current_mapping_result_path,
            onboarding_bundle_path=current_onboarding_bundle_path,
            inventory_path=current_inventory_path,
            mapping_adapter_name=current_mapping_adapter_name,
            mapping_adapter_version=current_mapping_adapter_version,
            verification_adapter_name=current_verification_adapter_name,
            verification_adapter_version=(
                current_verification_adapter_version
            ),
            mapping_capability_version=(
                current_mapping_capability_version
            ),
            verification_capability_version=(
                current_verification_capability_version
            ),
        )
        inputs.update(current_inputs)
        current_arguments = (
            {}
            if current is None
            else {
                "current_result": current["result"],
                "current_request": current["result"].request,
                "current_mapping_result": current["mapping_result"],
                "current_bundle": current["bundle"],
                "current_inventory": current["inventory"],
                "current_mapping_initialized_adapter": (
                    current["mapping_adapter"]
                ),
                "current_initialized_adapter": (
                    current["verification_adapter"]
                ),
                "current_negotiated_capabilities": (
                    current["capabilities"]
                ),
            }
        )
        assessment = assess_verification_evidence(
            envelope,
            recorded_result=recorded["result"],
            recorded_request=recorded["result"].request,
            recorded_mapping_result=recorded["mapping_result"],
            recorded_bundle=recorded["bundle"],
            recorded_current_inventory=recorded["inventory"],
            recorded_mapping_initialized_adapter=(
                recorded["mapping_adapter"]
            ),
            recorded_initialized_adapter=(
                recorded["verification_adapter"]
            ),
            recorded_negotiated_capabilities=recorded["capabilities"],
            **current_arguments,
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="verification evidence assessment output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="verification evidence assessment",
            )

        _publish_exact_file(
            destination,
            canonical_evidence_status_json(assessment),
            before_publish=validate_source,
        )
    except (OSError, TypeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    if assessment.status is not EvidenceStatus.FRESH:
        raise typer.Exit(code=1)


@generation_app.command(
    "run",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def generation_run(
    request_path: Path = typer.Argument(
        ...,
        help="Exact canonical generation request",
    ),
    command: list[str] = typer.Argument(
        ...,
        help="External generation adapter executable and argv after --",
    ),
    destination: Path = typer.Option(
        ...,
        "--destination",
        help="Generated-only receipt-backed output directory",
    ),
    adapter_cwd: Path = typer.Option(
        Path("."),
        "--adapter-cwd",
        help="Existing adapter working directory",
    ),
    operation_timeout: float = typer.Option(
        30.0,
        "--operation-timeout",
        help="Positive timeout in seconds for generation",
    ),
) -> None:
    """Generate through an external adapter and safely publish its exact tree."""
    import asyncio

    from pydantic import ValidationError

    from ucf.generation import (
        GenerationClientError,
        GenerationPublicationError,
        GenerationValidationError,
        generate_with_adapter,
        parse_generation_request_json,
        publish_generation_result,
    )
    from ucf.ir import IRValidationError

    try:
        _validate_operation_timeout(operation_timeout)
        request_payload, request_snapshot = _read_runtime_input(request_path)
        request = parse_generation_request_json(request_payload)
        request_absolute = request_path.absolute()
        destination_absolute = destination.absolute()
        if (
            request_absolute == destination_absolute
            or request_absolute.is_relative_to(destination_absolute)
        ):
            raise ValueError(
                "generation destination must not contain its request"
            )
        result = asyncio.run(
            generate_with_adapter(
                command=tuple(command),
                cwd=adapter_cwd,
                request=request,
                operation_timeout=operation_timeout,
            )
        )

        def validate_source() -> None:
            if _snapshot_runtime_input(request_path) != request_snapshot:
                raise ValueError(
                    "generation request changed before publication"
                )

        status = publish_generation_result(
            result,
            destination,
            before_commit=validate_source,
        )
    except (
        GenerationClientError,
        GenerationPublicationError,
        GenerationValidationError,
        IRValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    typer.echo(status.value)


@change_app.command("import-openspec")
def change_import_openspec(
    change_directory: Path = typer.Argument(
        ...,
        help="OpenSpec <root>/changes/<change-id> directory",
    ),
    base_behavior_path: Path = typer.Option(
        ...,
        "--base-behavior",
        help="Exact accepted base Behavior IR document",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical immutable change proposal path",
    ),
) -> None:
    """Import one pinned OpenSpec profile read-only and byte-exactly."""
    from ucf.change_lifecycle import (
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        import_openspec_change,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    try:
        behavior_payload, behavior_snapshot = _read_runtime_input(base_behavior_path)
        behavior = parse_ir_json(behavior_payload)
        proposal = import_openspec_change(change_directory, behavior)
        encoded = canonical_change_lifecycle_json(proposal)

        def validate_source() -> None:
            if _snapshot_runtime_input(base_behavior_path) != behavior_snapshot:
                raise ValueError("base Behavior input changed during import")
            confirmation = import_openspec_change(
                change_directory,
                behavior,
            )
            if canonical_change_lifecycle_json(confirmation) != encoded:
                raise ValueError("OpenSpec workspace changed during import")

        destination = _file_destination(
            output,
            inputs=(base_behavior_path,),
            label="change proposal output",
        )
        openspec_root = change_directory.absolute().parent.parent
        if destination.parent == openspec_root or (
            destination.parent.is_relative_to(openspec_root)
        ):
            raise ValueError("change proposal output must be outside the OpenSpec root")
        _publish_exact_file(
            destination,
            encoded,
            before_publish=validate_source,
        )
    except (
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("export-openspec")
def change_export_openspec(
    proposal_path: Path = typer.Argument(
        ...,
        help="Canonical UCF change proposal document",
    ),
    destination: Path = typer.Option(
        ...,
        "--destination",
        help="Absent or byte-identical OpenSpec root directory",
    ),
) -> None:
    """Export preserved OpenSpec artifacts without merging user content."""
    from ucf.change_lifecycle import (
        ChangeLifecycleValidationError,
        export_openspec_change,
        parse_change_proposal_json,
    )

    try:
        payload, snapshot = _read_runtime_input(proposal_path)
        proposal = parse_change_proposal_json(payload)
        destination_absolute = destination.absolute()
        proposal_absolute = proposal_path.absolute()
        if (
            proposal_absolute == destination_absolute
            or proposal_absolute.is_relative_to(destination_absolute)
        ):
            raise ValueError("OpenSpec export destination must not contain its input")

        def validate_source() -> None:
            if _snapshot_runtime_input(proposal_path) != snapshot:
                raise ValueError("change proposal input changed")

        export_openspec_change(
            proposal,
            destination,
            before_publish=validate_source,
        )
        validate_source()
    except (
        ChangeLifecycleValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("derive-delta")
def change_derive_delta(
    proposal_path: Path = typer.Option(
        ...,
        "--proposal",
        help="Exact predecessor change proposal",
    ),
    base_behavior_path: Path = typer.Option(
        ...,
        "--base-behavior",
        help="Exact proposal base Behavior IR",
    ),
    final_behavior_path: Path = typer.Option(
        ...,
        "--final-behavior",
        help="Reviewed final Behavior IR",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical immutable behavior delta path",
    ),
) -> None:
    """Derive the exhaustive typed difference between two Behavior documents."""
    from ucf.change_lifecycle import (
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        derive_behavior_delta,
        parse_change_proposal_json,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    input_paths = (
        proposal_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        proposal_payload, proposal_snapshot = _read_runtime_input(proposal_path)
        base_payload, base_snapshot = _read_runtime_input(base_behavior_path)
        final_payload, final_snapshot = _read_runtime_input(final_behavior_path)
        proposal = parse_change_proposal_json(proposal_payload)
        base = parse_ir_json(base_payload)
        final = parse_ir_json(final_payload)
        delta = derive_behavior_delta(proposal, base, final)
        encoded = canonical_change_lifecycle_json(delta)
        destination = _file_destination(
            output,
            inputs=input_paths,
            label="behavior delta output",
        )
        snapshots = {
            proposal_path: proposal_snapshot,
            base_behavior_path: base_snapshot,
            final_behavior_path: final_snapshot,
        }

        def validate_source() -> None:
            for path, expected in snapshots.items():
                if _snapshot_runtime_input(path) != expected:
                    raise ValueError("change delta input changed")

        _publish_exact_file(
            destination,
            encoded,
            before_publish=validate_source,
        )
    except (
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("derive-tasks")
def change_derive_tasks(
    proposal_path: Path = typer.Option(
        ...,
        "--proposal",
        help="Exact predecessor change proposal",
    ),
    delta_path: Path = typer.Option(
        ...,
        "--delta",
        help="Exact behavior delta",
    ),
    base_behavior_path: Path = typer.Option(
        ...,
        "--base-behavior",
        help="Exact proposal base Behavior IR",
    ),
    final_behavior_path: Path = typer.Option(
        ...,
        "--final-behavior",
        help="Reviewed final Behavior IR",
    ),
    subject_values: list[str] = typer.Option(
        ...,
        "--subject",
        help="TASK=OPERATION:KIND:ID explicit subject assignment",
    ),
    dependency_values: list[str] = typer.Option(
        [],
        "--depends",
        help="TASK=PREDECESSOR explicit dependency",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical immutable task graph path",
    ),
) -> None:
    """Map numbered OpenSpec checkboxes to explicit typed task coordinates."""
    from ucf.change_lifecycle import (
        ChangeLifecycleValidationError,
        DeltaSubjectRef,
        canonical_change_lifecycle_json,
        derive_task_graph,
        parse_behavior_delta_json,
        parse_change_proposal_json,
    )
    from ucf.ir import IRValidationError, parse_ir_json
    from ucf.ir.models import EntityKind

    input_paths = (
        proposal_path,
        delta_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        proposal_payload, proposal_snapshot = _read_runtime_input(proposal_path)
        delta_payload, delta_snapshot = _read_runtime_input(delta_path)
        base_payload, base_snapshot = _read_runtime_input(base_behavior_path)
        final_payload, final_snapshot = _read_runtime_input(final_behavior_path)
        proposal = parse_change_proposal_json(proposal_payload)
        delta = parse_behavior_delta_json(delta_payload)
        base = parse_ir_json(base_payload)
        final = parse_ir_json(final_payload)
        assignments: dict[str, list[DeltaSubjectRef]] = {}
        for value in subject_values:
            task_id, separator, coordinate = value.partition("=")
            components = coordinate.split(":", maxsplit=2)
            if not separator or len(components) != 3:
                raise ValueError("subject must be TASK=OPERATION:KIND:ID")
            operation, target_kind, target_id = components
            assignments.setdefault(task_id, []).append(
                DeltaSubjectRef(
                    kind="delta_subject_ref",
                    operation=operation,
                    target_kind=EntityKind(target_kind),
                    target_id=target_id,
                )
            )
        dependencies: dict[str, list[str]] = {}
        for value in dependency_values:
            task_id, separator, predecessor = value.partition("=")
            if not separator or not task_id or not predecessor:
                raise ValueError("dependency must be TASK=PREDECESSOR")
            dependencies.setdefault(task_id, []).append(predecessor)
        graph = derive_task_graph(
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
            subject_assignments={
                task_id: tuple(subjects) for task_id, subjects in assignments.items()
            },
            dependencies={
                task_id: tuple(predecessors)
                for task_id, predecessors in dependencies.items()
            },
        )
        encoded = canonical_change_lifecycle_json(graph)
        destination = _file_destination(
            output,
            inputs=input_paths,
            label="task graph output",
        )
        snapshots = {
            proposal_path: proposal_snapshot,
            delta_path: delta_snapshot,
            base_behavior_path: base_snapshot,
            final_behavior_path: final_snapshot,
        }

        def validate_source() -> None:
            for path, expected in snapshots.items():
                if _snapshot_runtime_input(path) != expected:
                    raise ValueError("change task input changed")

        _publish_exact_file(
            destination,
            encoded,
            before_publish=validate_source,
        )
    except (
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("complete-task")
def change_complete_task(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    task_graph_path: Path = typer.Option(..., "--tasks"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    task_id: str = typer.Option(..., "--task-id"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Create one immutable task-graph successor in dependency order."""
    from ucf.change_lifecycle import (
        ChangeLifecycleErrorCode,
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        complete_change_task,
        parse_behavior_delta_json,
        parse_change_proposal_json,
        parse_task_graph_json,
        validate_task_graph,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    input_paths = (
        proposal_path,
        delta_path,
        task_graph_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        payloads_and_snapshots = {
            path: _read_runtime_input(path) for path in input_paths
        }
        proposal = parse_change_proposal_json(payloads_and_snapshots[proposal_path][0])
        delta = parse_behavior_delta_json(payloads_and_snapshots[delta_path][0])
        graph = parse_task_graph_json(payloads_and_snapshots[task_graph_path][0])
        base = parse_ir_json(payloads_and_snapshots[base_behavior_path][0])
        final = parse_ir_json(payloads_and_snapshots[final_behavior_path][0])
        validate_task_graph(
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
        )
        successor = complete_change_task(
            graph,
            task_id,
            delta=delta,
            proposal=proposal,
            base_behavior=base,
            final_behavior=final,
        )
        validate_task_graph(
            successor,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
        )
        destination = _file_destination(
            output,
            inputs=input_paths,
            label="task graph successor output",
        )

        def validate_source() -> None:
            for path, (_, expected) in payloads_and_snapshots.items():
                if _snapshot_runtime_input(path) != expected:
                    raise ValueError("change task input changed")

        _publish_exact_file(
            destination,
            canonical_change_lifecycle_json(successor),
            before_publish=validate_source,
        )
    except ChangeLifecycleValidationError as error:
        typer.echo(str(error), err=True)
        exit_code = (
            1 if error.code is ChangeLifecycleErrorCode.INVALID_TRANSITION else 3
        )
        raise typer.Exit(code=exit_code) from error
    except (IRValidationError, OSError, TypeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("record-implementation")
def change_record_implementation(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    task_graph_path: Path = typer.Option(..., "--tasks"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    result_path: Path = typer.Option(..., "--result"),
    mapping_result_path: Path = typer.Option(..., "--mapping-result"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    current_inventory_path: Path = typer.Option(..., "--current-inventory"),
    mapping_adapter_name: str = typer.Option(
        ...,
        "--mapping-adapter-name",
    ),
    mapping_adapter_version: str = typer.Option(
        ...,
        "--mapping-adapter-version",
    ),
    verification_adapter_name: str = typer.Option(
        ...,
        "--verification-adapter-name",
    ),
    verification_adapter_version: str = typer.Option(
        ...,
        "--verification-adapter-version",
    ),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Attach execution results only after full contextual validation."""
    from ucf.change_lifecycle import (
        ChangeLifecycleErrorCode,
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        derive_implementation_record,
        parse_behavior_delta_json,
        parse_change_proposal_json,
        parse_task_graph_json,
        validate_task_graph,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    lifecycle_paths = (
        proposal_path,
        delta_path,
        task_graph_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        inputs = {path: _read_runtime_input(path) for path in lifecycle_paths}
        context, evidence_inputs = _read_change_evidence_context(
            result_path=result_path,
            mapping_result_path=mapping_result_path,
            onboarding_bundle_path=onboarding_bundle_path,
            current_inventory_path=current_inventory_path,
            mapping_adapter_name=mapping_adapter_name,
            mapping_adapter_version=mapping_adapter_version,
            verification_adapter_name=verification_adapter_name,
            verification_adapter_version=verification_adapter_version,
        )
        inputs.update(evidence_inputs)
        proposal = parse_change_proposal_json(inputs[proposal_path][0])
        delta = parse_behavior_delta_json(inputs[delta_path][0])
        graph = parse_task_graph_json(inputs[task_graph_path][0])
        base = parse_ir_json(inputs[base_behavior_path][0])
        final = parse_ir_json(inputs[final_behavior_path][0])
        validate_task_graph(
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
        )
        record = derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
            evidence_contexts=(context,),
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="implementation record output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="implementation evidence",
            )

        _publish_exact_file(
            destination,
            canonical_change_lifecycle_json(record),
            before_publish=validate_source,
        )
    except ChangeLifecycleValidationError as error:
        typer.echo(str(error), err=True)
        exit_code = 1 if error.code is ChangeLifecycleErrorCode.INCOMPLETE_TASKS else 3
        raise typer.Exit(code=exit_code) from error
    except (IRValidationError, OSError, TypeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("verify")
def change_verify(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    task_graph_path: Path = typer.Option(..., "--tasks"),
    implementation_path: Path = typer.Option(..., "--implementation"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    result_path: Path = typer.Option(..., "--result"),
    mapping_result_path: Path = typer.Option(..., "--mapping-result"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    current_inventory_path: Path = typer.Option(..., "--current-inventory"),
    mapping_adapter_name: str = typer.Option(
        ...,
        "--mapping-adapter-name",
    ),
    mapping_adapter_version: str = typer.Option(
        ...,
        "--mapping-adapter-version",
    ),
    verification_adapter_name: str = typer.Option(
        ...,
        "--verification-adapter-name",
    ),
    verification_adapter_version: str = typer.Option(
        ...,
        "--verification-adapter-version",
    ),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Accept a change only after complete tasks and passing exact evidence."""
    from ucf.change_lifecycle import (
        ChangeLifecycleErrorCode,
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        derive_verification_record,
        parse_behavior_delta_json,
        parse_change_proposal_json,
        parse_implementation_record_json,
        parse_task_graph_json,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    lifecycle_paths = (
        proposal_path,
        delta_path,
        task_graph_path,
        implementation_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        inputs = {path: _read_runtime_input(path) for path in lifecycle_paths}
        context, evidence_inputs = _read_change_evidence_context(
            result_path=result_path,
            mapping_result_path=mapping_result_path,
            onboarding_bundle_path=onboarding_bundle_path,
            current_inventory_path=current_inventory_path,
            mapping_adapter_name=mapping_adapter_name,
            mapping_adapter_version=mapping_adapter_version,
            verification_adapter_name=verification_adapter_name,
            verification_adapter_version=verification_adapter_version,
        )
        inputs.update(evidence_inputs)
        proposal = parse_change_proposal_json(inputs[proposal_path][0])
        delta = parse_behavior_delta_json(inputs[delta_path][0])
        graph = parse_task_graph_json(inputs[task_graph_path][0])
        implementation = parse_implementation_record_json(
            inputs[implementation_path][0]
        )
        base = parse_ir_json(inputs[base_behavior_path][0])
        final = parse_ir_json(inputs[final_behavior_path][0])
        verification = derive_verification_record(
            implementation,
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
            evidence_contexts=(context,),
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="verification record output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="verification",
            )

        _publish_exact_file(
            destination,
            canonical_change_lifecycle_json(verification),
            before_publish=validate_source,
        )
    except ChangeLifecycleValidationError as error:
        typer.echo(str(error), err=True)
        exit_code = (
            1
            if error.code
            in {
                ChangeLifecycleErrorCode.EVIDENCE_NOT_PASSED,
                ChangeLifecycleErrorCode.INCOMPLETE_TASKS,
            }
            else 3
        )
        raise typer.Exit(code=exit_code) from error
    except (IRValidationError, OSError, TypeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("archive")
def change_archive(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    task_graph_path: Path = typer.Option(..., "--tasks"),
    implementation_path: Path = typer.Option(..., "--implementation"),
    verification_path: Path = typer.Option(..., "--verification"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    result_path: Path = typer.Option(..., "--result"),
    mapping_result_path: Path = typer.Option(..., "--mapping-result"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    current_inventory_path: Path = typer.Option(..., "--current-inventory"),
    mapping_adapter_name: str = typer.Option(
        ...,
        "--mapping-adapter-name",
    ),
    mapping_adapter_version: str = typer.Option(
        ...,
        "--mapping-adapter-version",
    ),
    verification_adapter_name: str = typer.Option(
        ...,
        "--verification-adapter-name",
    ),
    verification_adapter_version: str = typer.Option(
        ...,
        "--verification-adapter-version",
    ),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Archive one exact accepted chain without mutating its predecessors."""
    from ucf.change_lifecycle import (
        ChangeLifecycleErrorCode,
        ChangeLifecycleValidationError,
        canonical_change_lifecycle_json,
        derive_archive_record,
        parse_behavior_delta_json,
        parse_change_proposal_json,
        parse_implementation_record_json,
        parse_task_graph_json,
        parse_verification_record_json,
    )
    from ucf.ir import IRValidationError, parse_ir_json

    lifecycle_paths = (
        proposal_path,
        delta_path,
        task_graph_path,
        implementation_path,
        verification_path,
        base_behavior_path,
        final_behavior_path,
    )
    try:
        inputs = {path: _read_runtime_input(path) for path in lifecycle_paths}
        context, evidence_inputs = _read_change_evidence_context(
            result_path=result_path,
            mapping_result_path=mapping_result_path,
            onboarding_bundle_path=onboarding_bundle_path,
            current_inventory_path=current_inventory_path,
            mapping_adapter_name=mapping_adapter_name,
            mapping_adapter_version=mapping_adapter_version,
            verification_adapter_name=verification_adapter_name,
            verification_adapter_version=verification_adapter_version,
        )
        inputs.update(evidence_inputs)
        proposal = parse_change_proposal_json(inputs[proposal_path][0])
        delta = parse_behavior_delta_json(inputs[delta_path][0])
        graph = parse_task_graph_json(inputs[task_graph_path][0])
        implementation = parse_implementation_record_json(
            inputs[implementation_path][0]
        )
        verification = parse_verification_record_json(inputs[verification_path][0])
        base = parse_ir_json(inputs[base_behavior_path][0])
        final = parse_ir_json(inputs[final_behavior_path][0])
        archive = derive_archive_record(
            proposal,
            delta,
            graph,
            implementation,
            verification,
            base,
            final,
            evidence_contexts=(context,),
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="archive record output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="archive",
            )

        _publish_exact_file(
            destination,
            canonical_change_lifecycle_json(archive),
            before_publish=validate_source,
        )
    except ChangeLifecycleValidationError as error:
        typer.echo(str(error), err=True)
        exit_code = (
            1
            if error.code
            in {
                ChangeLifecycleErrorCode.EVIDENCE_NOT_PASSED,
                ChangeLifecycleErrorCode.INCOMPLETE_TASKS,
            }
            else 3
        )
        raise typer.Exit(code=exit_code) from error
    except (
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("impact")
def change_impact(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Derive deterministic structural impact without semantic guessing."""
    from ucf.change_governance import (
        ChangeGovernanceValidationError,
        canonical_change_governance_json,
        derive_impact_report,
    )
    from ucf.change_lifecycle import ChangeLifecycleValidationError
    from ucf.ir import IRValidationError

    try:
        inputs, proposal, delta, base, final = _read_change_governance_context(
            proposal_path=proposal_path,
            delta_path=delta_path,
            base_behavior_path=base_behavior_path,
            final_behavior_path=final_behavior_path,
        )
        report = derive_impact_report(
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="change impact output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(inputs, label="change impact")

        _publish_exact_file(
            destination,
            canonical_change_governance_json(report),
            before_publish=validate_source,
        )
    except (
        ChangeGovernanceValidationError,
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("assess")
def change_assess(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    impact_path: Path = typer.Option(..., "--impact"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Validate and publish one exhaustive authored decision assessment."""
    from ucf.change_governance import (
        ChangeGovernanceValidationError,
        canonical_change_governance_json,
        parse_decision_assessment_json,
        parse_impact_report_json,
        validate_decision_assessment,
    )
    from ucf.change_lifecycle import ChangeLifecycleValidationError
    from ucf.ir import IRValidationError

    try:
        inputs, proposal, delta, base, final = _read_change_governance_context(
            proposal_path=proposal_path,
            delta_path=delta_path,
            base_behavior_path=base_behavior_path,
            final_behavior_path=final_behavior_path,
        )
        impact_payload, impact_snapshot = _read_runtime_input(impact_path)
        assessment_payload, assessment_snapshot = _read_runtime_input(assessment_path)
        inputs[impact_path] = (impact_payload, impact_snapshot)
        inputs[assessment_path] = (
            assessment_payload,
            assessment_snapshot,
        )
        impact = parse_impact_report_json(impact_payload)
        assessment = parse_decision_assessment_json(assessment_payload)
        validate_decision_assessment(
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="decision assessment output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="decision assessment",
            )

        _publish_exact_file(
            destination,
            canonical_change_governance_json(assessment),
            before_publish=validate_source,
        )
    except (
        ChangeGovernanceValidationError,
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("decide")
def change_decide(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    impact_path: Path = typer.Option(..., "--impact"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    declaration_path: Path = typer.Option(..., "--declaration"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Validate and publish a decision bound to the exact applicable classes."""
    from ucf.change_governance import (
        ChangeGovernanceValidationError,
        canonical_change_governance_json,
        parse_decision_assessment_json,
        parse_decision_declaration_json,
        parse_impact_report_json,
        validate_decision_declaration,
    )
    from ucf.change_lifecycle import ChangeLifecycleValidationError
    from ucf.ir import IRValidationError

    try:
        inputs, proposal, delta, base, final = _read_change_governance_context(
            proposal_path=proposal_path,
            delta_path=delta_path,
            base_behavior_path=base_behavior_path,
            final_behavior_path=final_behavior_path,
        )
        for path in (impact_path, assessment_path, declaration_path):
            inputs[path] = _read_runtime_input(path)
        impact = parse_impact_report_json(inputs[impact_path][0])
        assessment = parse_decision_assessment_json(inputs[assessment_path][0])
        declaration = parse_decision_declaration_json(inputs[declaration_path][0])
        validate_decision_declaration(
            declaration,
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="decision declaration output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(
                inputs,
                label="decision declaration",
            )

        _publish_exact_file(
            destination,
            canonical_change_governance_json(declaration),
            before_publish=validate_source,
        )
    except (
        ChangeGovernanceValidationError,
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@change_app.command("gate")
def change_gate(
    proposal_path: Path = typer.Option(..., "--proposal"),
    delta_path: Path = typer.Option(..., "--delta"),
    base_behavior_path: Path = typer.Option(..., "--base-behavior"),
    final_behavior_path: Path = typer.Option(..., "--final-behavior"),
    impact_path: Path = typer.Option(..., "--impact"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    declaration_path: Path | None = typer.Option(None, "--declaration"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Recompute the exact approval gate; blocked outcomes exit with one."""
    from ucf.change_governance import (
        ChangeGovernanceValidationError,
        GateStatus,
        canonical_change_governance_json,
        evaluate_change_gate,
        parse_decision_assessment_json,
        parse_decision_declaration_json,
        parse_impact_report_json,
    )
    from ucf.change_lifecycle import ChangeLifecycleValidationError
    from ucf.ir import IRValidationError

    try:
        inputs, proposal, delta, base, final = _read_change_governance_context(
            proposal_path=proposal_path,
            delta_path=delta_path,
            base_behavior_path=base_behavior_path,
            final_behavior_path=final_behavior_path,
        )
        for path in (impact_path, assessment_path):
            inputs[path] = _read_runtime_input(path)
        declaration = None
        if declaration_path is not None:
            inputs[declaration_path] = _read_runtime_input(declaration_path)
            declaration = parse_decision_declaration_json(inputs[declaration_path][0])
        impact = parse_impact_report_json(inputs[impact_path][0])
        assessment = parse_decision_assessment_json(inputs[assessment_path][0])
        gate = evaluate_change_gate(
            assessment,
            impact,
            declaration,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        passing = {
            GateStatus.PASS_NO_DECISION,
            GateStatus.PASS_APPROVED,
        }
        if gate.status not in passing:
            _validate_change_input_snapshots(inputs, label="change gate")
            typer.echo(gate.status.value, err=True)
            raise typer.Exit(code=1)
        destination = _file_destination(
            output,
            inputs=tuple(inputs),
            label="gate evaluation output",
        )

        def validate_source() -> None:
            _validate_change_input_snapshots(inputs, label="change gate")

        _publish_exact_file(
            destination,
            canonical_change_governance_json(gate),
            before_publish=validate_source,
        )
    except (
        ChangeGovernanceValidationError,
        ChangeLifecycleValidationError,
        IRValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@adapter_app.command("kit")
def adapter_kit(
    extract: Path | None = typer.Option(
        None,
        "--extract",
        help="Extract the complete conformance kit into an empty directory",
    ),
) -> None:
    """Inspect or safely extract the installed adapter conformance kit."""
    from ucf.adapter_conformance import (
        canonical_conformance_json,
        conformance_kit_index,
        extract_conformance_kit,
    )

    try:
        index = (
            extract_conformance_kit(extract)
            if extract is not None
            else conformance_kit_index()
        )
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    typer.echo(
        canonical_conformance_json(index).decode("utf-8"),
        nl=False,
    )


@adapter_app.command(
    "inventory",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def adapter_inventory(
    root: Path = typer.Argument(
        ...,
        help="Existing repository root to inventory read-only",
    ),
    command: list[str] = typer.Argument(
        ...,
        help="Adapter executable and argv, conventionally after --",
    ),
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Strict JSON exclusion policy",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical snapshot path outside the repository root",
    ),
    subject_uri: str = typer.Option(
        ...,
        "--subject-uri",
        help="Stable non-file URI identifying the inventoried repository",
    ),
    page_record_limit: int = typer.Option(
        256,
        "--page-record-limit",
        min=1,
        max=256,
        help="Maximum logical records requested per adapter page",
    ),
    operation_timeout: float = typer.Option(
        30.0,
        "--operation-timeout",
        help="Positive timeout in seconds for each adapter page",
    ),
) -> None:
    """Collect one strict, deterministic, observed-only inventory snapshot."""
    import asyncio

    from pydantic import ValidationError

    from ucf.adapter_protocol import AdapterProtocolError
    from ucf.inventory import (
        canonical_inventory_json,
        collect_inventory,
    )

    try:
        repository = _resolved_inventory_root(root)
        destination = _outside_inventory_destination(
            repository,
            output,
            inputs=(policy_path,),
        )
        _validate_operation_timeout(operation_timeout)
        request = _inventory_request_from_options(
            policy_path=policy_path,
            subject_uri=subject_uri,
            page_record_limit=page_record_limit,
        )
        snapshot = asyncio.run(
            collect_inventory(
                command=tuple(command),
                cwd=repository,
                request=request,
                operation_timeout=operation_timeout,
            )
        )
        _atomic_write(destination, canonical_inventory_json(snapshot))
    except AdapterProtocolError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    except ValidationError as error:
        typer.echo("inventory command configuration is invalid", err=True)
        raise typer.Exit(code=3) from error
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@adapter_app.command(
    "discover",
    context_settings={"allow_extra_args": True},
)
def adapter_discover(
    root: Path = typer.Argument(
        ...,
        help="Existing repository root to inspect read-only",
    ),
    command: list[str] = typer.Argument(
        ...,
        help="Adapter executable and argv after --",
    ),
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Strict JSON exclusion policy",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical discovery path outside the repository root",
    ),
    subject_uri: str = typer.Option(
        ...,
        "--subject-uri",
        help="Stable non-file URI identifying the repository",
    ),
    page_record_limit: int = typer.Option(
        256,
        "--page-record-limit",
        min=1,
        max=256,
        help="Maximum logical records requested per inventory page",
    ),
    operation_timeout: float = typer.Option(
        30.0,
        "--operation-timeout",
        help="Positive timeout in seconds for each adapter operation",
    ),
) -> None:
    """Export exact candidates for human review without materializing intent."""
    import asyncio

    from pydantic import ValidationError

    from ucf.adapter_protocol import AdapterProtocolError
    from ucf.onboarding import (
        canonical_onboarding_json,
        collect_onboarding_evidence,
    )

    try:
        repository = _resolved_inventory_root(root)
        destination = _outside_inventory_destination(
            repository,
            output,
            inputs=(policy_path,),
        )
        _validate_operation_timeout(operation_timeout)
        request = _inventory_request_from_options(
            policy_path=policy_path,
            subject_uri=subject_uri,
            page_record_limit=page_record_limit,
        )
        evidence = asyncio.run(
            collect_onboarding_evidence(
                command=tuple(command),
                cwd=repository,
                inventory_request=request,
                operation_timeout=operation_timeout,
            )
        )
        _atomic_write(
            destination,
            canonical_onboarding_json(evidence.discovery),
        )
    except AdapterProtocolError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    except ValidationError as error:
        typer.echo("discovery command configuration is invalid", err=True)
        raise typer.Exit(code=3) from error
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@adapter_app.command(
    "onboard",
    context_settings={"allow_extra_args": True},
)
def adapter_onboard(
    root: Path = typer.Argument(
        ...,
        help="Existing repository root to onboard read-only",
    ),
    command: list[str] = typer.Argument(
        ...,
        help="Adapter executable and argv after --",
    ),
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Strict JSON exclusion policy",
    ),
    decisions_path: Path = typer.Option(
        ...,
        "--decisions",
        help="Exact human-authored onboarding DecisionSet",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical onboarding bundle outside the repository root",
    ),
    subject_uri: str = typer.Option(
        ...,
        "--subject-uri",
        help="Stable non-file URI identifying the repository",
    ),
    page_record_limit: int = typer.Option(
        256,
        "--page-record-limit",
        min=1,
        max=256,
        help="Maximum logical records requested per inventory page",
    ),
    operation_timeout: float = typer.Option(
        30.0,
        "--operation-timeout",
        help="Positive timeout in seconds for each adapter operation",
    ),
) -> None:
    """Revalidate reviewed candidates and atomically freeze an honest baseline."""
    import asyncio

    from pydantic import ValidationError

    from ucf.adapter_protocol import AdapterProtocolError
    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        build_onboarding_bundle,
        canonical_onboarding_json,
        collect_onboarding_evidence,
        parse_decision_set_json,
        parse_onboarding_bundle_json,
    )

    try:
        repository = _resolved_inventory_root(root)
        destination = _outside_inventory_destination(
            repository,
            output,
            inputs=(policy_path, decisions_path),
        )
        _validate_operation_timeout(operation_timeout)
        try:
            decisions = parse_decision_set_json(decisions_path.read_bytes())
        except (IRValidationError, ValidationError, TypeError) as error:
            raise ValueError("onboarding decision set is invalid") from error
        request = _inventory_request_from_options(
            policy_path=policy_path,
            subject_uri=subject_uri,
            page_record_limit=page_record_limit,
        )
        evidence = asyncio.run(
            collect_onboarding_evidence(
                command=tuple(command),
                cwd=repository,
                inventory_request=request,
                operation_timeout=operation_timeout,
            )
        )
        bundle = build_onboarding_bundle(
            evidence.inventory,
            evidence.discovery,
            decisions,
        )
        encoded = canonical_onboarding_json(bundle)
        validated = parse_onboarding_bundle_json(encoded)
        _atomic_write(destination, canonical_onboarding_json(validated))
    except AdapterProtocolError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    except OnboardingValidationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    except ValidationError as error:
        typer.echo("onboarding command configuration is invalid", err=True)
        raise typer.Exit(code=3) from error
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@adapter_app.command(
    "conformance",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def adapter_conformance_run(
    command: list[str] = typer.Argument(
        ...,
        help="Adapter executable and argv, conventionally after --",
    ),
    cwd: Path = typer.Option(
        Path("."),
        "--cwd",
        help="Existing adapter working directory",
    ),
    report_path: Path | None = typer.Option(
        None,
        "--report",
        help="Write the canonical report atomically instead of stdout",
    ),
) -> None:
    """Run the versioned black-box conformance suite."""
    from ucf.adapter_conformance import (
        canonical_conformance_json,
        exit_code_for_report,
        run_conformance,
    )

    try:
        report = run_conformance(command=tuple(command), cwd=cwd)
        encoded = canonical_conformance_json(report)
        if report_path is None:
            typer.echo(encoded.decode("utf-8"), nl=False)
        else:
            _atomic_write(report_path, encoded)
    except (OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    raise typer.Exit(code=int(exit_code_for_report(report)))


@adapter_app.command(
    "import-runtime-evidence",
    context_settings={"allow_extra_args": True},
)
def adapter_import_runtime_evidence(
    command: list[str] = typer.Argument(
        ...,
        help="Adapter executable and argv after --",
    ),
    recording_path: Path = typer.Option(
        ...,
        "--recording",
        help="Bounded recorded runtime input",
    ),
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Exact runtime evidence allowlist policy",
    ),
    environment_path: Path = typer.Option(
        ...,
        "--environment",
        help="Exact runtime environment identity document",
    ),
    behavior_ir_path: Path = typer.Option(
        ...,
        "--behavior-ir",
        help="Exact Behavior IR document to enrich",
    ),
    source_uri: str = typer.Option(
        ...,
        "--source-uri",
        help="Stable opaque URI identifying the recording",
    ),
    captured_at: str = typer.Option(
        ...,
        "--captured-at",
        help="UTC capture timestamp",
    ),
    sampling_procedure_uri: str = typer.Option(
        ...,
        "--sampling-procedure-uri",
        help="Versioned procedure describing partial sampling",
    ),
    adapter_procedure_uri: str = typer.Option(
        ...,
        "--adapter-procedure-uri",
        help="Versioned adapter procedure expected in the result",
    ),
    adapter_cwd: Path = typer.Option(
        ...,
        "--adapter-cwd",
        help="Existing adapter working directory",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical authoritative runtime evidence result",
    ),
    operation_timeout: float = typer.Option(
        30.0,
        "--operation-timeout",
        help="Positive timeout in seconds for the adapter operation",
    ),
) -> None:
    """Import sanitized recorded evidence without promoting its claim level."""
    import asyncio

    from ucf.runtime_evidence import (
        RuntimeEvidenceAcceptedResult,
        RuntimeEvidenceClientError,
        RuntimeEvidenceRejectedResult,
        canonical_runtime_evidence_json,
        import_runtime_evidence,
        parse_runtime_evidence_result_json,
    )

    diagnostic: str | None = None
    rejection_codes: tuple[str, ...] = ()
    try:
        input_paths = (
            recording_path,
            policy_path,
            environment_path,
            behavior_ir_path,
        )
        destination = _file_destination(
            output,
            inputs=input_paths,
            label="runtime evidence output",
        )
        _validate_operation_timeout(operation_timeout)
        cwd = adapter_cwd.resolve(strict=True)
        if not cwd.is_dir() or not command:
            raise ValueError("runtime evidence adapter is invalid")
        request, behavior, environment, snapshots = (
            _runtime_evidence_request_from_options(
                recording_path=recording_path,
                policy_path=policy_path,
                environment_path=environment_path,
                behavior_ir_path=behavior_ir_path,
                source_uri=source_uri,
                captured_at=captured_at,
                sampling_procedure_uri=sampling_procedure_uri,
                adapter_procedure_uri=adapter_procedure_uri,
            )
        )
        result = asyncio.run(
            import_runtime_evidence(
                command=tuple(command),
                cwd=cwd,
                recording_path=recording_path,
                request=request,
                behavior=behavior,
                environment=environment,
                operation_timeout=operation_timeout,
            )
        )
        _validate_runtime_input_snapshots(snapshots)
        destination = _file_destination(
            output,
            inputs=input_paths,
            label="runtime evidence output",
        )
        if isinstance(result, RuntimeEvidenceRejectedResult):
            rejection_codes = tuple(reason.value for reason in result.reason_codes)
        elif isinstance(result, RuntimeEvidenceAcceptedResult):
            encoded = canonical_runtime_evidence_json(result)
            validated = parse_runtime_evidence_result_json(encoded)
            if not isinstance(validated, RuntimeEvidenceAcceptedResult):
                raise ValueError("runtime evidence result status changed")
            _atomic_write(
                destination,
                canonical_runtime_evidence_json(validated),
            )
        else:
            raise TypeError("unsupported runtime evidence result")
    except RuntimeEvidenceClientError as error:
        diagnostic = f"runtime_evidence/{error.category.value}/{error.code.value}"
    except (OSError, TypeError, ValueError):
        diagnostic = "runtime_evidence/invalid_input"

    if diagnostic is not None:
        typer.echo(diagnostic, err=True)
        raise typer.Exit(code=3)
    if rejection_codes:
        for reason in rejection_codes:
            typer.echo(
                f"runtime_evidence/policy_rejected/{reason}",
                err=True,
            )
        raise typer.Exit(code=1)


@ratchet_app.command("establish")
def ratchet_establish(
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Exact ratchet policy document",
    ),
    onboarding_bundle_path: Path = typer.Option(
        ...,
        "--onboarding-bundle",
        help="Exact reconciled onboarding bundle",
    ),
    assessment_path: Path = typer.Option(
        ...,
        "--assessment",
        help="Exact complete initial ratchet assessment",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="New canonical initial baseline path",
    ),
) -> None:
    """Explicitly establish the first immutable accepted baseline."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet import (
        RatchetValidationError,
        canonical_ratchet_json,
        establish_ratchet_baseline,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_policy_json,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                policy_path,
                onboarding_bundle_path,
                assessment_path,
            ),
            label="ratchet output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        baseline = establish_ratchet_baseline(
            policy,
            bundle,
            assessment,
        )
        encoded = canonical_ratchet_json(baseline)
        validated = parse_ratchet_baseline_json(encoded)
        _atomic_write(
            destination,
            canonical_ratchet_json(validated),
        )
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@ratchet_app.command("evaluate")
def ratchet_evaluate(
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Exact ratchet policy document",
    ),
    onboarding_bundle_path: Path = typer.Option(
        ...,
        "--onboarding-bundle",
        help="Exact current reconciled onboarding bundle",
    ),
    baseline_path: Path = typer.Option(
        ...,
        "--baseline",
        help="Exact accepted baseline",
    ),
    assessment_path: Path = typer.Option(
        ...,
        "--assessment",
        help="Exact current ratchet assessment",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="Canonical evaluation report path",
    ),
) -> None:
    """Evaluate current evidence without changing the accepted baseline."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet import (
        EvaluationOutcome,
        RatchetValidationError,
        canonical_ratchet_json,
        evaluate_ratchet,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_evaluation_report_json,
        parse_ratchet_policy_json,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                policy_path,
                onboarding_bundle_path,
                baseline_path,
                assessment_path,
            ),
            label="ratchet output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        baseline = parse_ratchet_baseline_json(baseline_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        report = evaluate_ratchet(
            policy,
            baseline,
            bundle,
            assessment,
        )
        encoded = canonical_ratchet_json(report)
        validated = parse_ratchet_evaluation_report_json(encoded)
        _atomic_write(
            destination,
            canonical_ratchet_json(validated),
        )
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    if report.outcome is not EvaluationOutcome.PASS:
        raise typer.Exit(code=1)


@ratchet_app.command("advance")
def ratchet_advance(
    policy_path: Path = typer.Option(
        ...,
        "--policy",
        help="Exact ratchet policy document",
    ),
    onboarding_bundle_path: Path = typer.Option(
        ...,
        "--onboarding-bundle",
        help="Exact current reconciled onboarding bundle",
    ),
    baseline_path: Path = typer.Option(
        ...,
        "--baseline",
        help="Exact accepted predecessor baseline",
    ),
    assessment_path: Path = typer.Option(
        ...,
        "--assessment",
        help="Exact current ratchet assessment",
    ),
    evaluation_path: Path = typer.Option(
        ...,
        "--evaluation",
        help="Exact recomputable evaluation report",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        help="New canonical successor baseline path",
    ),
) -> None:
    """Advance only through an exact complete passing evaluation."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet import (
        EvaluationOutcome,
        RatchetValidationError,
        advance_ratchet_baseline,
        canonical_ratchet_json,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_evaluation_report_json,
        parse_ratchet_policy_json,
        validate_ratchet_evaluation_report,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                policy_path,
                onboarding_bundle_path,
                baseline_path,
                assessment_path,
                evaluation_path,
            ),
            label="ratchet output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        baseline = parse_ratchet_baseline_json(baseline_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        report = parse_ratchet_evaluation_report_json(evaluation_path.read_bytes())
        validate_ratchet_evaluation_report(
            policy,
            baseline,
            bundle,
            assessment,
            report,
        )
        blocked = report.outcome is not EvaluationOutcome.PASS
        if not blocked:
            successor = advance_ratchet_baseline(
                policy,
                baseline,
                bundle,
                assessment,
                report,
            )
            encoded = canonical_ratchet_json(successor)
            validated = parse_ratchet_baseline_json(encoded)
            _atomic_write(
                destination,
                canonical_ratchet_json(validated),
            )
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    if blocked:
        raise typer.Exit(code=1)


@ratchet_v2_app.command("establish")
def ratchet_v2_establish(
    policy_path: Path = typer.Option(..., "--policy"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Establish an immutable Ratchet 2.0.0 dual-ledger baseline."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet.v2 import (
        RatchetValidationError,
        canonical_ratchet_json,
        establish_ratchet_baseline,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_policy_json,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(policy_path, onboarding_bundle_path, assessment_path),
            label="ratchet v2 output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        baseline = establish_ratchet_baseline(policy, bundle, assessment)
        encoded = canonical_ratchet_json(baseline)
        validated = parse_ratchet_baseline_json(encoded)
        _atomic_write(destination, canonical_ratchet_json(validated))
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


@ratchet_v2_app.command("evaluate")
def ratchet_v2_evaluate(
    policy_path: Path = typer.Option(..., "--policy"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    baseline_path: Path = typer.Option(..., "--baseline"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    accepted_baseline_id: str = typer.Option(..., "--accepted-baseline-id"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Evaluate both ledgers against an independently accepted baseline."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet.v2 import (
        CombinedOutcome,
        RatchetValidationError,
        canonical_ratchet_json,
        evaluate_ratchet,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_evaluation_report_json,
        parse_ratchet_policy_json,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                policy_path,
                onboarding_bundle_path,
                baseline_path,
                assessment_path,
            ),
            label="ratchet v2 output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        baseline = parse_ratchet_baseline_json(baseline_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        report = evaluate_ratchet(
            policy,
            baseline,
            bundle,
            assessment,
            accepted_baseline_id=accepted_baseline_id,
        )
        encoded = canonical_ratchet_json(report)
        validated = parse_ratchet_evaluation_report_json(encoded)
        _atomic_write(destination, canonical_ratchet_json(validated))
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    if report.combined_outcome not in {
        CombinedOutcome.PASS,
        CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT,
    }:
        raise typer.Exit(code=1)


@ratchet_v2_app.command("advance")
def ratchet_v2_advance(
    policy_path: Path = typer.Option(..., "--policy"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    baseline_path: Path = typer.Option(..., "--baseline"),
    assessment_path: Path = typer.Option(..., "--assessment"),
    evaluation_path: Path = typer.Option(..., "--evaluation"),
    accepted_baseline_id: str = typer.Option(..., "--accepted-baseline-id"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Advance both ledgers after an exact passing Ratchet 2.0.0 report."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet.v2 import (
        CombinedOutcome,
        RatchetValidationError,
        advance_ratchet_baseline,
        canonical_ratchet_json,
        parse_ratchet_assessment_json,
        parse_ratchet_baseline_json,
        parse_ratchet_evaluation_report_json,
        parse_ratchet_policy_json,
        validate_ratchet_evaluation_report,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                policy_path,
                onboarding_bundle_path,
                baseline_path,
                assessment_path,
                evaluation_path,
            ),
            label="ratchet v2 output",
        )
        policy = parse_ratchet_policy_json(policy_path.read_bytes())
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        baseline = parse_ratchet_baseline_json(baseline_path.read_bytes())
        assessment = parse_ratchet_assessment_json(assessment_path.read_bytes())
        report = parse_ratchet_evaluation_report_json(
            evaluation_path.read_bytes()
        )
        validate_ratchet_evaluation_report(
            policy,
            baseline,
            bundle,
            assessment,
            report,
            accepted_baseline_id=accepted_baseline_id,
        )
        blocked = report.combined_outcome not in {
            CombinedOutcome.PASS,
            CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT,
        }
        if not blocked:
            successor = advance_ratchet_baseline(
                policy,
                baseline,
                bundle,
                assessment,
                report,
                accepted_predecessor_id=accepted_baseline_id,
            )
            encoded = canonical_ratchet_json(successor)
            validated = parse_ratchet_baseline_json(encoded)
            _atomic_write(destination, canonical_ratchet_json(validated))
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error
    if blocked:
        raise typer.Exit(code=1)


@ratchet_v2_app.command("migrate-from-v1")
def ratchet_v2_migrate_from_v1(
    target_policy_path: Path = typer.Option(..., "--target-policy"),
    source_policy_path: Path = typer.Option(..., "--source-policy"),
    source_baseline_path: Path = typer.Option(..., "--source-baseline"),
    source_assessment_path: Path = typer.Option(..., "--source-assessment"),
    onboarding_bundle_path: Path = typer.Option(..., "--onboarding-bundle"),
    accepted_source_baseline_id: str = typer.Option(
        ...,
        "--accepted-source-baseline-id",
    ),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Migrate one exact, independently accepted Ratchet 1.x tip."""
    from pydantic import ValidationError

    from ucf.ir import IRValidationError
    from ucf.onboarding import (
        OnboardingValidationError,
        parse_onboarding_bundle_json,
    )
    from ucf.ratchet import (
        parse_ratchet_assessment_json as parse_v1_assessment_json,
    )
    from ucf.ratchet import parse_ratchet_baseline_json as parse_v1_baseline_json
    from ucf.ratchet import parse_ratchet_policy_json as parse_v1_policy_json
    from ucf.ratchet.v2 import (
        RatchetValidationError,
        canonical_ratchet_json,
        migrate_ratchet_v1_baseline,
        parse_ratchet_baseline_json,
        parse_ratchet_policy_json,
    )

    try:
        destination = _file_destination(
            output,
            inputs=(
                target_policy_path,
                source_policy_path,
                source_baseline_path,
                source_assessment_path,
                onboarding_bundle_path,
            ),
            label="ratchet v2 migration output",
        )
        target_policy = parse_ratchet_policy_json(target_policy_path.read_bytes())
        source_policy = parse_v1_policy_json(source_policy_path.read_bytes())
        source_baseline = parse_v1_baseline_json(
            source_baseline_path.read_bytes()
        )
        source_assessment = parse_v1_assessment_json(
            source_assessment_path.read_bytes()
        )
        bundle = parse_onboarding_bundle_json(onboarding_bundle_path.read_bytes())
        migrated = migrate_ratchet_v1_baseline(
            target_policy,
            source_policy,
            source_baseline,
            source_assessment,
            bundle,
            accepted_source_baseline_id=accepted_source_baseline_id,
        )
        encoded = canonical_ratchet_json(migrated)
        validated = parse_ratchet_baseline_json(encoded)
        _atomic_write(destination, canonical_ratchet_json(validated))
    except (
        IRValidationError,
        OnboardingValidationError,
        RatchetValidationError,
        ValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=3) from error


def _atomic_write(destination: Path, content: bytes) -> None:
    parent = destination.parent
    if not parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        replaced = True
    finally:
        if not replaced:
            temporary.unlink(missing_ok=True)


def _publish_exact_file(
    destination: Path,
    content: bytes,
    *,
    before_publish: Callable[[], None] | None = None,
) -> None:
    if before_publish is not None:
        before_publish()
    if _path_entry_exists(destination):
        if _read_stable_existing_output(destination) == content:
            return
        raise ValueError("existing output differs from canonical content")
    parent = destination.parent
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    published = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if before_publish is not None:
            before_publish()
        if _path_entry_exists(destination):
            raise ValueError("output appeared before publication")
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as error:
            if _read_stable_existing_output(destination) == content:
                return
            raise ValueError("output appeared before publication") from error
        temporary.unlink()
        published = True
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        parent_descriptor = os.open(parent, directory_flags)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        if not published:
            temporary.unlink(missing_ok=True)


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _read_stable_existing_output(path: Path) -> bytes:
    initial = path.lstat()
    if stat.S_ISLNK(initial.st_mode):
        raise ValueError("existing output must not be a symbolic link")
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError("existing output must be a regular file")
    if initial.st_nlink != 1:
        raise ValueError("existing output must have exactly one hard link")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if _publication_identity(opened) != _publication_identity(initial):
            raise ValueError("existing output changed while opening")
        payload = stream.read()
        finished = os.fstat(stream.fileno())
    if _publication_identity(finished) != _publication_identity(opened):
        raise ValueError("existing output changed while reading")
    current = path.lstat()
    if _publication_identity(current) != _publication_identity(finished):
        raise ValueError("existing output changed while validating")
    return payload


def _publication_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _validate_operation_timeout(operation_timeout: float) -> None:
    import math

    if not math.isfinite(operation_timeout) or operation_timeout <= 0:
        raise ValueError("operation timeout must be finite and positive")


type _RuntimeInputSnapshot = tuple[int, int, int, int, int, str]


def _runtime_evidence_request_from_options(
    *,
    recording_path: Path,
    policy_path: Path,
    environment_path: Path,
    behavior_ir_path: Path,
    source_uri: str,
    captured_at: str,
    sampling_procedure_uri: str,
    adapter_procedure_uri: str,
):
    import hashlib

    from ucf.adapter_protocol import CapabilitySelection
    from ucf.ir import canonical_ir_json, parse_ir_json
    from ucf.ir.models import Digest
    from ucf.ir.trust_models import BehaviorDocumentRef
    from ucf.runtime_evidence import (
        RUNTIME_EVIDENCE_CAPABILITY,
        RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
        RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI,
        RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
        RUNTIME_EVIDENCE_VERSION,
        RuntimeEnvironmentRef,
        RuntimeEvidenceImportRequest,
        RuntimeSamplingScope,
        RuntimeSource,
        canonical_runtime_evidence_digest,
        parse_runtime_environment_json,
        parse_runtime_evidence_policy_json,
        runtime_recording_digest,
    )

    policy_payload, policy_snapshot = _read_runtime_input(policy_path)
    environment_payload, environment_snapshot = _read_runtime_input(environment_path)
    behavior_payload, behavior_snapshot = _read_runtime_input(behavior_ir_path)
    recording_snapshot = _snapshot_runtime_input(recording_path)
    recording_revision = runtime_recording_digest(recording_path)
    if recording_snapshot != _snapshot_runtime_input(recording_path):
        raise ValueError("runtime recording changed while preparing request")

    policy = parse_runtime_evidence_policy_json(policy_payload)
    environment = parse_runtime_environment_json(environment_payload)
    behavior = parse_ir_json(behavior_payload)
    behavior_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(canonical_ir_json(behavior).encode("ascii")).hexdigest(),
    )
    request = RuntimeEvidenceImportRequest(
        kind="runtime_evidence_import_request",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=behavior.document_id,
            ir_version=behavior.ir_version,
            canonical_digest=behavior_digest,
        ),
        source=RuntimeSource(
            kind="runtime_source",
            source_uri=source_uri,
            source_revision=recording_revision,
            captured_at=captured_at,
        ),
        environment=RuntimeEnvironmentRef(
            kind="runtime_environment_ref",
            schema_uri=RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
            schema_version=RUNTIME_EVIDENCE_VERSION,
            environment_uri=environment.environment_uri,
            revision=environment.revision,
            canonical_digest=canonical_runtime_evidence_digest(environment),
        ),
        sampling=RuntimeSamplingScope(
            kind="runtime_sampling_scope",
            procedure_uri=sampling_procedure_uri,
            completeness="partial",
            total_known=False,
        ),
        policy=policy,
        procedure_uri=RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI,
        adapter_procedure_uri=adapter_procedure_uri,
    )
    snapshots = {
        recording_path: recording_snapshot,
        policy_path: policy_snapshot,
        environment_path: environment_snapshot,
        behavior_ir_path: behavior_snapshot,
    }
    _validate_runtime_input_snapshots(snapshots)
    return request, behavior, environment, snapshots


def _read_runtime_input(
    path: Path,
) -> tuple[bytes, _RuntimeInputSnapshot]:
    content, snapshot = _read_runtime_file(path, retain_content=True)
    if content is None:
        raise AssertionError("runtime input content was not retained")
    return content, snapshot


def _snapshot_runtime_input(path: Path) -> _RuntimeInputSnapshot:
    content, snapshot = _read_runtime_file(path, retain_content=False)
    if content is not None:
        raise AssertionError("runtime input content was unexpectedly retained")
    return snapshot


def _read_runtime_file(
    path: Path,
    *,
    retain_content: bool,
) -> tuple[bytes | None, _RuntimeInputSnapshot]:
    import hashlib
    import stat

    from ucf.runtime_evidence import MAX_RUNTIME_RECORDING_BYTES

    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_RUNTIME_RECORDING_BYTES:
        raise ValueError("runtime evidence input is not a bounded regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    retained = bytearray() if retain_content else None
    digest = hashlib.sha256()
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise ValueError("runtime evidence input identity changed")
        total = 0
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RUNTIME_RECORDING_BYTES:
                raise ValueError("runtime evidence input exceeds byte limit")
            digest.update(chunk)
            if retained is not None:
                retained.extend(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    opened_coordinates = (
        opened.st_dev,
        opened.st_ino,
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_ctime_ns,
    )
    after_coordinates = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if opened_coordinates != after_coordinates:
        raise ValueError("runtime evidence input changed while reading")
    snapshot = (*after_coordinates, digest.hexdigest())
    return (
        None if retained is None else bytes(retained),
        snapshot,
    )


def _validate_runtime_input_snapshots(
    snapshots: dict[Path, _RuntimeInputSnapshot],
) -> None:
    for path, expected in snapshots.items():
        actual = _snapshot_runtime_input(path)
        if actual != expected:
            raise ValueError("runtime evidence input changed")


def _read_change_governance_context(
    *,
    proposal_path: Path,
    delta_path: Path,
    base_behavior_path: Path,
    final_behavior_path: Path,
):
    from ucf.change_lifecycle import (
        parse_behavior_delta_json,
        parse_change_proposal_json,
    )
    from ucf.ir import parse_ir_json

    paths = (
        proposal_path,
        delta_path,
        base_behavior_path,
        final_behavior_path,
    )
    inputs = {path: _read_runtime_input(path) for path in paths}
    return (
        inputs,
        parse_change_proposal_json(inputs[proposal_path][0]),
        parse_behavior_delta_json(inputs[delta_path][0]),
        parse_ir_json(inputs[base_behavior_path][0]),
        parse_ir_json(inputs[final_behavior_path][0]),
    )


def _read_evidence_status_context(
    *,
    result_path: Path,
    mapping_result_path: Path,
    onboarding_bundle_path: Path,
    inventory_path: Path,
    mapping_adapter_name: str,
    mapping_adapter_version: str,
    verification_adapter_name: str,
    verification_adapter_version: str,
    mapping_capability_version: str,
    verification_capability_version: str,
):
    from ucf.implementation_evidence import (
        EXECUTION_VERIFICATION_CAPABILITY,
        IMPLEMENTATION_MAPPING_CAPABILITY,
        parse_execution_verification_result_json,
        parse_implementation_mapping_result_json,
    )
    from ucf.inventory import parse_inventory_snapshot_json
    from ucf.ir.models import Producer
    from ucf.onboarding import parse_onboarding_bundle_json

    paths = (
        result_path,
        mapping_result_path,
        onboarding_bundle_path,
        inventory_path,
    )
    inputs = {path: _read_runtime_input(path) for path in paths}
    return (
        {
            "result": parse_execution_verification_result_json(
                inputs[result_path][0]
            ),
            "mapping_result": parse_implementation_mapping_result_json(
                inputs[mapping_result_path][0]
            ),
            "bundle": parse_onboarding_bundle_json(
                inputs[onboarding_bundle_path][0]
            ),
            "inventory": parse_inventory_snapshot_json(
                inputs[inventory_path][0]
            ),
            "mapping_adapter": Producer(
                kind="producer",
                name=mapping_adapter_name,
                version=mapping_adapter_version,
            ),
            "verification_adapter": Producer(
                kind="producer",
                name=verification_adapter_name,
                version=verification_adapter_version,
            ),
            "capabilities": {
                IMPLEMENTATION_MAPPING_CAPABILITY: (
                    mapping_capability_version
                ),
                EXECUTION_VERIFICATION_CAPABILITY: (
                    verification_capability_version
                ),
            },
        },
        inputs,
    )


def _read_optional_evidence_status_context(
    *,
    result_path: Path | None,
    mapping_result_path: Path | None,
    onboarding_bundle_path: Path | None,
    inventory_path: Path | None,
    mapping_adapter_name: str | None,
    mapping_adapter_version: str | None,
    verification_adapter_name: str | None,
    verification_adapter_version: str | None,
    mapping_capability_version: str | None,
    verification_capability_version: str | None,
):
    values = (
        result_path,
        mapping_result_path,
        onboarding_bundle_path,
        inventory_path,
        mapping_adapter_name,
        mapping_adapter_version,
        verification_adapter_name,
        verification_adapter_version,
        mapping_capability_version,
        verification_capability_version,
    )
    if all(value is None for value in values):
        return None, {}
    if any(value is None for value in values):
        raise ValueError(
            "current evidence context must be supplied completely or omitted"
        )
    assert result_path is not None
    assert mapping_result_path is not None
    assert onboarding_bundle_path is not None
    assert inventory_path is not None
    assert mapping_adapter_name is not None
    assert mapping_adapter_version is not None
    assert verification_adapter_name is not None
    assert verification_adapter_version is not None
    assert mapping_capability_version is not None
    assert verification_capability_version is not None
    return _read_evidence_status_context(
        result_path=result_path,
        mapping_result_path=mapping_result_path,
        onboarding_bundle_path=onboarding_bundle_path,
        inventory_path=inventory_path,
        mapping_adapter_name=mapping_adapter_name,
        mapping_adapter_version=mapping_adapter_version,
        verification_adapter_name=verification_adapter_name,
        verification_adapter_version=verification_adapter_version,
        mapping_capability_version=mapping_capability_version,
        verification_capability_version=verification_capability_version,
    )


def _read_change_evidence_context(
    *,
    result_path: Path,
    mapping_result_path: Path,
    onboarding_bundle_path: Path,
    current_inventory_path: Path,
    mapping_adapter_name: str,
    mapping_adapter_version: str,
    verification_adapter_name: str,
    verification_adapter_version: str,
):
    from ucf.change_lifecycle import ExecutionEvidenceContext
    from ucf.implementation_evidence import (
        EXECUTION_VERIFICATION_CAPABILITY,
        IMPLEMENTATION_EVIDENCE_VERSION,
        IMPLEMENTATION_MAPPING_CAPABILITY,
        parse_execution_verification_result_json,
        parse_implementation_mapping_result_json,
    )
    from ucf.inventory import parse_inventory_snapshot_json
    from ucf.ir.models import Producer
    from ucf.onboarding import parse_onboarding_bundle_json

    paths = (
        result_path,
        mapping_result_path,
        onboarding_bundle_path,
        current_inventory_path,
    )
    inputs = {path: _read_runtime_input(path) for path in paths}
    result = parse_execution_verification_result_json(inputs[result_path][0])
    mapping_result = parse_implementation_mapping_result_json(
        inputs[mapping_result_path][0]
    )
    bundle = parse_onboarding_bundle_json(inputs[onboarding_bundle_path][0])
    inventory = parse_inventory_snapshot_json(inputs[current_inventory_path][0])
    return (
        ExecutionEvidenceContext(
            result=result,
            mapping_result=mapping_result,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=Producer(
                kind="producer",
                name=mapping_adapter_name,
                version=mapping_adapter_version,
            ),
            initialized_adapter=Producer(
                kind="producer",
                name=verification_adapter_name,
                version=verification_adapter_version,
            ),
            negotiated_capabilities={
                IMPLEMENTATION_MAPPING_CAPABILITY: (IMPLEMENTATION_EVIDENCE_VERSION),
                EXECUTION_VERIFICATION_CAPABILITY: (IMPLEMENTATION_EVIDENCE_VERSION),
            },
        ),
        inputs,
    )


def _validate_change_input_snapshots(
    inputs: dict[Path, tuple[bytes, _RuntimeInputSnapshot]],
    *,
    label: str,
) -> None:
    for path, (_, expected) in inputs.items():
        if _snapshot_runtime_input(path) != expected:
            raise ValueError(f"{label} input changed")


def _inventory_request_from_options(
    *,
    policy_path: Path,
    subject_uri: str,
    page_record_limit: int,
):
    from pydantic import ValidationError

    from ucf.inventory import (
        INVENTORY_REQUEST_SCHEMA_URI,
        INVENTORY_VERSION,
        FactKind,
        InventoryPageRequest,
        InventoryRequest,
        parse_ignore_policy_json,
    )
    from ucf.ir import IRValidationError

    try:
        policy = parse_ignore_policy_json(policy_path.read_bytes())
    except (IRValidationError, ValidationError, TypeError) as error:
        raise ValueError("inventory policy is invalid") from error
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri=subject_uri,
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=policy,
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=page_record_limit,
            cursor=None,
        ),
    )


def _resolved_inventory_root(root: Path) -> Path:
    repository = root.resolve(strict=True)
    if not repository.is_dir():
        raise ValueError("inventory root must be an existing directory")
    return repository


def _outside_inventory_destination(
    repository: Path,
    output: Path,
    *,
    inputs: tuple[Path, ...] = (),
) -> Path:
    destination = _file_destination(
        output,
        inputs=inputs,
        label="inventory output",
    )
    parent = destination.parent
    if parent == repository or parent.is_relative_to(repository):
        raise ValueError("inventory output must be outside the inventory root")
    return destination


def _file_destination(
    output: Path,
    *,
    inputs: tuple[Path, ...] = (),
    label: str = "output",
) -> Path:
    if output.name in {"", ".", ".."}:
        raise ValueError(f"{label} must name a file")
    parent = output.parent.resolve(strict=True)
    destination = parent / output.name
    if destination.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"{label} must be a regular file path")
    if any(
        source.resolve(strict=False) == destination
        or (destination.exists() and source.exists() and source.samefile(destination))
        for source in inputs
    ):
        raise ValueError("output must differ from every input")
    return destination


@ir_app.command("validate")
def ir_validate(
    document_path: Path = typer.Argument(
        ...,
        help="Path to a UCF behavior IR JSON document",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """Validate strict JSON structure and cross-record IR semantics."""
    from ucf.ir import IRValidationError, parse_ir_json

    try:
        document = parse_ir_json(document_path.read_bytes())
    except IRValidationError as error:
        console.print(
            f"[red]{error.code.value}[/red] {error.location}: {error.message}"
        )
        raise typer.Exit(code=1) from error

    console.print(
        f"[green]IR {document.ir_version} valid[/green]: "
        f"{document.document_id} "
        f"({len(document.entities)} entities)"
    )


@trust_app.command("validate")
def trust_validate(
    document_path: Path = typer.Argument(
        ...,
        help="Path to a UCF trust IR JSON document",
        exists=True,
        dir_okay=False,
    ),
    behavior_ir_path: Path = typer.Option(
        ...,
        "--behavior-ir",
        help="Exact UCF behavior IR document referenced by the trust overlay",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """Validate trust structure, behavior binding, mappings, and claims."""
    from ucf.ir import (
        IRValidationError,
        parse_ir_json,
        parse_trust_ir_json,
        validate_trust_against_behavior,
    )

    try:
        document = parse_trust_ir_json(document_path.read_bytes())
        behavior = parse_ir_json(behavior_ir_path.read_bytes())
        validate_trust_against_behavior(document, behavior)
    except IRValidationError as error:
        console.print(
            f"[red]{error.code.value}[/red] {error.location}: {error.message}"
        )
        raise typer.Exit(code=1) from error

    console.print(
        f"[green]Trust IR {document.trust_ir_version} valid[/green]: "
        f"{document.document_id} ({len(document.records)} records) "
        f"against {behavior.document_id}"
    )


def _load_registry(specs_dir: Path):
    from ucf.models.spec import SpecParseError
    from ucf.parser.loader import SpecLoader
    from ucf.parser.registry import DuplicateSpecError, SpecRegistry

    loader = SpecLoader(specs_dir)
    loaded, errors = loader.load_all_tolerant()

    registry = SpecRegistry()
    registered = []
    for path, spec in loaded:
        try:
            registry.register(spec, path)
        except DuplicateSpecError as exc:
            errors.append(SpecParseError(str(exc), path=str(path)))
        else:
            registered.append((path, spec))

    return registry, registered, errors


def _print_parse_errors(errors) -> None:
    console.print(f"[red]Parse errors ({len(errors)}):[/red]")
    for error in errors:
        console.print(f"  [red]✗[/red] {error.path}: {error}")
    console.print()


# ── ucf validate ──────────────────────────────────────────────


@app.command()
def validate(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Parse, load, and validate all specs in a directory."""
    from ucf.validator.core import IssueSeverity, SpecValidator

    console.print(f"\n[bold]UCF Validate[/bold]: {specs_dir}\n")

    registry, loaded, load_errors = _load_registry(specs_dir)

    if load_errors:
        _print_parse_errors(load_errors)

    console.print(f"Loaded [green]{len(loaded)}[/green] specs:")
    counts = registry.counts
    for kind, count in sorted(counts.items()):
        console.print(f"  {kind}: {count}")
    console.print()

    validator = SpecValidator(registry)
    issues = validator.validate_all()

    errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
    warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
    infos = [i for i in issues if i.severity == IssueSeverity.INFO]

    if issues:
        table = Table(title="Validation Issues", show_lines=True)
        table.add_column("Severity", width=8)
        table.add_column("Category", width=16)
        table.add_column("Spec")
        table.add_column("Message")
        table.add_column("Suggestion", style="dim")

        for issue in issues:
            sev_style = {
                IssueSeverity.ERROR: "red",
                IssueSeverity.WARNING: "yellow",
                IssueSeverity.INFO: "blue",
            }[issue.severity]
            table.add_row(
                f"[{sev_style}]{issue.severity.value}[/{sev_style}]",
                issue.category.value,
                issue.spec_name,
                issue.message,
                issue.suggestion,
            )

        console.print(table)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[red]{len(errors)} errors[/red] · "
        f"[yellow]{len(warnings)} warnings[/yellow] · "
        f"[blue]{len(infos)} info[/blue]\n"
    )

    if errors or load_errors:
        raise typer.Exit(code=1)


# ── ucf generate ──────────────────────────────────────────────


@app.command()
def generate(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
    output: Path = typer.Option(
        "tests/generated",
        "--output",
        "-o",
        help="Output directory for generated files",
    ),
    usecase: str = typer.Option(
        None,
        "--usecase",
        "-u",
        help="Generate for a specific use case only",
    ),
) -> None:
    """Generate test code (interface + orchestrator + impl stub) from use case specs."""
    from ucf.generator.plugin import GeneratorEngine, UnsupportedFeatureError
    from ucf.generator.pytest_plugin import PytestPlugin

    console.print(f"\n[bold]UCF Generate[/bold]: {specs_dir} → {output}\n")

    from ucf.validator.core import IssueSeverity, SpecValidator

    registry, _loaded, load_errors = _load_registry(specs_dir)
    if load_errors:
        _print_parse_errors(load_errors)
        raise typer.Exit(code=1)

    validation_errors = [
        issue
        for issue in SpecValidator(registry).validate_all()
        if issue.severity == IssueSeverity.ERROR
    ]
    if validation_errors:
        console.print(f"[red]Validation errors ({len(validation_errors)}):[/red]")
        for issue in validation_errors:
            console.print(f"  [red]✗[/red] {issue.spec_name}: {issue.message}")
        console.print()
        raise typer.Exit(code=1)

    plugin = PytestPlugin()
    engine = GeneratorEngine(registry, plugin, output)

    try:
        if usecase:
            usecases = [uc for uc in registry.usecases() if uc.metadata.name == usecase]
            if not usecases:
                console.print(f"[red]Use case '{usecase}' not found[/red]")
                raise typer.Exit(code=1)
            results = [engine.generate_usecase(uc) for uc in usecases]
        else:
            results = engine.generate_all()
    except UnsupportedFeatureError as exc:
        console.print(f"[red]Unsupported generation capability:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for result in results:
        console.print(f"  [bold]{result.usecase_name}[/bold]")
        for f in result.files_written:
            console.print(f"    [green]wrote[/green] {f}")
        for f in result.files_skipped:
            console.print(f"    [yellow]skipped[/yellow] {f} (exists)")

    total_written = sum(len(r.files_written) for r in results)
    total_skipped = sum(len(r.files_skipped) for r in results)
    console.print(
        f"\n[bold]Summary:[/bold] {len(results)} use case(s), "
        f"[green]{total_written} written[/green], "
        f"[yellow]{total_skipped} skipped[/yellow]\n"
    )


# ── ucf trace ─────────────────────────────────────────────────


@app.command()
def trace(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
    usecase: str = typer.Option(
        None,
        "--usecase",
        "-u",
        help="Trace a specific use case by name",
    ),
) -> None:
    """Trace data flow through use cases (Context Tracer)."""
    from ucf.tracer.context import FindingSeverity
    from ucf.tracer.display import format_step_label
    from ucf.tracer.engine import ContextTracer, CrossUseCaseAnalyzer

    console.print(f"\n[bold]UCF Trace[/bold]: {specs_dir}\n")

    registry, loaded, _ = _load_registry(specs_dir)
    tracer = ContextTracer(registry)
    cross = CrossUseCaseAnalyzer()

    usecases = registry.usecases()
    if usecase:
        usecases = [uc for uc in usecases if uc.metadata.name == usecase]
        if not usecases:
            console.print(f"[red]Use case '{usecase}' not found[/red]")
            raise typer.Exit(code=1)

    all_findings = []

    for uc in usecases:
        findings = tracer.trace_usecase(uc)
        all_findings.extend(findings)

        final_ctx = tracer.get_final_context(uc)
        cross.register_trace(uc.metadata.name, final_ctx)

        tree = Tree(f"[bold]Context Trace: {uc.metadata.name}[/bold]")

        init_node = tree.add("[dim]init[/dim] Components loaded")
        for slot_name, slot in final_ctx.slots.items():
            if slot.source_step.startswith("component:"):
                init_node.add(f"{slot_name} ({slot.type})")

        for step in uc.steps:
            step_node = tree.add(f"[cyan]{format_step_label(step)}[/cyan]")
            action_ref = step.use
            step_node.add(f"[dim]use:[/dim] {action_ref}")

            for field_name, binding in step.input.items():
                step_node.add(f"[dim]reads:[/dim] {field_name} = {binding}")

            for field_name in step.output:
                step_node.add(f"[dim]writes:[/dim] {field_name}")

        if findings:
            findings_node = tree.add("[bold]Findings[/bold]")
            for f in findings:
                sev_style = {
                    FindingSeverity.ERROR: "red",
                    FindingSeverity.WARNING: "yellow",
                    FindingSeverity.INFO: "blue",
                }[f.severity]
                findings_node.add(
                    f"[{sev_style}]{f.severity.value}[/{sev_style}] "
                    f"[{f.category.value}] {f.step_id}: {f.message}"
                )

        if uc.alternative_flows:
            for alt in uc.alternative_flows:
                alt_node = tree.add(f"[bold]Alt Flow: {alt.name}[/bold]")
                for step in alt.steps:
                    alt_node.add(f"[cyan]{format_step_label(step)}[/cyan] → {step.use}")

        console.print(tree)
        console.print()

    cross_findings = cross.find_conflicts()
    all_findings.extend(cross_findings)

    if cross_findings:
        console.print("[bold]Cross-UseCase Conflicts:[/bold]")
        for f in cross_findings:
            console.print(f"  [yellow]⚠[/yellow] {f.message}")
        console.print()

    errors = sum(1 for f in all_findings if f.severity == FindingSeverity.ERROR)
    warnings = sum(1 for f in all_findings if f.severity == FindingSeverity.WARNING)
    infos = sum(1 for f in all_findings if f.severity == FindingSeverity.INFO)

    console.print(
        f"[bold]Summary:[/bold] "
        f"[red]{errors} errors[/red] · "
        f"[yellow]{warnings} warnings[/yellow] · "
        f"[blue]{infos} info[/blue]\n"
    )


# ── ucf graph ─────────────────────────────────────────────────


graph_app = typer.Typer(help="Dependency graph operations")
app.add_typer(graph_app, name="graph")


@graph_app.command("show")
def graph_show(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Show the dependency graph overview."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)

    console.print("\n[bold]UCF Dependency Graph[/bold]\n")
    console.print(
        f"  Nodes: [green]{graph.g.number_of_nodes()}[/green] · "
        f"Edges: [green]{graph.g.number_of_edges()}[/green]\n"
    )

    table = Table(title="Edges", show_lines=True)
    table.add_column("Source")
    table.add_column("→")
    table.add_column("Target")
    table.add_column("Type")

    for u, v, data in graph.g.edges(data=True):
        table.add_row(u, "→", v, data.get("type", ""))

    console.print(table)
    console.print()


@graph_app.command("impact")
def graph_impact(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
    target: str = typer.Option(
        ...,
        "--target",
        "-t",
        help="Spec to analyze (e.g. action/add-to-cart)",
    ),
) -> None:
    """Analyze impact of changing a spec."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    result = graph.impact(target)

    console.print(f"\n[bold]Impact Analysis:[/bold] {target}\n")

    if result.direct_dependents:
        console.print("  [bold]Direct dependents:[/bold]")
        for dep in result.direct_dependents:
            console.print(f"    ← {dep}")

    if result.transitive_dependents:
        console.print("  [bold]Transitive dependents:[/bold]")
        for dep in result.transitive_dependents:
            console.print(f"    ← {dep}")

    if result.invariants:
        console.print("  [bold]Constrained by:[/bold]")
        for inv in result.invariants:
            console.print(f"    ⊢ {inv}")

    if result.conflicts:
        console.print("  [bold]Conflicts with:[/bold]")
        for c in result.conflicts:
            console.print(f"    ⟷ {c}")

    total = (
        len(result.direct_dependents)
        + len(result.transitive_dependents)
        + len(result.invariants)
    )
    console.print(f"\n  Total impact: {total} specs\n")


@graph_app.command("conflicts")
def graph_conflicts(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Detect write-write conflicts between specs."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    conflicts = graph.find_write_conflicts()

    console.print("\n[bold]UCF Conflict Map[/bold]\n")

    if not conflicts:
        console.print("  [green]No write-write conflicts detected.[/green]\n")
        return

    table = Table(title="Write-Write Conflicts", show_lines=True)
    table.add_column("Spec A")
    table.add_column("⟷")
    table.add_column("Spec B")
    table.add_column("Resource")

    for a, b, resource in conflicts:
        table.add_row(a, "⟷", b, resource)

    console.print(table)
    console.print(f"\n  {len(conflicts)} conflict pair(s)\n")


@graph_app.command("coverage")
def graph_coverage(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Show spec coverage report."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    report = graph.coverage()

    console.print("\n[bold]UCF Spec Coverage[/bold]\n")

    for kind, (connected, total) in sorted(report.counts.items()):
        pct = (connected / total * 100) if total > 0 else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        console.print(f"  {kind:12s} {connected:>3}/{total:<3} ({pct:5.1f}%) {bar}")

    if report.orphans:
        console.print(f"\n  [yellow]Orphan nodes ({len(report.orphans)}):[/yellow]")
        for orphan in report.orphans:
            console.print(f"    ⚠ {orphan}")

    console.print()


@graph_app.command("mermaid")
def graph_mermaid(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Generate Mermaid dependency diagram."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    console.print(graph.to_mermaid())


# ── ucf drift ─────────────────────────────────────────────────


@app.command()
def drift(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
    source_dir: Path = typer.Option(
        "src",
        "--source",
        "-s",
        help="Root directory of source code to scan",
    ),
    pattern: list[str] = typer.Option(
        ["**/*.py"],
        "--pattern",
        "-p",
        help="Glob patterns for source files",
    ),
) -> None:
    """Detect spec↔code drift: unimplemented specs, orphan code, stale mappings."""
    from ucf.drift.detector import DriftDetector
    from ucf.drift.mapper import SpecCodeMapper
    from ucf.drift.scanner import SourceScanner

    console.print(
        f"\n[bold]UCF Drift Detect[/bold]: specs={specs_dir}  source={source_dir}\n"
    )

    registry, loaded, _ = _load_registry(specs_dir)

    scanner = SourceScanner(source_dir, patterns=pattern)
    scan_result = scanner.scan()
    console.print(
        f"  Scanned [green]{scan_result.scanned_count}[/green] files, "
        f"found [green]{scan_result.marker_count}[/green] @implements markers\n"
    )

    mapper = SpecCodeMapper(registry, scan_result.implementations, convention="default")
    spec_map = mapper.build()

    detector = DriftDetector(registry, spec_map)
    drift_result = detector.detect()

    if drift_result.unimplemented_specs:
        table = Table(title="Unimplemented Specs", show_lines=True)
        table.add_column("Spec Ref")
        table.add_column("Kind")
        table.add_column("Detail")

        for entry in drift_result.unimplemented_specs:
            table.add_row(entry.ref, entry.kind, entry.detail)

        console.print(table)
        console.print()

    if drift_result.orphan_code:
        table = Table(
            title="Orphan Code (markers pointing to missing specs)", show_lines=True
        )
        table.add_column("File")
        table.add_column("Detail")

        for entry in drift_result.orphan_code:
            table.add_row(entry.ref, entry.detail)

        console.print(table)
        console.print()

    if drift_result.stale_mappings:
        table = Table(title="Stale Mappings", show_lines=True)
        table.add_column("Ref")
        table.add_column("Detail")

        for entry in drift_result.stale_mappings:
            table.add_row(entry.ref, entry.detail)

        console.print(table)
        console.print()

    if drift_result.drift_count == 0:
        console.print(
            "  [green]No drift detected — all specs are mapped to "
            "implementations.[/green]\n"
        )

    console.print(
        f"[bold]Summary:[/bold] "
        f"{spec_map.mapped_count}/{len(spec_map.spec_to_code)} specs mapped · "
        f"[red]{len(drift_result.unimplemented_specs)} unimplemented[/red] · "
        f"[yellow]{len(drift_result.orphan_code)} orphan[/yellow] · "
        f"[blue]{len(drift_result.stale_mappings)} stale[/blue]\n"
    )

    if drift_result.drift_count > 0:
        raise typer.Exit(code=1)


# ── ucf scaffold ──────────────────────────────────────────────


@app.command()
def scaffold(
    source_dir: Path = typer.Argument(
        ...,
        help="Path to Python source directory",
        exists=True,
        file_okay=False,
    ),
    output: Path = typer.Option(
        "specs",
        "--output",
        "-o",
        help="Output directory for generated spec stubs",
    ),
    patterns: list[str] = typer.Option(
        ["**/*.py"],
        "--pattern",
        "-p",
        help="Glob patterns for source files",
    ),
) -> None:
    """Generate skeleton UCF specs from existing Python code (brownfield adoption)."""
    from ucf.scaffold.generator import SkeletonSpecGenerator
    from ucf.scaffold.scanner import ASTScanner

    console.print(f"\n[bold]UCF Scaffold[/bold]: {source_dir} → {output}\n")

    scanner = ASTScanner(source_dir, patterns)
    scan_result = scanner.scan()

    console.print(
        f"  Scanned [green]{scan_result.scanned_count}[/green] files, "
        f"found [cyan]{len(scan_result.functions)}[/cyan] functions "
        f"and [cyan]{len(scan_result.classes)}[/cyan] classes\n"
    )

    if not scan_result.functions and not scan_result.classes:
        console.print("  [yellow]No public functions or classes found.[/yellow]\n")
        return

    gen = SkeletonSpecGenerator(output)
    gen_result = gen.generate(scan_result.functions, scan_result.classes)

    if gen_result.action_specs:
        tree = Tree("[bold]Generated action specs[/bold]")
        for p in gen_result.action_specs:
            tree.add(f"[green]{p}[/green]")
        console.print(tree)

    if gen_result.component_specs:
        tree = Tree("[bold]Generated component specs[/bold]")
        for p in gen_result.component_specs:
            tree.add(f"[cyan]{p}[/cyan]")
        console.print(tree)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"{gen_result.specs_written} specs written "
        f"({len(gen_result.action_specs)} actions, "
        f"{len(gen_result.component_specs)} components)\n"
    )


# ── ucf info ──────────────────────────────────────────────────


@app.command()
def info(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Show summary info about all loaded specs."""
    registry, loaded, errors = _load_registry(specs_dir)

    console.print(f"\n[bold]UCF Info[/bold]: {specs_dir}\n")
    console.print(f"  Total specs: [green]{registry.total}[/green]")

    for kind, count in sorted(registry.counts.items()):
        console.print(f"  {kind}: {count}")

    if errors:
        console.print(f"\n  [red]Parse errors: {len(errors)}[/red]")

    console.print()

    table = Table(title="Specs", show_lines=True)
    table.add_column("Kind")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Owner")

    for spec in registry.all_specs():
        table.add_row(
            spec.kind,
            spec.metadata.name,
            spec.metadata.version or "-",
            spec.metadata.owner or "-",
        )

    console.print(table)
    console.print()


@app.command()
def completeness(
    specs_dir: Path = typer.Argument(
        ...,
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Analyze spec completeness — find behavioral gaps in use case coverage."""
    from ucf.completeness.engine import CompletenessEngine
    from ucf.tracer.context import FindingSeverity

    console.print(f"\n[bold]UCF Completeness[/bold]: {specs_dir}\n")

    registry, loaded, _ = _load_registry(specs_dir)
    engine = CompletenessEngine(registry)
    report = engine.analyze()

    # Error Reachability
    if report.error_coverages:
        console.print("[bold]A. Error Reachability[/bold]")
        for ec in report.error_coverages:
            status = "[green]✓[/green]" if ec.is_covered else "[red]✗[/red]"
            console.print(f"  {status} actions/{ec.action_name} error {ec.error_code}")
            if ec.is_covered:
                for src in ec.covered_by:
                    console.print(f"      → covered by {src}")
        console.print()

    # Input Partition Coverage
    uncovered_parts = [p for p in report.partition_coverages if not p.is_covered]
    if report.partition_coverages:
        console.print("[bold]B. Input Partition Coverage[/bold]")
        console.print(
            f"  {report.partitions_covered}/{report.partitions_total} "
            "partitions covered"
        )
        for pc in uncovered_parts[:10]:
            console.print(
                f"  [red]✗[/red] {pc.action_name}.{pc.field_name} "
                f"partition '{pc.partition.name}'"
            )
        if len(uncovered_parts) > 10:
            console.print(f"  ... and {len(uncovered_parts) - 10} more")
        console.print()

    # State Coverage
    if report.state_graph:
        console.print("[bold]C. State Coverage[/bold]")
        console.print(
            f"  {len(report.state_graph.states)} states, "
            f"{len(report.state_graph.transitions)} transitions"
        )
        state_findings = [
            f
            for f in report.findings
            if f.category.value in ("unreachable_state", "dead_end_state")
        ]
        for sf in state_findings:
            sev_style = "yellow" if sf.severity == FindingSeverity.WARNING else "blue"
            console.print(
                f"  [{sev_style}]{sf.severity.value}[/{sev_style}] {sf.message}"
            )
        if not state_findings:
            console.print("  [green]All states are reachable[/green]")
        console.print()

    # Platform Binding Completeness
    if report.platform_scenarios:
        console.print("[bold]D. Platform Binding Completeness[/bold]")
        console.print(
            f"  {report.scenarios_covered}/{report.scenarios_total} scenarios covered"
        )
        uncovered_scenarios = [s for s in report.platform_scenarios if not s.is_covered]
        for ps in uncovered_scenarios[:10]:
            console.print(f"  [red]✗[/red] {ps.action_name} scenario '{ps.scenario}'")
        if len(uncovered_scenarios) > 10:
            console.print(f"  ... and {len(uncovered_scenarios) - 10} more")
        console.print()

    # Invariant Necessity
    if report.invariant_coverages:
        console.print("[bold]E. Invariant Necessity[/bold]")
        console.print(
            f"  {report.invariants_testable}/{report.invariants_total} "
            "invariants testable"
        )
        untestable = [i for i in report.invariant_coverages if not i.is_testable]
        for ic in untestable:
            console.print(
                f"  [yellow]?[/yellow] {ic.invariant_name} — not exercised by any UC"
            )
        console.print()

    # Resource Conflict Coverage
    if report.resource_conflicts:
        console.print("[bold]F. Resource Conflict Coverage[/bold]")
        for rc in report.resource_conflicts:
            status = (
                "[green]guarded[/green]" if rc.is_guarded else "[red]unguarded[/red]"
            )
            console.print(
                f"  {status} resource '{rc.resource}' writers: {', '.join(rc.writers)}"
            )
        console.print()

    # Summary
    warnings = sum(1 for f in report.findings if f.severity == FindingSeverity.WARNING)
    infos = sum(1 for f in report.findings if f.severity == FindingSeverity.INFO)

    console.print(
        f"[bold]Summary:[/bold] "
        f"[yellow]{warnings} warnings[/yellow] · "
        f"[blue]{infos} info[/blue] · "
        f"{report.gap_count} total gaps\n"
    )


@app.command()
def web(
    specs_dir: Path = typer.Argument(
        "specs",
        help="Path to specs directory",
        exists=True,
        file_okay=False,
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to serve on"),
    static_dir: Path | None = typer.Option(
        None,
        "--static",
        help="Path to frontend build (web/dist)",
    ),
) -> None:
    """Launch the UCF web dashboard."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Install web extras: pip install ucf[web][/red]")
        raise typer.Exit(1)

    from ucf.web.app import create_app

    if static_dir is None:
        candidate = Path("web/dist")
        if candidate.exists():
            static_dir = candidate

    _app = create_app(specs_dir, static_dir)
    console.print(f"[green]UCF Dashboard[/green] → http://{host}:{port}")
    console.print(f"  API docs → http://{host}:{port}/docs")
    if static_dir:
        console.print(f"  Frontend  → {static_dir}")
    uvicorn.run(_app, host=host, port=port)


if __name__ == "__main__":
    app()
