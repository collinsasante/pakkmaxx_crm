import frappe
from frappe import _

from pakkmaxx_crm.duplicates import find_duplicates
from pakkmaxx_crm.utils import normalize_email, normalize_phone

UTM_DOCTYPES = {"utm_source": "UTM Source", "utm_medium": "UTM Medium"}


@frappe.whitelist()
def check_duplicates(
	mobile_no: str | None = None,
	whatsapp_no: str | None = None,
	email: str | None = None,
	organization: str | None = None,
	exclude_lead: str | None = None,
) -> list[dict]:
	"""Records that already use this phone / WhatsApp / email. Returns IDs and owners only."""
	if not frappe.has_permission("CRM Lead", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return find_duplicates(mobile_no, whatsapp_no, email, organization,
		exclude=("CRM Lead", exclude_lead) if exclude_lead else None)


def _ensure_utm(doctype: str, value: str | None) -> str | None:
	value = (value or "").strip()[:140]
	if not value:
		return None
	if not frappe.db.exists(doctype, value):
		frappe.get_doc({"doctype": doctype, "name": value}).insert(ignore_permissions=True)
	return value


@frappe.whitelist(methods=["POST"])
def capture_lead(
	first_name: str,
	mobile_no: str | None = None,
	whatsapp_no: str | None = None,
	email: str | None = None,
	last_name: str | None = None,
	organization: str | None = None,
	source: str = "WhatsApp",
	city: str | None = None,
	message: str | None = None,
	services: list[str] | str | None = None,
	utm_source: str | None = None,
	utm_medium: str | None = None,
	utm_campaign: str | None = None,
	utm_content: str | None = None,
	landing_page: str | None = None,
) -> dict:
	"""Intake for integrations (website forms, a WhatsApp Business bot, ads).

	Idempotent: if the phone/WhatsApp/email already belongs to a lead or customer, nothing new
	is created and the existing record is returned. Requires an API user with CRM Lead create
	permission. New leads arrive unassigned for a manager to distribute.
	"""
	if not frappe.has_permission("CRM Lead", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not (mobile_no or whatsapp_no or email):
		frappe.throw(_("A phone number, WhatsApp number or email is required"))
	if not frappe.db.exists("CRM Lead Source", source):
		source = "Other"

	existing = [m for m in find_duplicates(mobile_no, whatsapp_no, email) if m["doctype"] in
		("CRM Lead", "Pakkmaxx Customer")]
	if existing:
		match = existing[0]
		if message and match["doctype"] == "CRM Lead":
			frappe.get_doc({"doctype": "FCRM Note", "title": f"New enquiry via {source}",
				"content": "<p>" + frappe.utils.escape_html(message) + "</p>",
				"pkx_note_type": "WhatsApp Conversation" if source == "WhatsApp" else "General",
				"reference_doctype": "CRM Lead", "reference_docname": match["name"]}).insert(ignore_permissions=True)
		return {"created": False, "doctype": match["doctype"], "name": match["name"]}

	if isinstance(services, str):
		services = frappe.parse_json(services) if services.strip().startswith("[") else [services]
	lead = frappe.get_doc(
		{
			"doctype": "CRM Lead",
			"first_name": first_name,
			"last_name": last_name,
			"organization": organization,
			"mobile_no": normalize_phone(mobile_no or whatsapp_no),
			"pkx_whatsapp_no": normalize_phone(whatsapp_no or mobile_no),
			"email": normalize_email(email),
			"source": source,
			"pkx_city": city,
			"pkx_utm_source": _ensure_utm("UTM Source", utm_source),
			"pkx_utm_medium": _ensure_utm("UTM Medium", utm_medium),
			"pkx_campaign": _ensure_utm("UTM Campaign", utm_campaign),
			"pkx_utm_campaign": utm_campaign,
			"pkx_utm_content": utm_content,
			"pkx_landing_page": landing_page,
			"pkx_engaged_website": 1 if landing_page else 0,
			"pkx_responds_on_whatsapp": 1 if source == "WhatsApp" else 0,
			"pkx_services": [{"service": s} for s in (services or []) if frappe.db.exists("Pakkmaxx Service", s)],
		}
	)
	lead.flags.pkx_system_update = True  # integration leads stay unassigned
	lead.insert()
	if message:
		frappe.get_doc({"doctype": "FCRM Note", "title": f"First message via {source}",
			"content": "<p>" + frappe.utils.escape_html(message) + "</p>", "pkx_note_type": "General",
			"reference_doctype": "CRM Lead", "reference_docname": lead.name}).insert(ignore_permissions=True)
	return {"created": True, "doctype": "CRM Lead", "name": lead.name}
