"""URL Shortener service."""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Any


@dataclass
class ShortURL:
    """A shortened URL record."""
    id: str
    slug: str
    original_url: str
    click_count: int
    created_by: str | None
    created_at: float


class URLShortener:
    """In-memory URL shortener service."""

    def __init__(self, base_url: str = "http://short.ly") -> None:
        self.base_url = base_url
        self._urls: dict[str, ShortURL] = {}
        self._id_counter = 0

    def generate_slug(self, length: int = 6) -> str:
        """Generate a random alphanumeric slug."""
        if not (4 <= length <= 20):
            raise ValueError("length must be between 4 and 20")
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def validate_url(self, url: str) -> tuple[bool, str | None]:
        """Validate URL format.
        
        Returns (is_valid, error_message)
        """
        if not url:
            return False, "URL is required"
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "URL must start with http:// or https://"
        if len(url) > 2048:
            return False, "URL is too long (max 2048 characters)"
        return True, None

    def slug_exists(self, slug: str) -> bool:
        """Check if slug already exists."""
        return slug in self._urls

    def store_url(
        self,
        slug: str,
        original_url: str,
        created_by: str | None = None,
    ) -> ShortURL:
        """Store a new short URL.
        
        Raises ValueError if slug already exists.
        """
        if slug in self._urls:
            raise ValueError(f"Slug '{slug}' already exists")
        
        import time
        self._id_counter += 1
        record = ShortURL(
            id=str(self._id_counter),
            slug=slug,
            original_url=original_url,
            click_count=0,
            created_by=created_by,
            created_at=time.time(),
        )
        self._urls[slug] = record
        return record

    def get_by_slug(self, slug: str) -> ShortURL | None:
        """Get URL by slug."""
        return self._urls.get(slug)

    def increment_clicks(self, slug: str) -> int:
        """Increment click count for a slug.
        
        Returns new click count.
        """
        if slug not in self._urls:
            raise ValueError(f"Slug '{slug}' not found")
        self._urls[slug].click_count += 1
        return self._urls[slug].click_count

    def get_full_short_url(self, slug: str) -> str:
        """Get full short URL."""
        return f"{self.base_url}/{slug}"

    def get_stats(self, slug: str) -> dict[str, Any]:
        """Get statistics for a slug."""
        record = self.get_by_slug(slug)
        if not record:
            raise ValueError(f"Slug '{slug}' not found")
        
        import datetime
        created_dt = datetime.datetime.fromtimestamp(record.created_at)
        
        return {
            "slug": record.slug,
            "original_url": record.original_url,
            "total_clicks": record.click_count,
            "created_at": created_dt.isoformat(),
            "created_by": record.created_by or "anonymous",
        }

    def list_expired_urls(self, days_threshold: int) -> list[str]:
        """List slugs for URLs older than threshold days."""
        import time
        
        threshold_ts = time.time() - (days_threshold * 86400)
        expired = [
            record.slug
            for record in self._urls.values()
            if record.created_at < threshold_ts
        ]
        return sorted(expired, key=lambda s: self._urls[s].created_at)

    def delete_url(self, slug: str) -> bool:
        """Delete a URL by slug.
        
        Returns True if deleted, raises ValueError if not found.
        """
        if slug not in self._urls:
            raise ValueError(f"Slug '{slug}' not found")
        del self._urls[slug]
        return True

    def delete_batch(self, slugs: list[str]) -> tuple[int, list[str]]:
        """Delete multiple URLs.
        
        Returns (deleted_count, failed_slugs).
        """
        deleted = 0
        failed = []
        for slug in slugs:
            try:
                self.delete_url(slug)
                deleted += 1
            except ValueError:
                failed.append(slug)
        return deleted, failed
