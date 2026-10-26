import hashlib
import json
import threading
import time
from collections.abc import Callable

from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus

CONFLICT_MESSAGE = "correlation_id {id!r} was already used with a different request."
DEFAULT_TTL_SECONDS = 3600.0


class IdempotencyConflict(Exception):
    pass


def fingerprint(request: ImpactRequest) -> str:
    payload = json.dumps(
        [request.tdd_text, request.project, request.repository, request.revision],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IdempotencyStore:
    """In-memory, thread-safe results by correlation id.

    Only ok and partial responses are stored. An entry older than `ttl_seconds` is dropped and
    the next request with that id is treated as new. `ttl_seconds=None` keeps entries forever.
    `clock` is injectable so tests can move time without sleeping.
    """

    def __init__(
        self,
        ttl_seconds: float | None = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._guard = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._entries: dict[str, tuple[float, str, ImpactResponse]] = {}

    def _expired(self, stored_at: float) -> bool:
        return self._ttl is not None and self._clock() - stored_at > self._ttl

    def _purge_expired(self) -> None:
        """Drop expired entries so memory stays bounded. Caller must hold `_guard`."""
        for key in [k for k, entry in self._entries.items() if self._expired(entry[0])]:
            del self._entries[key]

    def run(self, request: ImpactRequest, compute: Callable[[], ImpactResponse]) -> ImpactResponse:
        """Return the stored response for a repeated id, otherwise compute (and maybe store)."""
        correlation_id = request.correlation_id
        if correlation_id is None:
            return compute()

        request_fingerprint = fingerprint(request)
        with self._guard:
            key_lock = self._key_locks.setdefault(correlation_id, threading.Lock())
        with key_lock:
            with self._guard:
                self._purge_expired()
                entry = self._entries.get(correlation_id)
            if entry is not None:
                _, stored_fingerprint, stored_response = entry
                if stored_fingerprint != request_fingerprint:
                    raise IdempotencyConflict(CONFLICT_MESSAGE.format(id=correlation_id))
                return stored_response.model_copy(deep=True)
            response = compute()
            if response.status is not ResponseStatus.ERROR:
                with self._guard:
                    self._entries[correlation_id] = (
                        self._clock(),
                        request_fingerprint,
                        response.model_copy(deep=True),
                    )
            return response
