"""Authenticated JSON API for Pakkmaxx CRM.

Every endpoint requires a logged-in user or API key/secret (no guest access) and checks
Frappe permissions on the records it touches. Standard REST (/api/resource/...) also works
and is subject to the same record-level permission rules.
"""

import frappe
from frappe import _

LINKABLE = ("CRM Lead", "CRM Deal", "Pakkmaxx Customer")


def require(doctype: str, name: str, ptype: str = "read"):
	if doctype not in LINKABLE:
		frappe.throw(_("Unsupported record type {0}").format(doctype))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} not found").format(_(doctype), name), frappe.DoesNotExistError)
	if not frappe.has_permission(doctype, ptype, name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
