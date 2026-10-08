# Copyright (c) 2026, Pakkmaxx and contributors
"""Where people disagreed with the AI: measures how accurate the AI is."""

import frappe
from frappe import _

from pakkmaxx_crm.reporting import date_filter


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {"pkx_ai_status": "Analysed", **date_filter(filters, "pkx_ai_analyzed_at")}
	if filters.get("only_overrides"):
		f["pkx_ai_human_classification"] = ["is", "set"]
	leads = frappe.get_list(
		"CRM Lead",
		filters=f,
		fields=["name", "lead_name", "source", "lead_owner", "pkx_ai_classification", "pkx_ai_score",
			"pkx_ai_confidence", "pkx_ai_human_classification", "pkx_ai_human_score", "pkx_ai_override_reason",
			"pkx_ai_overridden_by", "pkx_ai_overridden_on"],
		order_by="pkx_ai_overridden_on desc",
		limit_page_length=0,
	)
	analysed = frappe.db.count("CRM Lead", {"pkx_ai_status": "Analysed"}) if not filters.get("only_overrides") else None
	overridden = [l for l in leads if l.pkx_ai_human_classification]
	agreed = [l for l in overridden if l.pkx_ai_human_classification == l.pkx_ai_classification]
	for l in leads:
		l["agreement"] = (
			"" if not l.pkx_ai_human_classification
			else _("Agreed") if l.pkx_ai_human_classification == l.pkx_ai_classification
			else _("Disagreed")
		)
	base = analysed if analysed is not None else len(leads)
	report_summary = [
		{"label": _("AI-analysed leads"), "value": base, "datatype": "Int"},
		{"label": _("Reviewed by a person"), "value": len(overridden), "datatype": "Int"},
		{"label": _("Override rate"), "value": round(100 * (len(overridden) - len(agreed)) / base, 1) if base else 0, "datatype": "Percent"},
		{"label": _("Human agreed with AI"), "value": len(agreed), "datatype": "Int"},
	]
	columns = [
		{"fieldname": "name", "label": _("Lead"), "fieldtype": "Link", "options": "CRM Lead", "width": 150},
		{"fieldname": "lead_name", "label": _("Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 100},
		{"fieldname": "pkx_ai_classification", "label": _("AI"), "fieldtype": "Data", "width": 120},
		{"fieldname": "pkx_ai_score", "label": _("AI Score"), "fieldtype": "Int", "width": 80},
		{"fieldname": "pkx_ai_confidence", "label": _("AI Confidence"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "pkx_ai_human_classification", "label": _("Human"), "fieldtype": "Data", "width": 120},
		{"fieldname": "pkx_ai_human_score", "label": _("Human Score"), "fieldtype": "Int", "width": 100},
		{"fieldname": "agreement", "label": _("Agreement"), "fieldtype": "Data", "width": 100},
		{"fieldname": "pkx_ai_override_reason", "label": _("Reason"), "fieldtype": "Data", "width": 220},
		{"fieldname": "pkx_ai_overridden_by", "label": _("By"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "pkx_ai_overridden_on", "label": _("On"), "fieldtype": "Datetime", "width": 150},
	]
	return columns, leads, None, None, report_summary
