"""Framework-provided actions available to all use case implementations."""

from __future__ import annotations

from typing import Any


class FrameworkActions:
    """Base class providing framework actions to all use case implementations.
    
    These actions are available without needing to implement them:
    - render_error_response: Render error to CLI or HTTP
    - render_cli_output: Render data to CLI
    - render_http_response: Render data to HTTP
    """

    def render_error_response(
        self,
        error_code: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render an error response.
        
        Args:
            error_code: Error code (e.g., INVALID_URL_FORMAT)
            message: Human-readable error message
            context: Additional error context
            
        Returns:
            Dict with 'rendered' key
        """
        # In real impl, this would use context to determine CLI vs HTTP
        # For now, just return success
        return {"rendered": True}

    def render_cli_output(self, data: Any, format: str = "json") -> None:
        """Render data to CLI output.
        
        Args:
            data: Data to render
            format: Output format (json, table, yaml)
        """
        # In real impl, this would format and print
        pass

    def render_http_response(
        self,
        data: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Render HTTP response.
        
        Args:
            data: Response body
            status: HTTP status code
            headers: HTTP headers
            
        Returns:
            Dict with 'rendered' key
        """
        return {"rendered": True, "status": status}
