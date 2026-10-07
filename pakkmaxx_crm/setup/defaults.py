"""Idempotent seed data for Pakkmaxx CRM.

Everything here is configuration that administrators can change afterwards from the UI.
Records are only created when missing, never overwritten, so re-running `bench migrate`
does not undo an administrator's changes. Replacing Frappe CRM's generic statuses with the
Pakkmaxx pipeline happens once (guarded by a flag) and only for statuses no record uses.
"""

import frappe

PKX_ROLES = {
	"CRM Administrator": "Full control of Pakkmaxx CRM configuration and data",
	"CRM Manager": "Sees all CRM records, assigns leads, manages pipelines, views performance",
	"Sales Representative": "Works assigned leads, opportunities, follow-ups and customers",
	"CRM Read Only": "Views permitted CRM records without changing them",
}

ROLE_PROFILES = {
	"Pakkmaxx CRM Administrator": ["CRM Administrator", "CRM Manager", "Sales Manager", "Sales User"],
	"Pakkmaxx CRM Manager": ["CRM Manager", "Sales Manager", "Sales User"],
	"Pakkmaxx Sales Manager": ["Sales Manager", "Sales User"],
	"Pakkmaxx Sales Representative": ["Sales Representative", "Sales User"],
	"Pakkmaxx CRM Read Only": ["CRM Read Only"],
}

# (name, type, color) in pipeline order. Types are Frappe CRM status types.
LEAD_STATUSES = [
	("New", "Open", "gray"),
	("Contacted", "Ongoing", "blue"),
	("Follow-up Required", "Ongoing", "orange"),
	("Qualified", "Ongoing", "cyan"),
	("Proposal/Quote Requested", "Ongoing", "amber"),
	("Negotiation", "Ongoing", "yellow"),
	("Converted", "Won", "green"),
	("Unqualified", "Lost", "pink"),
	("Lost", "Lost", "red"),
]

# Opportunity pipeline: (name, type, probability, color)
DEAL_STATUSES = [
	("Qualified", "Open", 10, "gray"),
	("Requirement Collected", "Ongoing", 25, "blue"),
	("Quote/Proposal", "Ongoing", 50, "amber"),
	("Negotiation", "Ongoing", 70, "orange"),
	("Won", "Won", 100, "green"),
	("Lost", "Lost", 0, "red"),
]

LEAD_SOURCES = [
	"WhatsApp", "Facebook", "Instagram", "TikTok", "Website", "Referral", "Existing Customer",
	"Advertisement", "Google", "Walk In", "Phone Call", "Event", "Manual Entry", "Other",
]

# Frappe CRM's generic defaults that do not apply to Pakkmaxx (removed once, only if unused)
GENERIC_SOURCES_TO_REMOVE = [
	"Customer's Vendor", "Supplier Reference", "Mass Mailing", "Cold Calling", "Reference", "Exhibition",
]

LOST_REASONS = [
	"Price too high", "Chose another forwarder", "Shipment cancelled", "No response",
	"Transit time too long", "Not ready to ship", "Service not offered", "Unqualified",
]

SERVICES = [
	("Air Freight", "Freight"), ("Sea Freight", "Freight"), ("Express", "Freight"),
	("Consolidation", "Freight"), ("Door-to-Door", "Freight"), ("Warehouse Services", "Warehousing"),
	("Product Sourcing", "Sourcing"), ("Repacking", "Value Added"),
]

PRODUCT_CATEGORIES = [
	"Clothing & Fashion", "Electronics", "Phones & Accessories", "Cosmetics & Beauty", "Food Products",
	"Hair & Wigs", "Shoes & Bags", "Furniture", "Home & Kitchen", "Auto Parts", "Machinery & Equipment",
	"Building Materials", "Baby Products", "General Goods",
]

BUSINESS_TYPES = [
	"Importer", "Retailer", "Wholesaler", "WhatsApp Seller", "Online Seller", "SME", "Individual",
	"Corporate",
]

SEGMENTS = [
	("New Customer", "#3b82f6"), ("Active Customer", "#22c55e"), ("Repeat Customer", "#14b8a6"),
	("High Value", "#a855f7"), ("SME", "#64748b"), ("Retailer", "#64748b"),
	("WhatsApp Seller", "#16a34a"), ("Importer", "#64748b"), ("Dormant", "#ef4444"), ("VIP", "#eab308"),
]

TAGS = [
	"China Importer", "Clothing", "Electronics", "Cosmetics", "Food Products", "WhatsApp Seller",
	"High Volume", "Price Sensitive", "Urgent", "Repeat Customer",
]

SCORING_RULES = [
	("Provided phone number", "mobile_no", "is set", "", 10),
	("Provided WhatsApp number", "pkx_whatsapp_no", "is set", "", 10),
	("Provided email", "email", "is set", "", 5),
	("Responds on WhatsApp", "pkx_responds_on_whatsapp", "equals", "1", 15),
	("Requested freight quote", "pkx_requested_quote", "equals", "1", 20),
	("Requested callback", "pkx_requested_callback", "equals", "1", 10),
	("Requested onboarding", "pkx_requested_onboarding", "equals", "1", 15),
	("Engaged with website", "pkx_engaged_website", "equals", "1", 5),
	("Opened our communication", "pkx_opened_communication", "equals", "1", 5),
	("Business customer", "pkx_customer_type", "equals", "Business", 10),
	("Frequent importer", "pkx_shipping_frequency", "in list",
		"Monthly,Bi-weekly,Weekly,Multiple per week", 15),
	("High volume (5+ CBM / month)", "pkx_est_monthly_volume_cbm", "greater than or equal", "5", 15),
	("High spend (GHS 20,000+ / month)", "pkx_est_monthly_spend", "greater than or equal", "20000", 10),
]


def _ensure(doctype: str, name: str, values: dict):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def create_roles():
	for role, desc in PKX_ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": 1, "description": desc}
			).insert(ignore_permissions=True)


def create_role_profiles():
	for profile, roles in ROLE_PROFILES.items():
		if frappe.db.exists("Role Profile", profile):
			continue
		doc = frappe.new_doc("Role Profile")
		doc.role_profile = profile
		for role in roles:
			doc.append("roles", {"role": role})
		doc.insert(ignore_permissions=True)


def _replace_statuses(doctype: str, keyfield: str, wanted: list, used_in: str):
	wanted_names = [w[0] for w in wanted]
	for position, row in enumerate(wanted, start=1):
		name = row[0]
		values = {"type": row[1], "position": position, "color": row[-1]}
		if doctype == "CRM Deal Status":
			values["probability"] = row[2]
		if frappe.db.exists(doctype, name):
			frappe.db.set_value(doctype, name, values)
		else:
			frappe.get_doc({"doctype": doctype, keyfield: name, **values}).insert(ignore_permissions=True)
	for name in frappe.get_all(doctype, pluck="name"):
		if name not in wanted_names and not frappe.db.exists(used_in, {"status": name}):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)


def setup_pipeline():
	"""Install the Pakkmaxx lead lifecycle and opportunity pipeline once.

	Afterwards administrators own these lists (CRM Settings > Statuses)."""
	if frappe.db.get_default("pakkmaxx_crm_pipeline_installed"):
		return
	_replace_statuses("CRM Lead Status", "lead_status", LEAD_STATUSES, "CRM Lead")
	_replace_statuses("CRM Deal Status", "deal_status", DEAL_STATUSES, "CRM Deal")
	for source in GENERIC_SOURCES_TO_REMOVE:
		if frappe.db.exists("CRM Lead Source", source) and not (
			frappe.db.exists("CRM Lead", {"source": source}) or frappe.db.exists("CRM Deal", {"source": source})
		):
			frappe.delete_doc("CRM Lead Source", source, ignore_permissions=True, force=True)
	frappe.db.set_default("pakkmaxx_crm_pipeline_installed", "1")


def setup_masters():
	for source in LEAD_SOURCES:
		_ensure("CRM Lead Source", source, {"source_name": source})
	for reason in LOST_REASONS:
		_ensure("CRM Lost Reason", reason, {"lost_reason": reason})
	for name, group in SERVICES:
		_ensure("Pakkmaxx Service", name, {"service_name": name, "service_group": group})
	for name in PRODUCT_CATEGORIES:
		_ensure("Pakkmaxx Product Category", name, {"category_name": name})
	for name in BUSINESS_TYPES:
		_ensure("Pakkmaxx Business Type", name, {"business_type": name})
	for name, color in SEGMENTS:
		_ensure("Pakkmaxx Customer Segment", name, {"segment_name": name, "color": color})
	for tag in TAGS:
		_ensure("Tag", tag, {"name": tag})


def setup_currency():
	"""Ghana Cedi is the CRM currency. No USD conversion is shown anywhere."""
	if frappe.db.exists("Currency", "GHS"):
		frappe.db.set_value("Currency", "GHS", {"enabled": 1, "symbol": "GH₵"})
	settings = frappe.get_single("FCRM Settings")
	if not settings.currency:
		settings.currency = "GHS"
	settings.enable_sales_hierarchy = 1
	if not settings.brand_name:
		settings.brand_name = "Pakkmaxx CRM"
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.set_default("currency", frappe.db.get_default("currency") or "GHS")
	frappe.db.set_default("country", frappe.db.get_default("country") or "Ghana")


def setup_settings():
	settings = frappe.get_single("Pakkmaxx CRM Settings")
	if settings.scoring_rules:
		return
	for label, fieldname, operator, value, points in SCORING_RULES:
		settings.append(
			"scoring_rules",
			{"enabled": 1, "label": label, "fieldname": fieldname, "operator": operator, "value": value,
				"points": points},
		)
	settings.flags.ignore_permissions = True
	settings.save()


# ---------------------------------------------------------------------------
# Lead workflow
# ---------------------------------------------------------------------------

WORKFLOW_NAME = "Pakkmaxx Lead Workflow"

STATE_STYLES = {
	"New": "", "Contacted": "Primary", "Follow-up Required": "Warning", "Qualified": "Info",
	"Proposal/Quote Requested": "Warning", "Negotiation": "Warning", "Converted": "Success",
	"Unqualified": "Inverse", "Lost": "Danger",
}

# (from, action, to, role)
WORKER = "Sales User"
REOPEN_ROLES = ("Sales Manager", "CRM Manager")
TRANSITIONS = [
	("New", "Mark Contacted", "Contacted", WORKER),
	("New", "Needs Follow-up", "Follow-up Required", WORKER),
	("New", "Mark Unqualified", "Unqualified", WORKER),
	("New", "Mark Lost", "Lost", WORKER),
	("Contacted", "Needs Follow-up", "Follow-up Required", WORKER),
	("Contacted", "Qualify", "Qualified", WORKER),
	("Contacted", "Mark Unqualified", "Unqualified", WORKER),
	("Contacted", "Mark Lost", "Lost", WORKER),
	("Follow-up Required", "Mark Contacted", "Contacted", WORKER),
	("Follow-up Required", "Qualify", "Qualified", WORKER),
	("Follow-up Required", "Mark Unqualified", "Unqualified", WORKER),
	("Follow-up Required", "Mark Lost", "Lost", WORKER),
	("Qualified", "Request Quote", "Proposal/Quote Requested", WORKER),
	("Qualified", "Needs Follow-up", "Follow-up Required", WORKER),
	("Qualified", "Mark Lost", "Lost", WORKER),
	("Proposal/Quote Requested", "Start Negotiation", "Negotiation", WORKER),
	("Proposal/Quote Requested", "Needs Follow-up", "Follow-up Required", WORKER),
	("Proposal/Quote Requested", "Mark Lost", "Lost", WORKER),
	("Negotiation", "Back to Quote", "Proposal/Quote Requested", WORKER),
	("Negotiation", "Needs Follow-up", "Follow-up Required", WORKER),
	("Negotiation", "Mark Lost", "Lost", WORKER),
	*[(s, "Reopen", "Contacted", r) for s in ("Unqualified", "Lost") for r in REOPEN_ROLES],
]


def setup_workflow():
	for state, style in STATE_STYLES.items():
		_ensure("Workflow State", state, {"workflow_state_name": state, "style": style})
	for action in {t[1] for t in TRANSITIONS}:
		_ensure("Workflow Action Master", action, {"workflow_action_name": action})

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return  # administrators own it after the first install
	wf = frappe.new_doc("Workflow")
	wf.workflow_name = WORKFLOW_NAME
	wf.document_type = "CRM Lead"
	wf.workflow_state_field = "status"
	wf.is_active = 1
	wf.override_status = 1
	wf.send_email_alert = 0
	for state in STATE_STYLES:
		wf.append("states", {"state": state, "doc_status": "0", "allow_edit": WORKER})
	for state, action, next_state, role in TRANSITIONS:
		wf.append("transitions", {"state": state, "action": action, "next_state": next_state, "allowed": role,
			"allow_self_approval": 1})
	wf.insert(ignore_permissions=True)
