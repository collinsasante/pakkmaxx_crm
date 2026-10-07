"""Assignment guard: ordinary sales users cannot hand leads, opportunities or customers to
other people, nor remove existing assignments. Managers can (within their team)."""

import frappe
from frappe import _

from pakkmaxx_crm.utils import GUARDED_DOCTYPES, can_manage_user_records


def _assigned_on_source_lead(todo) -> bool:
	"""Frappe CRM copies the lead's assignees to the new deal during conversion."""
	if todo.reference_type != "CRM Deal":
		return False
	lead = frappe.db.get_value("CRM Deal", todo.reference_name, "lead")
	if not lead:
		return False
	return bool(
		frappe.db.exists(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": lead, "allocated_to": todo.allocated_to,
				"status": ["!=", "Cancelled"]},
		)
	)


def validate_todo(doc, method=None):
	if doc.reference_type not in GUARDED_DOCTYPES or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	user = frappe.session.user
	if user == "Administrator" or doc.get("assignment_rule"):
		return

	if doc.is_new():
		if doc.allocated_to == user or can_manage_user_records(doc.allocated_to):
			return
		if _assigned_on_source_lead(doc):
			return
		owner_field = {"CRM Lead": "lead_owner", "CRM Deal": "deal_owner", "Pakkmaxx Customer": "sales_rep"}[
			doc.reference_type
		]
		# Frappe CRM assigns the record owner automatically when the owner field is set
		if frappe.db.get_value(doc.reference_type, doc.reference_name, owner_field) == doc.allocated_to:
			return
		frappe.throw(_("Only managers can assign {0} records to other users.").format(_(doc.reference_type)),
			frappe.PermissionError)

	if doc.has_value_changed("status") and doc.status == "Cancelled":
		if not can_manage_user_records(doc.allocated_to):
			frappe.throw(_("Only managers can remove an assignment."), frappe.PermissionError)


def on_todo_trash(doc, method=None):
	if doc.reference_type in GUARDED_DOCTYPES and frappe.session.user != "Administrator":
		if not can_manage_user_records(doc.allocated_to):
			frappe.throw(_("Only managers can remove an assignment."), frappe.PermissionError)
