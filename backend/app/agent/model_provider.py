"""Uniform interface for calling Claude and Gemini."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agent.prompts import ANOMALY_SYSTEM_PROMPT
from app.config import settings

RETRY_ATTEMPTS = 3
RETRY_TIMEOUT_SECONDS = 20.0

_AUTH_MARKERS = (
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "invalid_api_key",
    "api key not valid",
    "permission_denied",
    "authentication_error",
)


def is_auth_error(exc: BaseException) -> bool:
    """True when retrying cannot help (bad/missing key, 401/403)."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        code = getattr(current, "status_code", None) or getattr(current, "status", None)
        if code in (401, 403):
            return True
        response = getattr(current, "response", None)
        if getattr(response, "status_code", None) in (401, 403):
            return True
        name = type(current).__name__.lower()
        if "auth" in name or "permissiondenied" in name or "forbidden" in name:
            return True
        text = str(current).lower()
        if any(marker in text for marker in _AUTH_MARKERS):
            return True
        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None:
            stack.append(current.__context__)
    return False


class ModelProvider(Protocol):
    async def generate_structured(self, prompt: str, schema: dict) -> dict: ...


async def retry_generate(
    operation: Callable[[], Awaitable[dict]],
    attempts: int = RETRY_ATTEMPTS,
    timeout_seconds: float = RETRY_TIMEOUT_SECONDS,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if is_auth_error(exc) or attempt >= attempts - 1:
                break
            await asyncio.sleep(0.4 * (attempt + 1))
    assert last_error is not None
    raise last_error


class ClaudeProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.model = model

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        async def _call() -> dict:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key, max_retries=0)
            response = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=ANOMALY_SYSTEM_PROMPT,
                tools=[
                    {
                        "name": "score_anomaly",
                        "description": "Score a reconciliation anomaly",
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": "score_anomaly"},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return dict(block.input)
            raise ValueError("Claude response did not include structured tool output")

        return await retry_generate(_call)


class GeminiProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.6-flash",
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.GOOGLE_API_KEY
        self.model = model

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        async def _call() -> dict:
            import google.generativeai as genai

            if not self.api_key:
                raise RuntimeError("GOOGLE_API_KEY is not set")

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.model,
                system_instruction=ANOMALY_SYSTEM_PROMPT,
            )
            response = await model.generate_content_async(
                f"{prompt}\n\nReturn JSON matching this schema:\n{json.dumps(schema)}",
                generation_config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)

        return await retry_generate(_call)


def get_model_provider() -> ModelProvider:
    if settings.LLM_PROVIDER.lower() == "gemini":
        return GeminiProvider()
    return ClaudeProvider()
