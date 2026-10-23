import json
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


SCENARIOS = (
    "valid",
    "invalid_json",
    "wrong_shape",
    "unknown_node_id",
    "invalid_risk",
    "empty",
    "extra_item",
    "minimal_valid",
)


def scripted_reply(scenario: str, node_ids: Iterable[str]) -> str:
    """Build the reply a fake model gives for a named scenario."""
    ids = list(node_ids)
    reasons = {node_id: f"Reason for {node_id}." for node_id in ids}
    valid = {"summary": "Fake summary.", "risk_level": "medium", "reasons": reasons}
    if scenario == "valid":
        return json.dumps(valid)
    if scenario == "minimal_valid":
        # Valid reply with no per-item reasons; used by the dummy app default (fixture data).
        return json.dumps(
            {
                "summary": "Fixture analysis: the change touches the listed items.",
                "risk_level": "medium",
                "reasons": {},
            }
        )
    if scenario == "invalid_json":
        return '{"summary": "Fake summary.", "risk_level": '
    if scenario == "wrong_shape":
        return json.dumps(["not", "an", "object"])
    if scenario == "unknown_node_id":
        return json.dumps({**valid, "reasons": {**reasons, "unknown-id": "Not in the graph."}})
    if scenario == "invalid_risk":
        return json.dumps({**valid, "risk_level": "critical"})
    if scenario == "empty":
        return ""
    if scenario == "extra_item":
        extra = {"id": "extra-item", "name": "Extra", "reason": "Added by the model."}
        return json.dumps(
            {
                **valid,
                "reasons": {**reasons, "extra-item": "Added by the model."},
                "directly_affected": [extra],
            }
        )
    raise ValueError(f"Unknown scenario: {scenario}")


class FakeLLM:
    """Scripted LLMClient for tests: records prompts and counts calls."""

    def __init__(self, replies: str | Sequence[str] | Callable[[str], str] = "") -> None:
        self._replies = replies
        self.calls = 0
        self.prompts: list[str] = []

    @classmethod
    def for_scenario(cls, scenario: str, node_ids: Iterable[str] = ()) -> "FakeLLM":
        return cls(scripted_reply(scenario, node_ids))

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        index = self.calls
        self.calls += 1
        if callable(self._replies):
            return self._replies(prompt)
        if isinstance(self._replies, str):
            return self._replies
        return self._replies[min(index, len(self._replies) - 1)]
