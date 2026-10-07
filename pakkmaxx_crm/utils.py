import re

import frappe
from frappe.utils.caching import request_cache

# Roles allowed to see and manage every CRM record. "Sales Manager" outside the
# CRM Sales Hierarchy also sees everything (Frappe CRM's own rule), see is_unrestricted().
ADMIN_ROLES = {"System Manager", "CRM Administrator"}
MANAGER_ROLES = ADMIN_ROLES | {"CRM Manager"}

# CRM records whose ownership and assignment Pakkmaxx guards.
GUARDED_DOCTYPES = ("CRM Lead", "CRM Deal", "Pakkmaxx Customer")


def get_settings():
	return frappe.get_cached_doc("Pakkmaxx CRM Settings")


@request_cache
def roles_of(user: str) -> set:
	return set(frappe.get_roles(user))


def is_admin(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(roles_of(user) & ADMIN_ROLES)


def is_crm_manager(user: str | None = None) -> bool:
	"""CRM Manager / Administrator: may assign, reassign and configure the CRM."""
	user = user or frappe.session.user
	return user == "Administrator" or bool(roles_of(user) & MANAGER_ROLES)


@request_cache
def in_sales_hierarchy(user: str) -> bool:
	return bool(frappe.db.exists("CRM Sales Hierarchy", {"user": user}))


def is_team_manager(user: str | None = None) -> bool:
	"""A Sales Manager placed in the CRM Sales Hierarchy: manages the users below them."""
	user = user or frappe.session.user
	return "Sales Manager" in roles_of(user) and in_sales_hierarchy(user)


def is_unrestricted(user: str | None = None) -> bool:
	"""Sees every CRM record. Mirrors crm.permissions.org_hierarchy so both apps agree."""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in roles_of(user):
		return True
	if is_crm_manager(user):
		return True
	if "Sales Manager" in roles_of(user):
		hierarchy_on = frappe.db.get_single_value("FCRM Settings", "enable_sales_hierarchy")
		return not (hierarchy_on and in_sales_hierarchy(user))
	return False


def can_assign_records(user: str | None = None) -> bool:
	"""Who may assign or reassign leads, opportunities and customers to other users."""
	user = user or frappe.session.user
	return is_crm_manager(user) or "Sales Manager" in roles_of(user)


@request_cache
def team_members(user: str) -> list[str]:
	"""Users in `user`'s subtree of the CRM Sales Hierarchy, including `user`."""
	node = frappe.db.get_value("CRM Sales Hierarchy", {"user": user}, ["lft", "rgt"], as_dict=True)
	if not node:
		return [user]
	members = frappe.get_all(
		"CRM Sales Hierarchy",
		filters={"lft": [">=", node.lft], "rgt": ["<=", node.rgt]},
		pluck="user",
	)
	return list({user, *[m for m in members if m]})


def can_manage_user_records(target_user: str | None, user: str | None = None) -> bool:
	"""May `user` hand a record to (or take it from) `target_user`?"""
	user = user or frappe.session.user
	if is_unrestricted(user) and can_assign_records(user):
		return True
	if is_team_manager(user):
		return not target_user or target_user in team_members(user)
	return False


# ---------------------------------------------------------------------------
# Phone / email normalisation
# ---------------------------------------------------------------------------

_NON_DIGITS = re.compile(r"[^\d+]")


def normalize_phone(value: str | None, default_cc: str | None = None) -> str | None:
	"""Normalise a phone number to E.164-like `+<cc><number>`.

	Ghana is the default: 0241234567 -> +233241234567, 241234567 -> +233241234567,
	233241234567 -> +233241234567, 00233... -> +233.... Numbers already in
	international form (e.g. Chinese suppliers +86...) are kept.
	Values that do not look like phone numbers are returned stripped, unchanged.
	"""
	if not value:
		return value
	raw = str(value).strip()
	cleaned = _NON_DIGITS.sub("", raw)
	if cleaned.count("+") > 1 or ("+" in cleaned and not cleaned.startswith("+")):
		return raw
	digits = cleaned.lstrip("+")
	if not digits or len(digits) < 7 or len(digits) > 15:
		return raw

	if cleaned.startswith("+"):
		return "+" + digits
	if digits.startswith("00"):
		return "+" + digits[2:]

	cc = (default_cc or _default_cc()).lstrip("+")
	if digits.startswith(cc) and len(digits) >= len(cc) + 8:
		return "+" + digits
	if digits.startswith("0"):
		return "+" + cc + digits[1:]
	if cc == "233" and len(digits) == 9:
		return "+233" + digits
	return "+" + digits if len(digits) > 10 else raw


def _default_cc() -> str:
	try:
		return (get_settings().default_country_code or "233").strip()
	except Exception:
		return "233"


def normalize_email(value: str | None) -> str | None:
	if not value:
		return value
	return str(value).strip().lower()


def whatsapp_link(number: str | None) -> str | None:
	"""wa.me click-to-chat URL for a number (digits only, no +)."""
	number = normalize_phone(number)
	if not number or not number.startswith("+"):
		return None
	return "https://wa.me/" + number.lstrip("+")
