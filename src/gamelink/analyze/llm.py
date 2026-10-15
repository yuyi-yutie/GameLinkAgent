"""Thin, provider-agnostic LLM client (OpenAI-compatible chat completions).

Streams the response so the CLI can show live progress while the model works,
and asks for native JSON mode so the structured reply is valid by construction.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from gamelink.config import LLMSettings
from gamelink.errors import AnalysisError, ConfigError

# Chunk kinds yielded by :meth:`LLMClient.stream`.
REASONING = "reasoning"
CONTENT = "content"

_JSON_MODE = {"type": "json_object"}


class _JsonModeUnsupported(Exception):
    """Internal: the provider rejected ``response_format``; retry without it."""


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        timeout: float = 600.0,
        json_mode: bool = True,
    ) -> None:
        self.settings = settings
        self.timeout = timeout
        self.json_mode = json_mode

    def _endpoint(self) -> str:
        return self.settings.base_url.rstrip("/") + "/chat/completions"

    def _headers(self) -> dict[str, str]:
        if not self.settings.api_key:
            raise ConfigError(
                "尚未配置 LLM API key —— 运行 `gla` 进入欢迎界面，或 `gla config` 配置"
                "（也可设置 GAMELINK_LLM_API_KEY 环境变量）"
            )
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    def stream(self, system: str, user: str) -> Iterator[tuple[str, str]]:
        """Yield ``(kind, text)`` deltas; kind is ``"reasoning"`` or ``"content"``."""
        if self.json_mode:
            try:
                yield from self._stream(system, user, json_mode=True)
                return
            except _JsonModeUnsupported:
                # Provider does not support response_format; remember and fall back.
                self.json_mode = False
        yield from self._stream(system, user, json_mode=False)

    def _stream(self, system: str, user: str, *, json_mode: bool) -> Iterator[tuple[str, str]]:
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = _JSON_MODE

        headers = self._headers()
        try:
            with httpx.stream(
                "POST", self._endpoint(), json=payload, headers=headers, timeout=self.timeout
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    body = response.text[:500]
                    if json_mode and response.status_code == 400:
                        raise _JsonModeUnsupported(body)
                    raise AnalysisError(
                        f"LLM request failed ({response.status_code}): {body}"
                    )
                for line in response.iter_lines():
                    data = line.strip()
                    if not data:
                        continue
                    if data.startswith("data:"):
                        data = data[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    if delta.get("reasoning_content"):
                        yield REASONING, delta["reasoning_content"]
                    if delta.get("content"):
                        yield CONTENT, delta["content"]
        except httpx.HTTPError as exc:
            raise AnalysisError(f"LLM request failed: {exc}") from exc
