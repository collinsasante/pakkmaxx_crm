"""Builds the minimal, redacted context the AI needs to qualify a lead.

Sent: qualification-relevant CRM facts (no names, phones or emails), the previous assessment,
a running summary of older conversation, and the most recent messages (capped).
Not sent: personal identifiers, staff details, unrelated CRM records, credentials.
"""

import hashlib
import json
import re

import frappe
from frappe.utils import cint

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
SECRET = re.compile(r"\b(password|passcode|pin|otp|code|token)\b\s*(is|:|=)?\s*\S+", re.IGNORECASE)
LONG_NUMBER = re.compile(r"\b\d{12,}\b")
MAX_TOTAL_CHARS = 24_000


def redact(text: str) -> str:
	text = EMAIL.sub("[email]", text)
	text = SECRET.sub(lambda m: f"{m.group(1)} [redacted]", text)
	text = LONG_NUMBER.sub("[redacted]", text)
	return PHONE.sub("[phone]", text)


def _crm_facts(lead) -> dict:
	facts = {
		"lead_status": lead.status,
		"source": lead.source,
		"customer_type": lead.get("pkx_customer_type"),
		"business_type": lead.get("pkx_business_type"),
		"services_recorded": [r.service for r in lead.get("pkx_services") or []],
		"product_categories_recorded": [r.product_category for r in lead.get("pkx_product_categories") or []],
		"what_they_ship": lead.get("pkx_products_description"),
		"origin": lead.get("pkx_origin_city"),
		"destination": lead.get("pkx_destination_city"),
		"shipping_frequency": lead.get("pkx_shipping_frequency"),
		"est_monthly_volume_cbm": lead.get("pkx_est_monthly_volume_cbm") or None,
		"est_monthly_weight_kg": lead.get("pkx_est_monthly_weight_kg") or None,
		"expected_first_shipment": str(lead.get("pkx_expected_ship_date") or "") or None,
		"tags": [t for t in (lead.get("_user_tags") or "").split(",") if t],
	}
	if lead.get("pkx_customer"):
		customer = frappe.db.get_value(
			"Pakkmaxx Customer", lead.pkx_customer, ["lifecycle_stage", "won_deals_count"], as_dict=True
		)
		if customer:
			facts["existing_customer"] = {"lifecycle": customer.lifecycle_stage, "won_shipments": customer.won_deals_count}
	deals = frappe.get_all("CRM Deal", filters={"lead": lead.name}, fields=["status"])
	if deals:
		facts["opportunities"] = [d.status for d in deals]
	open_follow_ups = frappe.get_all(
		"CRM Task",
		filters={"reference_doctype": "CRM Lead", "reference_docname": lead.name, "status": ["not in", ["Done", "Canceled"]]},
		fields=["title"],
		limit=3,
	)
	if open_follow_ups:
		facts["open_follow_ups"] = [redact(t.title or "")[:120] for t in open_follow_ups]
	return {k: v for k, v in facts.items() if v not in (None, "", [], {})}


def _previous(lead_name: str):
	return frappe.db.get_value(
		"Pakkmaxx AI Qualification",
		{"lead": lead_name, "status": "Completed"},
		["name", "classification", "score", "summary", "context_summary", "last_message_id", "analyzed_at"],
		as_dict=True,
		order_by="analyzed_at desc",
	)


def build_context(lead_name: str, settings) -> dict:
	"""Returns {"payload": <sent to the AI>, "meta": <stored for audit / change detection>}."""
	lead = frappe.get_doc("CRM Lead", lead_name)
	previous = _previous(lead_name)
	max_messages = max(5, min(cint(settings.ai_max_messages) or 40, 100))
	max_chars = max(100, cint(settings.ai_max_chars_per_message) or 800)
	do_redact = cint(settings.ai_redact) if settings.ai_redact is not None else 1

	messages, ids, conversation_id, truncated = [], [], None, False
	if "verzchat_crm" in frappe.get_installed_apps() and lead.get("verzchat_contact_id"):
		from verzchat_crm.conversations import recent_messages

		page = recent_messages(lead_name, limit=max_messages)  # raises VerzChatError if VerzChat is down
		conversation_id, truncated = page["conversation_id"], page["has_more"]
		for i, m in enumerate(page["messages"], 1):
			text = (m["text"] or "")[:max_chars]
			ids.append(m["id"])
			messages.append(
				{
					"n": i,
					"from": "customer" if m["direction"] == "INBOUND" else "pakkmaxx_agent",
					"at": m["at"][:16],
					"text": redact(text) if do_redact else text,
				}
			)
		# keep the newest messages within the overall size budget
		while messages and len(json.dumps(messages, ensure_ascii=False)) > MAX_TOTAL_CHARS:
			messages.pop(0)
			ids.pop(0)
			truncated = True

	payload = {
		"crm_data": _crm_facts(lead),
		"previous_assessment": (
			{"classification": previous.classification, "score": previous.score, "summary": previous.summary}
			if previous
			else None
		),
		"earlier_conversation_summary": previous.context_summary if (previous and truncated) else None,
		"conversation_truncated": truncated,
		"conversation": messages,
	}
	meta = {
		"conversation_id": conversation_id,
		"messages_analyzed": len(messages),
		"first_message_id": ids[0] if ids else None,
		"last_message_id": ids[-1] if ids else None,
		"customer_messages": sum(1 for m in messages if m["from"] == "customer"),
		"previous": previous.name if previous else None,
		"context_hash": hashlib.sha256(
			json.dumps({"crm": payload["crm_data"], "last": ids[-1] if ids else None, "n": len(messages)},
				sort_keys=True, default=str).encode()
		).hexdigest()[:32],
	}
	return {"payload": payload, "meta": meta}
