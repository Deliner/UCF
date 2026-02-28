"""URL Shortener implementation.

@implements("actions/acquire-lock")
@implements("actions/release-lock")
@implements("actions/generate-slug")
@implements("actions/validate-url")
@implements("actions/check-slug-exists")
@implements("actions/store-short-url")
@implements("actions/get-url-by-slug")
@implements("actions/increment-click-count")
@implements("actions/perform-redirect")
@implements("actions/get-url-stats")
@implements("actions/list-expired-urls")
@implements("actions/delete-url")
@implements("actions/delete-urls-batch")
@implements("use-cases/create-short-url")
@implements("use-cases/redirect-to-original")
@implements("use-cases/get-url-stats")
@implements("use-cases/expire-old-urls")
"""

from ucf.shortener.url_service import URLShortener

__all__ = ["URLShortener"]
