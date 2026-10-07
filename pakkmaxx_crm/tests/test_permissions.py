"""Every role, tested independently. All checks go through the server (has_permission,
get_list, document save, whitelisted API), never through UI visibility."""

import frappe
from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal
from frappe.desk.form.assign_to import add as assign

from pakkmaxx_crm.api.activities import get_timeline, log_interaction
from pakkmaxx_crm.api.customers import create_opportunity
from pakkmaxx_crm.api.followups import create_follow_up
from pakkmaxx_crm.tests.utils import (
	ADMIN,
	CRM_MANAGER,
	READ_ONLY,
	REP_A,
	REP_B,
	TEAM_MANAGER,
	PakkmaxxTestCase,
	as_user,
	random_mobile,
)


class TestRolePermissions(PakkmaxxTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Rep A: a lead with a note and a follow-up, converted and won (=> deal, contact, customer)
		as_user(REP_A)
		lead_a = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Kofi", "last_name": "A",
			"mobile_no": random_mobile(), "source": "Facebook", "organization": "Kofi Imports A"}).insert()
		cls.note_a = log_interaction("CRM Lead", lead_a.name, "Asked for air freight rates", "WhatsApp Conversation")
		cls.task_a = create_follow_up("CRM Lead", lead_a.name, "Call back", frappe.utils.add_days(frappe.utils.now(), 1))
		cls.lead_a_open = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Yaw", "mobile_no": random_mobile(),
			"source": "TikTok"}).insert().name
		cls.deal_a = convert_to_deal(lead=lead_a.name)
		deal = frappe.get_doc("CRM Deal", cls.deal_a)
		deal.status = "Won"
		deal.deal_value = 5000
		deal.save()
		cls.customer_a = frappe.db.get_value("CRM Deal", cls.deal_a, "pkx_customer")
		cls.contact_a = frappe.db.get_value("Pakkmaxx Customer", cls.customer_a, "contact")
		cls.org_a = frappe.db.get_value("CRM Deal", cls.deal_a, "organization")
		cls.lead_a = lead_a.name

		# Rep B: their own lead
		as_user(REP_B)
		cls.lead_b = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Esi", "mobile_no": random_mobile(),
			"source": "Instagram"}).insert().name
		as_user("Administrator")

	# --- Sales Representative ------------------------------------------------------

	def test_rep_cannot_see_another_reps_records(self):
		as_user(REP_B)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead_a))
		self.assertFalse(frappe.has_permission("CRM Deal", "read", self.deal_a))
		self.assertFalse(frappe.has_permission("Pakkmaxx Customer", "read", self.customer_a))
		self.assertFalse(frappe.has_permission("FCRM Note", "read", self.note_a))
		self.assertFalse(frappe.has_permission("CRM Task", "read", self.task_a))
		self.assertFalse(frappe.has_permission("Contact", "read", self.contact_a))
		self.assertFalse(frappe.has_permission("CRM Organization", "read", self.org_a))

		self.assertNotIn(self.lead_a, frappe.get_list("CRM Lead", pluck="name"))
		self.assertNotIn(self.note_a, frappe.get_list("FCRM Note", pluck="name"))
		self.assertNotIn(self.task_a, frappe.get_list("CRM Task", pluck="name"))
		self.assertNotIn(self.customer_a, frappe.get_list("Pakkmaxx Customer", pluck="name"))
		self.assertNotIn(self.contact_a, frappe.get_list("Contact", pluck="name"))
		self.assertIn(self.lead_b, frappe.get_list("CRM Lead", pluck="name"))

		# direct document access and API access are refused too
		self.assertRaises(frappe.PermissionError, get_timeline, "CRM Lead", self.lead_a)
		self.assertRaises(frappe.PermissionError, get_timeline, "Pakkmaxx Customer", self.customer_a)
		self.assertRaises(frappe.PermissionError, log_interaction, "CRM Lead", self.lead_a, "sneaky note")
		self.assertRaises(frappe.PermissionError, create_follow_up, "CRM Lead", self.lead_a, "x",
			frappe.utils.now())

	def test_rep_sees_own_records(self):
		as_user(REP_A)
		for doctype, name in (("CRM Lead", self.lead_a), ("CRM Deal", self.deal_a),
				("Pakkmaxx Customer", self.customer_a), ("FCRM Note", self.note_a), ("CRM Task", self.task_a),
				("Contact", self.contact_a)):
			self.assertTrue(frappe.has_permission(doctype, "read", name), f"{doctype} {name}")
		self.assertTrue(frappe.has_permission("CRM Lead", "write", self.lead_a_open))

	def test_rep_cannot_reassign_or_take_ownership(self):
		as_user(REP_A)
		lead = frappe.get_doc("CRM Lead", self.lead_a_open)
		lead.lead_owner = REP_B
		self.assertRaises(frappe.PermissionError, lead.save)

		self.assertRaises(frappe.PermissionError, assign,
			{"assign_to": [REP_B], "doctype": "CRM Lead", "name": self.lead_a_open})

		deal = frappe.get_doc("CRM Deal", self.deal_a)
		deal.deal_owner = REP_B
		self.assertRaises(frappe.PermissionError, deal.save)

		# a new lead cannot be created "for" someone else
		self.assertRaises(frappe.PermissionError, frappe.get_doc({"doctype": "CRM Lead", "first_name": "X",
			"mobile_no": random_mobile(), "lead_owner": REP_B}).insert)

		# nor can a rep assign follow-ups to colleagues
		self.assertRaises(frappe.PermissionError, create_follow_up, "CRM Lead", self.lead_a_open, "x",
			frappe.utils.now(), assigned_to=REP_B)

	def test_rep_cannot_reopen_won_deal_or_tamper_values(self):
		as_user(REP_A)
		deal = frappe.get_doc("CRM Deal", self.deal_a)
		deal.status = "Negotiation"
		self.assertRaises(frappe.PermissionError, deal.save)

		deal.reload()
		deal.pkx_weighted_value = 999999
		deal.pkx_won_on = "2020-01-01 00:00:00"
		deal.save()
		deal.reload()
		self.assertEqual(deal.pkx_weighted_value, 5000)
		self.assertNotEqual(str(deal.pkx_won_on), "2020-01-01 00:00:00")

		lead = frappe.get_doc("CRM Lead", self.lead_a_open)
		lead.lead_score = 100
		lead.pkx_customer = self.customer_a
		lead.save()
		lead.reload()
		self.assertNotEqual(lead.lead_score, 100)
		self.assertFalse(lead.pkx_customer)

	def test_rep_cannot_attach_deal_to_hidden_customer(self):
		as_user(REP_B)
		self.assertRaises(frappe.PermissionError, create_opportunity, self.customer_a, deal_value=100)
		deal = frappe.get_doc({"doctype": "CRM Deal", "organization": None, "pkx_customer": self.customer_a})
		self.assertRaises(frappe.PermissionError, deal.insert)

	def test_rep_cannot_change_pipeline_configuration(self):
		as_user(REP_A)
		status = frappe.get_doc("CRM Deal Status", "Won")
		status.probability = 50
		self.assertRaises(frappe.PermissionError, status.save)
		self.assertRaises(frappe.PermissionError, frappe.get_doc(
			{"doctype": "CRM Lead Status", "lead_status": "Hacked", "type": "Open"}).insert)
		self.assertFalse(frappe.has_permission("Pakkmaxx CRM Settings", "write"))

	def test_user_cannot_change_own_roles(self):
		as_user(REP_A)
		user = frappe.get_doc("User", REP_A)
		user.append("roles", {"role": "System Manager"})
		try:
			user.save()
		except (frappe.PermissionError, frappe.ValidationError):
			pass
		as_user("Administrator")
		self.assertNotIn("System Manager", frappe.get_roles(REP_A))
		self.assertNotIn("CRM Manager", frappe.get_roles(REP_A))

	# --- Sales Manager (team) --------------------------------------------------------

	def test_team_manager_sees_team_only(self):
		as_user(TEAM_MANAGER)
		self.assertTrue(frappe.has_permission("CRM Lead", "read", self.lead_a))
		self.assertTrue(frappe.has_permission("Pakkmaxx Customer", "read", self.customer_a))
		self.assertTrue(frappe.has_permission("FCRM Note", "read", self.note_a))
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead_b))
		self.assertNotIn(self.lead_b, frappe.get_list("CRM Lead", pluck="name"))

	def test_team_manager_can_reassign_within_team_only(self):
		as_user(TEAM_MANAGER)
		lead = frappe.get_doc("CRM Lead", self.lead_a_open)
		lead.lead_owner = REP_B  # outside the team
		self.assertRaises(frappe.PermissionError, lead.save)
		lead.reload()
		lead.lead_owner = TEAM_MANAGER
		lead.save()
		lead.reload()
		lead.lead_owner = REP_A
		lead.save()

	# --- CRM Manager / Administrator -------------------------------------------------

	def test_crm_manager_and_admin_see_everything(self):
		for user in (CRM_MANAGER, ADMIN):
			as_user(user)
			names = frappe.get_list("CRM Lead", pluck="name", limit=0)
			self.assertIn(self.lead_a, names)
			self.assertIn(self.lead_b, names)
			self.assertTrue(frappe.has_permission("FCRM Note", "read", self.note_a))
			self.assertTrue(frappe.has_permission("Pakkmaxx Customer", "write", self.customer_a))

	def test_crm_manager_can_reassign_and_configure(self):
		as_user(CRM_MANAGER)
		lead = frappe.get_doc("CRM Lead", self.lead_b)
		lead.lead_owner = REP_A
		lead.save()
		lead.lead_owner = REP_B
		lead.save()
		status = frappe.get_doc("CRM Deal Status", "Negotiation")
		status.probability = 75
		status.save()
		status.probability = 70
		status.save()

	# --- Read Only -------------------------------------------------------------------

	def test_read_only_cannot_modify(self):
		as_user(READ_ONLY)
		self.assertFalse(frappe.has_permission("CRM Lead", "create"))
		self.assertFalse(frappe.has_permission("CRM Lead", "write", self.lead_a))
		self.assertFalse(frappe.has_permission("CRM Deal", "write", self.deal_a))
		self.assertFalse(frappe.has_permission("Pakkmaxx Customer", "write", self.customer_a))
		self.assertRaises(frappe.PermissionError,
			frappe.get_doc({"doctype": "CRM Lead", "first_name": "Nope", "mobile_no": random_mobile()}).insert)

	def test_read_only_sees_permitted_records(self):
		as_user("Administrator")
		frappe.share.add("CRM Lead", self.lead_b, READ_ONLY, read=1)
		as_user(READ_ONLY)
		self.assertTrue(frappe.has_permission("CRM Lead", "read", self.lead_b))
		self.assertFalse(frappe.has_permission("CRM Lead", "write", self.lead_b))


class TestDuplicates(PakkmaxxTestCase):
	def test_duplicate_phone_blocked_until_confirmed(self):
		first = self.new_lead(mobile_no="020 555 1234")
		self.assertEqual(first.mobile_no, "+233205551234")
		dup = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Other", "mobile_no": "+233 20 555 1234"})
		self.assertRaises(frappe.DuplicateEntryError, dup.insert)
		dup = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Other", "mobile_no": "233205551234",
			"pkx_allow_duplicate": 1})
		dup.insert()
		self.assertTrue(dup.name)

	def test_duplicate_detected_across_reps(self):
		self.new_lead(user=REP_A, mobile_no="020 555 7777")
		as_user(REP_B)
		dup = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Copy", "mobile_no": "0205557777"})
		with self.assertRaises(frappe.DuplicateEntryError) as ctx:
			dup.insert()
		self.assertNotIn("0205557777", str(ctx.exception), "other rep's contact details are not revealed")
