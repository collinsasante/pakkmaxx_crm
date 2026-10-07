# Copyright (c) 2026, Pakkmaxx and contributors
"""Opportunity pipeline in GHS by stage, salesperson, expected close month or source, or in detail."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from pakkmaxx_crm.reporting import deal_rows, ghs, status_types

GROUPS = {"Stage": "status", "Sales Rep": "deal_owner", "Expected Close Month": "close_month", "Source": "source"}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	types = status_types("CRM Deal Status")
	positions = {s.name: s.position for s in frappe.get_all("CRM Deal Status", fields=["name", "position"])}
	deals = deal_rows(filters)
	kind = filters.get("status_type")
	if kind == "Open":
		deals = [d for d in deals if types.get(d.status) not in ("Won", "Lost")]
	elif kind in ("Won", "Lost"):
		deals = [d for d in deals if types.get(d.status) == kind]

	if filters.get("view") == "Detail":
		return _detail(deals)

	group = GROUPS.get(filters.get("view") or "Stage", "status")
	rows = defaultdict(lambda: defaultdict(float))
	for d in deals:
		key = (d.expected_closure_date.strftime("%Y-%m") if d.expected_closure_date else _("Not set")) if group == "close_month" else (d.get(group) or _("Not set"))
		value = ghs(d)
		rows[key]["count"] += 1
		rows[key]["value"] += value
		rows[key]["weighted"] += value * flt(d.probability) / 100
	order = sorted(rows, key=lambda k: positions.get(k, 99)) if group == "status" else sorted(rows, key=lambda k: -rows[k]["value"])
	data = [{"group": k, **rows[k], "average": round(rows[k]["value"] / rows[k]["count"], 2)} for k in order]
	columns = [
		{"fieldname": "group", "label": _(filters.get("view") or "Stage"), "fieldtype": "Data", "width": 180},
		{"fieldname": "count", "label": _("Opportunities"), "fieldtype": "Int", "width": 120},
		{"fieldname": "value", "label": _("Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 150},
		{"fieldname": "weighted", "label": _("Weighted (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 150},
		{"fieldname": "average", "label": _("Average (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 140},
	]
	chart = {"data": {"labels": [d["group"] for d in data], "datasets": [{"name": _("Value (GHS)"), "values": [d["value"] for d in data]}]}, "type": "bar"}
	return columns, data, None, chart


def _detail(deals):
	data = [{**d, "value_ghs": ghs(d), "weighted_ghs": ghs(d) * flt(d.probability) / 100} for d in deals]
	columns = [
		{"fieldname": "name", "label": _("Opportunity"), "fieldtype": "Link", "options": "CRM Deal", "width": 160},
		{"fieldname": "organization", "label": _("Organization"), "fieldtype": "Data", "width": 150},
		{"fieldname": "lead_name", "label": _("Contact"), "fieldtype": "Data", "width": 140},
		{"fieldname": "pkx_customer", "label": _("Customer"), "fieldtype": "Link", "options": "Pakkmaxx Customer", "width": 130},
		{"fieldname": "status", "label": _("Stage"), "fieldtype": "Data", "width": 130},
		{"fieldname": "deal_owner", "label": _("Sales Rep"), "fieldtype": "Link", "options": "User", "width": 160},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 110},
		{"fieldname": "value_ghs", "label": _("Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 130},
		{"fieldname": "probability", "label": _("Probability"), "fieldtype": "Percent", "width": 100},
		{"fieldname": "weighted_ghs", "label": _("Weighted (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 130},
		{"fieldname": "expected_closure_date", "label": _("Expected Close"), "fieldtype": "Date", "width": 120},
		{"fieldname": "pkx_won_on", "label": _("Won On"), "fieldtype": "Datetime", "width": 150},
	]
	return columns, data
