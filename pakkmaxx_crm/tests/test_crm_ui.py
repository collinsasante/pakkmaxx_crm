import frappe
from frappe.tests import IntegrationTestCase

from pakkmaxx_crm.setup.crm_ui import use_exact_timestamps


class TestCRMTimestamps(IntegrationTestCase):
	def test_crm_shows_exact_timestamps_after_setup(self):
		frappe.db.set_single_value("FCRM Settings", "crm_timeline_timestamp_format", "Relative")
		use_exact_timestamps()
		self.assertEqual(frappe.db.get_single_value("FCRM Settings", "crm_timeline_timestamp_format"), "Exact")
		use_exact_timestamps()  # idempotent
		self.assertEqual(frappe.db.get_single_value("FCRM Settings", "crm_timeline_timestamp_format"), "Exact")

	def test_setup_on_migrate_does_not_override_an_administrator_choice(self):
		from pakkmaxx_crm.install import setup

		frappe.db.set_single_value("FCRM Settings", "crm_timeline_timestamp_format", "Relative")
		setup()
		self.assertEqual(frappe.db.get_single_value("FCRM Settings", "crm_timeline_timestamp_format"), "Relative")
