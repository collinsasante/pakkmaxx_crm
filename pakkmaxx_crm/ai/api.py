"""Whitelisted endpoints for the lead page. Browser -> Frappe only; the AI key never leaves the server."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from pakkmaxx_crm.ai.service import ACTIVE, DOCTYPE, ai_enabled, queue_analysis

HISTORY_FIELDS = [
	"name", "status", "trigger", "classification", "score", "confidence", "intent", "service_interest",
	"product_category", "origin", "destination", "quantity", "estimated_volume", "expected_shipping_date",
	"estimated_value", "buying_signals", "negative_signals", "missing_information", "recommended_next_action",
	"summary", "evidence", "model", "analyzed_at", "creation", "error", "messages_analyzed", "requested_by",
]


def _check(lead: str, ptype: str):
	if not frappe.db.exists("CRM Lead", lead):
		frappe.throw(_("Lead not found"), frappe.DoesNotExistError)
	if not frappe.has_permission("CRM Lead", ptype, lead):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def analyze_lead(lead: str, reanalyze: bool = False) -> dict:
	"""Analyze Lead / Re-analyse buttons. Anyone who may edit the lead may request it."""
	_check(lead, "write")
	if not ai_enabled():
		return {"queued": False, "message": _("AI qualification is turned off in Pakkmaxx CRM Settings")}
	reanalyze = frappe.utils.sbool(reanalyze)
	record = queue_analysis(lead, "Re-analyse" if reanalyze else "Manual", force=reanalyze, requested_by=frappe.session.user)
	return {"queued": True, "record": record}


@frappe.whitelist()
def get_ai_panel(lead: str) -> dict:
	"""Latest analysis + history for the lead page. Read access to the lead is enough."""
	_check(lead, "read")
	history = frappe.get_all(DOCTYPE, filters={"lead": lead}, fields=HISTORY_FIELDS, order_by="creation desc", limit=20)
	lead_doc = frappe.db.get_value(
		"CRM Lead",
		lead,
		["pkx_ai_human_classification", "pkx_ai_human_score", "pkx_ai_override_reason", "pkx_ai_overridden_by",
			"pkx_ai_overridden_on", "pkx_ai_status", "pkx_ai_effective_classification"],
		as_dict=True,
	)
	return {
		"enabled": ai_enabled(),
		"pending": any(h.status in ACTIVE for h in history),
		"latest": next((h for h in history if h.status == "Completed"), None),
		"history": history,
		"override": lead_doc,
		"can_write": bool(frappe.has_permission("CRM Lead", "write", lead)),
	}


@frappe.whitelist(methods=["POST"])
def create_follow_up_from_ai(lead: str, due: str | None = None) -> dict:
	"""A salesperson accepts the AI's recommended next action as a follow-up task (assigned to themselves).
	The AI never creates tasks on its own."""
	from pakkmaxx_crm.api.followups import create_follow_up

	_check(lead, "write")
	latest = frappe.db.get_value(
		DOCTYPE, {"lead": lead, "status": "Completed"}, ["name", "recommended_next_action"], as_dict=True,
		order_by="analyzed_at desc",
	)
	if not latest or not latest.recommended_next_action:
		frappe.throw(_("There is no AI recommendation for this lead yet"))
	due = due or f"{frappe.utils.add_days(frappe.utils.nowdate(), 1)} 10:00:00"
	task = create_follow_up("CRM Lead", lead, latest.recommended_next_action[:140], due, "Medium",
		notes=_("Suggested by AI analysis {0}").format(latest.name))
	return {"task": task, "title": latest.recommended_next_action[:140]}
