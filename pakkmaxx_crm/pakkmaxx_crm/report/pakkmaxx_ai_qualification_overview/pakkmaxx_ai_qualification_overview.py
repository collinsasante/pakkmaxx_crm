# Copyright (c) 2026, Pakkmaxx and contributors
"""How the AI is classifying leads, and what the analyses cost."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt

from pakkmaxx_crm.reporting import date_filter

CLASSES = ("High Value", "Qualified", "Needs Follow-up", "Unqualified")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	leads = frappe.get_list(
		"CRM Lead",
		filters={"pkx_ai_status": "Analysed", **date_filter(filters, "pkx_ai_analyzed_at")},
		fields=["pkx_ai_classification", "pkx_ai_effective_classification", "pkx_ai_score", "pkx_ai_confidence"],
		limit_page_length=0,
	)
	runs = frappe.get_list(
		"Pakkmaxx AI Qualification",
		filters=date_filter(filters, "creation"),
		fields=["status", "latency_ms", "input_tokens", "output_tokens", "cost_usd", "model"],
		limit_page_length=0,
	)
	total = len(leads) or 1
	by_class = Counter(l.pkx_ai_effective_classification or l.pkx_ai_classification for l in leads)
	data = [
		{"metric": _("Leads analysed"), "value": len(leads)},
		*({"metric": _(c), "value": by_class.get(c, 0), "share": round(100 * by_class.get(c, 0) / total, 1)} for c in CLASSES),
		{"metric": _("Average AI score"), "value": round(sum(l.pkx_ai_score or 0 for l in leads) / total, 1)},
		{"metric": _("Average AI confidence (%)"), "value": round(sum(flt(l.pkx_ai_confidence) for l in leads) / total, 1)},
	]
	status = Counter(r.status for r in runs)
	completed = [r for r in runs if r.status == "Completed"]
	data += [
		{"metric": _("Analyses run"), "value": len(runs)},
		*({"metric": _("Analyses {0}").format(_(s).lower()), "value": status.get(s, 0)} for s in ("Completed", "Skipped", "Failed")),
		{"metric": _("Average latency (ms)"), "value": round(sum(r.latency_ms or 0 for r in completed) / (len(completed) or 1))},
		{"metric": _("Tokens (input / output)"), "value": f"{sum(r.input_tokens or 0 for r in runs):,} / {sum(r.output_tokens or 0 for r in runs):,}"},
		{"metric": _("Estimated cost (USD)"), "value": round(sum(flt(r.cost_usd) for r in runs), 4)},
		{"metric": _("Models"), "value": ", ".join(sorted({r.model for r in completed if r.model})) or "-"},
	]
	columns = [
		{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 260},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 180},
		{"fieldname": "share", "label": _("% of Analysed Leads"), "fieldtype": "Percent", "width": 160},
	]
	chart = {"data": {"labels": [_(c) for c in CLASSES], "datasets": [{"name": _("Leads"), "values": [by_class.get(c, 0) for c in CLASSES]}]}, "type": "donut"}
	return columns, data, None, chart
