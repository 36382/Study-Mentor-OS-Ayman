"""Unified AI service: AWS Bedrock (Converse API) + Gemini, with tool calling.

The same normalized message format is used for both backends:

- user text:        {"role": "user",      "content": [{"text": "..."}]}
- assistant reply:  {"role": "assistant", "content": [{"text": "..."},
                                                   {"toolUse": {"toolUseId", "name", "input"}}]}
- tool result:      {"role": "user",      "content": [{"toolResult": {"toolUseId", "name",
                                                              "content": [{"text": "..."}]}}]}

``converse()`` returns ``(assistant_text, tool_calls)`` so the agent can run a
tool-use loop identically over Bedrock and Gemini.
"""

from __future__ import annotations

import json
import os
from urllib import request

from .config import get_ai_backend, get_aws_config, get_gemini_config

# --------------------------------------------------------------------------
# Tool catalog (shared by both backends). OpenAPI-style JSON schemas.
# --------------------------------------------------------------------------

TOOL_SPECS: list[dict] = [
    {
        "name": "get_today_summary",
        "description": "يعيد ملخص حالة اليوم: دقائق المذاكرة المسجلة، آخر سجل يومي، وجدول اليوم من الشيت.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_risk",
        "description": "يعيد المادة الأكثر خطورة/أولوية وترتيب المواد عالية المخاطر.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "log_study",
        "description": "يسجل جلسة مذاكرة منجزة في الشيت. استخدمه عندما يذكر الطالب مدة مذاكرة.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "رمز المادة مثل CS120"},
                "minutes": {"type": "integer", "description": "عدد الدقائق (1-600)"},
                "note": {"type": "string", "description": "ملاحظة قصيرة اختيارية"},
            },
            "required": ["code", "minutes"],
        },
    },
    {
        "name": "list_tasks",
        "description": "يعرض المهام الدراسية المفتوحة من الشيت.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "mark_task_done",
        "description": "يعلّم مهمة دراسية كمُنجزة بالبحث عن جزء من اسمها.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "جزء من اسم المهمة"}},
            "required": ["query"],
        },
    },
    {
        "name": "add_appointment",
        "description": "يضيف موعداً دراسياً إلى تقويم الشيت.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "عنوان الموعد"},
                "date": {"type": "string", "description": "التاريخ بصيغة YYYY-MM-DD"},
                "time": {"type": "string", "description": "الوقت بصيغة HH:MM (افتراضي 09:00)"},
            },
            "required": ["title", "date"],
        },
    },
    {
        "name": "list_appointments",
        "description": "يعرض المواعيد القادمة.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "send_parent_report",
        "description": "يرسل تقرير اليوم للوالد في تيليجرام (والبريد إن كان مضبوطاً). استخدمه فقط عند طلب صريح.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

TOOL_NAMES = {spec["name"] for spec in TOOL_SPECS}


def convert_messages_for_gemini(messages: list[dict]) -> list[dict]:
    """Convert the normalized message format into Gemini ``contents``."""
    contents = []
    for msg in messages:
        parts = []
        for block in msg.get("content", []):
            if "text" in block:
                parts.append({"text": block["text"]})
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                parts.append({"functionCall": {"name": tool_use["name"], "args": tool_use.get("input") or {}}})
            elif "toolResult" in block:
                tool_result = block["toolResult"]
                text = " ".join(c.get("text", "") for c in tool_result.get("content", []))
                parts.append(
                    {
                        "functionResponse": {
                            "name": tool_result.get("name") or tool_result["toolUseId"],
                            "response": {"result": text},
                        }
                    }
                )
        if not parts:
            continue
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": parts})
    return contents


class AIService:
    """Bedrock Converse + Gemini wrapper with function calling."""

    def __init__(self) -> None:
        self.config = get_aws_config()
        self.gemini_config = get_gemini_config()
        self.backend = get_ai_backend()
        self.client = None
        self._bedrock_checked = False

    # ------------------------------------------------------------ backend selection

    def _has_aws_configuration(self) -> bool:
        return any(
            os.environ.get(name)
            for name in (
                "AWS_ACCESS_KEY_ID",
                "AWS_PROFILE",
                "AWS_WEB_IDENTITY_TOKEN_FILE",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
                "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            )
        )

    def _bedrock_client(self):
        if self._bedrock_checked:
            return self.client
        self._bedrock_checked = True
        if self.backend in {"auto", "bedrock"} and self._has_aws_configuration():
            try:
                import boto3

                self.client = boto3.client("bedrock-runtime", region_name=self.config["region"])
            except Exception:
                self.client = None
        return self.client

    def is_available(self) -> bool:
        if self.backend == "gemini":
            return bool(self.gemini_config["api_key"])
        if self.backend == "bedrock":
            return self._bedrock_client() is not None
        return self._bedrock_client() is not None or bool(self.gemini_config["api_key"])

    def backend_name(self) -> str:
        if self.backend == "gemini":
            return "gemini" if self.is_available() else "gemini-unconfigured"
        if self.backend == "bedrock":
            return "bedrock" if self.is_available() else "bedrock-unconfigured"
        if self._bedrock_client() is not None:
            return "bedrock+gemini"
        if self.gemini_config["api_key"]:
            return "gemini"
        return "none"

    # ------------------------------------------------------------ simple generation

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """One-shot generation without tools (used by /ai and simple flows)."""
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        text, _ = self.converse(messages, system_prompt=system_prompt, tools=None)
        return text

    # ------------------------------------------------------------ converse with tools

    def converse(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        tools: list[dict] | None = TOOL_SPECS,
    ) -> tuple[str, list[dict]]:
        """Returns (text, tool_calls). tool_calls is empty when the model answers directly."""
        try:
            if self.backend in {"auto", "bedrock"} and self._bedrock_client() is not None:
                return self._converse_bedrock(messages, system_prompt, tools)
            if self.backend in {"auto", "gemini"} and self.gemini_config["api_key"]:
                return self._converse_gemini(messages, system_prompt, tools)
        except Exception as exc:  # never crash the bot on an AI hiccup
            return (f"تعذر الاتصال بمزود الذكاء الاصطناعي: {exc}", [])
        return ("لا يوجد مزود ذكاء اصطناعي مضبوط. اضبط GEMINI_API_KEY أو مفاتيح AWS Bedrock.", [])

    # ------------------------------------------------------------ Bedrock

    def _converse_bedrock(self, messages, system_prompt, tools) -> tuple[str, list[dict]]:
        kwargs: dict = {
            "modelId": self.config["model_id"],
            "messages": messages,  # already in Converse format
            "inferenceConfig": {"maxTokens": 700, "temperature": 0.4},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
        if tools:
            kwargs["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": spec["name"],
                            "description": spec["description"],
                            "inputSchema": {"json": spec["parameters"]},
                        }
                    }
                    for spec in tools
                ]
            }
        response = self.client.converse(**kwargs)
        message = response.get("output", {}).get("message", {})
        text_parts = []
        calls = []
        for block in message.get("content", []):
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                calls.append(
                    {
                        "id": tool_use.get("toolUseId", f"call{len(calls)}"),
                        "name": tool_use.get("name", ""),
                        "args": tool_use.get("input") or {},
                    }
                )
        return ("\n".join(part for part in text_parts if part).strip(), calls)

    # ------------------------------------------------------------ Gemini

    def _converse_gemini(self, messages, system_prompt, tools) -> tuple[str, list[dict]]:
        payload: dict = {
            "contents": convert_messages_for_gemini(messages),
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 700},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {"name": spec["name"], "description": spec["description"], "parameters": spec["parameters"]}
                        for spec in tools
                    ]
                }
            ]

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_config['model']}:generateContent?key={self.gemini_config['api_key']}"
        )
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        with request.urlopen(req, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))

        candidates = body.get("candidates", [])
        if not candidates:
            return ("لم يصل رد من Gemini.", [])
        parts = (candidates[0].get("content") or {}).get("parts", [])
        text_parts = []
        calls = []
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                call = part["functionCall"]
                calls.append(
                    {
                        "id": f"call{len(calls)}",
                        "name": call.get("name", ""),
                        "args": call.get("args") or {},
                    }
                )
        return ("\n".join(part for part in text_parts if part).strip(), calls)
