# Copyright (c) 2026, Pakkmaxx and contributors
"""Where do Pakkmaxx's customers come from? Source -> lead -> qualified -> opportunity -> won -> customer."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from pakkmaxx_crm.reporting import WON, deal_rows, ghs, lead_rows, status_types


METRICS = ("leads", "contacted", "qualified", "opportunities", "won", "customers", "pipeline_value", "won_value")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group = {"Campaign": "pkx_campaign", "Sales Rep": "lead_owner"}.get(filters.get("group_by"), "source")
	deal_types = status_types("CRM Deal Status")
	leads = lead_rows(filters)
	deals_by_lead = defaultdict(list)
	for d in deal_rows(extra={"lead": ["is", "set"]}):
		deals_by_lead[d.lead].append(d)

	rows = defaultdict(lambda: defaultdict(float))
	for lead in leads:
		key = lead.get(group) or _("Not set")
		r = rows[key]
		r["leads"] += 1
		if lead.pkx_first_contacted_on or lead.status != "New":
			r["contacted"] += 1
		if lead.converted or lead.status in ("Qualified", "Proposal/Quote Requested", "Negotiation"):
			r["qualified"] += 1
		deals = deals_by_lead.get(lead.name, [])
		r["opportunities"] += len(deals)
		for d in deals:
			r["pipeline_value"] += ghs(d)
			if deal_types.get(d.status) == WON:
				r["won"] += 1
				r["won_value"] += ghs(d)
		if lead.pkx_customer:
			r["customers"] += 1

	data = []
	for key, r in sorted(rows.items(), key=lambda kv: -kv[1]["won_value"]):
		leads_n = r["leads"] or 1
		data.append(
			{
				"group": key,
				**{k: r[k] for k in METRICS},
				"lead_to_customer": round(100 * r["customers"] / leads_n, 1),
				"won_per_lead": round(flt(r["won_value"]) / leads_n, 2),
			}
		)

	label = {"source": _("Source"), "pkx_campaign": _("Campaign"), "lead_owner": _("Sales Rep")}[group]
	columns = [
		{"fieldname": "group", "label": label, "fieldtype": "Data", "width": 160},
		{"fieldname": "leads", "label": _("Leads"), "fieldtype": "Int", "width": 80},
		{"fieldname": "contacted", "label": _("Contacted"), "fieldtype": "Int", "width": 95},
		{"fieldname": "qualified", "label": _("Qualified"), "fieldtype": "Int", "width": 90},
		{"fieldname": "opportunities", "label": _("Opportunities"), "fieldtype": "Int", "width": 110},
		{"fieldname": "won", "label": _("Won"), "fieldtype": "Int", "width": 70},
		{"fieldname": "customers", "label": _("Customers"), "fieldtype": "Int", "width": 95},
		{"fieldname": "lead_to_customer", "label": _("Lead → Customer %"), "fieldtype": "Percent", "width": 130},
		{"fieldname": "pipeline_value", "label": _("Opportunity Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 170},
		{"fieldname": "won_value", "label": _("Won Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 150},
		{"fieldname": "won_per_lead", "label": _("Won Value per Lead"), "fieldtype": "Currency", "options": "GHS", "width": 150},
	]
	chart = {
		"data": {
			"labels": [d["group"] for d in data[:12]],
			"datasets": [
				{"name": _("Leads"), "values": [d["leads"] for d in data[:12]]},
				{"name": _("Customers"), "values": [d["customers"] for d in data[:12]]},
			],
		},
		"type": "bar",
	}
	return columns, data, None, chart
