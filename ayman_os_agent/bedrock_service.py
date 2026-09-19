from __future__ import annotations

import json
import os
from urllib import request, error

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None

from .config import get_ai_backend, get_aws_config, get_gemini_config


class BedrockService:
    """Thin wrapper around AWS Bedrock runtime with Gemini fallback."""

    def __init__(self) -> None:
        self.config = get_aws_config()
        self.gemini_config = get_gemini_config()
        self.backend = get_ai_backend()
        self.client = None
        has_aws_configuration = any(
            os.environ.get(name)
            for name in (
                "AWS_ACCESS_KEY_ID",
                "AWS_PROFILE",
                "AWS_WEB_IDENTITY_TOKEN_FILE",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
                "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            )
        )
        if boto3 is not None and self.backend in {"auto", "bedrock"} and has_aws_configuration:
            self.client = boto3.client("bedrock-runtime", region_name=self.config["region"])

    def is_available(self) -> bool:
        if self.backend == "gemini":
            return bool(self.gemini_config["api_key"])
        if self.backend == "bedrock":
            return self.client is not None
        return self.client is not None or bool(self.gemini_config["api_key"])

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        if self.backend in {"auto", "bedrock"} and self.client is not None:
            return self._generate_bedrock(prompt, system_prompt)

        if self.backend in {"auto", "gemini"} and self.gemini_config["api_key"]:
            return self._generate_gemini(prompt, system_prompt)

        return (
            "No AI backend is configured. Set AI_BACKEND=gemini with GEMINI_API_KEY, "
            "or AI_BACKEND=bedrock with AWS credentials/role.\n\n"
            f"Prompt preview: {prompt[:220]}"
        )

    def _generate_bedrock(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt

            response = self.client.invoke_model(
                modelId=self.config["model_id"],
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            text = payload.get("content", [{}])[0].get("text", "")
            return text.strip() or "No response from Bedrock."
        except Exception as exc:  # pragma: no cover
            return f"Bedrock request failed: {exc}"

    def _generate_gemini(self, prompt: str, system_prompt: str | None = None) -> str:
        api_key = self.gemini_config["api_key"]
        if not api_key:
            return "Gemini API key is not configured."

        payload = {
            "contents": [{"parts": [{"text": (system_prompt + "\n\n" if system_prompt else "") + prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300},
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_config['model']}:generateContent?key={api_key}"
        )
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if not candidates:
                return "No response from Gemini API."
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip() or "No response from Gemini API."
        except error.HTTPError as exc:
            return f"Gemini API request failed: {exc.read().decode('utf-8', errors='replace')}"
        except Exception as exc:  # pragma: no cover
            return f"Gemini request failed: {exc}"
