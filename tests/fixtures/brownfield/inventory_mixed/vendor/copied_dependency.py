"""Vendored decoy: an inventory adapter must prune this subtree."""

VENDOR_DECOY_SENTINEL_DO_NOT_OBSERVE = "vendor-privileged-contract"


class VendoredRootAdministrator:
    marker = VENDOR_DECOY_SENTINEL_DO_NOT_OBSERVE
