import frappe
from frappe.tests import UnitTestCase

from pakkmaxx_crm.scoring import calculate_lead_score, rule_matches, temperature_for
from pakkmaxx_crm.utils import normalize_email, normalize_phone, whatsapp_link


class TestNormalisation(UnitTestCase):
	def test_ghana_numbers(self):
		for raw in ("0241234567", "024 123 4567", "024-123-4567", "+233 24 123 4567", "233241234567",
				"00233241234567", "241234567", "(024) 123 4567"):
			self.assertEqual(normalize_phone(raw, "233"), "+233241234567", raw)

	def test_international_numbers_kept(self):
		self.assertEqual(normalize_phone("+86 138 0013 8000", "233"), "+8613800138000")
		self.assertEqual(normalize_phone("008613800138000", "233"), "+8613800138000")

	def test_garbage_is_left_alone(self):
		self.assertEqual(normalize_phone("call me", "233"), "call me")
		self.assertEqual(normalize_phone("12", "233"), "12")
		self.assertIsNone(normalize_phone(None))

	def test_email_and_whatsapp_link(self):
		self.assertEqual(normalize_email("  Ama.Mensah@Example.COM "), "ama.mensah@example.com")
		self.assertEqual(whatsapp_link("024 123 4567"), "https://wa.me/233241234567")


class TestScoring(UnitTestCase):
	def rule(self, fieldname, operator, value="", points=10):
		return frappe._dict(enabled=1, label=fieldname, fieldname=fieldname, operator=operator, value=value,
			points=points)

	def test_operators(self):
		doc = frappe._dict(pkx_requested_quote=1, pkx_customer_type="Business", pkx_est_monthly_volume_cbm=6,
			pkx_shipping_frequency="Weekly", email="", pkx_services=[{"service": "Air Freight"}])
		self.assertTrue(rule_matches(doc, self.rule("pkx_requested_quote", "equals", "1")))
		self.assertTrue(rule_matches(doc, self.rule("pkx_customer_type", "equals", "business")))
		self.assertTrue(rule_matches(doc, self.rule("pkx_est_monthly_volume_cbm", "greater than or equal", "5")))
		self.assertFalse(rule_matches(doc, self.rule("pkx_est_monthly_volume_cbm", "less than", "5")))
		self.assertTrue(rule_matches(doc, self.rule("pkx_shipping_frequency", "in list", "Monthly, Weekly")))
		self.assertTrue(rule_matches(doc, self.rule("email", "is not set")))
		self.assertTrue(rule_matches(doc, self.rule("pkx_services", "is set")))

	def test_score_is_capped_and_graded(self):
		settings = frappe.get_single("Pakkmaxx CRM Settings")
		doc = frappe._dict({r.fieldname: 1 for r in settings.scoring_rules})
		doc.update(mobile_no="+233241234567", pkx_whatsapp_no="+233241234567", email="a@b.co",
			pkx_customer_type="Business", pkx_shipping_frequency="Weekly", pkx_est_monthly_volume_cbm=10,
			pkx_est_monthly_spend=50000)
		score, reasons = calculate_lead_score(doc)
		self.assertEqual(score, 100)
		self.assertTrue(reasons)
		self.assertEqual(temperature_for(100), "Hot")
		self.assertEqual(temperature_for(0), "Cold")
