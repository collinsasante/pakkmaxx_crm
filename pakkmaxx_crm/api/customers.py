import frappe
from frappe import _

from pakkmaxx_crm.api import require
from pakkmaxx_crm.customers import ensure_customer_for_deal, recompute_customer


@frappe.whitelist(methods=["POST"])
def convert_to_customer(deal: str) -> str:
	"""Create or link the Pakkmaxx Customer for a won opportunity (idempotent)."""
	require("CRM Deal", deal, "write")
	doc = frappe.get_doc("CRM Deal", deal)
	if frappe.get_cached_value("CRM Deal Status", doc.status, "type") != "Won":
		frappe.throw(_("Only a won opportunity can be converted to a customer."))
	return ensure_customer_for_deal(doc)


@frappe.whitelist(methods=["POST"])
def create_opportunity(
	customer: str,
	deal_value: float | None = None,
	services: list[str] | str | None = None,
	expected_closure_date: str | None = None,
	next_step: str | None = None,
) -> str:
	"""New opportunity for an existing customer (repeat business)."""
	require("Pakkmaxx Customer", customer, "read")
	if not frappe.has_permission("CRM Deal", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if isinstance(services, str):
		services = frappe.parse_json(services) if services.strip().startswith("[") else [services]
	cust = frappe.get_doc("Pakkmaxx Customer", customer)
	deal = frappe.get_doc(
		{
			"doctype": "CRM Deal",
			"pkx_customer": customer,
			"organization": cust.organization,
			"lead_name": cust.customer_name,
			"deal_value": deal_value,
			"expected_closure_date": expected_closure_date,
			"next_step": next_step,
			"pkx_customer_type": cust.customer_type,
			"pkx_business_type": cust.business_type,
			"pkx_services": [{"service": s} for s in (services or []) if frappe.db.exists("Pakkmaxx Service", s)],
		}
	)
	deal.insert()
	recompute_customer(customer)
	return deal.name
