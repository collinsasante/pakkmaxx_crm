"""Pakkmaxx custom fields on Frappe CRM / Frappe core doctypes.

All fieldnames are prefixed `pkx_`. Fields that exist with the same fieldname on CRM Lead
and CRM Deal are copied automatically by Frappe CRM when a lead is converted.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

GHS = "GHS"

PREFERRED_CONTACT = "\nWhatsApp\nPhone Call\nSMS\nEmail\nIn Person"
CUSTOMER_TYPE = "\nIndividual\nBusiness"
FREQUENCY = "\nOne-time\nOccasional\nQuarterly\nMonthly\nBi-weekly\nWeekly\nMultiple per week"
LIFECYCLE = "\nLead\nProspect\nQualified\nCustomer\nActive Customer\nRepeat Customer\nDormant\nLost"
NOTE_TYPES = "General\nSales\nFollow-up\nAccount\nWhatsApp Conversation\nMeeting\nCall Summary"

# Server-computed fields: read-only in every UI and overwritten on save.
COMPUTED_LEAD_FIELDS = (
	"pkx_qualification_score",
	"pkx_next_follow_up_on",
	"pkx_first_contacted_on",
	"pkx_last_contacted_on",
	"pkx_lifecycle_stage",
	"pkx_customer",
	"pkx_converted_on",
	"lead_score",
	"lead_temperature",
)
COMPUTED_DEAL_FIELDS = (
	"pkx_weighted_value",
	"pkx_won_on",
	"pkx_lost_on",
	"pkx_next_follow_up_on",
	"pkx_first_contacted_on",
	"pkx_last_contacted_on",
)


def _chain(anchor: str, fields: list[dict]) -> list[dict]:
	prev = anchor
	for f in fields:
		f.setdefault("insert_after", prev)
		prev = f["fieldname"]
	return fields


def _attribution_fields() -> list[dict]:
	return [
		dict(fieldname="pkx_attribution_tab", label="Attribution", fieldtype="Tab Break"),
		dict(fieldname="pkx_campaign", label="Campaign", fieldtype="Link", options="UTM Campaign",
			in_standard_filter=1),
		dict(fieldname="pkx_ad_reference", label="Ad / Post Reference", fieldtype="Data"),
		dict(fieldname="pkx_referred_by", label="Referred By (Person)", fieldtype="Data"),
		dict(fieldname="pkx_referred_by_customer", label="Referred By Customer", fieldtype="Link",
			options="Pakkmaxx Customer"),
		dict(fieldname="pkx_landing_page", label="Landing Page", fieldtype="Data"),
		dict(fieldname="pkx_attribution_cb", fieldtype="Column Break"),
		dict(fieldname="pkx_utm_source", label="UTM Source", fieldtype="Link", options="UTM Source"),
		dict(fieldname="pkx_utm_medium", label="UTM Medium", fieldtype="Link", options="UTM Medium"),
		dict(fieldname="pkx_utm_campaign", label="UTM Campaign", fieldtype="Data"),
		dict(fieldname="pkx_utm_content", label="UTM Content", fieldtype="Data"),
	]


def _requirement_fields(volume_prefix: str) -> list[dict]:
	monthly = volume_prefix == "est_monthly"
	return [
		dict(fieldname="pkx_services", label="Services Interested In", fieldtype="Table MultiSelect",
			options="Pakkmaxx Service Item"),
		dict(fieldname="pkx_product_categories", label="Product Categories", fieldtype="Table MultiSelect",
			options="Pakkmaxx Product Category Item"),
		dict(fieldname="pkx_origin_city", label="Origin (China City)", fieldtype="Data",
			description="e.g. Guangzhou, Yiwu, Shenzhen"),
		dict(fieldname="pkx_destination_city", label="Destination (Ghana City)", fieldtype="Data",
			description="e.g. Accra, Kumasi, Tema"),
		dict(fieldname=f"pkx_{volume_prefix}_cb", fieldtype="Column Break"),
		*(
			[
				dict(fieldname="pkx_shipping_frequency", label="Shipping Frequency", fieldtype="Select",
					options=FREQUENCY, in_standard_filter=1),
				dict(fieldname="pkx_est_monthly_volume_cbm", label="Est. Monthly Volume (CBM)", fieldtype="Float"),
				dict(fieldname="pkx_est_monthly_weight_kg", label="Est. Monthly Weight (kg)", fieldtype="Float"),
				dict(fieldname="pkx_est_monthly_spend", label="Est. Monthly Shipping Spend", fieldtype="Currency",
					options=GHS),
				dict(fieldname="pkx_current_provider", label="Current Shipping Provider", fieldtype="Data"),
			]
			if monthly
			else [
				dict(fieldname="pkx_deal_volume_cbm", label="Est. Shipment Volume (CBM)", fieldtype="Float"),
				dict(fieldname="pkx_deal_weight_kg", label="Est. Shipment Weight (kg)", fieldtype="Float"),
				dict(fieldname="pkx_weighted_value", label="Weighted Value", fieldtype="Currency",
					options="currency", read_only=1,
					description="Deal value x probability, calculated by the server"),
			]
		),
	]


def _tracking_fields(extra: list[dict]) -> list[dict]:
	return [
		dict(fieldname="pkx_tracking_tab", label="Follow-up", fieldtype="Tab Break"),
		dict(fieldname="pkx_next_follow_up_on", label="Next Follow-up", fieldtype="Datetime", read_only=1,
			in_list_view=0),
		dict(fieldname="pkx_first_contacted_on", label="First Contacted On", fieldtype="Datetime", read_only=1),
		dict(fieldname="pkx_last_contacted_on", label="Last Contacted On", fieldtype="Datetime", read_only=1),
		dict(fieldname="pkx_tracking_cb", fieldtype="Column Break"),
		*extra,
	]


def get_custom_fields() -> dict:
	lead = [
		dict(fieldname="pkx_whatsapp_no", label="WhatsApp No", fieldtype="Data", options="Phone",
			insert_after="mobile_no", search_index=1),
		dict(fieldname="pkx_preferred_contact_method", label="Preferred Contact Method", fieldtype="Select",
			options=PREFERRED_CONTACT, insert_after="pkx_whatsapp_no", default="WhatsApp"),
	]
	lead += _chain(
		"lost_notes",
		[
			dict(fieldname="pkx_profile_tab", label="Shipping Profile", fieldtype="Tab Break"),
			dict(fieldname="pkx_customer_type", label="Customer Type", fieldtype="Select", options=CUSTOMER_TYPE,
				in_standard_filter=1),
			dict(fieldname="pkx_business_type", label="Business Type", fieldtype="Link",
				options="Pakkmaxx Business Type", in_standard_filter=1),
			dict(fieldname="pkx_customer_size", label="Customer Size", fieldtype="Select",
				options="\nMicro (just me)\nSmall (2-10 staff)\nMedium (11-50 staff)\nLarge (50+ staff)"),
			dict(fieldname="pkx_profile_cb", fieldtype="Column Break"),
			dict(fieldname="pkx_country", label="Country", fieldtype="Link", options="Country", default="Ghana"),
			dict(fieldname="pkx_city", label="City", fieldtype="Data", in_standard_filter=1),
			dict(fieldname="pkx_location", label="Location / Area", fieldtype="Data"),
			dict(fieldname="pkx_needs_section", label="Shipping Needs", fieldtype="Section Break"),
			*_requirement_fields("est_monthly"),
			dict(fieldname="pkx_qualification_tab", label="Qualification", fieldtype="Tab Break"),
			dict(fieldname="pkx_is_genuine", label="Genuine Lead?", fieldtype="Select",
				options="\nYes\nNo\nUnsure"),
			dict(fieldname="pkx_products_description", label="What Do They Ship?", fieldtype="Small Text"),
			dict(fieldname="pkx_expected_ship_date", label="Expected First Shipment", fieldtype="Date"),
			dict(fieldname="pkx_budget", label="Budget per Shipment", fieldtype="Currency", options=GHS),
			dict(fieldname="pkx_qualification_cb", fieldtype="Column Break"),
			dict(fieldname="pkx_decision_maker", label="Decision Maker", fieldtype="Data",
				description="Who makes the purchasing decision?"),
			dict(fieldname="pkx_qualification_score", label="Qualification Score", fieldtype="Percent",
				read_only=1),
			dict(fieldname="pkx_qualification_notes", label="Qualification Notes", fieldtype="Small Text"),
			dict(fieldname="pkx_unqualified_reason", label="Unqualified Reason", fieldtype="Small Text",
				depends_on="eval:doc.status=='Unqualified'"),
			dict(fieldname="pkx_signals_section", label="Engagement Signals", fieldtype="Section Break",
				description="Used by lead scoring"),
			dict(fieldname="pkx_responds_on_whatsapp", label="Responds on WhatsApp", fieldtype="Check"),
			dict(fieldname="pkx_requested_quote", label="Requested Freight Quote", fieldtype="Check"),
			dict(fieldname="pkx_requested_callback", label="Requested Callback", fieldtype="Check"),
			dict(fieldname="pkx_signals_cb", fieldtype="Column Break"),
			dict(fieldname="pkx_requested_onboarding", label="Requested Onboarding", fieldtype="Check"),
			dict(fieldname="pkx_engaged_website", label="Engaged With Website", fieldtype="Check"),
			dict(fieldname="pkx_opened_communication", label="Opened Our Communication", fieldtype="Check"),
			*_attribution_fields(),
			*_tracking_fields(
				[
					dict(fieldname="pkx_next_action", label="Next Action", fieldtype="Data",
						description="e.g. Send sea freight rate and follow up tomorrow"),
					dict(fieldname="pkx_lifecycle_stage", label="Lifecycle Stage", fieldtype="Select",
						options=LIFECYCLE, read_only=1, in_standard_filter=1),
					dict(fieldname="pkx_customer", label="Customer", fieldtype="Link",
						options="Pakkmaxx Customer", read_only=1, search_index=1),
					dict(fieldname="pkx_converted_on", label="Converted On", fieldtype="Datetime", read_only=1),
					dict(fieldname="pkx_allow_duplicate", label="Confirmed: Not a Duplicate", fieldtype="Check",
						no_copy=1,
						description="Tick to save a lead that shares a phone, WhatsApp number or email with an existing record"),
				]
			),
		],
	)

	deal = [
		dict(fieldname="pkx_whatsapp_no", label="WhatsApp No", fieldtype="Data", options="Phone",
			insert_after="mobile_no", search_index=1),
	]
	deal += _chain(
		"lost_notes",
		[
			dict(fieldname="pkx_shipment_tab", label="Shipment Requirement", fieldtype="Tab Break"),
			dict(fieldname="pkx_customer", label="Customer", fieldtype="Link", options="Pakkmaxx Customer",
				search_index=1, in_standard_filter=1),
			dict(fieldname="pkx_customer_type", label="Customer Type", fieldtype="Select", options=CUSTOMER_TYPE),
			dict(fieldname="pkx_business_type", label="Business Type", fieldtype="Link",
				options="Pakkmaxx Business Type"),
			dict(fieldname="pkx_requirement_section", label="Requirement", fieldtype="Section Break"),
			*_requirement_fields("deal"),
			*_attribution_fields(),
			*_tracking_fields(
				[
					dict(fieldname="pkx_won_on", label="Won On", fieldtype="Datetime", read_only=1),
					dict(fieldname="pkx_lost_on", label="Lost On", fieldtype="Datetime", read_only=1),
				]
			),
		],
	)

	task = [
		dict(fieldname="pkx_task_type", label="Type", fieldtype="Select", options="Task\nFollow-up",
			default="Task", insert_after="title", in_list_view=1, in_standard_filter=1),
		dict(fieldname="pkx_follow_up_reason", label="Follow-up Reason", fieldtype="Data",
			insert_after="pkx_task_type", depends_on="eval:doc.pkx_task_type=='Follow-up'"),
		dict(fieldname="pkx_remind_at", label="Remind At", fieldtype="Datetime", insert_after="due_date",
			description="Defaults to the reminder lead time before the due date"),
		dict(fieldname="pkx_reminder_sent", label="Reminder Sent", fieldtype="Check", read_only=1,
			insert_after="pkx_remind_at", no_copy=1),
		dict(fieldname="pkx_completed_on", label="Completed On", fieldtype="Datetime", read_only=1,
			insert_after="pkx_reminder_sent", no_copy=1),
		dict(fieldname="pkx_outcome", label="Outcome", fieldtype="Small Text", insert_after="description"),
	]

	note = [
		dict(fieldname="pkx_note_type", label="Note Type", fieldtype="Select", options=NOTE_TYPES,
			default="General", insert_after="title", in_list_view=1, in_standard_filter=1),
		dict(fieldname="pkx_interaction_at", label="Interaction Time", fieldtype="Datetime",
			insert_after="pkx_note_type", default="Now",
			description="When the WhatsApp chat, meeting or call took place"),
	]

	contact = [
		dict(fieldname="pkx_whatsapp_no", label="WhatsApp No", fieldtype="Data", options="Phone",
			insert_after="mobile_no", search_index=1),
		dict(fieldname="pkx_preferred_contact_method", label="Preferred Contact Method", fieldtype="Select",
			options=PREFERRED_CONTACT, insert_after="pkx_whatsapp_no"),
		dict(fieldname="pkx_city", label="City", fieldtype="Data", insert_after="company_name"),
		dict(fieldname="pkx_country", label="Country", fieldtype="Link", options="Country",
			insert_after="pkx_city"),
	]

	return {
		"CRM Lead": lead,
		"CRM Deal": deal,
		"CRM Task": task,
		"FCRM Note": note,
		"Contact": contact,
	}


PROPERTY_SETTERS = [
	# score and temperature are owned by Pakkmaxx lead scoring
	("CRM Lead", "lead_score", "read_only", "1", "Check"),
	("CRM Lead", "lead_temperature", "read_only", "1", "Check"),
	("CRM Lead", "lead_temperature", "in_standard_filter", "1", "Check"),
	("CRM Lead", "source", "in_standard_filter", "1", "Check"),
	("CRM Lead", "lead_owner", "in_standard_filter", "1", "Check"),
	("CRM Lead", "status", "in_standard_filter", "1", "Check"),
	("CRM Deal", "deal_owner", "in_standard_filter", "1", "Check"),
	("CRM Deal", "source", "in_standard_filter", "1", "Check"),
	# fast lookup by phone/WhatsApp/email from the search bar
	("CRM Lead", None, "search_fields", "lead_name,organization,mobile_no,pkx_whatsapp_no,email", "Data"),
	("CRM Deal", None, "search_fields", "organization,lead_name,mobile_no,pkx_whatsapp_no,email", "Data"),
	# audit trail on records that matter
	("CRM Task", None, "track_changes", "1", "Check"),
	("Contact", None, "track_changes", "1", "Check"),
	("CRM Organization", None, "track_changes", "1", "Check"),
	("CRM Call Log", None, "track_changes", "1", "Check"),
]


def setup_custom_fields():
	import frappe
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	create_custom_fields(get_custom_fields(), ignore_validate=True, update=True)
	for doctype, fieldname, prop, value, ptype in PROPERTY_SETTERS:
		make_property_setter(
			doctype,
			fieldname,
			prop,
			value,
			ptype,
			for_doctype=fieldname is None,
			validate_fields_for_doctype=False,
		)
	for doctype, column in (("CRM Lead", "mobile_no"), ("CRM Lead", "email"), ("CRM Deal", "mobile_no")):
		frappe.db.add_index(doctype, [column])
