# Copyright (c) 2026, Pakkmaxx and contributors
# For license information, please see license.txt

from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from pakkmaxx_crm.scoring import validate_rules


class PakkmaxxCRMSettings(Document):
	def validate(self):
		validate_rules(self)
		if cint(self.warm_threshold) > cint(self.hot_threshold):
			import frappe

			frappe.throw(_("Warm threshold cannot be above the Hot threshold"))
		self.default_country_code = (self.default_country_code or "233").strip().lstrip("+")

	def on_update(self):
		import frappe

		frappe.clear_document_cache(self.doctype, self.name)
