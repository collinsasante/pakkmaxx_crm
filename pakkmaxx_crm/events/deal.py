import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from pakkmaxx_crm.customers import deal_status_type, ensure_customer_for_deal, recompute_customer
from pakkmaxx_crm.events.common import (
	add_info_comment,
	guard_owner_field,
	is_system_update,
	protect_fields,
	revoke_previous_owner,
)
from pakkmaxx_crm.events.lead import normalize_contact_fields
from pakkmaxx_crm.setup.custom_fields import COMPUTED_DEAL_FIELDS
from pakkmaxx_crm.utils import can_assign_records

NON_NEGATIVE = ("deal_value", "expected_deal_value", "pkx_deal_volume_cbm", "pkx_deal_weight_kg")


def before_validate(doc, method=None):
	# before Frappe CRM's validate, which assigns/shares on an owner change
	guard_owner_field(doc, "deal_owner", _("Deal Owner"))


def validate(doc, method=None):
	normalize_contact_fields(doc)
	protect_fields(doc, COMPUTED_DEAL_FIELDS)
	if doc.is_new() and doc.get("lead"):
		# contact history carries over from the lead (read from the database, not the client)
		doc.update(
			frappe.db.get_value(
				"CRM Lead", doc.lead, ["pkx_first_contacted_on", "pkx_last_contacted_on"], as_dict=True
			)
			or {}
		)
	validate_customer_link(doc)

	for field in NON_NEGATIVE:
		if flt(doc.get(field)) < 0:
			frappe.throw(_("{0} cannot be negative").format(_(doc.meta.get_label(field))))

	if doc.is_new() or doc.has_value_changed("status"):
		validate_stage_change(doc)

	doc.probability = max(0.0, min(100.0, flt(doc.probability)))
	doc.pkx_weighted_value = flt(doc.deal_value) * flt(doc.probability) / 100.0


def validate_customer_link(doc):
	"""A user may only attach an opportunity to a customer they are allowed to see."""
	if not doc.get("pkx_customer") or not (doc.is_new() or doc.has_value_changed("pkx_customer")):
		return
	if is_system_update(doc):
		return
	if not frappe.has_permission("Pakkmaxx Customer", "read", doc.pkx_customer):
		frappe.throw(_("You do not have access to customer {0}").format(doc.pkx_customer), frappe.PermissionError)
	customer = frappe.db.get_value(
		"Pakkmaxx Customer",
		doc.pkx_customer,
		["contact", "organization", "mobile_no", "whatsapp_no", "email", "source", "customer_name"],
		as_dict=True,
	)
	if customer.contact and not doc.get("contacts"):
		doc.append("contacts", {"contact": customer.contact, "is_primary": 1})
	for target, source in (("organization", "organization"), ("mobile_no", "mobile_no"),
			("pkx_whatsapp_no", "whatsapp_no"), ("email", "email")):
		if not doc.get(target) and customer.get(source):
			doc.set(target, customer.get(source))
	if not doc.get("source"):
		doc.source = "Existing Customer" if frappe.db.exists("CRM Lead Source", "Existing Customer") else customer.source


def validate_stage_change(doc):
	new_type = deal_status_type(doc.status)
	old_status = None if doc.is_new() else doc.get_doc_before_save().status
	old_type = deal_status_type(old_status)

	if old_type in ("Won", "Lost") and new_type not in ("Won", "Lost") and not is_system_update(doc):
		if not can_assign_records():
			frappe.throw(
				_("Only a manager can reopen a {0} opportunity.").format(_(old_status)), frappe.PermissionError
			)

	# Probability follows the pipeline stage; the browser's value is not trusted on a stage change.
	if old_status != doc.status:
		doc.probability = flt(frappe.get_cached_value("CRM Deal Status", doc.status, "probability"))

	if new_type == "Won":
		if flt(doc.deal_value) <= 0:
			frappe.throw(_("Enter the deal value (GHS) before marking the opportunity Won."),
				title=_("Deal value required"))
		doc.pkx_won_on = doc.pkx_won_on or now_datetime()
		doc.pkx_lost_on = None
	elif new_type == "Lost":
		doc.pkx_lost_on = doc.pkx_lost_on or now_datetime()
		doc.pkx_won_on = None
	else:
		doc.pkx_won_on = None
		doc.pkx_lost_on = None


def after_insert(doc, method=None):
	if doc.get("pkx_customer"):
		recompute_customer(doc.pkx_customer)


def on_update(doc, method=None):
	revoke_previous_owner(doc, "deal_owner")
	if not doc.has_value_changed("status") and not doc.has_value_changed("deal_value"):
		return
	before = doc.get_doc_before_save()
	if deal_status_type(doc.status) == "Won":
		customer = ensure_customer_for_deal(doc)
		if before and deal_status_type(before.status) != "Won":
			add_info_comment("CRM Deal", doc.name, _("Opportunity won by {0}").format(frappe.session.user))
	elif doc.get("pkx_customer"):
		recompute_customer(doc.pkx_customer)
	if before and before.get("pkx_customer") and before.pkx_customer != doc.get("pkx_customer"):
		recompute_customer(before.pkx_customer)
