import frappe
from frappe import _

from pakkmaxx_crm.utils import can_assign_records, can_manage_user_records, is_crm_manager


def is_system_update(doc) -> bool:
	"""Changes made by Pakkmaxx's own server logic (not by a user's form submission)."""
	return bool(doc.flags.get("pkx_system_update") or frappe.flags.in_install or frappe.flags.in_migrate)


def protect_fields(doc, fieldnames):
	"""Ignore client-supplied values for server-computed fields.

	New documents start empty; existing documents keep their stored value.
	"""
	if is_system_update(doc):
		return
	before = doc.get_doc_before_save() if not doc.is_new() else None
	for fieldname in fieldnames:
		if not doc.meta.has_field(fieldname):
			continue
		original = before.get(fieldname) if before else None
		if doc.get(fieldname) != original:
			doc.set(fieldname, original)


def guard_owner_field(doc, fieldname: str, label: str):
	"""Only managers may hand a record to someone else or take it away from its owner."""
	if is_system_update(doc):
		return
	user = frappe.session.user
	new_owner = doc.get(fieldname)

	if doc.is_new():
		if not new_owner:
			# a rep's new record is theirs; managers may leave it unassigned for distribution
			if not can_assign_records(user):
				doc.set(fieldname, user)
			return
		if new_owner != user and not can_manage_user_records(new_owner):
			frappe.throw(
				_("You are not allowed to set the {0} to another user.").format(label),
				frappe.PermissionError,
			)
		return

	if not doc.has_value_changed(fieldname):
		return
	old_owner = doc.get_doc_before_save().get(fieldname)
	if not (can_manage_user_records(new_owner) and can_manage_user_records(old_owner)):
		frappe.throw(
			_("Only a CRM Manager or the team's Sales Manager can change the {0}.").format(label),
			frappe.PermissionError,
		)


def require_manager(message: str):
	if not is_crm_manager():
		frappe.throw(message, frappe.PermissionError)


def status_type(doctype: str, status: str | None) -> str | None:
	if not status:
		return None
	return frappe.get_cached_value(doctype, status, "type")


def add_info_comment(doctype: str, name: str, text: str):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": text,
		}
	).insert(ignore_permissions=True)
