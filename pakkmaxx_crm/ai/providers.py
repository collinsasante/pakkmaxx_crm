"""Provider abstraction: qualification logic never depends on a specific vendor.

To add a provider (e.g. Claude): subclass AIProvider, implement complete_json, register it in
PROVIDERS and add its name to the "AI Provider" select in Pakkmaxx CRM Settings.
"""

import os
import time
from dataclasses import dataclass

import frappe
import requests


class AIProviderError(Exception):
	"""Provider unavailable or returned an error. `retryable` says whether trying later may help."""

	def __init__(self, message: str, retryable: bool = True):
		super().__init__(message)
		self.retryable = retryable


@dataclass
class AIResult:
	text: str
	provider: str
	model: str
	input_tokens: int = 0
	output_tokens: int = 0
	latency_ms: int = 0


class AIProvider:
	name = "base"

	def __init__(self, settings):
		self.settings = settings

	def complete_json(self, system: str, user: str) -> AIResult:  # pragma: no cover - interface
		raise NotImplementedError


class DeepSeekProvider(AIProvider):
	"""DeepSeek chat completions (OpenAI-compatible) with JSON output mode.

	Docs: https://api-docs.deepseek.com - POST {base}/chat/completions,
	response_format={"type": "json_object"}; the prompt must mention JSON and show the format.
	"""

	name = "DeepSeek"

	def _api_key(self) -> str:
		key = (
			os.environ.get("DEEPSEEK_API_KEY")
			or frappe.conf.get("deepseek_api_key")
			or self.settings.get_password("ai_api_key", raise_exception=False)
		)
		if not key:
			raise AIProviderError("DeepSeek API key is not configured", retryable=False)
		return key

	def complete_json(self, system: str, user: str) -> AIResult:
		base = (self.settings.ai_base_url or "https://api.deepseek.com").rstrip("/")
		model = self.settings.ai_model or "deepseek-flash"
		body = {
			"model": model,
			"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
			"response_format": {"type": "json_object"},
			"temperature": float(self.settings.ai_temperature if self.settings.ai_temperature is not None else 0.1),
			"max_tokens": int(self.settings.ai_max_output_tokens or 1200),
			"stream": False,
		}
		started = time.monotonic()
		try:
			resp = requests.post(
				f"{base}/chat/completions",
				json=body,
				headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"},
				timeout=int(self.settings.ai_timeout_seconds or 45),
			)
		except requests.RequestException as exc:
			raise AIProviderError(f"DeepSeek unreachable: {type(exc).__name__}") from exc
		latency = int((time.monotonic() - started) * 1000)

		if resp.status_code in (401, 403):
			raise AIProviderError("DeepSeek rejected the API key", retryable=False)
		if resp.status_code == 402:
			raise AIProviderError("DeepSeek account has insufficient balance", retryable=False)
		if resp.status_code == 400:
			raise AIProviderError(f"DeepSeek rejected the request: {resp.text[:200]}", retryable=False)
		if resp.status_code >= 400:
			raise AIProviderError(f"DeepSeek error {resp.status_code}", retryable=resp.status_code in (408, 429) or resp.status_code >= 500)
		try:
			data = resp.json()
			choice = data["choices"][0]
			text = (choice.get("message") or {}).get("content") or ""
		except (ValueError, KeyError, IndexError, TypeError) as exc:
			raise AIProviderError("DeepSeek returned an unexpected response") from exc
		if choice.get("finish_reason") == "length":
			raise AIProviderError("DeepSeek response was cut off (raise Max Output Tokens)", retryable=False)
		if not text.strip():
			raise AIProviderError("DeepSeek returned empty content")  # documented intermittent behaviour
		usage = data.get("usage") or {}
		return AIResult(
			text=text,
			provider=self.name,
			model=data.get("model") or model,
			input_tokens=int(usage.get("prompt_tokens") or 0),
			output_tokens=int(usage.get("completion_tokens") or 0),
			latency_ms=latency,
		)


PROVIDERS = {"DeepSeek": DeepSeekProvider}


def get_provider(settings) -> AIProvider:
	cls = PROVIDERS.get(settings.ai_provider or "DeepSeek")
	if not cls:
		raise AIProviderError(f"Unknown AI provider {settings.ai_provider}", retryable=False)
	return cls(settings)
