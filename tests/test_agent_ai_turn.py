from conftest import FakeStore

from ayman_os_agent.agent import OSAgent


class StubAI:
    """Two-step AI: first demands a tool call, then answers with the result."""

    def __init__(self):
        self.steps = 0
        self.saw_tool_result = None

    def is_available(self):
        return True

    def backend_name(self):
        return "stub"

    def converse(self, messages, system_prompt=None, tools=None):
        self.steps += 1
        if self.steps == 1:
            return "", [{"id": "t1", "name": "get_risk", "args": {}}]
        last = messages[-1]["content"][0]
        assert "toolResult" in last
        self.saw_tool_result = last["toolResult"]
        return "المادة الأخطر هي CS120", []

    def generate(self, prompt, system_prompt=None):
        return "ok"


def test_ai_turn_executes_tool_and_returns_answer():
    agent = OSAgent(store=FakeStore(writable=False))
    agent.ai = StubAI()

    answer = agent.ai_turn("وش أخطر مادة؟", "chat-1")

    assert answer == "المادة الأخطر هي CS120"
    assert agent.ai.saw_tool_result["name"] == "get_risk"
    assert "أعلى مخاطرة" in agent.ai.saw_tool_result["content"][0]["text"] or "ورقة" in agent.ai.saw_tool_result["content"][0]["text"]


def test_ai_turn_keeps_session_memory():
    agent = OSAgent(store=FakeStore(writable=False))
    agent.ai = StubAI()
    agent.ai_turn("سؤال أول", "chat-1")
    history = agent.session_history("chat-1")
    assert history[0] == {"role": "user", "text": "سؤال أول"}
    assert history[-1]["role"] == "assistant"
    assert len(agent.session_history("chat-2")) == 0  # separate chats stay separate
