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


class TestContactActions(IntegrationTestCase):
	def test_external_whatsapp_button_removed_call_kept(self):
		import shutil
		import subprocess
		import tempfile

		from pakkmaxx_crm.setup import crm_ui

		name = "Pakkmaxx Contact Actions - CRM Lead"
		frappe.db.set_value("CRM Form Script", name, "script", crm_ui.PREV_CONTACT_ACTIONS_SCRIPT.format(cls="CRMLead"))
		crm_ui.setup_form_scripts()
		script = frappe.db.get_value("CRM Form Script", name, "script")
		self.assertNotIn("wa.me", script)
		self.assertIn("label: 'Call'", script)
		frappe.db.set_value("CRM Form Script", name, "script", "class CRMLead { /* edited by an administrator */ }")
		crm_ui.setup_form_scripts()
		self.assertIn("edited by an administrator", frappe.db.get_value("CRM Form Script", name, "script"))
		frappe.db.set_value("CRM Form Script", name, "script", crm_ui.CONTACT_ACTIONS_SCRIPT.format(cls="CRMLead"))
		node = shutil.which("node")
		if node:
			with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
				f.write(crm_ui.CONTACT_ACTIONS_SCRIPT.format(cls="CRMLead"))
			self.assertEqual(subprocess.run([node, "--check", f.name], capture_output=True).returncode, 0)


class TestSetPasswordAutofillFix(IntegrationTestCase):
	def test_fix_script_is_loaded_on_website_pages(self):
		import os

		self.assertIn("/assets/pakkmaxx_crm/js/update_password_autofill.js", frappe.get_hooks("web_include_js"))
		path = frappe.get_app_path("pakkmaxx_crm", "public", "js", "update_password_autofill.js")
		with open(path) as f:
			script = f.read()
		# re-runs Frappe's keyup-only check on input/change (autofill), only on the set-password page
		self.assertIn('"/update-password"', script)
		self.assertIn('addEventListener("input"', script)
		self.assertIn('addEventListener("change"', script)
		self.assertTrue(os.path.getsize(path) < 3000)
