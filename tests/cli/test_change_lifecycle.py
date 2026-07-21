from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from click import unstyle
from typer.testing import CliRunner

from tests.change_lifecycle._fixture_factory import (
    behavior_pair,
    lifecycle_chain,
    task_graph,
)
from ucf.change_lifecycle import (
    canonical_change_lifecycle_json,
    delta_subject_ref,
    derive_behavior_delta,
    import_openspec_change,
    parse_archive_record_json,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    parse_implementation_record_json,
    parse_task_graph_json,
    parse_verification_record_json,
)
from ucf.cli import app
from ucf.implementation_evidence import (
    canonical_implementation_evidence_json,
)
from ucf.inventory import canonical_inventory_json
from ucf.ir import canonical_ir_json
from ucf.onboarding import canonical_onboarding_json

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[2]
OPENSPEC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "change_lifecycle" / "v1" / "openspec-spec-driven-1"
)
CHANGE_ID = "require-quote-order-total"


def _tree_snapshot(root: Path) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _write_lifecycle_inputs(tmp_path: Path):
    chain = lifecycle_chain()
    context = chain.evidence_contexts[0]
    paths = {
        "proposal": tmp_path / "proposal.json",
        "delta": tmp_path / "delta.json",
        "tasks": tmp_path / "tasks.json",
        "implementation": tmp_path / "implementation.json",
        "verification": tmp_path / "verification.json",
        "result": tmp_path / "result.json",
        "mapping": tmp_path / "mapping.json",
        "bundle": tmp_path / "bundle.json",
        "inventory": tmp_path / "inventory.json",
        "base": tmp_path / "base.json",
        "final": tmp_path / "final.json",
    }
    for name, document in (
        ("proposal", chain.proposal),
        ("delta", chain.delta),
        ("tasks", chain.graph),
        ("implementation", chain.implementation),
        ("verification", chain.verification),
    ):
        paths[name].write_bytes(canonical_change_lifecycle_json(document))
    paths["result"].write_bytes(canonical_implementation_evidence_json(context.result))
    paths["mapping"].write_bytes(
        canonical_implementation_evidence_json(context.mapping_result)
    )
    paths["bundle"].write_bytes(canonical_onboarding_json(context.bundle))
    paths["inventory"].write_bytes(canonical_inventory_json(context.current_inventory))
    paths["base"].write_text(canonical_ir_json(chain.base), encoding="utf-8")
    paths["final"].write_text(
        canonical_ir_json(chain.final),
        encoding="utf-8",
    )
    return chain, context, paths


def _archive_arguments(paths, context, output: Path) -> list[str]:
    return [
        "change",
        "archive",
        "--proposal",
        str(paths["proposal"]),
        "--delta",
        str(paths["delta"]),
        "--tasks",
        str(paths["tasks"]),
        "--implementation",
        str(paths["implementation"]),
        "--verification",
        str(paths["verification"]),
        "--base-behavior",
        str(paths["base"]),
        "--final-behavior",
        str(paths["final"]),
        "--result",
        str(paths["result"]),
        "--mapping-result",
        str(paths["mapping"]),
        "--onboarding-bundle",
        str(paths["bundle"]),
        "--current-inventory",
        str(paths["inventory"]),
        "--mapping-adapter-name",
        context.mapping_initialized_adapter.name,
        "--mapping-adapter-version",
        context.mapping_initialized_adapter.version,
        "--verification-adapter-name",
        context.initialized_adapter.name,
        "--verification-adapter-version",
        context.initialized_adapter.version,
        "--output",
        str(output),
    ]


def _record_implementation_arguments(paths, context, output: Path) -> list[str]:
    return [
        "change",
        "record-implementation",
        "--proposal",
        str(paths["proposal"]),
        "--delta",
        str(paths["delta"]),
        "--tasks",
        str(paths["tasks"]),
        "--base-behavior",
        str(paths["base"]),
        "--final-behavior",
        str(paths["final"]),
        "--result",
        str(paths["result"]),
        "--mapping-result",
        str(paths["mapping"]),
        "--onboarding-bundle",
        str(paths["bundle"]),
        "--current-inventory",
        str(paths["inventory"]),
        "--mapping-adapter-name",
        context.mapping_initialized_adapter.name,
        "--mapping-adapter-version",
        context.mapping_initialized_adapter.version,
        "--verification-adapter-name",
        context.initialized_adapter.name,
        "--verification-adapter-version",
        context.initialized_adapter.version,
        "--output",
        str(output),
    ]


def test_cli_change_import_and_export_are_silent_exact_and_repeatable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    workspace_before = _tree_snapshot(workspace)
    base, _ = behavior_pair()
    behavior_path = tmp_path / "base.json"
    behavior_path.write_text(canonical_ir_json(base), encoding="utf-8")
    first = tmp_path / "proposal-a.json"
    second = tmp_path / "proposal-b.json"
    arguments = [
        "change",
        "import-openspec",
        str(workspace / "changes" / CHANGE_ID),
        "--base-behavior",
        str(behavior_path),
    ]

    first_result = runner.invoke(app, [*arguments, "--output", str(first)])
    second_result = runner.invoke(app, [*arguments, "--output", str(second)])

    assert first_result.exit_code == 0, first_result.output
    assert second_result.exit_code == 0, second_result.output
    assert first_result.stdout == first_result.stderr == ""
    assert second_result.stdout == second_result.stderr == ""
    assert first.read_bytes() == second.read_bytes()
    proposal = parse_change_proposal_json(first.read_bytes())
    assert first.read_bytes() == canonical_change_lifecycle_json(proposal)
    assert _tree_snapshot(workspace) == workspace_before

    destination = tmp_path / "exported"
    exported = runner.invoke(
        app,
        [
            "change",
            "export-openspec",
            str(first),
            "--destination",
            str(destination),
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert exported.stdout == exported.stderr == ""
    assert _tree_snapshot(destination) == workspace_before
    assert first.read_bytes() == canonical_change_lifecycle_json(proposal)


def test_cli_change_import_invalid_input_preserves_existing_output(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    change = workspace / "changes" / CHANGE_ID
    (change / ".openspec.yaml").write_text(
        "schema: custom-workflow\n",
        encoding="utf-8",
    )
    workspace_before = _tree_snapshot(workspace)
    base, _ = behavior_pair()
    behavior_path = tmp_path / "base.json"
    behavior_path.write_text(canonical_ir_json(base), encoding="utf-8")
    output = tmp_path / "proposal.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        [
            "change",
            "import-openspec",
            str(change),
            "--base-behavior",
            str(behavior_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "unsupported_openspec_profile" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert _tree_snapshot(workspace) == workspace_before
    assert not tuple(tmp_path.glob(".proposal.json.*.tmp"))


def test_cli_change_export_conflict_preserves_user_tree(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        workspace / "changes" / CHANGE_ID,
        base,
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_bytes(canonical_change_lifecycle_json(proposal))
    destination = tmp_path / "destination"
    shutil.copytree(OPENSPEC_FIXTURE, destination)
    (destination / "sentinel.txt").write_text("owned\n", encoding="utf-8")
    before = _tree_snapshot(destination)

    result = runner.invoke(
        app,
        [
            "change",
            "export-openspec",
            str(proposal_path),
            "--destination",
            str(destination),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "destination_conflict" in result.stderr
    assert _tree_snapshot(destination) == before
    assert not tuple(tmp_path.glob(".destination.ucf-stage-*"))


def test_cli_change_help_exposes_pinned_boundary() -> None:
    result = runner.invoke(app, ["change", "--help"])

    assert result.exit_code == 0
    assert "import-openspec" in result.stdout
    assert "export-openspec" in result.stdout


def test_cli_change_import_source_drift_prevents_output_publish(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import ucf.cli as cli_module

    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    change = workspace / "changes" / CHANGE_ID
    base, _ = behavior_pair()
    behavior_path = tmp_path / "base.json"
    behavior_path.write_text(canonical_ir_json(base), encoding="utf-8")
    output = tmp_path / "proposal.json"
    output.write_bytes(b"preserve-me")
    original_publish = cli_module._publish_exact_file

    def mutate_before_publish(
        destination: Path,
        content: bytes,
        *,
        before_publish=None,
    ) -> None:
        (change / "notes.txt").write_text("drifted\n", encoding="utf-8")
        original_publish(
            destination,
            content,
            before_publish=before_publish,
        )

    monkeypatch.setattr(
        cli_module,
        "_publish_exact_file",
        mutate_before_publish,
    )
    result = runner.invoke(
        app,
        [
            "change",
            "import-openspec",
            str(change),
            "--base-behavior",
            str(behavior_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "changed during import" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".proposal.json.*.tmp"))


def test_cli_change_export_source_drift_prevents_tree_publish(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import ucf.change_lifecycle as lifecycle_module

    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        workspace / "changes" / CHANGE_ID,
        base,
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_bytes(canonical_change_lifecycle_json(proposal))
    destination = tmp_path / "exported"
    original_export = lifecycle_module.export_openspec_change

    def mutate_before_export(
        value,
        target: Path,
        *,
        before_publish=None,
    ) -> None:
        proposal_path.write_bytes(proposal_path.read_bytes() + b" ")
        original_export(
            value,
            target,
            before_publish=before_publish,
        )

    monkeypatch.setattr(
        lifecycle_module,
        "export_openspec_change",
        mutate_before_export,
    )
    result = runner.invoke(
        app,
        [
            "change",
            "export-openspec",
            str(proposal_path),
            "--destination",
            str(destination),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "change proposal input changed" in result.stderr
    assert not destination.exists()
    assert not tuple(tmp_path.glob(".exported.ucf-stage-*"))


def test_cli_change_derives_exact_behavior_delta(tmp_path: Path) -> None:
    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    base, final = behavior_pair()
    proposal = import_openspec_change(
        workspace / "changes" / CHANGE_ID,
        base,
    )
    proposal_path = tmp_path / "proposal.json"
    base_path = tmp_path / "base.json"
    final_path = tmp_path / "final.json"
    output = tmp_path / "delta.json"
    proposal_path.write_bytes(canonical_change_lifecycle_json(proposal))
    base_path.write_text(canonical_ir_json(base), encoding="utf-8")
    final_path.write_text(canonical_ir_json(final), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "change",
            "derive-delta",
            "--proposal",
            str(proposal_path),
            "--base-behavior",
            str(base_path),
            "--final-behavior",
            str(final_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == result.stderr == ""
    delta = parse_behavior_delta_json(output.read_bytes())
    assert delta.proposal.change_id == CHANGE_ID
    assert len(delta.entries) == 1
    assert delta.entries[0].kind == "modified_behavior"


def test_cli_change_derives_explicit_ordered_task_graph(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, workspace)
    base, final = behavior_pair()
    proposal = import_openspec_change(
        workspace / "changes" / CHANGE_ID,
        base,
    )
    delta = derive_behavior_delta(proposal, base, final)
    proposal_path = tmp_path / "proposal.json"
    delta_path = tmp_path / "delta.json"
    base_path = tmp_path / "base.json"
    final_path = tmp_path / "final.json"
    output = tmp_path / "tasks.json"
    proposal_path.write_bytes(canonical_change_lifecycle_json(proposal))
    delta_path.write_bytes(canonical_change_lifecycle_json(delta))
    base_path.write_text(canonical_ir_json(base), encoding="utf-8")
    final_path.write_text(canonical_ir_json(final), encoding="utf-8")
    subject = "modified:use_case:use-case.quote-order"

    result = runner.invoke(
        app,
        [
            "change",
            "derive-tasks",
            "--proposal",
            str(proposal_path),
            "--delta",
            str(delta_path),
            "--base-behavior",
            str(base_path),
            "--final-behavior",
            str(final_path),
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
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == result.stderr == ""
    graph = parse_task_graph_json(output.read_bytes())
    assert tuple(task.id for task in graph.tasks) == (
        "task.1-1",
        "task.1-2",
        "task.1-3",
    )
    assert tuple(task.order for task in graph.tasks) == (1, 2, 3)
    assert all(task.status == "pending" for task in graph.tasks)


def test_cli_change_derive_tasks_rejects_forged_delta_against_exact_behavior_pair(
    tmp_path: Path,
) -> None:
    chain, _, paths = _write_lifecycle_inputs(tmp_path)
    entry = chain.delta.entries[0]
    fabricated_entry = entry.model_copy(
        update={
            "base_subject": entry.base_subject.model_copy(
                update={"target_id": "use-case.fabricated"}
            ),
            "final_subject": entry.final_subject.model_copy(
                update={"target_id": "use-case.fabricated"}
            ),
        }
    )
    fabricated_delta = chain.delta.model_copy(update={"entries": (fabricated_entry,)})
    paths["delta"].write_bytes(canonical_change_lifecycle_json(fabricated_delta))
    subject = delta_subject_ref(fabricated_entry)
    coordinate = f"{subject.operation}:{subject.target_kind.value}:{subject.target_id}"
    output = tmp_path / "tasks-output.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        [
            "change",
            "derive-tasks",
            "--proposal",
            str(paths["proposal"]),
            "--delta",
            str(paths["delta"]),
            "--base-behavior",
            str(paths["base"]),
            "--final-behavior",
            str(paths["final"]),
            "--subject",
            f"task.1-1={coordinate}",
            "--subject",
            f"task.1-2={coordinate}",
            "--subject",
            f"task.1-3={coordinate}",
            "--depends",
            "task.1-2=task.1-1",
            "--depends",
            "task.1-3=task.1-2",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "incomplete_delta" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".tasks-output.json.*.tmp"))


def test_cli_change_completes_tasks_only_in_dependency_order(
    tmp_path: Path,
) -> None:
    proposal, delta, graph = task_graph()
    base, final = behavior_pair()
    proposal_path = tmp_path / "proposal.json"
    delta_path = tmp_path / "delta.json"
    graph_path = tmp_path / "tasks.json"
    base_path = tmp_path / "base.json"
    final_path = tmp_path / "final.json"
    proposal_path.write_bytes(canonical_change_lifecycle_json(proposal))
    delta_path.write_bytes(canonical_change_lifecycle_json(delta))
    graph_path.write_bytes(canonical_change_lifecycle_json(graph))
    base_path.write_text(canonical_ir_json(base), encoding="utf-8")
    final_path.write_text(canonical_ir_json(final), encoding="utf-8")
    blocked_output = tmp_path / "blocked.json"

    blocked = runner.invoke(
        app,
        [
            "change",
            "complete-task",
            "--proposal",
            str(proposal_path),
            "--delta",
            str(delta_path),
            "--tasks",
            str(graph_path),
            "--base-behavior",
            str(base_path),
            "--final-behavior",
            str(final_path),
            "--task-id",
            "task.1-2",
            "--output",
            str(blocked_output),
        ],
    )

    assert blocked.exit_code == 1
    assert blocked.stdout == ""
    assert blocked.stderr == (
        "invalid_transition at $.tasks: task completion requires completed "
        "predecessors: ('task.1-1',)\n"
    )
    assert not blocked_output.exists()

    first_output = tmp_path / "first.json"
    first = runner.invoke(
        app,
        [
            "change",
            "complete-task",
            "--proposal",
            str(proposal_path),
            "--delta",
            str(delta_path),
            "--tasks",
            str(graph_path),
            "--base-behavior",
            str(base_path),
            "--final-behavior",
            str(final_path),
            "--task-id",
            "task.1-1",
            "--output",
            str(first_output),
        ],
    )
    assert first.exit_code == 0, first.output
    assert first.stdout == first.stderr == ""
    assert parse_task_graph_json(first_output.read_bytes()).tasks[0].status == (
        "completed"
    )


def test_cli_change_records_only_fully_context_validated_implementation(
    tmp_path: Path,
) -> None:
    chain, context, paths = _write_lifecycle_inputs(tmp_path)
    output = tmp_path / "implementation.json"

    result = runner.invoke(
        app,
        _record_implementation_arguments(paths, context, output),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == result.stderr == ""
    implementation = parse_implementation_record_json(output.read_bytes())
    assert implementation == chain.implementation


def test_cli_change_record_implementation_distinguishes_blocked_from_invalid(
    tmp_path: Path,
) -> None:
    _, context, paths = _write_lifecycle_inputs(tmp_path)
    _, _, pending_graph = task_graph()
    paths["tasks"].write_bytes(canonical_change_lifecycle_json(pending_graph))
    blocked_output = tmp_path / "blocked.json"
    blocked_output.write_bytes(b"preserve-blocked")

    blocked = runner.invoke(
        app,
        _record_implementation_arguments(paths, context, blocked_output),
    )

    assert blocked.exit_code == 1
    assert blocked.stdout == ""
    assert blocked.stderr == (
        "incomplete_tasks at $.tasks: implementation requires completed tasks: "
        "('task.1-1', 'task.1-2', 'task.1-3')\n"
    )
    assert blocked_output.read_bytes() == b"preserve-blocked"
    assert not tuple(tmp_path.glob(".blocked.json.*.tmp"))

    paths["tasks"].write_bytes(b"{")
    invalid_output = tmp_path / "invalid.json"
    invalid_output.write_bytes(b"preserve-invalid")

    invalid = runner.invoke(
        app,
        _record_implementation_arguments(paths, context, invalid_output),
    )

    assert invalid.exit_code == 3
    assert invalid.stdout == ""
    assert "invalid_json at $" in invalid.stderr
    assert invalid_output.read_bytes() == b"preserve-invalid"
    assert not tuple(tmp_path.glob(".invalid.json.*.tmp"))


def test_cli_change_downstream_malformed_behavior_is_stable_invalid_input(
    tmp_path: Path,
) -> None:
    _, context, paths = _write_lifecycle_inputs(tmp_path)
    paths["base"].write_bytes(b"{")
    output = tmp_path / "implementation-output.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _record_implementation_arguments(paths, context, output),
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == (
        "invalid_json at line 1, column 2: "
        "Expecting property name enclosed in double quotes\n"
    )
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".implementation-output.json.*.tmp"))


def test_cli_change_verifies_only_passing_context_bound_evidence(
    tmp_path: Path,
) -> None:
    chain, context, paths = _write_lifecycle_inputs(tmp_path)
    output = tmp_path / "derived-verification.json"

    result = runner.invoke(
        app,
        [
            "change",
            "verify",
            "--proposal",
            str(paths["proposal"]),
            "--delta",
            str(paths["delta"]),
            "--tasks",
            str(paths["tasks"]),
            "--implementation",
            str(paths["implementation"]),
            "--base-behavior",
            str(paths["base"]),
            "--final-behavior",
            str(paths["final"]),
            "--result",
            str(paths["result"]),
            "--mapping-result",
            str(paths["mapping"]),
            "--onboarding-bundle",
            str(paths["bundle"]),
            "--current-inventory",
            str(paths["inventory"]),
            "--mapping-adapter-name",
            context.mapping_initialized_adapter.name,
            "--mapping-adapter-version",
            context.mapping_initialized_adapter.version,
            "--verification-adapter-name",
            context.initialized_adapter.name,
            "--verification-adapter-version",
            context.initialized_adapter.version,
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == result.stderr == ""
    verification = parse_verification_record_json(output.read_bytes())
    assert verification == chain.verification


def test_cli_change_downstream_help_marks_behavior_pair_required() -> None:
    for command in (
        "derive-tasks",
        "complete-task",
        "record-implementation",
        "verify",
    ):
        result = runner.invoke(app, ["change", command, "--help"])

        assert result.exit_code == 0, result.output
        help_text = unstyle(result.stdout)
        assert "--base-behavior" in help_text
        assert "--final-behavior" in help_text
        assert help_text.count("required") >= 2


def test_cli_change_archives_exact_accepted_chain_and_final_behavior(
    tmp_path: Path,
) -> None:
    chain, context, paths = _write_lifecycle_inputs(tmp_path)
    output = tmp_path / "archive.json"

    result = runner.invoke(
        app,
        _archive_arguments(paths, context, output),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == result.stderr == ""
    archive = parse_archive_record_json(output.read_bytes())
    assert archive == chain.archive


def test_cli_change_archive_help_does_not_promote_trust() -> None:
    result = runner.invoke(app, ["change", "archive", "--help"])

    assert result.exit_code == 0, result.output
    assert "accepted chain" in result.stdout
    assert "verified chain" not in result.stdout


def test_cli_change_archive_distinguishes_blocked_from_invalid(
    tmp_path: Path,
) -> None:
    chain, context, paths = _write_lifecycle_inputs(tmp_path)
    _, _, pending_graph = task_graph()
    paths["tasks"].write_bytes(canonical_change_lifecycle_json(pending_graph))
    blocked_output = tmp_path / "blocked.json"
    blocked_output.write_bytes(b"preserve-blocked")

    blocked = runner.invoke(
        app,
        _archive_arguments(paths, context, blocked_output),
    )

    assert blocked.exit_code == 1
    assert blocked.stdout == ""
    assert "incomplete_tasks" in blocked.stderr
    assert blocked_output.read_bytes() == b"preserve-blocked"
    assert not tuple(tmp_path.glob(".blocked.json.*.tmp"))

    paths["tasks"].write_bytes(canonical_change_lifecycle_json(chain.graph))
    paths["final"].write_text(
        canonical_ir_json(chain.base),
        encoding="utf-8",
    )
    invalid_output = tmp_path / "invalid.json"
    invalid_output.write_bytes(b"preserve-invalid")
    invalid = runner.invoke(
        app,
        _archive_arguments(paths, context, invalid_output),
    )

    assert invalid.exit_code == 3
    assert invalid.stdout == ""
    assert "document_identity_mismatch" in invalid.stderr
    assert invalid_output.read_bytes() == b"preserve-invalid"
    assert not tuple(tmp_path.glob(".invalid.json.*.tmp"))
