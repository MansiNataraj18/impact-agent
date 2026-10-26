from impact_agent.api.idempotency import IdempotencyConflict, IdempotencyStore
from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_compute(calls: list[int], text: str = "done"):
    def compute() -> ImpactResponse:
        calls.append(1)
        return ImpactResponse(status=ResponseStatus.OK, tdd_text=text, correlation_id="id")

    return compute


def test_entry_inside_limit_returns_stored_response():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=60, clock=clock)
    request = ImpactRequest(tdd_text="x", correlation_id="id")
    calls: list[int] = []
    store.run(request, make_compute(calls))
    clock.now = 59
    assert store.run(request, make_compute(calls)).tdd_text == "done"
    assert len(calls) == 1


def test_entry_older_than_limit_is_treated_as_new():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=60, clock=clock)
    request = ImpactRequest(tdd_text="x", correlation_id="id")
    calls: list[int] = []
    store.run(request, make_compute(calls))
    clock.now = 61
    store.run(request, make_compute(calls))
    assert len(calls) == 2


def test_conflict_while_entry_is_alive():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=60, clock=clock)
    calls: list[int] = []
    store.run(ImpactRequest(tdd_text="x", correlation_id="id"), make_compute(calls))
    clock.now = 30
    try:
        store.run(ImpactRequest(tdd_text="y", correlation_id="id"), make_compute(calls))
    except IdempotencyConflict:
        pass
    else:
        raise AssertionError("expected IdempotencyConflict")
    assert len(calls) == 1


def test_different_input_allowed_after_entry_expires():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=60, clock=clock)
    calls: list[int] = []
    store.run(ImpactRequest(tdd_text="x", correlation_id="id"), make_compute(calls))
    clock.now = 61
    response = store.run(
        ImpactRequest(tdd_text="y", correlation_id="id"), make_compute(calls, text="second")
    )
    assert response.tdd_text == "second"
    assert len(calls) == 2


def test_no_limit_keeps_entries_forever():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=None, clock=clock)
    request = ImpactRequest(tdd_text="x", correlation_id="id")
    calls: list[int] = []
    store.run(request, make_compute(calls))
    clock.now = 10**9
    store.run(request, make_compute(calls))
    assert len(calls) == 1


def test_expired_entries_are_removed_from_memory():
    clock = FakeClock()
    store = IdempotencyStore(ttl_seconds=60, clock=clock)
    calls: list[int] = []
    store.run(ImpactRequest(tdd_text="x", correlation_id="old"), make_compute(calls))
    clock.now = 61
    store.run(ImpactRequest(tdd_text="x", correlation_id="new"), make_compute(calls))
    assert set(store._entries) == {"new"}
