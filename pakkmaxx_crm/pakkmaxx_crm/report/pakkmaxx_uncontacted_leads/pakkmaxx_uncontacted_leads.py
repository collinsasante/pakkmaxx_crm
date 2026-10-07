# Copyright (c) 2026, Pakkmaxx and contributors
"""New leads nobody has contacted yet, oldest first."""

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_hours

from pakkmaxx_crm.reporting import lead_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	leads = lead_rows(
		filters,
		fields=["name", "lead_name", "mobile_no", "pkx_whatsapp_no", "source", "lead_owner", "creation",
			"lead_score", "lead_temperature"],
		extra={"status": "New", "pkx_first_contacted_on": ["is", "not set"]},
	)
	now = now_datetime()
	data = []
	for l in sorted(leads, key=lambda x: x.creation):
		hours = round(time_diff_in_hours(now, l.creation), 1)
		if filters.get("older_than_hours") and hours < float(filters.older_than_hours):
			continue
		data.append({**l, "waiting_hours": hours, "lead_owner": l.lead_owner or _("Unassigned")})
	columns = [
		{"fieldname": "name", "label": _("Lead"), "fieldtype": "Link", "options": "CRM Lead", "width": 160},
		{"fieldname": "lead_name", "label": _("Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "pkx_whatsapp_no", "label": _("WhatsApp"), "fieldtype": "Data", "width": 140},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 110},
		{"fieldname": "lead_owner", "label": _("Owner"), "fieldtype": "Data", "width": 160},
		{"fieldname": "lead_temperature", "label": _("Temperature"), "fieldtype": "Data", "width": 100},
		{"fieldname": "waiting_hours", "label": _("Waiting (hours)"), "fieldtype": "Float", "width": 120},
		{"fieldname": "creation", "label": _("Created"), "fieldtype": "Datetime", "width": 160},
	]
	return columns, data
