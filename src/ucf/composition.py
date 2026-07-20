"""Use case composition — resolves the `extends` field to produce flattened UCs.

@implements("actions/resolve-uc-extends")
@implements("use-cases/compose-use-cases")
@implements("invariants/no-circular-extends")
@implements("invariants/extends-no-step-id-clash")
"""

from __future__ import annotations

from ucf.models.usecase import UseCaseSpec, invariant_reference
from ucf.parser.registry import SpecRegistry


class CompositionError(Exception):
    """Raised when UC composition fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def resolve_extends(
    uc: UseCaseSpec,
    registry: SpecRegistry,
    *,
    _chain: list[str] | None = None,
) -> tuple[UseCaseSpec, list[str], list[str]]:
    """Resolve the extends chain and return a flattened use case.

    Returns:
        (flattened_uc, extends_chain, parent_step_ids)
    """
    if uc.extends is None:
        return uc, [uc.metadata.name], []

    chain = _chain or [uc.metadata.name]

    parent_ref = uc.extends.replace("$ref:", "")
    parent = registry.resolve_ref(parent_ref)

    if parent is None:
        raise CompositionError(
            "PARENT_NOT_FOUND",
            f"extends reference '{uc.extends}' does not resolve to a known use case",
        )

    if not isinstance(parent, UseCaseSpec):
        raise CompositionError(
            "PARENT_NOT_FOUND",
            f"extends reference '{uc.extends}' resolves to a {parent.kind}, "
            "not a use case",
        )

    if parent.metadata.name in chain:
        raise CompositionError(
            "CIRCULAR_EXTENDS",
            f"circular extends: {' -> '.join(chain)} -> {parent.metadata.name}",
        )

    chain.append(parent.metadata.name)

    if parent.extends is not None:
        parent, ancestor_chain, ancestor_step_ids = resolve_extends(
            parent,
            registry,
            _chain=chain,
        )
        chain = ancestor_chain
    else:
        chain = list(chain)

    parent_step_ids_set = {s.id for s in parent.steps}
    child_step_ids_set = {s.id for s in uc.steps}
    clash = parent_step_ids_set & child_step_ids_set
    if clash:
        raise CompositionError(
            "STEP_ID_CLASH",
            f"step IDs conflict between parent and child: {sorted(clash)}",
        )

    parent_step_ids = [s.id for s in parent.steps]

    merged_requires = list(parent.requires)
    existing_refs = {
        r.ref if hasattr(r, "ref") else r.get("$ref", "") for r in merged_requires
    }
    for r in uc.requires:
        ref_val = r.ref if hasattr(r, "ref") else r.get("$ref", "")
        if ref_val not in existing_refs:
            merged_requires.append(r)

    merged_invariants = list(parent.invariants)
    existing_inv = {invariant_reference(i) for i in merged_invariants}
    for i in uc.invariants:
        inv_val = invariant_reference(i)
        if inv_val not in existing_inv:
            merged_invariants.append(i)

    seen_post = set(parent.postconditions)
    merged_postconditions = list(parent.postconditions)
    for p in uc.postconditions:
        if p not in seen_post:
            merged_postconditions.append(p)

    seen_pre = set(parent.preconditions)
    merged_preconditions = list(parent.preconditions)
    for p in uc.preconditions:
        if p not in seen_pre:
            merged_preconditions.append(p)

    merged_steps = list(parent.steps) + list(uc.steps)
    merged_alt_flows = list(parent.alternative_flows) + list(uc.alternative_flows)

    flattened = UseCaseSpec(
        kind="usecase",
        metadata=uc.metadata,
        extends=None,
        trigger=uc.trigger or parent.trigger,
        input_from_event={**parent.input_from_event, **uc.input_from_event},
        requires=merged_requires,
        preconditions=merged_preconditions,
        steps=merged_steps,
        alternative_flows=merged_alt_flows,
        postconditions=merged_postconditions,
        invariants=merged_invariants,
        concurrency=list(parent.concurrency) + list(uc.concurrency),
    )

    return flattened, chain, parent_step_ids
