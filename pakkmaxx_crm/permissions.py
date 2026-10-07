"""Record-level permissions for Pakkmaxx CRM.

Frappe CRM already restricts CRM Lead / CRM Deal (own + assigned, or the user's team when
the CRM Sales Hierarchy is enabled). Everything hanging off those records (notes, tasks,
call logs, contacts, organizations) is readable by every Sales User out of the box. These
hooks close that gap: a dependent record is visible only if the user can see the lead, deal
or customer it belongs to, or created it themselves.

Hooks are combined with Frappe CRM's using AND, so they can only narrow access.
"""

import frappe
from crm.permissions.org_hierarchy import _permission_query_conditions as crm_conditions

from pakkmaxx_crm.utils import is_crm_manager, is_unrestricted, team_members


def _esc(value: str) -> str:
	return frappe.db.escape(value)


def _in_list(values) -> str:
	return "(" + ", ".join(_esc(v) for v in values) + ")"


def _crm_visible_sql(doctype: str, user: str) -> str:
	"""SELECT returning names of CRM Lead / CRM Deal rows visible to `user`."""
	cond = crm_conditions(user, doctype)
	where = cond.get_sql(with_namespace=True, quote_char="`", secondary_quote_char="'") if cond else "1=1"
	return f"select `tab{doctype}`.name from `tab{doctype}` where {where}"


def visible_leads_sql(user: str) -> str:
	return _crm_visible_sql("CRM Lead", user)


def visible_deals_sql(user: str) -> str:
	return _crm_visible_sql("CRM Deal", user)


def _customer_condition(user: str, alias: str = "`tabPakkmaxx Customer`") -> str:
	team = _in_list(team_members(user))
	return (
		f"({alias}.sales_rep in {team} or {alias}.owner in {team}"
		f" or {alias}.name in (select _t.reference_name from `tabToDo` _t"
		f" where _t.reference_type = 'Pakkmaxx Customer' and _t.status != 'Cancelled'"
		f" and _t.allocated_to in {team})"
		f" or {alias}.name in (select _d.pkx_customer from `tabCRM Deal` _d where _d.pkx_customer is not null"
		f" and _d.name in ({visible_deals_sql(user)})))"
	)


def visible_customers_sql(user: str) -> str:
	if is_unrestricted(user):
		return "select name from `tabPakkmaxx Customer`"
	return (
		"select `tabPakkmaxx Customer`.name from `tabPakkmaxx Customer` where "
		+ _customer_condition(user)
	)


# ---------------------------------------------------------------------------
# permission_query_conditions
# ---------------------------------------------------------------------------


def customer_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	return _customer_condition(user)


def _reference_condition(table: str, user: str, extra: str = "") -> str:
	team = _in_list(team_members(user))
	parts = [
		f"{table}.owner in {team}",
		f"({table}.reference_doctype = 'CRM Lead' and {table}.reference_docname in ({visible_leads_sql(user)}))",
		f"({table}.reference_doctype = 'CRM Deal' and {table}.reference_docname in ({visible_deals_sql(user)}))",
		f"({table}.reference_doctype = 'Pakkmaxx Customer' and {table}.reference_docname in ({visible_customers_sql(user)}))",
	]
	if extra:
		parts.append(extra)
	return "(" + " or ".join(parts) + ")"


def note_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	return _reference_condition("`tabFCRM Note`", user)


def task_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	team = _in_list(team_members(user))
	return _reference_condition("`tabCRM Task`", user, f"`tabCRM Task`.assigned_to in {team}")


def call_log_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	team = _in_list(team_members(user))
	return _reference_condition(
		"`tabCRM Call Log`",
		user,
		f"`tabCRM Call Log`.caller in {team} or `tabCRM Call Log`.receiver in {team}",
	)


def contact_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	team = _in_list(team_members(user))
	deals = visible_deals_sql(user)
	return (
		f"(`tabContact`.owner in {team}"
		f" or `tabContact`.name in (select _c.contact from `tabCRM Contacts` _c"
		f" where _c.parenttype = 'CRM Deal' and _c.parent in ({deals}))"
		f" or `tabContact`.name in (select _pc.contact from `tabPakkmaxx Customer` _pc"
		f" where _pc.contact is not null and _pc.name in ({visible_customers_sql(user)})))"
	)


def organization_query(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return ""
	team = _in_list(team_members(user))
	return (
		f"(`tabCRM Organization`.owner in {team}"
		f" or `tabCRM Organization`.name in (select _d.organization from `tabCRM Deal` _d"
		f" where _d.organization is not null and _d.name in ({visible_deals_sql(user)}))"
		f" or `tabCRM Organization`.name in (select _pc.organization from `tabPakkmaxx Customer` _pc"
		f" where _pc.organization is not null and _pc.name in ({visible_customers_sql(user)})))"
	)


# ---------------------------------------------------------------------------
# has_permission (single document checks). Must return True to allow.
# ---------------------------------------------------------------------------


def _row_visible(doctype: str, name: str, condition: str) -> bool:
	if not condition:
		return True
	return bool(
		frappe.db.sql(
			f"select `tab{doctype}`.name from `tab{doctype}` where `tab{doctype}`.name = %s and {condition} limit 1",
			name,
		)
	)


def _is_new(doc) -> bool:
	return doc.is_new() if hasattr(doc, "is_new") else not doc.get("name")


def _reference_allows(doc, ptype: str, user: str) -> bool:
	ref_dt, ref_name = doc.get("reference_doctype"), doc.get("reference_docname")
	if not (ref_dt and ref_name):
		return True
	if ref_dt not in ("CRM Lead", "CRM Deal", "Pakkmaxx Customer"):
		return True
	return bool(frappe.has_permission(ref_dt, "read", ref_name, user=user))


def _dependent_permission(doc, ptype, user, query_fn) -> bool:
	user = user or frappe.session.user
	if is_unrestricted(user):
		return True
	if ptype == "create" or _is_new(doc):
		# a new note/task/call may only be attached to a record the user can see
		return _reference_allows(doc, ptype, user)
	return _row_visible(doc.doctype, doc.name, query_fn(user))


def note_permission(doc, ptype=None, user=None, debug=False):
	return _dependent_permission(doc, ptype, user, note_query)


def task_permission(doc, ptype=None, user=None, debug=False):
	return _dependent_permission(doc, ptype, user, task_query)


def call_log_permission(doc, ptype=None, user=None, debug=False):
	return _dependent_permission(doc, ptype, user, call_log_query)


def contact_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_unrestricted(user) or ptype == "create" or _is_new(doc):
		return True
	return _row_visible("Contact", doc.name, contact_query(user))


def organization_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_unrestricted(user) or ptype == "create" or _is_new(doc):
		return True
	return _row_visible("CRM Organization", doc.name, organization_query(user))


def customer_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_unrestricted(user) or ptype == "create" or _is_new(doc):
		return True
	return _row_visible("Pakkmaxx Customer", doc.name, customer_query(user))


# Pipeline / status / source configuration: everyone reads, only CRM managers change.
CONFIG_DOCTYPES = (
	"CRM Lead Status",
	"CRM Deal Status",
	"CRM Lead Source",
	"CRM Lost Reason",
	"CRM Industry",
	"CRM Territory",
	"CRM Communication Status",
)


def config_permission(doc, ptype=None, user=None, debug=False):
	if ptype in (None, "read", "select", "print", "email", "report", "export"):
		return True
	return is_crm_manager(user or frappe.session.user)
