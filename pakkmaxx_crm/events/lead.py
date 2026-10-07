import frappe
from frappe import _

from pakkmaxx_crm.duplicates import check_lead_duplicates
from pakkmaxx_crm.events.common import guard_owner_field, protect_fields, revoke_previous_owner
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
	# before Frappe CRM's validate, which assigns/shares on an owner change
	guard_owner_field(doc, "lead_owner", _("Lead Owner"))
	_map_unqualified_reason(doc)


def on_update(doc, method=None):
	revoke_previous_owner(doc, "lead_owner")


def _map_unqualified_reason(doc):
	"""Unqualified is a Lost-type status in Frappe CRM, which demands a lost reason.
	Map the Pakkmaxx unqualified reason onto it so users give the reason only once."""
	if doc.status == "Unqualified" and (doc.pkx_unqualified_reason or "").strip():
		if not doc.lost_reason and frappe.db.exists("CRM Lost Reason", "Unqualified"):
			doc.lost_reason = "Unqualified"
		doc.lost_notes = doc.lost_notes or doc.pkx_unqualified_reason


def validate(doc, method=None):
	normalize_contact_fields(doc)
	protect_fields(doc, COMPUTED_LEAD_FIELDS)

	apply_qualification_score(doc)
	apply_lead_score(doc)

	if doc.has_value_changed("status") and not doc.is_new():
		validate_status_change(doc)

	doc.pkx_lifecycle_stage = lifecycle_stage(doc)
	apply_ai_override(doc)
	check_lead_duplicates(doc)


def apply_ai_override(doc):
	"""Human qualification decisions: reason required, stamped by the server, never replaced by AI runs."""
	if not doc.meta.has_field("pkx_ai_human_classification"):
		return
	before = doc.get_doc_before_save() if not doc.is_new() else None
	changed = any(
		doc.get(f) != (before.get(f) if before else None)
		for f in ("pkx_ai_human_classification", "pkx_ai_human_score", "pkx_ai_override_reason")
	)
	if doc.pkx_ai_human_score not in (None, "") and not 0 <= int(doc.pkx_ai_human_score) <= 100:
		frappe.throw(_("Human score must be between 0 and 100"))
	if doc.pkx_ai_human_classification:
		if not (doc.pkx_ai_override_reason or "").strip():
			frappe.throw(_("Please give the reason for the human qualification decision."), title=_("Reason required"))
		if changed:
			doc.pkx_ai_overridden_by = frappe.session.user
			doc.pkx_ai_overridden_on = frappe.utils.now_datetime()
	elif changed:
		doc.pkx_ai_human_score = None
		doc.pkx_ai_override_reason = None
		doc.pkx_ai_overridden_by = None
		doc.pkx_ai_overridden_on = None
	doc.pkx_ai_effective_classification = doc.pkx_ai_human_classification or doc.get("pkx_ai_classification")


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
