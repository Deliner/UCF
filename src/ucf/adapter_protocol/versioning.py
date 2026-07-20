from __future__ import annotations


def version_at_least(actual: str, minimum: str) -> bool:
    """Compare canonical three-segment decimal versions without integer casts."""

    actual_key = tuple(
        (len(segment), segment) for segment in actual.split(".")
    )
    minimum_key = tuple(
        (len(segment), segment) for segment in minimum.split(".")
    )
    return actual_key >= minimum_key
