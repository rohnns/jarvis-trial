from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass


class AIProvider(ABC):
    """Common interface for all conversational AI backends."""

    @abstractmethod
    async def ask(self, prompt: str) -> str:
        """Return a response for a user prompt."""
        raise RuntimeError("AIProvider.ask must be implemented by subclasses")


@dataclass(frozen=True)
class OllamaProvider(AIProvider):
    """Local Ollama backend using the configured model."""

    model: str
    base_url: str = "http://127.0.0.1:11434"

    async def ask(self, prompt: str) -> str:
        return await asyncio.to_thread(self._ask_sync, prompt)

    def _ask_sync(self, prompt: str) -> str:
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                text = str(data.get("response", "")).strip()
                return text or "I got an empty response from Ollama. Dramatic, but unhelpful."
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return f"Ollama is not reachable for model {self.model}: {exc}"


@dataclass(frozen=True)
class ChatGPTProvider(AIProvider):
    """OpenAI-compatible provider using OPENAI_API_KEY."""

    model: str = "gpt-4o-mini"
    api_url: str = "https://api.openai.com/v1/chat/completions"

    async def ask(self, prompt: str) -> str:
        return await asyncio.to_thread(_chat_completions_request, self.api_url, os.environ.get("OPENAI_API_KEY", ""), self.model, prompt)


@dataclass(frozen=True)
class GeminiProvider(AIProvider):
    """Gemini REST provider using GEMINI_API_KEY."""

    model: str = "gemini-1.5-flash"

    async def ask(self, prompt: str) -> str:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return "Gemini is not configured. Set GEMINI_API_KEY."
        return await asyncio.to_thread(self._ask_sync, api_key, prompt)

    def _ask_sync(self, api_key: str, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            return f"Gemini request failed: {exc}"


@dataclass(frozen=True)
class ClaudeProvider(AIProvider):
    """Anthropic Messages API provider using ANTHROPIC_API_KEY."""

    model: str = "claude-3-5-haiku-latest"
    api_url: str = "https://api.anthropic.com/v1/messages"

    async def ask(self, prompt: str) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "Claude is not configured. Set ANTHROPIC_API_KEY."
        return await asyncio.to_thread(self._ask_sync, api_key, prompt)

    def _ask_sync(self, api_key: str, prompt: str) -> str:
        payload = json.dumps({"model": self.model, "max_tokens": 800, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["content"][0]["text"].strip()
        except Exception as exc:
            return f"Claude request failed: {exc}"


def _chat_completions_request(api_url: str, api_key: str, model: str, prompt: str) -> str:
    if not api_key:
        return "ChatGPT is not configured. Set OPENAI_API_KEY."
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    request = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"ChatGPT request failed: {exc}"
