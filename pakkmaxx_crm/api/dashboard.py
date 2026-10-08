"""Number-card endpoints for the Pakkmaxx CRM dashboard (Desk "Custom" number cards).

Each returns {"value", "fieldtype"} for the current user's permitted records.
"""

import frappe

from pakkmaxx_crm import reporting


def _filters(filters):
	return frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})


def _card(value, fieldtype="Int", route=None, route_options=None):
	out = {"value": value, "fieldtype": fieldtype}
	if fieldtype == "Currency":
		out["options"] = "GHS"
	if route:
		out["route"] = route
		out["route_options"] = route_options or {}
	return out


def _make(name, source, key, fieldtype="Int"):
	def endpoint(filters: dict | str | None = None) -> dict:
		data = source(_filters(filters))
		return _card(data.get(key, 0), fieldtype)

	endpoint.__name__ = name
	endpoint.__qualname__ = name
	globals()[name] = frappe.whitelist()(endpoint)


for _name, _source, _key, _ft in (
	("total_leads", reporting.lead_summary, "total", "Int"),
	("new_leads", reporting.lead_summary, "new", "Int"),
	("qualified_leads", reporting.lead_summary, "qualified", "Int"),
	("unassigned_leads", reporting.lead_summary, "unassigned", "Int"),
	("uncontacted_leads", reporting.lead_summary, "uncontacted", "Int"),
	("lead_conversion_rate", reporting.lead_summary, "conversion_rate", "Percent"),
	("open_opportunities", reporting.deal_summary, "open_count", "Int"),
	("won_opportunities", reporting.deal_summary, "won_count", "Int"),
	("lost_opportunities", reporting.deal_summary, "lost_count", "Int"),
	("pipeline_value", reporting.deal_summary, "pipeline_value", "Currency"),
	("weighted_pipeline", reporting.deal_summary, "weighted_value", "Currency"),
	("won_value", reporting.deal_summary, "won_value", "Currency"),
	("average_deal_value", reporting.deal_summary, "avg_deal_value", "Currency"),
	("win_rate", reporting.deal_summary, "win_rate", "Percent"),
	("active_customers", reporting.customer_summary, "active", "Int"),
	("dormant_customers", reporting.customer_summary, "dormant", "Int"),
	("average_days_to_convert", reporting.customer_summary, "avg_days_to_convert", "Float"),
):
	_make(_name, _source, _key, _ft)


@frappe.whitelist()
def todays_follow_ups(filters: dict | str | None = None) -> dict:
	return _card(reporting.follow_up_summary()["today"])


@frappe.whitelist()
def overdue_follow_ups(filters: dict | str | None = None) -> dict:
	return _card(reporting.follow_up_summary()["overdue"])


@frappe.whitelist()
def upcoming_follow_ups(filters: dict | str | None = None) -> dict:
	return _card(reporting.follow_up_summary()["upcoming"])


@frappe.whitelist()
def summary() -> dict:
	"""Everything at once, for API clients (e.g. a future mobile app)."""
	return {
		"leads": reporting.lead_summary(),
		"opportunities": reporting.deal_summary(),
		"customers": reporting.customer_summary(),
		"follow_ups": reporting.follow_up_summary(),
		"my_follow_ups": reporting.follow_up_summary(frappe.session.user),
	}


def _ai_count(filters: dict) -> int:
	return len(frappe.get_list("CRM Lead", filters=filters, pluck="name", limit_page_length=0))


@frappe.whitelist()
def ai_qualified_leads(filters: dict | str | None = None) -> dict:
	return _card(_ai_count({"pkx_ai_effective_classification": "Qualified"}))


@frappe.whitelist()
def ai_high_value_leads(filters: dict | str | None = None) -> dict:
	return _card(_ai_count({"pkx_ai_effective_classification": "High Value"}))


@frappe.whitelist()
def ai_pending_analyses(filters: dict | str | None = None) -> dict:
	return _card(_ai_count({"pkx_ai_status": "Pending"}))


@frappe.whitelist()
def ai_override_rate(filters: dict | str | None = None) -> dict:
	analysed = frappe.get_list("CRM Lead", filters={"pkx_ai_status": "Analysed"},
		fields=["pkx_ai_classification", "pkx_ai_human_classification"], limit_page_length=0)
	changed = [l for l in analysed if l.pkx_ai_human_classification and l.pkx_ai_human_classification != l.pkx_ai_classification]
	return _card(round(100 * len(changed) / len(analysed), 1) if analysed else 0, "Percent")


@frappe.whitelist()
def ai_failed_analyses(filters: dict | str | None = None) -> dict:
	since = frappe.utils.add_days(frappe.utils.now_datetime(), -7)
	return _card(len(frappe.get_list("Pakkmaxx AI Qualification", filters={"status": "Failed", "creation": [">=", since]},
		pluck="name", limit_page_length=0)))
