import frappe
from frappe import _

from pakkmaxx_crm.duplicates import check_lead_duplicates
from pakkmaxx_crm.events.common import guard_owner_field, protect_fields
from pakkmaxx_crm.scoring import apply_lead_score, apply_qualification_score, validate_can_qualify
from pakkmaxx_crm.setup.custom_fields import COMPUTED_LEAD_FIELDS
from pakkmaxx_crm.utils import normalize_email, normalize_phone

STAGE_BY_STATUS = {
	"New": "Lead",
	"Contacted": "Prospect",
	"Follow-up Required": "Prospect",
	"Qualified": "Qualified",
	"Proposal/Quote Requested": "Qualified",
	"Negotiation": "Qualified",
	"Converted": "Qualified",
	"Unqualified": "Lost",
	"Lost": "Lost",
}


def normalize_contact_fields(doc):
	for field in ("mobile_no", "phone", "pkx_whatsapp_no"):
		if doc.meta.has_field(field) and doc.get(field):
			doc.set(field, normalize_phone(doc.get(field)))
	if doc.get("email"):
		doc.email = normalize_email(doc.email)
	# In Ghana the WhatsApp number is usually the mobile number.
	if doc.meta.has_field("pkx_whatsapp_no") and not doc.get("pkx_whatsapp_no") and doc.get("mobile_no"):
		if doc.get("pkx_preferred_contact_method") in (None, "", "WhatsApp"):
			doc.pkx_whatsapp_no = doc.mobile_no


def lifecycle_stage(doc) -> str:
	if doc.get("pkx_customer"):
		stage = frappe.db.get_value("Pakkmaxx Customer", doc.pkx_customer, "lifecycle_stage")
		if stage:
			return stage
	return STAGE_BY_STATUS.get(doc.status, "Lead")


def before_validate(doc, method=None):
	"""Unqualified is a Lost-type status in Frappe CRM, which demands a lost reason.
	Map the Pakkmaxx unqualified reason onto it so users give the reason only once."""
	if doc.status == "Unqualified" and (doc.pkx_unqualified_reason or "").strip():
		if not doc.lost_reason and frappe.db.exists("CRM Lost Reason", "Unqualified"):
			doc.lost_reason = "Unqualified"
		doc.lost_notes = doc.lost_notes or doc.pkx_unqualified_reason


def validate(doc, method=None):
	normalize_contact_fields(doc)
	protect_fields(doc, COMPUTED_LEAD_FIELDS)
	guard_owner_field(doc, "lead_owner", _("Lead Owner"))

	apply_qualification_score(doc)
	apply_lead_score(doc)

	if doc.has_value_changed("status") and not doc.is_new():
		validate_status_change(doc)

	doc.pkx_lifecycle_stage = lifecycle_stage(doc)
	check_lead_duplicates(doc)


def validate_status_change(doc):
	if doc.status == "Qualified":
		validate_can_qualify(doc)
	elif doc.status == "Unqualified" and not (doc.pkx_unqualified_reason or "").strip():
		frappe.throw(_("Please give the reason this lead is unqualified."), title=_("Reason required"))
	elif doc.status == "Converted" and not doc.flags.get("pkx_system_update"):
		frappe.throw(_("A lead becomes Converted by converting it to an opportunity."))


def on_change(doc, method=None):
	"""Frappe CRM's conversion db_sets status=Qualified then converted=1; finish the Pakkmaxx side."""
	if not doc.get("converted") or doc.status == "Converted":
		return
	if not frappe.db.exists("CRM Lead Status", "Converted"):
		return
	frappe.db.set_value(
		"CRM Lead",
		doc.name,
		{
			"status": "Converted",
			"pkx_converted_on": doc.get("pkx_converted_on") or frappe.utils.now_datetime(),
			"pkx_lifecycle_stage": "Qualified" if not doc.get("pkx_customer") else doc.pkx_lifecycle_stage,
		},
	)
	doc.status = "Converted"
