import hashlib
import json
import threading
from collections.abc import Callable

from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus

CONFLICT_MESSAGE = "correlation_id {id!r} was already used with a different request."


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

    Only ok and partial responses are stored. There is no retention limit yet.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._entries: dict[str, tuple[str, ImpactResponse]] = {}

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
                entry = self._entries.get(correlation_id)
            if entry is not None:
                if entry[0] != request_fingerprint:
                    raise IdempotencyConflict(CONFLICT_MESSAGE.format(id=correlation_id))
                return entry[1].model_copy(deep=True)
            response = compute()
            if response.status is not ResponseStatus.ERROR:
                with self._guard:
                    self._entries[correlation_id] = (
                        request_fingerprint,
                        response.model_copy(deep=True),
                    )
            return response
