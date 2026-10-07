import frappe
from frappe import _

from pakkmaxx_crm.api import require
from pakkmaxx_crm.followups import get_follow_up_buckets
from pakkmaxx_crm.utils import can_assign_records


@frappe.whitelist(methods=["POST"])
def create_follow_up(
	reference_doctype: str,
	reference_name: str,
	reason: str,
	due: str,
	priority: str = "Medium",
	notes: str | None = None,
	assigned_to: str | None = None,
	remind_at: str | None = None,
) -> str:
	"""Create a follow-up (a CRM Task of type Follow-up) on a lead, opportunity or customer."""
	require(reference_doctype, reference_name, "read")
	if assigned_to and assigned_to != frappe.session.user and not can_assign_records():
		frappe.throw(_("Only managers can assign follow-ups to someone else."), frappe.PermissionError)
	if priority not in ("Low", "Medium", "High"):
		frappe.throw(_("Invalid priority"))
	task = frappe.get_doc(
		{
			"doctype": "CRM Task",
			"title": reason,
			"pkx_task_type": "Follow-up",
			"pkx_follow_up_reason": reason,
			"description": frappe.utils.escape_html(notes or ""),
			"priority": priority,
			"status": "Todo",
			"due_date": due,
			"pkx_remind_at": remind_at,
			"assigned_to": assigned_to or frappe.session.user,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_name,
		}
	)
	task.insert()
	if reference_doctype == "CRM Lead" and frappe.has_permission("CRM Lead", "write", reference_name):
		frappe.db.set_value("CRM Lead", reference_name, "pkx_next_action", reason[:140])
	return task.name


@frappe.whitelist(methods=["POST"])
def complete_follow_up(task: str, outcome: str | None = None) -> str:
	doc = frappe.get_doc("CRM Task", task)
	doc.check_permission("write")
	doc.status = "Done"
	if outcome:
		doc.pkx_outcome = outcome
	doc.save()
	return doc.name


@frappe.whitelist()
def my_follow_ups(include_tasks: bool = False) -> dict:
	"""Overdue, today's and next-7-days follow-ups assigned to the current user."""
	return get_follow_up_buckets(frappe.session.user, follow_ups_only=not frappe.utils.sbool(include_tasks))
