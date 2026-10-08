"""AI output is untrusted input: parse and validate strictly before anything touches the CRM."""

import json
import re
from dataclasses import dataclass, field

from frappe.utils import cint

from pakkmaxx_crm.ai.prompt import INTENTS, MODEL_LABELS, SERVICES

TEXT_FIELDS = {
	"product_category": 140,
	"origin": 140,
	"destination": 140,
	"quantity": 140,
	"estimated_volume": 140,
	"expected_shipping_date": 140,
	"estimated_value": 140,
	"recommended_next_action": 500,
	"summary": 600,
	"context_summary": 800,
}
LIST_FIELDS = ("buying_signals", "negative_signals", "missing_information", "evidence")
MAX_LIST_ITEMS = 8
MAX_ITEM_CHARS = 200
CLASSES = ("Unqualified", "Needs Follow-up", "Qualified", "High Value")


class ValidationFailed(Exception):
	pass


@dataclass
class Qualification:
	score: int
	confidence: float
	model_label: str
	intent: str
	service_interest: list[str]
	texts: dict = field(default_factory=dict)
	lists: dict = field(default_factory=dict)
	warnings: list[str] = field(default_factory=list)


def _clean_text(value, limit: int):
	if value is None:
		return None
	if not isinstance(value, str | int | float):
		raise ValidationFailed("expected text")
	text = re.sub(r"\s+", " ", str(value)).strip()
	if not text or text.lower() in ("null", "none", "n/a", "unknown"):
		return None
	return text[:limit]


def parse_json(text: str) -> dict:
	text = (text or "").strip()
	text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)  # tolerate fenced output
	try:
		data = json.loads(text)
	except ValueError as exc:
		raise ValidationFailed(f"invalid JSON: {exc}") from exc
	if not isinstance(data, dict):
		raise ValidationFailed("JSON root must be an object")
	return data


def validate(data: dict) -> Qualification:
	missing = [k for k in ("score", "confidence", "classification", "summary", "recommended_next_action") if k not in data]
	if missing:
		raise ValidationFailed(f"missing keys: {', '.join(missing)}")

	score = data["score"]
	if isinstance(score, bool) or not isinstance(score, int | float):
		raise ValidationFailed("score must be a number")
	if not 0 <= score <= 100:
		raise ValidationFailed(f"score out of range: {score}")

	confidence = data["confidence"]
	if isinstance(confidence, bool) or not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
		raise ValidationFailed(f"confidence must be between 0 and 1: {confidence!r}")

	warnings = []
	label = str(data["classification"]).strip().lower().replace(" ", "_").replace("-", "_")
	if label not in MODEL_LABELS:
		raise ValidationFailed(f"unknown classification: {data['classification']!r}")

	intent = str(data.get("intent") or "unknown").strip().lower()
	if intent not in INTENTS:
		warnings.append(f"unknown intent {intent!r} replaced with 'unknown'")
		intent = "unknown"

	services_in = data.get("service_interest") or []
	if not isinstance(services_in, list):
		raise ValidationFailed("service_interest must be a list")
	services = []
	for s in services_in:
		s = str(s).strip().lower().replace(" ", "_").replace("-", "_")
		if s in SERVICES and s not in services:
			services.append(s)
		elif s:
			warnings.append(f"ignored unknown service {s!r}")

	texts = {}
	for key, limit in TEXT_FIELDS.items():
		try:
			texts[key] = _clean_text(data.get(key), limit)
		except ValidationFailed as exc:
			raise ValidationFailed(f"{key}: {exc}") from exc
	if not texts["summary"] or not texts["recommended_next_action"]:
		raise ValidationFailed("summary and recommended_next_action are required")

	lists = {}
	for key in LIST_FIELDS:
		value = data.get(key) or []
		if not isinstance(value, list):
			raise ValidationFailed(f"{key} must be a list")
		items = [_clean_text(v, MAX_ITEM_CHARS) for v in value if isinstance(v, str | int | float)]
		lists[key] = [i for i in items if i][:MAX_LIST_ITEMS]

	return Qualification(
		score=int(round(score)),
		confidence=float(confidence),
		model_label=label,
		intent=intent,
		service_interest=services,
		texts=texts,
		lists=lists,
		warnings=warnings,
	)


def classify(score: int, settings) -> str:
	"""Classification follows the configurable thresholds in Pakkmaxx CRM Settings."""
	follow_up = cint(settings.ai_needs_follow_up_from) if settings.ai_needs_follow_up_from is not None else 30
	qualified = cint(settings.ai_qualified_from) or 60
	high = cint(settings.ai_high_value_from) or 80
	if score >= high:
		return "High Value"
	if score >= qualified:
		return "Qualified"
	if score >= follow_up:
		return "Needs Follow-up"
	return "Unqualified"
