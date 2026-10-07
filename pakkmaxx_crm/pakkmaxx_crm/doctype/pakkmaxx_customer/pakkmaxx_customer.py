# Copyright (c) 2026, Pakkmaxx and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from pakkmaxx_crm.duplicates import find_duplicates
from pakkmaxx_crm.events.common import guard_owner_field, protect_fields
from pakkmaxx_crm.utils import normalize_email, normalize_phone

# Maintained by pakkmaxx_crm.customers.recompute_customer, never by users.
COMPUTED_FIELDS = (
	"lifecycle_stage",
	"source",
	"campaign",
	"original_lead",
	"first_deal",
	"lead_created_on",
	"days_to_convert",
	"first_won_on",
	"last_won_on",
	"won_deals_count",
	"open_deals_count",
	"lifetime_value",
	"last_activity_on",
	"next_follow_up_on",
	"portal_user",
)


class PakkmaxxCustomer(Document):
	def validate(self):
		for field in ("mobile_no", "whatsapp_no"):
			if self.get(field):
				self.set(field, normalize_phone(self.get(field)))
		self.email = normalize_email(self.email)
		if not self.whatsapp_no and self.mobile_no:
			self.whatsapp_no = self.mobile_no

		protect_fields(self, COMPUTED_FIELDS)
		guard_owner_field(self, "sales_rep", _("Sales Representative"))
		self.validate_duplicates()

	def validate_duplicates(self):
		"""One customer per phone number / email."""
		if self.flags.get("pkx_skip_duplicate_check"):
			return
		if not self.is_new() and not any(
			self.has_value_changed(f) for f in ("mobile_no", "whatsapp_no", "email")
		):
			return
		matches = [
			m
			for m in find_duplicates(
				mobile_no=self.mobile_no,
				whatsapp_no=self.whatsapp_no,
				email=self.email,
				exclude=None if self.is_new() else ("Pakkmaxx Customer", self.name),
			)
			if m["doctype"] == "Pakkmaxx Customer"
		]
		if matches:
			frappe.throw(
				_("A customer with this phone number or email already exists: {0}").format(
					", ".join(frappe.bold(m["name"]) for m in matches)
				),
				title=_("Duplicate customer"),
				exc=frappe.DuplicateEntryError,
			)

	def on_update(self):
		if self.has_value_changed("sales_rep") and self.sales_rep:
			from frappe.desk.form.assign_to import _add as assign

			if not frappe.db.exists(
				"ToDo",
				{"reference_type": self.doctype, "reference_name": self.name, "allocated_to": self.sales_rep,
					"status": "Open"},
			):
				assign({"assign_to": [self.sales_rep], "doctype": self.doctype, "name": self.name},
					ignore_permissions=True)
