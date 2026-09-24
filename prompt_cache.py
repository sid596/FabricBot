"""Thread-safe Gemini cache renewal, including externally expired caches."""
import logging
import threading
import time
from datetime import datetime, timezone

from google.genai import errors, types

log = logging.getLogger(__name__)


class PromptCache:
    def __init__(self, client, model, instruction, ttl=86400):
        self.client, self.model, self.instruction = client, model, instruction
        self.ttl = ttl
        self._cache = None
        self._expires = 0
        self._retry_after = 0
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            if self._cache is None and time.monotonic() < self._retry_after:
                return None
            if self._cache is None or time.monotonic() >= self._expires:
                try:
                    cache = self.client.caches.create(
                        model=self.model,
                        config=types.CreateCachedContentConfig(
                            display_name="angie-rules-v2",
                            system_instruction=self.instruction, ttl=f"{self.ttl}s",
                        ),
                    )
                except errors.APIError:
                    self._cache = None
                    self._retry_after = time.monotonic() + 60
                    raise
                lifetime = self.ttl
                if cache.expire_time:
                    lifetime = min(lifetime, (cache.expire_time - datetime.now(timezone.utc)).total_seconds())
                self._cache = cache
                self._expires = time.monotonic() + max(0, lifetime - min(60, self.ttl / 10))
            return self._cache

    def generate(self, contents, schema):
        config = {"response_mime_type": "application/json", "response_schema": schema}
        cache = None
        try:
            cache = self.get()
        except errors.APIError:
            log.warning("Prompt cache unavailable; using full instructions")
        if cache is not None:
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=contents,
                    config={**config, "cached_content": cache.name},
                )
            except errors.APIError as exc:
                if exc.code not in (400, 403, 404) or not any(
                    word in str(exc).lower() for word in ("cache", "cachedcontent")
                ):
                    raise
                with self._lock:
                    if self._cache is cache:
                        self._cache = None
                log.info("Gemini cache invalidated; retrying once with full instructions")
        return self.client.models.generate_content(
            model=self.model, contents=contents,
            config={**config, "system_instruction": self.instruction},
        )
