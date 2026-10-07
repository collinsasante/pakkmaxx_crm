"""Contact tracking: every logged interaction updates first/last contacted dates on the
lead, opportunity and customer, and moves a New lead to Contacted."""

import frappe
from frappe.utils import get_datetime, now_datetime

from pakkmaxx_crm.customers import next_follow_up_for, recompute_customer

TRACKED = ("CRM Lead", "CRM Deal", "Pakkmaxx Customer")
CONTACT_NOTE_TYPES = ("WhatsApp Conversation", "Meeting", "Call Summary", "Follow-up")


def touch_contact(reference_doctype: str | None, reference_name: str | None, when=None):
	if reference_doctype not in TRACKED or not reference_name:
		return
	if not frappe.db.exists(reference_doctype, reference_name):
		return
	when = get_datetime(when or now_datetime())

	if reference_doctype == "Pakkmaxx Customer":
		frappe.db.set_value("Pakkmaxx Customer", reference_name, "last_activity_on", when, update_modified=False)
		recompute_customer(reference_name)
		return

	first, last = frappe.db.get_value(
		reference_doctype, reference_name, ["pkx_first_contacted_on", "pkx_last_contacted_on"]
	)
	values = {"pkx_last_contacted_on": max(get_datetime(last), when) if last else when}
	if not first or get_datetime(first) > when:
		values["pkx_first_contacted_on"] = when
	frappe.db.set_value(reference_doctype, reference_name, values, update_modified=False)

	if reference_doctype == "CRM Lead":
		_advance_new_lead(reference_name)
	else:
		customer, lead = frappe.db.get_value("CRM Deal", reference_name, ["pkx_customer", "lead"])
		if customer:
			recompute_customer(customer)


def _advance_new_lead(name: str):
	"""First real contact moves a New lead to Contacted (through the workflow)."""
	if frappe.db.get_value("CRM Lead", name, "status") != "New":
		return
	lead = frappe.get_doc("CRM Lead", name)
	lead.status = "Contacted"
	lead.flags.pkx_system_update = True
	lead.flags.pkx_skip_duplicate_check = True
	try:
		lead.save(ignore_permissions=True)
	except frappe.ValidationError:
		# the workflow may have been reconfigured; contact dates are still recorded
		frappe.clear_last_message()


def refresh_next_follow_up(reference_doctype: str | None, reference_name: str | None):
	if reference_doctype not in TRACKED or not reference_name:
		return
	if not frappe.db.exists(reference_doctype, reference_name):
		return
	if reference_doctype == "Pakkmaxx Customer":
		recompute_customer(reference_name)
		return
	frappe.db.set_value(
		reference_doctype,
		reference_name,
		"pkx_next_follow_up_on",
		next_follow_up_for(reference_doctype, reference_name),
		update_modified=False,
	)
	if reference_doctype == "CRM Deal":
		customer = frappe.db.get_value("CRM Deal", reference_name, "pkx_customer")
		if customer:
			recompute_customer(customer)


# --- doc_events --------------------------------------------------------------


def on_note_insert(doc, method=None):
	if doc.get("pkx_note_type") in CONTACT_NOTE_TYPES:
		touch_contact(doc.reference_doctype, doc.reference_docname, doc.get("pkx_interaction_at"))


def on_call_log_update(doc, method=None):
	if doc.status in ("Completed", "In Progress") or doc.telephony_medium == "Manual":
		touch_contact(doc.reference_doctype, doc.reference_docname, doc.start_time or doc.creation)


def on_communication_insert(doc, method=None):
	if doc.communication_type != "Communication":
		return
	touch_contact(doc.reference_doctype, doc.reference_name, doc.communication_date)


def on_whatsapp_message_update(doc, method=None):
	"""Hook for the optional frappe_whatsapp integration (WhatsApp Message doctype)."""
	touch_contact(doc.get("reference_doctype"), doc.get("reference_name"), doc.get("creation"))
