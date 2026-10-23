from impact_agent.core.llm import LLMClient


class EchoLLM:
    def complete(self, prompt: str) -> str:
        return prompt


def use(client: LLMClient, prompt: str) -> str:
    return client.complete(prompt)


def test_class_with_complete_satisfies_protocol():
    assert use(EchoLLM(), "hello") == "hello"
