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


# ── ucf drift ─────────────────────────────────────────────────


@app.command()
def drift(
    specs_dir: Path = typer.Argument(
        ..., help="Path to specs directory", exists=True, file_okay=False,
    ),
    source_dir: Path = typer.Option(
        "src", "--source", "-s", help="Root directory of source code to scan",
    ),
    pattern: list[str] = typer.Option(
        ["**/*.py"], "--pattern", "-p", help="Glob patterns for source files",
    ),
) -> None:
    """Detect spec↔code drift: unimplemented specs, orphan code, stale mappings."""
    from ucf.drift.detector import DriftDetector
    from ucf.drift.mapper import SpecCodeMapper
    from ucf.drift.scanner import SourceScanner

    console.print(f"\n[bold]UCF Drift Detect[/bold]: specs={specs_dir}  source={source_dir}\n")

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
        table = Table(title="Orphan Code (markers pointing to missing specs)", show_lines=True)
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
        console.print("  [green]No drift detected — all specs are mapped to implementations.[/green]\n")

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
        ..., help="Path to Python source directory", exists=True, file_okay=False,
    ),
    output: Path = typer.Option(
        "specs", "--output", "-o", help="Output directory for generated spec stubs",
    ),
    patterns: list[str] = typer.Option(
        ["**/*.py"], "--pattern", "-p", help="Glob patterns for source files",
    ),
) -> None:
    """Generate skeleton UCF specs from existing Python code (brownfield adoption)."""
    from ucf.scaffold.scanner import ASTScanner
    from ucf.scaffold.generator import SkeletonSpecGenerator

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


@app.command()
def completeness(
    specs_dir: Path = typer.Argument(
        ..., help="Path to specs directory", exists=True, file_okay=False,
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
            console.print(
                f"  {status} actions/{ec.action_name} error {ec.error_code}"
            )
            if ec.is_covered:
                for src in ec.covered_by:
                    console.print(f"      → covered by {src}")
        console.print()

    # Input Partition Coverage
    uncovered_parts = [p for p in report.partition_coverages if not p.is_covered]
    if report.partition_coverages:
        console.print("[bold]B. Input Partition Coverage[/bold]")
        console.print(
            f"  {report.partitions_covered}/{report.partitions_total} partitions covered"
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
            f for f in report.findings
            if f.category.value in ("unreachable_state", "dead_end_state")
        ]
        for sf in state_findings:
            sev_style = "yellow" if sf.severity == FindingSeverity.WARNING else "blue"
            console.print(f"  [{sev_style}]{sf.severity.value}[/{sev_style}] {sf.message}")
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
            console.print(
                f"  [red]✗[/red] {ps.action_name} scenario '{ps.scenario}'"
            )
        if len(uncovered_scenarios) > 10:
            console.print(f"  ... and {len(uncovered_scenarios) - 10} more")
        console.print()

    # Invariant Necessity
    if report.invariant_coverages:
        console.print("[bold]E. Invariant Necessity[/bold]")
        console.print(
            f"  {report.invariants_testable}/{report.invariants_total} invariants testable"
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
            status = "[green]guarded[/green]" if rc.is_guarded else "[red]unguarded[/red]"
            console.print(
                f"  {status} resource '{rc.resource}' "
                f"writers: {', '.join(rc.writers)}"
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
        "specs", help="Path to specs directory", exists=True, file_okay=False,
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to serve on"),
    static_dir: Path | None = typer.Option(
        None, "--static", help="Path to frontend build (web/dist)",
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
