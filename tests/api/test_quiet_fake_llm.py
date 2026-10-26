from impact_agent.api.app import QuietFakeLLM
from impact_agent.core.llm import FakeLLM


def test_quiet_fake_llm_returns_same_reply_as_fake_llm():
    quiet = QuietFakeLLM.for_scenario("minimal_valid")
    normal = FakeLLM.for_scenario("minimal_valid")
    assert quiet.complete("prompt") == normal.complete("prompt")


def test_quiet_fake_llm_does_not_keep_prompts():
    llm = QuietFakeLLM.for_scenario("minimal_valid")
    for i in range(100):
        llm.complete(f"prompt {i}")
    assert llm.prompts == []
    assert llm.calls == 100
