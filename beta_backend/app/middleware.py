from collections import defaultdict, deque
from time import time

from fastapi import HTTPException, Request

from app.config import Settings


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        if not self.settings.rate_limit_enabled:
            return

        path = request.url.path
        if path.startswith("/auth"):
            limit = self.settings.auth_rate_limit_per_minute
        elif path.startswith("/identity"):
            limit = max(5, self.settings.auth_rate_limit_per_minute // 2)
        else:
            limit = self.settings.rate_limit_per_minute
        key = f"{request.client.host if request.client else 'unknown'}:{path}"
        now = time()
        bucket = self._buckets[key]

        while bucket and now - bucket[0] > 60:
            bucket.popleft()

        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        bucket.append(now)
