# Copyright (c) 2026, Pakkmaxx and contributors
"""Per salesperson: leads, contact & qualification, opportunities, win rate, value, follow-up discipline."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, now_datetime

from pakkmaxx_crm.reporting import LOST, WON, date_filter, deal_rows, ghs, lead_rows, status_types


METRICS = ("leads", "contacted", "qualified", "unqualified", "lost_leads", "customers", "opportunities", "won",
	"lost", "won_value", "pipeline_value", "follow_ups_due", "follow_ups_done", "follow_ups_on_time")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	lead_types = status_types("CRM Lead Status")
	deal_types = status_types("CRM Deal Status")
	rows = defaultdict(lambda: defaultdict(float))
	conv_days = defaultdict(list)

	for l in lead_rows(filters):
		rep = l.lead_owner or _("Unassigned")
		r = rows[rep]
		r["leads"] += 1
		if l.pkx_first_contacted_on or l.status != "New":
			r["contacted"] += 1
		if l.converted or l.status in ("Qualified", "Proposal/Quote Requested", "Negotiation"):
			r["qualified"] += 1
		if l.status == "Unqualified":
			r["unqualified"] += 1
		elif lead_types.get(l.status) == LOST:
			r["lost_leads"] += 1
		if l.pkx_customer:
			r["customers"] += 1

	for d in deal_rows(filters):
		rep = d.deal_owner or _("Unassigned")
		r = rows[rep]
		r["opportunities"] += 1
		kind = deal_types.get(d.status)
		if kind == WON:
			r["won"] += 1
			r["won_value"] += ghs(d)
			if d.pkx_won_on:
				conv_days[rep].append(date_diff(d.pkx_won_on, d.creation))
		elif kind == LOST:
			r["lost"] += 1
		else:
			r["pipeline_value"] += ghs(d)

	task_filters = {"pkx_task_type": "Follow-up", **date_filter(filters, "due_date")}
	for t in frappe.get_list("CRM Task", filters=task_filters,
			fields=["assigned_to", "status", "due_date", "pkx_completed_on"], limit_page_length=0):
		if not t.due_date or (t.due_date > now_datetime() and t.status != "Done"):
			continue  # not yet due
		r = rows[t.assigned_to or _("Unassigned")]
		r["follow_ups_due"] += 1
		if t.status == "Done":
			r["follow_ups_done"] += 1
			if t.pkx_completed_on and t.pkx_completed_on <= t.due_date:
				r["follow_ups_on_time"] += 1

	if filters.get("sales_rep"):
		rows = {k: v for k, v in rows.items() if k == filters.sales_rep}

	data = []
	for rep, r in sorted(rows.items(), key=lambda kv: -kv[1]["won_value"]):
		closed = r["won"] + r["lost"]
		data.append({
			"sales_rep": rep, **{k: r[k] for k in METRICS},
			"contact_rate": round(100 * r["contacted"] / r["leads"], 1) if r["leads"] else 0,
			"lead_conversion": round(100 * r["customers"] / r["leads"], 1) if r["leads"] else 0,
			"win_rate": round(100 * r["won"] / closed, 1) if closed else 0,
			"follow_up_completion": round(100 * r["follow_ups_done"] / r["follow_ups_due"], 1) if r["follow_ups_due"] else 0,
			"avg_days_to_win": round(sum(conv_days[rep]) / len(conv_days[rep]), 1) if conv_days[rep] else None,
		})

	def col(fieldname, label, fieldtype="Int", width=100, **kw):
		return {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width, **kw}

	columns = [
		col("sales_rep", "Sales Rep", "Data", 180),
		col("leads", "Leads"), col("contacted", "Contacted"), col("contact_rate", "Contact %", "Percent"),
		col("qualified", "Qualified"), col("unqualified", "Unqualified"), col("lost_leads", "Lost Leads"),
		col("opportunities", "Opportunities", width=110), col("won", "Won"), col("lost", "Lost"),
		col("win_rate", "Win Rate", "Percent"),
		col("won_value", "Won Value (GHS)", "Currency", 140, options="GHS"),
		col("pipeline_value", "Open Pipeline (GHS)", "Currency", 150, options="GHS"),
		col("customers", "Customers"), col("lead_conversion", "Lead → Customer %", "Percent", 140),
		col("follow_ups_due", "Follow-ups Due", width=120), col("follow_ups_done", "Done"),
		col("follow_up_completion", "Follow-up Completion %", "Percent", 170),
		col("avg_days_to_win", "Avg Days to Win", "Float", 130),
	]
	chart = {"data": {"labels": [d["sales_rep"] for d in data], "datasets": [{"name": _("Won Value (GHS)"), "values": [flt(d["won_value"]) for d in data]}]}, "type": "bar"}
	return columns, data, None, chart
