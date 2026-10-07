"""Surface Pakkmaxx fields in the Frappe CRM app (/crm).

Frappe CRM renders forms from `CRM Fields Layout` records. We only *add* Pakkmaxx sections
(and the WhatsApp field next to the mobile number) when they are missing, so layout changes
made by administrators in CRM Settings survive migrations.
"""

import json

import frappe


def _col(name, fields):
	return {"name": name, "fields": fields}


def _section(name, label, columns, opened=True):
	return {"label": label, "name": name, "opened": opened, "columns": columns}


LEAD_SECTIONS = [
	_section("pkx_profile_section", "Shipping Profile", [_col("pkx_profile_col", [
		"pkx_customer_type", "pkx_business_type", "pkx_city", "pkx_services", "pkx_product_categories",
		"pkx_shipping_frequency", "pkx_est_monthly_volume_cbm", "pkx_est_monthly_weight_kg",
		"pkx_est_monthly_spend", "pkx_current_provider"])]),
	_section("pkx_qualification_section", "Qualification", [_col("pkx_qualification_col", [
		"pkx_is_genuine", "pkx_products_description", "pkx_origin_city", "pkx_destination_city",
		"pkx_budget", "pkx_expected_ship_date", "pkx_decision_maker", "pkx_qualification_score",
		"lead_score", "lead_temperature", "pkx_unqualified_reason"])]),
	_section("pkx_signals_section", "Engagement Signals", [_col("pkx_signals_col", [
		"pkx_responds_on_whatsapp", "pkx_requested_quote", "pkx_requested_callback",
		"pkx_requested_onboarding", "pkx_engaged_website", "pkx_opened_communication"])], opened=False),
	_section("pkx_followup_section", "Follow-up", [_col("pkx_followup_col", [
		"pkx_next_action", "pkx_next_follow_up_on", "pkx_first_contacted_on", "pkx_last_contacted_on",
		"pkx_lifecycle_stage", "pkx_customer"])]),
	_section("pkx_attribution_section", "Attribution", [_col("pkx_attribution_col", [
		"pkx_campaign", "pkx_ad_reference", "pkx_referred_by", "pkx_referred_by_customer",
		"pkx_landing_page", "pkx_utm_source", "pkx_utm_medium", "pkx_utm_campaign", "pkx_utm_content"])],
		opened=False),
]

DEAL_SECTIONS = [
	_section("pkx_shipment_section", "Shipment Requirement", [_col("pkx_shipment_col", [
		"pkx_customer", "pkx_services", "pkx_product_categories", "pkx_origin_city", "pkx_destination_city",
		"pkx_deal_volume_cbm", "pkx_deal_weight_kg", "deal_value", "pkx_weighted_value",
		"expected_closure_date"])]),
	_section("pkx_followup_section", "Follow-up", [_col("pkx_followup_col", [
		"pkx_whatsapp_no", "pkx_next_follow_up_on", "pkx_first_contacted_on", "pkx_last_contacted_on",
		"pkx_won_on", "pkx_lost_on"])]),
	_section("pkx_attribution_section", "Attribution", [_col("pkx_attribution_col", [
		"source", "pkx_campaign", "pkx_ad_reference", "pkx_referred_by", "pkx_referred_by_customer",
		"pkx_utm_source", "pkx_utm_medium", "pkx_utm_campaign"])], opened=False),
]

QUICK_ENTRY_SECTIONS = {
	"CRM Lead": [
		{"name": "pkx_quick_section", "label": "Pakkmaxx", "columns": [
			_col("pkx_quick_col1", ["source", "pkx_customer_type", "pkx_services"]),
			_col("pkx_quick_col2", ["pkx_city", "pkx_preferred_contact_method", "pkx_next_action"]),
			_col("pkx_quick_col3", ["pkx_allow_duplicate"]),
		]},
	],
	"CRM Deal": [
		{"name": "pkx_quick_section", "label": "Opportunity", "columns": [
			_col("pkx_quick_col1", ["pkx_customer", "pkx_services"]),
			_col("pkx_quick_col2", ["deal_value", "expected_closure_date"]),
			_col("pkx_quick_col3", ["source", "pkx_origin_city"]),
		]},
	],
	"CRM Task": [
		{"name": "pkx_followup_section", "columns": [
			_col("pkx_followup_col1", ["pkx_task_type", "pkx_follow_up_reason"]),
			_col("pkx_followup_col2", ["pkx_remind_at", "pkx_outcome"]),
		]},
	],
}


def _sections_of(layout: list) -> list:
	"""Layouts are either a list of sections or a list of tabs holding sections."""
	if layout and isinstance(layout[0], dict) and "sections" in layout[0]:
		return layout[0]["sections"]
	return layout


def _all_fields(layout: list) -> set:
	fields = set()
	for item in layout:
		for section in item.get("sections", [item]):
			for column in section.get("columns", []):
				fields.update(column.get("fields", []))
	return fields


def _insert_after(layout: list, anchor: str, new_fields: list[str]):
	present = _all_fields(layout)
	missing = [f for f in new_fields if f not in present]
	if not missing:
		return
	for item in layout:
		for section in item.get("sections", [item]):
			for column in section.get("columns", []):
				fields = column.get("fields", [])
				if anchor in fields:
					idx = fields.index(anchor) + 1
					column["fields"] = fields[:idx] + missing + fields[idx:]
					return


def _add_sections(layout: list, sections: list):
	sections_list = _sections_of(layout)
	existing = {s.get("name") for s in sections_list}
	present = _all_fields(layout)
	for section in sections:
		if section["name"] in existing:
			continue
		section = json.loads(json.dumps(section))
		for column in section["columns"]:
			column["fields"] = [f for f in column["fields"] if f not in present]
		if any(c["fields"] for c in section["columns"]):
			sections_list.append(section)


def _update_layout(name: str, mutate):
	if not frappe.db.exists("CRM Fields Layout", name):
		return
	doc = frappe.get_doc("CRM Fields Layout", name)
	layout = json.loads(doc.layout or "[]")
	before = json.dumps(layout, sort_keys=True)
	mutate(layout)
	if json.dumps(layout, sort_keys=True) != before:
		doc.layout = json.dumps(layout)
		doc.save(ignore_permissions=True)


def setup_layouts():
	for dt, sections in (("CRM Lead", LEAD_SECTIONS), ("CRM Deal", DEAL_SECTIONS)):
		for kind in ("Side Panel", "Data Fields"):
			def mutate(layout, sections=sections):
				_insert_after(layout, "mobile_no", ["pkx_whatsapp_no"])
				_add_sections(layout, sections)

			_update_layout(f"{dt}-{kind}", mutate)

	for dt, sections in QUICK_ENTRY_SECTIONS.items():
		def mutate(layout, sections=sections):
			_insert_after(layout, "mobile_no", ["pkx_whatsapp_no"])
			_add_sections(layout, sections)

		_update_layout(f"{dt}-Quick Entry", mutate)

	_update_layout("FCRM Note-Quick Entry", lambda layout: _prepend_fields(layout, ["pkx_note_type", "pkx_interaction_at"]))
	_update_layout(
		"Contact-Side Panel",
		lambda layout: _insert_after(layout, "mobile_no", ["pkx_whatsapp_no", "pkx_preferred_contact_method", "pkx_city"]),
	)


def _prepend_fields(layout: list, fields: list[str]):
	present = _all_fields(layout)
	missing = [f for f in fields if f not in present]
	sections = _sections_of(layout)
	if missing and sections and sections[0].get("columns"):
		sections[0]["columns"][0]["fields"] = missing + sections[0]["columns"][0]["fields"]


# ---------------------------------------------------------------------------
# CRM Form Scripts: click-to-chat / click-to-call buttons on lead & deal pages
# ---------------------------------------------------------------------------

CONTACT_ACTIONS_SCRIPT = """class {cls} {{
    onRender() {{
        const doc = this.doc
        const digits = (value) => (value || '').replace(/[^0-9]/g, '')
        this.actions = [
            {{
                label: 'WhatsApp',
                icon: 'message-circle',
                onClick: () => {{
                    const number = digits(doc.pkx_whatsapp_no || doc.mobile_no)
                    if (!number) {{
                        this.toast.error('No WhatsApp number on this record')
                        return
                    }}
                    window.open('https://wa.me/' + number, '_blank', 'noopener')
                }},
            }},
            {{
                label: 'Call',
                icon: 'phone',
                onClick: () => {{
                    const number = (doc.mobile_no || doc.phone || '').replace(/[^0-9+]/g, '')
                    if (!number) {{
                        this.toast.error('No phone number on this record')
                        return
                    }}
                    window.location.href = 'tel:' + number
                }},
            }},
        ]
    }}
}}"""


def setup_form_scripts():
	for dt, cls in (("CRM Lead", "CRMLead"), ("CRM Deal", "CRMDeal")):
		name = f"Pakkmaxx Contact Actions - {dt}"
		if frappe.db.exists("CRM Form Script", name):
			continue
		frappe.get_doc(
			{
				"doctype": "CRM Form Script",
				"name": name,
				"dt": dt,
				"view": "Form",
				"enabled": 1,
				"is_standard": 0,
				"script": CONTACT_ACTIONS_SCRIPT.format(cls=cls),
			}
		).insert(ignore_permissions=True)
