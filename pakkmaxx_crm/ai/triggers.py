"""When to analyse. Cost control: never per message; only on meaningful change, with a cooldown."""

import re

import frappe
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from pakkmaxx_crm.ai.service import ACTIVE, DOCTYPE, queue_analysis, settings


def _keywords(conf) -> list[str]:
	return [k.strip().lower() for k in (conf.ai_trigger_keywords or "").split(",") if k.strip()]


def _in_cooldown(lead: str, conf) -> bool:
	last = frappe.db.get_value(DOCTYPE, {"lead": lead, "status": "Completed"}, "analyzed_at", order_by="analyzed_at desc")
	minutes = cint(conf.ai_cooldown_minutes)
	return bool(last and minutes and get_datetime(last) > add_to_date(now_datetime(), minutes=-minutes))


def on_verzchat_message(lead: str, event: str, message: dict, conversation: dict):
	"""verzchat_message_handlers hook: count customer messages and decide whether to analyse."""
	conf = settings()
	if not (cint(conf.ai_enabled) and cint(conf.ai_auto_analysis)):
		return
	if event != "message.received" or message.get("direction") != "INBOUND":
		return
	pending = cint(frappe.db.get_value("CRM Lead", lead, "pkx_ai_pending_messages")) + 1
	frappe.db.set_value(
		"CRM Lead",
		lead,
		{"pkx_ai_pending_messages": pending, "pkx_ai_last_customer_message_at": now_datetime()},
		update_modified=False,
	)
	text = (message.get("content") or message.get("mediaCaption") or "").lower()
	keyword_hit = any(re.search(rf"\b{re.escape(k)}\b", text) for k in _keywords(conf))
	reason = (
		"New Customer Messages" if pending >= max(1, cint(conf.ai_min_customer_messages) or 3)
		else "Intent Keywords" if keyword_hit
		else None
	)
	if reason and not _in_cooldown(lead, conf):
		queue_analysis(lead, reason)


def analyze_quiet_conversations():
	"""Scheduled: customers who wrote and then went quiet get one analysis (after the cooldown)."""
	conf = settings()
	if not (cint(conf.ai_enabled) and cint(conf.ai_auto_analysis)):
		return
	cutoff = add_to_date(now_datetime(), minutes=-(cint(conf.ai_quiet_minutes) or 120))
	leads = frappe.get_all(
		"CRM Lead",
		filters={"pkx_ai_pending_messages": [">", 0], "pkx_ai_last_customer_message_at": ["<=", cutoff]},
		pluck="name",
		limit=200,
	)
	for lead in leads:
		if frappe.db.exists(DOCTYPE, {"lead": lead, "status": ["in", ACTIVE]}) or _in_cooldown(lead, conf):
			continue
		queue_analysis(lead, "Quiet Conversation")
	frappe.db.commit()


def on_lead_insert(doc, method=None):
	"""Manually created leads (not from VerzChat) can be analysed from their CRM fields."""
	conf = settings()
	if cint(conf.ai_enabled) and cint(conf.ai_analyze_manual_leads) and not doc.get("verzchat_contact_id"):
		queue_analysis(doc.name, "Lead Created")
