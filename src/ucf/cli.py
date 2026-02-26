"""UCF CLI — validate, trace, graph, and generate from specs."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

app = typer.Typer(
    name="ucf",
    help="Use Case-Driven Development Framework",
    no_args_is_help=True,
)
console = Console()


def _load_registry(specs_dir: Path):
    from ucf.parser.loader import SpecLoader
    from ucf.parser.registry import SpecRegistry

    loader = SpecLoader(specs_dir)
    loaded, errors = loader.load_all_tolerant()

    registry = SpecRegistry()
    for path, spec in loaded:
        registry.register(spec, path)

    return registry, loaded, errors


# ── ucf validate ──────────────────────────────────────────────


@app.command()
def validate(
    specs_dir: Path = typer.Argument(
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
) -> None:
    """Parse, load, and validate all specs in a directory."""
    from ucf.validator.core import IssueSeverity, SpecValidator

    console.print(f"\n[bold]UCF Validate[/bold]: {specs_dir}\n")

    registry, loaded, load_errors = _load_registry(specs_dir)

    if load_errors:
        console.print(f"[red]Parse errors ({len(load_errors)}):[/red]")
        for err in load_errors:
            console.print(f"  [red]✗[/red] {err.path}: {err}")
        console.print()

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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
    output: Path = typer.Option(
        "tests/generated", "--output", "-o", help="Output directory for generated files",
    ),
    usecase: str = typer.Option(
        None, "--usecase", "-u", help="Generate for a specific use case only",
    ),
) -> None:
    """Generate test code (interface + orchestrator + impl stub) from use case specs."""
    from ucf.generator.plugin import GeneratorEngine
    from ucf.generator.pytest_plugin import PytestPlugin

    console.print(f"\n[bold]UCF Generate[/bold]: {specs_dir} → {output}\n")

    registry, loaded, _ = _load_registry(specs_dir)
    plugin = PytestPlugin()
    engine = GeneratorEngine(registry, plugin, output)

    if usecase:
        usecases = [uc for uc in registry.usecases() if uc.metadata.name == usecase]
        if not usecases:
            console.print(f"[red]Use case '{usecase}' not found[/red]")
            raise typer.Exit(code=1)
        results = [engine.generate_usecase(uc) for uc in usecases]
    else:
        results = engine.generate_all()

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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
    usecase: str = typer.Option(
        None, "--usecase", "-u", help="Trace a specific use case by name",
    ),
) -> None:
    """Trace data flow through use cases (Context Tracer)."""
    from ucf.tracer.context import FindingSeverity
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
            step_node = tree.add(f"[cyan]{step.id}[/cyan]")
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
                    alt_node.add(f"[cyan]{step.id}[/cyan] → {step.use}")

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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
) -> None:
    """Show the dependency graph overview."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)

    console.print(f"\n[bold]UCF Dependency Graph[/bold]\n")
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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
    target: str = typer.Option(
        ..., "--target", "-t", help="Spec to analyze (e.g. action/add-to-cart)",
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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
) -> None:
    """Detect write-write conflicts between specs."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    conflicts = graph.find_write_conflicts()

    console.print(f"\n[bold]UCF Conflict Map[/bold]\n")

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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
) -> None:
    """Show spec coverage report."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    report = graph.coverage()

    console.print(f"\n[bold]UCF Spec Coverage[/bold]\n")

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
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
) -> None:
    """Generate Mermaid dependency diagram."""
    from ucf.graph.dependency import DependencyGraph

    registry, _, _ = _load_registry(specs_dir)
    graph = DependencyGraph(registry)
    console.print(graph.to_mermaid())


# ── ucf info ──────────────────────────────────────────────────


@app.command()
def info(
    specs_dir: Path = typer.Argument(
        ..., help="Path to specs directory", exists=True, file_okay=False,
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


if __name__ == "__main__":
    app()
