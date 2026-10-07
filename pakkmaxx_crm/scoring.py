"""Server-side lead scoring and qualification.

Scoring rules live in Pakkmaxx CRM Settings > Scoring Rules, so sales leadership can tune
them without code. Rules are evaluated with plain comparisons (no eval).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from pakkmaxx_crm.utils import get_settings

OPERATORS = (
	"is set",
	"is not set",
	"equals",
	"not equals",
	"greater than",
	"greater than or equal",
	"less than",
	"less than or equal",
	"in list",
)

# Each answered question counts equally towards the qualification score.
QUALIFICATION_QUESTIONS = (
	("pkx_is_genuine", "Is the lead genuine?"),
	("pkx_products_description", "What do they ship?"),
	("pkx_origin_city", "Where are they shipping from?"),
	("pkx_shipping_frequency", "Expected shipping frequency"),
	("pkx_volume", "Estimated volume (CBM or kg)"),
	("pkx_services", "Service they are interested in"),
	("pkx_budget", "Budget"),
	("pkx_expected_ship_date", "When they expect to ship"),
	("pkx_decision_maker", "Who makes the purchasing decision"),
)


def _is_set(value) -> bool:
	if isinstance(value, list):
		return bool(value)
	if isinstance(value, int | float):
		return value != 0
	return bool(value and str(value).strip())


def rule_matches(doc, rule) -> bool:
	value = doc.get(rule.fieldname)
	op = rule.operator
	expected = (rule.value or "").strip()
	if op == "is set":
		return _is_set(value)
	if op == "is not set":
		return not _is_set(value)
	if op in ("equals", "not equals"):
		if isinstance(value, int | float):
			same = flt(value) == flt(expected)
		else:
			same = str(value or "").strip().lower() == expected.lower()
		return same if op == "equals" else not same
	if op == "in list":
		options = {v.strip().lower() for v in expected.split(",") if v.strip()}
		return str(value or "").strip().lower() in options
	number, target = flt(value), flt(expected)
	return {
		"greater than": number > target,
		"greater than or equal": number >= target,
		"less than": number < target,
		"less than or equal": number <= target,
	}.get(op, False)


def calculate_lead_score(doc) -> tuple[int, list[str]]:
	settings = get_settings()
	score, reasons = 0, []
	for rule in settings.scoring_rules:
		if not rule.enabled:
			continue
		if rule_matches(doc, rule):
			score += cint(rule.points)
			reasons.append(f"{rule.label} ({cint(rule.points):+d})")
	return max(0, min(100, score)), reasons


def temperature_for(score: int) -> str:
	settings = get_settings()
	if score >= cint(settings.hot_threshold or 70):
		return "Hot"
	if score >= cint(settings.warm_threshold or 40):
		return "Warm"
	return "Cold"


def apply_lead_score(doc):
	if not cint(get_settings().enable_lead_scoring):
		return
	score, _reasons = calculate_lead_score(doc)
	doc.lead_score = score
	doc.lead_temperature = temperature_for(score)


def qualification_answers(doc) -> dict[str, bool]:
	answers = {}
	for fieldname, label in QUALIFICATION_QUESTIONS:
		if fieldname == "pkx_volume":
			answers[label] = bool(flt(doc.get("pkx_est_monthly_volume_cbm")) or flt(doc.get("pkx_est_monthly_weight_kg")))
		elif fieldname == "pkx_is_genuine":
			answers[label] = doc.get(fieldname) in ("Yes", "No")
		else:
			answers[label] = _is_set(doc.get(fieldname))
	return answers


def apply_qualification_score(doc):
	answers = qualification_answers(doc)
	doc.pkx_qualification_score = round(100 * sum(answers.values()) / len(answers), 1)


def validate_can_qualify(doc):
	"""Gate for moving a lead to Qualified."""
	settings = get_settings()
	missing = [q for q, ok in qualification_answers(doc).items() if not ok]
	minimum = flt(settings.min_qualification_score)
	if flt(doc.pkx_qualification_score) < minimum:
		frappe.throw(
			_("Qualification score is {0}%, the minimum is {1}%. Still unanswered: {2}").format(
				doc.pkx_qualification_score, minimum, ", ".join(missing)
			),
			title=_("Lead not qualified yet"),
		)
	if cint(settings.require_genuine_for_qualified) and doc.pkx_is_genuine != "Yes":
		frappe.throw(_("Confirm the lead is genuine (Genuine Lead? = Yes) before qualifying it."))


def validate_rules(settings):
	"""Called from Pakkmaxx CRM Settings.validate."""
	meta = frappe.get_meta("CRM Lead")
	for rule in settings.scoring_rules:
		if rule.operator not in OPERATORS:
			frappe.throw(_("Row {0}: unknown condition {1}").format(rule.idx, rule.operator))
		if not meta.has_field(rule.fieldname) and rule.fieldname not in ("name", "owner"):
			frappe.throw(
				_("Row {0}: {1} is not a field on CRM Lead").format(rule.idx, frappe.bold(rule.fieldname))
			)
		if rule.operator.startswith(("greater", "less")):
			try:
				float(rule.value)
			except (TypeError, ValueError):
				frappe.throw(_("Row {0}: {1} needs a number").format(rule.idx, rule.operator))
