"""End-to-end CRM workflows: WhatsApp lead -> customer, lost, unqualified, repeat business."""

import frappe
from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal
from frappe.utils import add_to_date, now_datetime

from pakkmaxx_crm.api.activities import get_timeline, log_interaction
from pakkmaxx_crm.api.customers import create_opportunity
from pakkmaxx_crm.api.followups import create_follow_up, my_follow_ups
from pakkmaxx_crm.api.leads import capture_lead
from pakkmaxx_crm.followups import send_due_reminders
from pakkmaxx_crm.tests.utils import CRM_MANAGER, REP_A, PakkmaxxTestCase, as_user, random_mobile


class TestLeadToCustomer(PakkmaxxTestCase):
	def test_whatsapp_lead_to_repeat_customer(self):
		mobile = random_mobile()

		# 1. A WhatsApp enquiry arrives through the integration API (as the CRM manager's API user)
		as_user(CRM_MANAGER)
		result = capture_lead(first_name="Abena", last_name="Owusu", whatsapp_no=mobile, source="WhatsApp",
			message="Hi, how much to ship 2 CBM of clothing from Guangzhou?", services=["Sea Freight"])
		self.assertTrue(result["created"])
		lead = frappe.get_doc("CRM Lead", result["name"])
		self.assertEqual(lead.source, "WhatsApp")
		self.assertTrue(lead.pkx_whatsapp_no.startswith("+233"), lead.pkx_whatsapp_no)
		self.assertEqual(lead.mobile_no, lead.pkx_whatsapp_no)
		self.assertFalse(lead.lead_owner, "integration leads arrive unassigned")
		self.assertEqual(lead.status, "New")
		self.assertGreater(lead.lead_score, 0)

		# capturing the same number again does not create a duplicate
		again = capture_lead(first_name="Abena", whatsapp_no=mobile, source="WhatsApp")
		self.assertFalse(again["created"])
		self.assertEqual(again["name"], lead.name)

		# 2. Manager assigns the lead to a salesperson
		lead.lead_owner = REP_A
		lead.save()
		self.assertTrue(frappe.db.exists("ToDo", {"reference_name": lead.name, "allocated_to": REP_A,
			"status": "Open"}))

		# 3. Salesperson contacts the customer on WhatsApp and logs it
		as_user(REP_A)
		log_interaction("CRM Lead", lead.name, "Sent sea freight rates. She ships monthly.",
			"WhatsApp Conversation")
		lead.reload()
		self.assertEqual(lead.status, "Contacted", "first logged contact moves New -> Contacted")
		self.assertIsNotNone(lead.pkx_first_contacted_on)
		self.assertEqual(lead.pkx_lifecycle_stage, "Prospect")

		# 4. Qualification is enforced
		lead.status = "Qualified"
		self.assertRaises(frappe.ValidationError, lead.save)
		lead.reload()
		lead.pkx_requested_quote = 1
		lead.pkx_responds_on_whatsapp = 1
		self.qualify(lead)
		self.assertEqual(lead.status, "Qualified")
		self.assertGreaterEqual(lead.pkx_qualification_score, 60)
		self.assertIn(lead.lead_temperature, ("Warm", "Hot"))

		# 5. Follow-up with reminder
		due = add_to_date(now_datetime(), minutes=20).replace(microsecond=0)
		task = create_follow_up("CRM Lead", lead.name, "Send sea freight rate", str(due), "High")
		lead.reload()
		self.assertEqual(str(lead.pkx_next_follow_up_on), str(due))
		self.assertEqual(lead.pkx_next_action, "Send sea freight rate")
		buckets = my_follow_ups()
		# "in 20 minutes" can fall on tomorrow when the suite runs just before midnight
		bucket = "today" if due.date() == frappe.utils.getdate() else "upcoming"
		self.assertIn(task, [t.name for t in buckets[bucket]])

		as_user("Administrator")
		send_due_reminders()  # reminder time (due - 30 min) has passed
		self.assertTrue(frappe.db.exists("CRM Notification", {"to_user": REP_A, "notification_type_doc": task}))
		self.assertTrue(frappe.db.get_value("CRM Task", task, "pkx_reminder_sent"))

		# 6. Convert to an opportunity
		as_user(REP_A)
		deal_name = convert_to_deal(lead=lead.name)
		deal = frappe.get_doc("CRM Deal", deal_name)
		lead.reload()
		self.assertEqual(lead.status, "Converted")
		self.assertEqual(deal.source, "WhatsApp")
		self.assertEqual(deal.pkx_whatsapp_no, lead.pkx_whatsapp_no)
		self.assertEqual([s.service for s in deal.pkx_services], ["Sea Freight"])
		self.assertEqual(deal.deal_owner, REP_A)
		self.assertIsNotNone(deal.pkx_first_contacted_on)

		# 7. Move through the pipeline; probability follows the stage
		for stage, probability in (("Requirement Collected", 25), ("Quote/Proposal", 50), ("Negotiation", 70)):
			deal.status = stage
			deal.deal_value = 12000
			deal.save()
			self.assertEqual(deal.probability, probability)
			self.assertEqual(deal.pkx_weighted_value, 12000 * probability / 100)

		deal.status = "Won"
		deal.deal_value = 0
		self.assertRaises(frappe.ValidationError, deal.save)
		deal.reload()
		deal.status = "Won"
		deal.deal_value = 15000
		deal.save()
		deal.reload()

		# 8. Customer created, retains source / rep / lead / history
		self.assertTrue(deal.pkx_customer)
		customer = frappe.get_doc("Pakkmaxx Customer", deal.pkx_customer)
		self.assertEqual(customer.source, "WhatsApp")
		self.assertEqual(customer.sales_rep, REP_A)
		self.assertEqual(customer.original_lead, lead.name)
		self.assertEqual(customer.first_deal, deal.name)
		self.assertEqual(customer.won_deals_count, 1)
		self.assertEqual(customer.lifetime_value, 15000)
		self.assertEqual(customer.lifecycle_stage, "Active Customer")
		self.assertEqual(frappe.db.get_value("CRM Lead", lead.name, "pkx_customer"), customer.name)

		timeline = get_timeline("Pakkmaxx Customer", customer.name)
		kinds = {i["kind"] for i in timeline}
		self.assertIn("note", kinds, "WhatsApp conversation from the lead is in the customer history")
		self.assertIn("task", kinds)
		self.assertIn("change", kinds)

		# 9. Existing customer -> new opportunity -> won => repeat customer
		new_deal = create_opportunity(customer.name, deal_value=9000, services=["Air Freight"])
		d2 = frappe.get_doc("CRM Deal", new_deal)
		self.assertEqual(d2.source, "Existing Customer")
		self.assertEqual(d2.pkx_whatsapp_no, customer.whatsapp_no)
		d2.status = "Won"
		d2.save()
		customer.reload()
		self.assertEqual(customer.won_deals_count, 2)
		self.assertEqual(customer.lifetime_value, 24000)
		self.assertEqual(customer.lifecycle_stage, "Repeat Customer")
		self.assertEqual(frappe.db.count("Pakkmaxx Customer", {"mobile_no": customer.mobile_no}), 1)

	def test_lead_lost(self):
		lead = self.new_lead()
		lead.status = "Lost"
		self.assertRaises(frappe.ValidationError, lead.save)  # lost reason required
		lead.reload()
		lead.status = "Lost"
		lead.lost_reason = "Price too high"
		lead.save()
		self.assertEqual(lead.pkx_lifecycle_stage, "Lost")
		# a lost lead cannot be converted
		self.assertRaises(frappe.ValidationError, convert_to_deal, lead=lead.name)

	def test_lead_unqualified(self):
		lead = self.new_lead()
		lead.status = "Unqualified"
		self.assertRaises(frappe.ValidationError, lead.save)  # reason required
		lead.reload()
		lead.status = "Unqualified"
		lead.pkx_unqualified_reason = "Only wants a one-off personal parcel under 1kg"
		lead.save()
		self.assertEqual(lead.status, "Unqualified")
		# reps cannot reopen; managers can
		lead.status = "Contacted"
		self.assertRaises(frappe.ValidationError, lead.save)
		as_user(CRM_MANAGER)
		lead = frappe.get_doc("CRM Lead", lead.name)
		lead.status = "Contacted"
		lead.save()
		self.assertEqual(lead.status, "Contacted")

	def test_workflow_blocks_skipping_stages(self):
		lead = self.new_lead()
		lead.status = "Negotiation"
		self.assertRaises(frappe.ValidationError, lead.save)
		lead.reload()
		lead.status = "Converted"
		self.assertRaises(frappe.ValidationError, lead.save)
