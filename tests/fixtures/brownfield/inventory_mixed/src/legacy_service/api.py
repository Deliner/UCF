"""Small public surface of the unchanged legacy service."""


def read_health() -> dict[str, str]:
    """Return the service health representation."""
    return {"status": "ok"}


def format_greeting(name: str) -> str:
    """Build the legacy greeting text."""
    return f"Hello, {name}!"
