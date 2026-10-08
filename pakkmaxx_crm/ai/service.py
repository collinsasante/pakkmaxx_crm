"""Queue and run AI qualification. Runs in background jobs; never blocks a request."""

import json

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, now_datetime

from pakkmaxx_crm.ai.context import build_context
from pakkmaxx_crm.ai.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from pakkmaxx_crm.ai.providers import AIProviderError, get_provider
from pakkmaxx_crm.ai.validation import ValidationFailed, classify, parse_json, validate

DOCTYPE = "Pakkmaxx AI Qualification"
ACTIVE = ("Queued", "Running")


def settings():
	return frappe.get_cached_doc("Pakkmaxx CRM Settings")


def ai_enabled() -> bool:
	return bool(cint(settings().ai_enabled))


def queue_analysis(lead: str, trigger: str, *, force: bool = False, requested_by: str | None = None) -> str | None:
	"""Create a Queued record and enqueue the job. One active analysis per lead.

	`force` (manual Re-analyse) skips the "nothing changed" check, not the feature flag.
	"""
	if not ai_enabled():
		return None
	active = frappe.db.get_value(DOCTYPE, {"lead": lead, "status": ["in", ACTIVE]})
	if active:
		return active
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"lead": lead,
			"status": "Queued",
			"trigger": trigger,
			"requested_by": requested_by,
			"attempts": 0,
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value("CRM Lead", lead, "pkx_ai_status", "Pending", update_modified=False)
	frappe.enqueue(
		"pakkmaxx_crm.ai.service.run_analysis",
		queue="default",
		timeout=300,
		record=doc.name,
		force=force,
		enqueue_after_commit=True,
		job_id=f"pkx_ai_qualify::{lead}",
		deduplicate=True,
	)
	return doc.name


def _fail(doc, message: str, raw: str | None = None):
	doc.status = "Failed"
	doc.error = message[:1000]
	if raw is not None:
		doc.raw_response = raw[:20000]
	doc.save(ignore_permissions=True)
	if not frappe.db.exists(DOCTYPE, {"lead": doc.lead, "status": "Completed"}):
		frappe.db.set_value("CRM Lead", doc.lead, "pkx_ai_status", "Failed", update_modified=False)
	else:
		frappe.db.set_value("CRM Lead", doc.lead, "pkx_ai_status", "Analysed", update_modified=False)


def _clear_pending(lead: str, context_taken_at) -> dict:
	"""Reset the new-message counter only if no customer message arrived after the conversation was read;
	otherwise those newer messages stay pending for the next analysis."""
	last = frappe.db.get_value("CRM Lead", lead, "pkx_ai_last_customer_message_at")
	if last and get_datetime(last) > get_datetime(context_taken_at):
		return {}
	return {"pkx_ai_pending_messages": 0}


def run_analysis(record: str, force: bool = False):
	frappe.set_user("Administrator")  # system job; permission was checked when it was requested
	doc = frappe.get_doc(DOCTYPE, record)
	if doc.status not in ACTIVE:
		return
	conf = settings()
	if not cint(conf.ai_enabled):
		doc.status, doc.error = "Skipped", "AI qualification is disabled"
		doc.save(ignore_permissions=True)
		frappe.db.set_value("CRM Lead", doc.lead, "pkx_ai_status", "Not Analysed", update_modified=False)
		frappe.db.commit()
		return

	doc.status, doc.attempts = "Running", cint(doc.attempts) + 1
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	context_taken_at = now_datetime()
	try:
		ctx = build_context(doc.lead, conf)
	except Exception as exc:
		_fail(doc, f"Could not load the conversation: {str(exc)[:300]}")
		frappe.db.commit()
		return
	meta, payload = ctx["meta"], ctx["payload"]
	doc.update(
		{
			"verzchat_conversation_id": meta["conversation_id"],
			"messages_analyzed": meta["messages_analyzed"],
			"first_message_id": meta["first_message_id"],
			"last_message_id": meta["last_message_id"],
			"context_hash": meta["context_hash"],
			"previous_analysis": meta["previous"],
			"prompt_version": PROMPT_VERSION,
		}
	)

	previous_hash = frappe.db.get_value(DOCTYPE, meta["previous"], "context_hash") if meta["previous"] else None
	if not force and previous_hash and previous_hash == meta["context_hash"]:
		doc.status, doc.error = "Skipped", "No new information since the previous analysis"
		doc.save(ignore_permissions=True)
		frappe.db.set_value("CRM Lead", doc.lead, {"pkx_ai_status": "Analysed", **_clear_pending(doc.lead, context_taken_at)},
			update_modified=False)
		frappe.db.commit()
		return
	if not payload["conversation"] and not payload["crm_data"]:
		doc.status, doc.error = "Skipped", "Nothing to analyse yet"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return

	try:
		provider = get_provider(conf)
		result = provider.complete_json(SYSTEM_PROMPT, build_user_prompt(payload))
	except AIProviderError as exc:
		_fail(doc, f"AI provider: {exc}")
		frappe.log_error(title="AI qualification provider error", message=f"{doc.name} lead={doc.lead}: {exc}")
		frappe.db.commit()
		return

	doc.update(
		{
			"provider": result.provider,
			"model": result.model,
			"latency_ms": result.latency_ms,
			"input_tokens": result.input_tokens,
			"output_tokens": result.output_tokens,
			"cost_usd": round(
				result.input_tokens * flt(conf.ai_cost_input_per_million) / 1e6
				+ result.output_tokens * flt(conf.ai_cost_output_per_million) / 1e6,
				6,
			),
		}
	)
	try:
		q = validate(parse_json(result.text))
	except ValidationFailed as exc:
		_fail(doc, f"Invalid AI response: {exc}", raw=result.text)
		frappe.log_error(title="AI qualification invalid response", message=f"{doc.name}: {exc}")
		frappe.db.commit()
		return

	classification = classify(q.score, conf)
	lines = lambda items: "\n".join(f"• {i}" for i in items) or None  # noqa: E731
	doc.update(
		{
			"status": "Completed",
			"classification": classification,
			"score": q.score,
			"confidence": round(q.confidence * 100, 1),
			"model_classification": q.model_label,
			"intent": q.intent,
			"service_interest": ", ".join(q.service_interest) or None,
			**{k: q.texts[k] for k in ("product_category", "origin", "destination", "quantity", "estimated_volume",
				"expected_shipping_date", "estimated_value", "recommended_next_action", "summary", "context_summary")},
			"buying_signals": lines(q.lists["buying_signals"]),
			"negative_signals": lines(q.lists["negative_signals"]),
			"missing_information": lines(q.lists["missing_information"]),
			"evidence": lines(q.lists["evidence"]),
			"analyzed_at": now_datetime(),
			"error": "; ".join(q.warnings)[:1000] or None,
			"raw_response": result.text[:20000],
		}
	)
	lead_links = frappe.db.get_value("CRM Lead", doc.lead, ["pkx_customer", "pkx_ai_human_classification"], as_dict=True)
	doc.customer = lead_links.pkx_customer
	doc.deal = frappe.db.get_value("CRM Deal", {"lead": doc.lead}, "name", order_by="creation desc")
	doc.save(ignore_permissions=True)

	# Mirror onto the lead. The human override fields are never touched here.
	frappe.db.set_value(
		"CRM Lead",
		doc.lead,
		{
			"pkx_ai_classification": classification,
			"pkx_ai_score": q.score,
			"pkx_ai_confidence": doc.confidence,
			"pkx_ai_status": "Analysed",
			"pkx_ai_analyzed_at": doc.analyzed_at,
			"pkx_ai_last_analysis": doc.name,
			"pkx_ai_next_action": doc.recommended_next_action,
			"pkx_ai_missing_information": doc.missing_information,
			"pkx_ai_buying_signals": doc.buying_signals,
			"pkx_ai_summary": doc.summary,
			**_clear_pending(doc.lead, context_taken_at),
			"pkx_ai_effective_classification": lead_links.pkx_ai_human_classification or classification,
		},
		update_modified=False,
	)
	frappe.db.commit()
	frappe.publish_realtime("pkx_ai_qualification", {"lead": doc.lead, "record": doc.name}, doctype="CRM Lead", docname=doc.lead)


def clear_old_raw_responses():
	"""Daily: raw provider output is only kept briefly for debugging (configurable)."""
	days = cint(settings().ai_keep_raw_days) or 14
	frappe.db.sql(
		f"update `tab{DOCTYPE}` set raw_response = null where raw_response is not null and creation < %s",
		add_days(now_datetime(), -days),
	)
	frappe.db.commit()
