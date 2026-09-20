import io
import json

from ayman_os_agent import ai_service
from ayman_os_agent.ai_service import TOOL_SPECS, AIService, convert_messages_for_gemini

# ------------------------------------------------------------------ tool schema

def test_tool_specs_unique_names():
    names = [spec["name"] for spec in TOOL_SPECS]
    assert len(names) == len(set(names))


# ------------------------------------------------------------------ conversion

def test_convert_user_text():
    contents = convert_messages_for_gemini([{"role": "user", "content": [{"text": "مرحبا"}]}])
    assert contents == [{"role": "user", "parts": [{"text": "مرحبا"}]}]


def test_convert_tool_roundtrip():
    messages = [
        {"role": "user", "content": [{"text": "ذاكرت 30 دقيقة"}]},
        {
            "role": "assistant",
            "content": [
                {"text": "سأسجلها"},
                {"toolUse": {"toolUseId": "t1", "name": "log_study", "input": {"code": "CS120", "minutes": 30}}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"toolResult": {"toolUseId": "t1", "name": "log_study", "content": [{"text": "✅ سجلت"}]}},
            ],
        },
    ]
    contents = convert_messages_for_gemini(messages)
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][1]["functionCall"]["name"] == "log_study"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "log_study"
    assert contents[2]["parts"][0]["functionResponse"]["response"]["result"] == "✅ سجلت"


# ------------------------------------------------------------------ Gemini HTTP path

class FakeHTTPResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_converse_gemini_text_reply(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return FakeHTTPResponse(
            json.dumps({"candidates": [{"content": {"parts": [{"text": "أهلًا بك"}]}}]}).encode()
        )

    monkeypatch.setattr(ai_service.request, "urlopen", fake_urlopen)
    service = AIService()
    service.backend = "gemini"
    service.gemini_config = {"api_key": "test-key", "model": "gemini-2.0-flash"}

    text, calls = service.converse(
        [{"role": "user", "content": [{"text": "hi"}]}], system_prompt="كن موجزاً", tools=TOOL_SPECS
    )

    assert text == "أهلًا بك" and calls == []
    assert "key=test-key" in captured["url"]
    assert captured["body"]["tools"][0]["functionDeclarations"][0]["name"] == TOOL_SPECS[0]["name"]
    assert captured["body"]["systemInstruction"]["parts"][0]["text"] == "كن موجزاً"


# ------------------------------------------------------------------ Bedrock path

class FakeBedrockClient:
    def __init__(self):
        self.kwargs = None

    def converse(self, **kwargs):
        self.kwargs = kwargs
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "سأتحقق"},
                        {"toolUse": {"toolUseId": "t9", "name": "get_risk", "input": {}}},
                    ],
                }
            }
        }


def test_converse_bedrock_tool_call():
    client = FakeBedrockClient()
    service = AIService()
    service.backend = "bedrock"
    service.client = client
    service._bedrock_checked = True

    text, calls = service.converse([{"role": "user", "content": [{"text": "وش الأخطر؟"}]}], system_prompt="s")

    assert text == "سأتحقق"
    assert calls == [{"id": "t9", "name": "get_risk", "args": {}}]
    tool_spec = client.kwargs["toolConfig"]["tools"][0]["toolSpec"]
    assert tool_spec["inputSchema"]["json"]["type"] == "object"
    assert client.kwargs["system"] == [{"text": "s"}]


def test_unavailable_backend_message():
    service = AIService()
    service.backend = "auto"
    service._bedrock_checked = True
    service.client = None
    service.gemini_config = {"api_key": None, "model": "gemini-2.0-flash"}
    text, calls = service.converse([{"role": "user", "content": [{"text": "hi"}]}])
    assert "لا يوجد مزود" in text and calls == []
