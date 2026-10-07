# Copyright (c) 2026, Pakkmaxx and contributors
"""Follow-ups by urgency: overdue, today, upcoming, or completed (with on-time rate)."""

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, now_datetime, nowdate

OPEN = ["Backlog", "Todo", "In Progress"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	bucket = filters.get("bucket") or "Overdue"
	now = now_datetime()
	end_today = get_datetime(f"{nowdate()} 23:59:59")
	f = {}
	if not filters.get("include_tasks"):
		f["pkx_task_type"] = "Follow-up"
	if filters.get("assigned_to"):
		f["assigned_to"] = filters.assigned_to
	if bucket == "Overdue":
		f.update({"status": ["in", OPEN], "due_date": ["<", now]})
	elif bucket == "Today":
		f.update({"status": ["in", OPEN], "due_date": ["between", [now, end_today]]})
	elif bucket == "Upcoming":
		f.update({"status": ["in", OPEN], "due_date": ["between", [end_today, get_datetime(f"{add_days(nowdate(), 7)} 23:59:59")]]})
	elif bucket == "Completed":
		f["status"] = "Done"
	rows = frappe.get_list(
		"CRM Task",
		filters=f,
		fields=["name", "title", "pkx_follow_up_reason", "priority", "status", "due_date", "assigned_to",
			"reference_doctype", "reference_docname", "pkx_completed_on", "pkx_outcome"],
		order_by="due_date asc",
		limit_page_length=0,
	)
	for r in rows:
		r["on_time"] = 1 if r.pkx_completed_on and r.due_date and r.pkx_completed_on <= r.due_date else 0
		r["overdue_hours"] = (
			round((now - r.due_date).total_seconds() / 3600, 1) if r.due_date and r.status in OPEN and r.due_date < now else 0
		)
	columns = [
		{"fieldname": "name", "label": _("Task"), "fieldtype": "Link", "options": "CRM Task", "width": 80},
		{"fieldname": "title", "label": _("Follow-up"), "fieldtype": "Data", "width": 220},
		{"fieldname": "reference_doctype", "label": _("For"), "fieldtype": "Link", "options": "DocType", "width": 120},
		{"fieldname": "reference_docname", "label": _("Record"), "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 170},
		{"fieldname": "assigned_to", "label": _("Assigned To"), "fieldtype": "Link", "options": "User", "width": 170},
		{"fieldname": "priority", "label": _("Priority"), "fieldtype": "Data", "width": 80},
		{"fieldname": "due_date", "label": _("Due"), "fieldtype": "Datetime", "width": 160},
		{"fieldname": "overdue_hours", "label": _("Overdue (h)"), "fieldtype": "Float", "width": 100},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
	]
	if bucket == "Completed":
		columns += [
			{"fieldname": "pkx_completed_on", "label": _("Completed"), "fieldtype": "Datetime", "width": 160},
			{"fieldname": "on_time", "label": _("On Time"), "fieldtype": "Check", "width": 80},
			{"fieldname": "pkx_outcome", "label": _("Outcome"), "fieldtype": "Data", "width": 200},
		]
	return columns, rows
