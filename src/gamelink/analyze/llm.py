"""Thin, provider-agnostic LLM client (OpenAI-compatible chat completions)."""

from __future__ import annotations

import httpx

from gamelink.config import LLMSettings
from gamelink.errors import AnalysisError, ConfigError


class LLMClient:
    def __init__(self, settings: LLMSettings, timeout: float = 180.0) -> None:
        self.settings = settings
        self.timeout = timeout

    def complete(self, system: str, user: str) -> str:
        if not self.settings.api_key:
            raise ConfigError(
                "GAMELINK_LLM_API_KEY is not set — configure .env (see .env.example)"
            )
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnalysisError(
                f"LLM request failed ({exc.response.status_code}): {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AnalysisError(f"LLM request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AnalysisError(f"unexpected LLM response shape: {data}") from exc
