"""Pakkmaxx Customer: creation on win, de-duplication, relationship stats and lifecycle."""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, get_datetime, getdate, now_datetime, nowdate

from pakkmaxx_crm.events.common import add_info_comment
from pakkmaxx_crm.utils import get_settings, normalize_email, normalize_phone

WON = "Won"


def deal_status_type(status: str | None) -> str | None:
	return frappe.get_cached_value("CRM Deal Status", status, "type") if status else None


def _primary_contact(deal) -> str | None:
	if deal.get("contact"):
		return deal.contact
	for row in deal.get("contacts") or []:
		if row.get("is_primary"):
			return row.contact
	rows = deal.get("contacts") or []
	return rows[0].contact if rows else None


def find_existing_customer(deal, lead=None) -> str | None:
	"""Match a deal to an existing customer: explicit link > lead > contact > phone > email > org."""
	if deal.get("pkx_customer"):
		return deal.pkx_customer
	if lead and lead.get("pkx_customer"):
		return lead.pkx_customer

	contact = _primary_contact(deal)
	if contact and (name := frappe.db.get_value("Pakkmaxx Customer", {"contact": contact})):
		return name

	phones = [
		p
		for p in (
			normalize_phone(deal.get("mobile_no")),
			normalize_phone(deal.get("pkx_whatsapp_no")),
			normalize_phone(lead.get("pkx_whatsapp_no")) if lead else None,
		)
		if p
	]
	if phones:
		name = frappe.db.get_value(
			"Pakkmaxx Customer",
			{"mobile_no": ["in", phones]},
		) or frappe.db.get_value("Pakkmaxx Customer", {"whatsapp_no": ["in", phones]})
		if name:
			return name

	email = normalize_email(deal.get("email"))
	if email and (name := frappe.db.get_value("Pakkmaxx Customer", {"email": email})):
		return name

	if deal.get("organization"):
		return frappe.db.get_value("Pakkmaxx Customer", {"organization": deal.organization})
	return None


def _copy_table(target, fieldname, source_rows, link_field):
	existing = {r.get(link_field) for r in target.get(fieldname) or []}
	for row in source_rows or []:
		value = row.get(link_field)
		if value and value not in existing:
			target.append(fieldname, {link_field: value})
			existing.add(value)


def create_customer_from_deal(deal, lead=None) -> str:
	contact = _primary_contact(deal)
	is_business = bool(deal.get("organization")) or (lead and lead.get("pkx_customer_type") == "Business")
	name = (
		(deal.get("organization") if is_business else None)
		or (lead.lead_name if lead else None)
		or deal.get("lead_name")
		or (frappe.db.get_value("Contact", contact, "full_name") if contact else None)
		or deal.name
	)

	customer = frappe.new_doc("Pakkmaxx Customer")
	customer.update(
		{
			"customer_name": name,
			"customer_type": "Business" if is_business else "Individual",
			"business_type": deal.get("pkx_business_type") or (lead.get("pkx_business_type") if lead else None),
			"contact": contact,
			"organization": deal.get("organization"),
			"mobile_no": deal.get("mobile_no") or (lead.mobile_no if lead else None),
			"whatsapp_no": deal.get("pkx_whatsapp_no") or (lead.get("pkx_whatsapp_no") if lead else None),
			"email": deal.get("email") or (lead.email if lead else None),
			"preferred_contact_method": lead.get("pkx_preferred_contact_method") if lead else "WhatsApp",
			"country": (lead.get("pkx_country") if lead else None) or "Ghana",
			"city": lead.get("pkx_city") if lead else None,
			"location": lead.get("pkx_location") if lead else None,
			"industry": deal.get("industry"),
			"sales_rep": deal.get("deal_owner"),
			"source": deal.get("source") or (lead.source if lead else None),
			"campaign": deal.get("pkx_campaign") or (lead.get("pkx_campaign") if lead else None),
			"original_lead": lead.name if lead else None,
			"first_deal": deal.name,
			"lead_created_on": lead.creation if lead else deal.creation,
		}
	)
	_copy_table(customer, "services", deal.get("pkx_services"), "service")
	_copy_table(customer, "product_categories", deal.get("pkx_product_categories"), "product_category")
	if lead:
		_copy_table(customer, "services", lead.get("pkx_services"), "service")
		_copy_table(customer, "product_categories", lead.get("pkx_product_categories"), "product_category")
	if frappe.db.exists("Pakkmaxx Customer Segment", "New Customer"):
		customer.append("segments", {"segment": "New Customer"})
	customer.flags.pkx_system_update = True
	customer.flags.pkx_skip_duplicate_check = True
	customer.insert(ignore_permissions=True)
	return customer.name


def ensure_customer_for_deal(deal) -> str:
	"""Create or link the Pakkmaxx Customer for a won deal. Idempotent."""
	lead = frappe.get_doc("CRM Lead", deal.lead) if deal.get("lead") else None
	customer = find_existing_customer(deal, lead)
	created = False
	if not customer:
		customer = create_customer_from_deal(deal, lead)
		created = True

	if deal.get("pkx_customer") != customer:
		frappe.db.set_value("CRM Deal", deal.name, "pkx_customer", customer, update_modified=False)
		deal.pkx_customer = customer
	if lead and lead.get("pkx_customer") != customer:
		frappe.db.set_value("CRM Lead", lead.name, "pkx_customer", customer, update_modified=False)

	if created:
		add_info_comment("Pakkmaxx Customer", customer, _("Customer created from won opportunity {0}").format(deal.name))
		add_info_comment("CRM Deal", deal.name, _("Customer {0} created").format(customer))
		if lead:
			add_info_comment("CRM Lead", lead.name, _("Converted to customer {0}").format(customer))
	recompute_customer(customer)
	return customer


# ---------------------------------------------------------------------------
# Stats & lifecycle
# ---------------------------------------------------------------------------


def _base_value(deal) -> float:
	"""Deal value in GHS. Frappe CRM stores exchange_rate to the CRM currency."""
	value = flt(deal.deal_value)
	if deal.currency and deal.currency != "GHS":
		value *= flt(deal.exchange_rate) or 1
	return value


def compute_lifecycle(won_count: int, last_won_on, last_activity_on) -> str:
	settings = get_settings()
	reference = max(
		[getdate(d) for d in (last_won_on, last_activity_on) if d] or [getdate(nowdate())]
	)
	idle_days = date_diff(nowdate(), reference)
	if won_count and idle_days >= cint(settings.dormant_after_days or 120):
		return "Dormant"
	if won_count >= 2:
		return "Repeat Customer"
	if won_count == 1 and last_won_on and date_diff(nowdate(), last_won_on) <= cint(settings.active_window_days or 90):
		return "Active Customer"
	return "Customer"


def recompute_customer(name: str):
	if not name or not frappe.db.exists("Pakkmaxx Customer", name):
		return
	deals = frappe.get_all(
		"CRM Deal",
		filters={"pkx_customer": name},
		fields=["name", "status", "deal_value", "currency", "exchange_rate", "pkx_won_on", "closed_date",
			"pkx_last_contacted_on", "pkx_next_follow_up_on", "lead", "creation"],
		ignore_permissions=True,
	)
	won, open_count, values, won_dates, activity, follow_ups = 0, 0, 0.0, [], [], []
	for d in deals:
		kind = deal_status_type(d.status)
		if kind == WON:
			won += 1
			values += _base_value(d)
			won_dates.append(getdate(d.pkx_won_on or d.closed_date or d.creation))
		elif kind != "Lost":
			open_count += 1
		if d.pkx_last_contacted_on:
			activity.append(get_datetime(d.pkx_last_contacted_on))
		if d.pkx_next_follow_up_on:
			follow_ups.append(get_datetime(d.pkx_next_follow_up_on))

	customer = frappe.get_doc("Pakkmaxx Customer", name)
	if customer.last_activity_on:
		activity.append(get_datetime(customer.last_activity_on))
	direct_follow_up = next_follow_up_for("Pakkmaxx Customer", name)
	if direct_follow_up:
		follow_ups.append(get_datetime(direct_follow_up))

	first_won = min(won_dates) if won_dates else None
	last_won = max(won_dates) if won_dates else None
	last_activity = max(activity) if activity else None
	values_to_set = {
		"won_deals_count": won,
		"open_deals_count": open_count,
		"lifetime_value": values,
		"first_won_on": first_won,
		"last_won_on": last_won,
		"last_activity_on": last_activity,
		"next_follow_up_on": min(follow_ups) if follow_ups else None,
		"lifecycle_stage": compute_lifecycle(won, last_won, last_activity),
	}
	if first_won and customer.lead_created_on:
		values_to_set["days_to_convert"] = max(0, date_diff(first_won, customer.lead_created_on))

	changed = {k: v for k, v in values_to_set.items() if customer.get(k) != v}
	if changed:
		customer.update(changed)
		customer.flags.pkx_system_update = True
		customer.flags.pkx_skip_duplicate_check = True
		customer.save(ignore_permissions=True)


def next_follow_up_for(reference_doctype: str, reference_name: str):
	rows = frappe.get_all(
		"CRM Task",
		filters={
			"reference_doctype": reference_doctype,
			"reference_docname": reference_name,
			"pkx_task_type": "Follow-up",
			"status": ["not in", ["Done", "Canceled"]],
			"due_date": ["is", "set"],
		},
		fields=["due_date"],
		order_by="due_date asc",
		limit=1,
		ignore_permissions=True,
	)
	return rows[0].due_date if rows else None


def refresh_all_lifecycles():
	"""Daily: customers drift into Dormant without any document changing."""
	for name in frappe.get_all("Pakkmaxx Customer", filters={"disabled": 0}, pluck="name"):
		recompute_customer(name)
		frappe.db.commit()
