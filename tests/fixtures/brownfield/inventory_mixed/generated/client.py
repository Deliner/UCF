"""Generated decoy: an inventory adapter must prune this subtree."""

GENERATED_DECOY_SENTINEL_DO_NOT_OBSERVE = "generated-secret-contract"


def generated_delete_everything() -> None:
    raise RuntimeError(GENERATED_DECOY_SENTINEL_DO_NOT_OBSERVE)
