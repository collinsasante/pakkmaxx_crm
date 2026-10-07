"""Shared, permission-aware CRM metrics for dashboards and reports.

All queries go through frappe.get_list / get_all with permission checks so a sales rep's
dashboard shows their own pipeline, a team manager sees their team, and managers see all.
Money is reported in GHS.
"""

from collections import defaultdict

import frappe
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, nowdate

WON, LOST = "Won", "Lost"


def status_types(doctype: str) -> dict[str, str]:
	return {s.name: s.type for s in frappe.get_all(doctype, fields=["name", "type"])}


def date_filter(filters: dict | None, field: str = "creation") -> dict:
	filters = frappe._dict(filters or {})
	out = {}
	if filters.get("from_date") and filters.get("to_date"):
		out[field] = ["between", [getdate(filters.from_date), get_datetime(f"{filters.to_date} 23:59:59")]]
	elif filters.get("from_date"):
		out[field] = [">=", getdate(filters.from_date)]
	elif filters.get("to_date"):
		out[field] = ["<=", get_datetime(f"{filters.to_date} 23:59:59")]
	return out


def ghs(deal) -> float:
	value = flt(deal.get("deal_value"))
	if deal.get("currency") and deal.currency != "GHS":
		value *= flt(deal.get("exchange_rate")) or 1
	return value


def lead_rows(filters=None, fields=None, extra=None) -> list:
	filters = frappe._dict(filters or {})
	f = {**date_filter(filters), **(extra or {})}
	for key, field in (("source", "source"), ("sales_rep", "lead_owner"), ("status", "status"),
			("campaign", "pkx_campaign")):
		if filters.get(key):
			f[field] = filters.get(key)
	return frappe.get_list(
		"CRM Lead",
		filters=f,
		fields=fields or ["name", "status", "source", "lead_owner", "converted", "pkx_customer", "creation",
			"pkx_first_contacted_on", "pkx_campaign", "pkx_business_type", "pkx_lifecycle_stage"],
		limit_page_length=0,
	)


def deal_rows(filters=None, extra=None, date_field="creation") -> list:
	filters = frappe._dict(filters or {})
	f = {**date_filter(filters, date_field), **(extra or {})}
	for key, field in (("source", "source"), ("sales_rep", "deal_owner"), ("status", "status")):
		if filters.get(key):
			f[field] = filters.get(key)
	return frappe.get_list(
		"CRM Deal",
		filters=f,
		fields=["name", "status", "source", "deal_owner", "deal_value", "currency", "exchange_rate", "probability",
			"pkx_weighted_value", "expected_closure_date", "pkx_won_on", "pkx_lost_on", "lead", "pkx_customer",
			"organization", "lead_name", "creation", "pkx_campaign"],
		limit_page_length=0,
	)


def deal_summary(filters=None) -> dict:
	types = status_types("CRM Deal Status")
	deals = deal_rows(filters)
	out = defaultdict(float)
	for d in deals:
		kind = types.get(d.status)
		if kind == WON:
			out["won_count"] += 1
			out["won_value"] += ghs(d)
		elif kind == LOST:
			out["lost_count"] += 1
		else:
			out["open_count"] += 1
			out["pipeline_value"] += ghs(d)
			out["weighted_value"] += ghs(d) * flt(d.probability) / 100
	closed = out["won_count"] + out["lost_count"]
	out["win_rate"] = round(100 * out["won_count"] / closed, 1) if closed else 0
	out["avg_deal_value"] = round(out["won_value"] / out["won_count"], 2) if out["won_count"] else 0
	return dict(out)


def lead_summary(filters=None) -> dict:
	types = status_types("CRM Lead Status")
	leads = lead_rows(filters)
	total = len(leads)
	qualified = sum(1 for l in leads if l.status in ("Qualified", "Proposal/Quote Requested", "Negotiation")
		or l.converted)
	customers = sum(1 for l in leads if l.pkx_customer)
	return {
		"total": total,
		"new": sum(1 for l in leads if l.status == "New"),
		"qualified": qualified,
		"lost": sum(1 for l in leads if types.get(l.status) == LOST),
		"converted_to_opportunity": sum(1 for l in leads if l.converted),
		"became_customer": customers,
		"conversion_rate": round(100 * customers / total, 1) if total else 0,
		"unassigned": sum(1 for l in leads if not l.lead_owner and types.get(l.status) not in (WON, LOST)),
		"uncontacted": sum(1 for l in leads if l.status == "New" and not l.pkx_first_contacted_on),
	}


def customer_summary(filters=None) -> dict:
	rows = frappe.get_list(
		"Pakkmaxx Customer",
		filters={"disabled": 0, **date_filter(filters, "first_won_on")},
		fields=["lifecycle_stage", "days_to_convert"],
		limit_page_length=0,
	)
	counts = defaultdict(int)
	days = [r.days_to_convert for r in rows if r.days_to_convert is not None]
	for r in rows:
		counts[r.lifecycle_stage] += 1
	return {
		"total": len(rows),
		"active": counts["Active Customer"] + counts["Repeat Customer"],
		"repeat": counts["Repeat Customer"],
		"dormant": counts["Dormant"],
		"avg_days_to_convert": round(sum(days) / len(days), 1) if days else 0,
	}


def follow_up_summary(user: str | None = None) -> dict:
	open_statuses = ["Backlog", "Todo", "In Progress"]
	base = {"status": ["in", open_statuses], "pkx_task_type": "Follow-up"}
	if user:
		base["assigned_to"] = user
	now = now_datetime()
	end_today = get_datetime(f"{nowdate()} 23:59:59")
	end_week = get_datetime(f"{add_days(nowdate(), 7)} 23:59:59")

	def count(extra):
		return len(frappe.get_list("CRM Task", filters={**base, **extra}, pluck="name", limit_page_length=0))

	return {
		"overdue": count({"due_date": ["<", now]}),
		"today": count({"due_date": ["between", [now, end_today]]}),
		"upcoming": count({"due_date": ["between", [end_today, end_week]]}),
	}
