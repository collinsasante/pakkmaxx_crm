"""Duplicate detection across leads, contacts and customers.

Matching runs with elevated rights (a rep must learn that a number is already in the CRM even
if the record belongs to a colleague) but only returns the record ID and its owner, never
the other record's contact details. Nothing is ever merged automatically.
"""

import frappe
from frappe import _
from frappe.utils import cint, escape_html

from pakkmaxx_crm.utils import get_settings, normalize_email, normalize_phone


def find_duplicates(
	mobile_no: str | None = None,
	whatsapp_no: str | None = None,
	email: str | None = None,
	organization: str | None = None,
	exclude: tuple[str, str] | None = None,
) -> list[dict]:
	phones = {p for p in (normalize_phone(mobile_no), normalize_phone(whatsapp_no)) if p}
	email = normalize_email(email)
	matches: dict[tuple, dict] = {}

	def add(doctype, name, matched_on, owner):
		if exclude and (doctype, name) == tuple(exclude):
			return
		key = (doctype, name)
		if key in matches:
			if matched_on not in matches[key]["matched_on"]:
				matches[key]["matched_on"].append(matched_on)
			return
		matches[key] = {
			"doctype": doctype,
			"name": name,
			"matched_on": [matched_on],
			"owner": owner,
			"owner_name": frappe.utils.get_fullname(owner) if owner else None,
			"can_open": bool(frappe.has_permission(doctype, "read", name)),
		}

	if phones:
		phone_list = list(phones)
		for row in frappe.get_all(
			"CRM Lead",
			or_filters={"mobile_no": ["in", phone_list], "phone": ["in", phone_list],
				"pkx_whatsapp_no": ["in", phone_list]},
			fields=["name", "lead_owner"],
			limit=20,
			ignore_permissions=True,
		):
			add("CRM Lead", row.name, "phone", row.lead_owner)
		for row in frappe.get_all(
			"Pakkmaxx Customer",
			or_filters={"mobile_no": ["in", phone_list], "whatsapp_no": ["in", phone_list]},
			fields=["name", "sales_rep"],
			limit=20,
			ignore_permissions=True,
		):
			add("Pakkmaxx Customer", row.name, "phone", row.sales_rep)
		contacts = set(
			frappe.get_all("Contact Phone", filters={"phone": ["in", phone_list], "parenttype": "Contact"},
				pluck="parent", ignore_permissions=True)
		) | set(
			frappe.get_all("Contact", filters={"pkx_whatsapp_no": ["in", phone_list]}, pluck="name",
				ignore_permissions=True)
		)
		for name in list(contacts)[:20]:
			add("Contact", name, "phone", frappe.db.get_value("Contact", name, "owner"))

	if email:
		for row in frappe.get_all("CRM Lead", filters={"email": email}, fields=["name", "lead_owner"],
				limit=20, ignore_permissions=True):
			add("CRM Lead", row.name, "email", row.lead_owner)
		for row in frappe.get_all("Pakkmaxx Customer", filters={"email": email},
				fields=["name", "sales_rep"], limit=20, ignore_permissions=True):
			add("Pakkmaxx Customer", row.name, "email", row.sales_rep)
		for name in frappe.get_all("Contact Email", filters={"email_id": email, "parenttype": "Contact"},
				pluck="parent", limit=20, ignore_permissions=True):
			add("Contact", name, "email", frappe.db.get_value("Contact", name, "owner"))

	if organization and organization.strip():
		for row in frappe.get_all("CRM Lead", filters={"organization": organization.strip(), "converted": 0},
				fields=["name", "lead_owner"], limit=10, ignore_permissions=True):
			add("CRM Lead", row.name, "company", row.lead_owner)

	return list(matches.values())


def _describe(matches: list[dict]) -> str:
	lines = []
	for m in matches:
		owner = m["owner_name"] or _("unassigned")
		lines.append(
			f"<li>{escape_html(_(m['doctype']))} <b>{escape_html(m['name'])}</b>"
			f" ({escape_html(', '.join(_(x) for x in m['matched_on']))}) - {escape_html(owner)}</li>"
		)
	return "<ul>" + "".join(lines) + "</ul>"


def check_lead_duplicates(doc):
	"""Block a lead whose phone / WhatsApp / email already exists, unless confirmed."""
	if doc.flags.get("pkx_skip_duplicate_check") or cint(doc.get("pkx_allow_duplicate")):
		return
	if not doc.is_new() and not any(
		doc.has_value_changed(f) for f in ("mobile_no", "phone", "pkx_whatsapp_no", "email")
	):
		return

	exclude = None if doc.is_new() else ("CRM Lead", doc.name)
	matches = find_duplicates(
		mobile_no=doc.mobile_no or doc.phone,
		whatsapp_no=doc.pkx_whatsapp_no,
		email=doc.email,
		exclude=exclude,
	)
	hard = [m for m in matches if set(m["matched_on"]) & {"phone", "email"}]
	if not hard:
		return
	if not cint(get_settings().block_duplicate_leads):
		frappe.msgprint(_("Possible duplicate:") + _describe(hard), indicator="orange", alert=True)
		return
	frappe.throw(
		_("This lead's phone, WhatsApp number or email already exists in the CRM:")
		+ _describe(hard)
		+ _("If this really is a different person, tick <b>Confirmed: Not a Duplicate</b> and save again."),
		title=_("Possible duplicate"),
		exc=frappe.DuplicateEntryError,
	)
