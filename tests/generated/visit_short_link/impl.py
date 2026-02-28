"""Implementation for use case: visit-short-link.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from typing import Any

from .interface import VisitShortLinkInterface, RedirectToDestinationResult

class VisitShortLinkImpl(VisitShortLinkInterface):

    # ── State Setup ──

    # ── Actions ──

    def action_redirect_to_destination(self, short_code: Any) -> RedirectToDestinationResult:
        raise NotImplementedError("Fill in: action_redirect_to_destination")

    # ── Verifications ──

    def verify_visitor_is_redirected_to_original_page(self) -> None:
        raise NotImplementedError("Fill in: verify_visitor_is_redirected_to_original_page")

    def verify_visit_is_recorded_for_analytics(self) -> None:
        raise NotImplementedError("Fill in: verify_visit_is_recorded_for_analytics")

    def verify_redirect_happens_in_200ms(self) -> None:
        raise NotImplementedError("Fill in: verify_redirect_happens_in_200ms")

    def verify_required_inputs_validated(self) -> None:
        raise NotImplementedError("Fill in: verify_required_inputs_validated")
