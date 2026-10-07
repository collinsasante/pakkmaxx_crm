# Copyright (c) 2026, Pakkmaxx and contributors
"""Customers: new, active, repeat, dormant; by source or segment."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, nowdate

from pakkmaxx_crm.reporting import date_filter


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {"disabled": 0, **date_filter(filters, "first_won_on")}
	for key in ("lifecycle_stage", "source", "sales_rep", "customer_type"):
		if filters.get(key):
			f[key] = filters.get(key)
	customers = frappe.get_list(
		"Pakkmaxx Customer",
		filters=f,
		fields=["name", "customer_name", "customer_type", "lifecycle_stage", "source", "sales_rep", "whatsapp_no",
			"city", "first_won_on", "last_won_on", "won_deals_count", "lifetime_value", "last_activity_on",
			"days_to_convert"],
		order_by="lifetime_value desc",
		limit_page_length=0,
	)
	if filters.get("segment"):
		allowed = set(frappe.get_all("Pakkmaxx Customer Segment Item",
			filters={"segment": filters.segment, "parenttype": "Pakkmaxx Customer"}, pluck="parent"))
		customers = [c for c in customers if c.name in allowed]

	group = {"Source": "source", "Lifecycle Stage": "lifecycle_stage", "Sales Rep": "sales_rep",
		"Segment": "segment"}.get(filters.get("group_by"))
	if group:
		return _grouped(customers, group, filters.group_by)

	for c in customers:
		reference = c.last_activity_on or c.last_won_on
		c["days_inactive"] = date_diff(nowdate(), reference) if reference else None
	columns = [
		{"fieldname": "name", "label": _("Customer"), "fieldtype": "Link", "options": "Pakkmaxx Customer", "width": 130},
		{"fieldname": "customer_name", "label": _("Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "customer_type", "label": _("Type"), "fieldtype": "Data", "width": 90},
		{"fieldname": "lifecycle_stage", "label": _("Lifecycle"), "fieldtype": "Data", "width": 130},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 110},
		{"fieldname": "sales_rep", "label": _("Sales Rep"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "whatsapp_no", "label": _("WhatsApp"), "fieldtype": "Data", "width": 130},
		{"fieldname": "won_deals_count", "label": _("Won"), "fieldtype": "Int", "width": 60},
		{"fieldname": "lifetime_value", "label": _("Lifetime Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 150},
		{"fieldname": "first_won_on", "label": _("Customer Since"), "fieldtype": "Date", "width": 110},
		{"fieldname": "last_won_on", "label": _("Last Won"), "fieldtype": "Date", "width": 110},
		{"fieldname": "days_inactive", "label": _("Days Inactive"), "fieldtype": "Int", "width": 110},
		{"fieldname": "days_to_convert", "label": _("Days to Convert"), "fieldtype": "Int", "width": 120},
	]
	return columns, customers


def _grouped(customers, group, label):
	rows = defaultdict(lambda: {"customers": 0, "value": 0.0, "repeat": 0, "dormant": 0})
	segments = defaultdict(list)
	if group == "segment":
		for s in frappe.get_all("Pakkmaxx Customer Segment Item", filters={"parenttype": "Pakkmaxx Customer"},
				fields=["parent", "segment"]):
			segments[s.parent].append(s.segment)
	for c in customers:
		if group == "segment":
			keys = segments.get(c.name) or [_("Not set")]
		else:
			keys = [c.get(group) or _("Not set")]
		for key in keys:
			r = rows[key]
			r["customers"] += 1
			r["value"] += c.lifetime_value or 0
			r["repeat"] += 1 if c.lifecycle_stage == "Repeat Customer" else 0
			r["dormant"] += 1 if c.lifecycle_stage == "Dormant" else 0
	data = [{"group": k, **v} for k, v in sorted(rows.items(), key=lambda kv: -kv[1]["value"])]
	columns = [
		{"fieldname": "group", "label": _(label), "fieldtype": "Data", "width": 180},
		{"fieldname": "customers", "label": _("Customers"), "fieldtype": "Int", "width": 100},
		{"fieldname": "repeat", "label": _("Repeat"), "fieldtype": "Int", "width": 90},
		{"fieldname": "dormant", "label": _("Dormant"), "fieldtype": "Int", "width": 90},
		{"fieldname": "value", "label": _("Lifetime Value (GHS)"), "fieldtype": "Currency", "options": "GHS", "width": 170},
	]
	chart = {"data": {"labels": [d["group"] for d in data], "datasets": [{"name": _("Customers"), "values": [d["customers"] for d in data]}]}, "type": "pie"}
	return columns, data, None, chart
