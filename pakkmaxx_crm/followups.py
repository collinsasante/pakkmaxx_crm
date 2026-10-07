"""Follow-ups are CRM Tasks with type "Follow-up" so they live in Frappe CRM's own Tasks tab.

This module adds: reminder times, reminder delivery, completion stamps, the next
follow-up date on the related record and a daily digest.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, get_datetime, getdate, now_datetime, nowdate

from pakkmaxx_crm.events.activity import refresh_next_follow_up, touch_contact
from pakkmaxx_crm.utils import can_assign_records, get_settings

OPEN = ("Backlog", "Todo", "In Progress")
CLOSED = ("Done", "Canceled")


# --- CRM Task doc_events ----------------------------------------------------------


def validate_task(doc, method=None):
	doc.pkx_task_type = doc.pkx_task_type or "Task"
	user = frappe.session.user

	if doc.assigned_to and doc.assigned_to != user and not doc.flags.get("pkx_system_update"):
		previous = None if doc.is_new() else doc.get_doc_before_save().assigned_to
		if (doc.is_new() or doc.assigned_to != previous) and not can_assign_records(user):
			frappe.throw(_("Only managers can assign tasks or follow-ups to someone else."), frappe.PermissionError)
	if doc.is_new() and not doc.assigned_to:
		doc.assigned_to = user

	if doc.pkx_task_type == "Follow-up":
		if not doc.due_date:
			frappe.throw(_("A follow-up needs a date and time."), title=_("Follow-up date required"))
		doc.pkx_follow_up_reason = doc.pkx_follow_up_reason or doc.title

	if doc.due_date and not doc.pkx_remind_at:
		minutes = cint(get_settings().default_reminder_minutes)
		doc.pkx_remind_at = add_to_date(doc.due_date, minutes=-minutes)
	if not doc.is_new() and (doc.has_value_changed("pkx_remind_at") or doc.has_value_changed("due_date")):
		doc.pkx_reminder_sent = 0

	if doc.status == "Done" and not doc.pkx_completed_on:
		doc.pkx_completed_on = now_datetime()
	elif doc.status != "Done":
		doc.pkx_completed_on = None


def on_task_change(doc, method=None):
	refresh_next_follow_up(doc.reference_doctype, doc.reference_docname)
	if doc.has_value_changed("status") and doc.status == "Done" and doc.pkx_task_type == "Follow-up":
		touch_contact(doc.reference_doctype, doc.reference_docname, doc.pkx_completed_on)


def on_task_delete(doc, method=None):
	refresh_next_follow_up(doc.reference_doctype, doc.reference_docname)


# --- reminders --------------------------------------------------------------------


def _reference_label(task) -> str:
	if not task.reference_doctype or not task.reference_docname:
		return ""
	title_field = {"CRM Lead": "lead_name", "CRM Deal": "organization", "Pakkmaxx Customer": "customer_name"}.get(
		task.reference_doctype
	)
	title = frappe.db.get_value(task.reference_doctype, task.reference_docname, title_field) if title_field else None
	return f"{title or task.reference_docname}"


def notify(user: str, task, subject: str):
	"""Bell notification in both the CRM app and Desk."""
	frappe.get_doc(
		{
			"doctype": "CRM Notification",
			"from_user": "Administrator",
			"to_user": user,
			"type": "Task",
			"message": f"<div>{frappe.utils.escape_html(subject)}</div>",
			"notification_text": subject,
			"notification_type_doctype": "CRM Task",
			"notification_type_doc": task.name,
			"reference_doctype": task.reference_doctype,
			"reference_name": task.reference_docname,
		}
	).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": user,
			"type": "Alert",
			"subject": subject,
			"document_type": task.reference_doctype or "CRM Task",
			"document_name": task.reference_docname or task.name,
			"from_user": "Administrator",
		}
	).insert(ignore_permissions=True)


def send_due_reminders():
	"""Cron (every 5 min): remind the assignee when a task's reminder time arrives."""
	tasks = frappe.get_all(
		"CRM Task",
		filters={
			"status": ["in", OPEN],
			"pkx_reminder_sent": 0,
			"pkx_remind_at": ["<=", now_datetime()],
			"assigned_to": ["is", "set"],
		},
		fields=["name", "title", "assigned_to", "due_date", "pkx_task_type", "reference_doctype",
			"reference_docname"],
		limit=500,
	)
	for task in tasks:
		label = _reference_label(task)
		kind = _("Follow-up") if task.pkx_task_type == "Follow-up" else _("Task")
		when = frappe.utils.format_datetime(task.due_date, "dd MMM HH:mm") if task.due_date else ""
		subject = f"{kind}: {task.title}" + (f" - {label}" if label else "") + (f" (due {when})" if when else "")
		notify(task.assigned_to, task, subject)
		frappe.db.set_value("CRM Task", task.name, "pkx_reminder_sent", 1, update_modified=False)
	frappe.db.commit()


def get_follow_up_buckets(user: str | None = None, follow_ups_only: bool = True) -> dict:
	"""Overdue / today / upcoming (7 days) open follow-ups visible to the user."""
	now = now_datetime()
	today_end = get_datetime(f"{nowdate()} 23:59:59")
	week_end = get_datetime(f"{add_days(nowdate(), 7)} 23:59:59")
	filters = {"status": ["in", OPEN], "due_date": ["is", "set"]}
	if follow_ups_only:
		filters["pkx_task_type"] = "Follow-up"
	if user:
		filters["assigned_to"] = user
	fields = ["name", "title", "due_date", "priority", "assigned_to", "pkx_follow_up_reason",
		"reference_doctype", "reference_docname", "status"]
	common = dict(fields=fields, order_by="due_date asc", limit=200)
	return {
		"overdue": frappe.get_list("CRM Task", filters={**filters, "due_date": ["<", now]}, **common),
		"today": frappe.get_list("CRM Task", filters={**filters, "due_date": ["between", [now, today_end]]},
			**common),
		"upcoming": frappe.get_list(
			"CRM Task", filters={**filters, "due_date": ["between", [today_end, week_end]]}, **common
		),
	}


def send_daily_digest():
	"""Daily (morning): each user gets one notification summarising their follow-ups."""
	if not cint(get_settings().send_daily_digest):
		return
	users = frappe.get_all(
		"CRM Task",
		filters={"status": ["in", OPEN], "due_date": ["<=", get_datetime(f"{nowdate()} 23:59:59")],
			"assigned_to": ["is", "set"]},
		pluck="assigned_to",
		distinct=True,
	)
	uncontacted_hours = cint(get_settings().uncontacted_alert_hours or 24)
	cutoff = add_to_date(now_datetime(), hours=-uncontacted_hours)
	for user in set(users) | set(
		frappe.get_all("CRM Lead", filters={"status": "New", "creation": ["<", cutoff], "lead_owner": ["is", "set"]},
			pluck="lead_owner", distinct=True)
	):
		if not frappe.db.get_value("User", user, "enabled"):
			continue
		overdue = frappe.db.count("CRM Task", {"assigned_to": user, "status": ["in", OPEN],
			"due_date": ["<", now_datetime()]})
		today = frappe.db.count("CRM Task", {"assigned_to": user, "status": ["in", OPEN],
			"due_date": ["between", [now_datetime(), get_datetime(f"{nowdate()} 23:59:59")]]})
		uncontacted = frappe.db.count("CRM Lead", {"lead_owner": user, "status": "New", "creation": ["<", cutoff]})
		if not (overdue or today or uncontacted):
			continue
		subject = _("Today: {0} follow-ups due, {1} overdue, {2} leads not yet contacted").format(
			today, overdue, uncontacted
		)
		frappe.get_doc(
			{"doctype": "Notification Log", "for_user": user, "type": "Alert", "subject": subject,
				"document_type": "CRM Task", "from_user": "Administrator"}
		).insert(ignore_permissions=True)
	frappe.db.commit()
