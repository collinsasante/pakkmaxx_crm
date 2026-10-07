# Copyright (c) 2026, Pakkmaxx and contributors
"""Leads grouped by source, status, salesperson, business type, lifecycle or period."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import getdate

from pakkmaxx_crm.reporting import lead_rows

GROUPS = {
	"Source": "source",
	"Status": "status",
	"Sales Rep": "lead_owner",
	"Business Type": "pkx_business_type",
	"Lifecycle Stage": "pkx_lifecycle_stage",
	"Month": "month",
	"Week": "week",
	"Day": "day",
}


def _key(lead, group):
	if group in ("month", "week", "day"):
		d = getdate(lead.creation)
		if group == "month":
			return d.strftime("%Y-%m")
		if group == "week":
			return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
		return d.isoformat()
	return lead.get(group) or _("Not set")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group = GROUPS.get(filters.get("group_by") or "Source", "source")
	leads = lead_rows(filters)
	if filters.get("only_unqualified_or_lost"):
		leads = [l for l in leads if l.status in ("Unqualified", "Lost")]
	counts = Counter(_key(l, group) for l in leads)
	converted = Counter(_key(l, group) for l in leads if l.converted)
	customers = Counter(_key(l, group) for l in leads if l.pkx_customer)
	order = sorted(counts) if group in ("month", "week", "day") else [k for k, _n in counts.most_common()]
	data = [
		{"group": k, "leads": counts[k], "converted": converted[k], "customers": customers[k],
			"conversion": round(100 * customers[k] / counts[k], 1) if counts[k] else 0}
		for k in order
	]
	columns = [
		{"fieldname": "group", "label": _(filters.get("group_by") or "Source"), "fieldtype": "Data", "width": 180},
		{"fieldname": "leads", "label": _("Leads"), "fieldtype": "Int", "width": 90},
		{"fieldname": "converted", "label": _("Converted to Opportunity"), "fieldtype": "Int", "width": 180},
		{"fieldname": "customers", "label": _("Became Customers"), "fieldtype": "Int", "width": 150},
		{"fieldname": "conversion", "label": _("Lead → Customer %"), "fieldtype": "Percent", "width": 140},
	]
	chart = {
		"data": {"labels": [d["group"] for d in data[:30]], "datasets": [{"name": _("Leads"), "values": [d["leads"] for d in data[:30]]}]},
		"type": "line" if group in ("month", "week", "day") else "bar",
	}
	return columns, data, None, chart
