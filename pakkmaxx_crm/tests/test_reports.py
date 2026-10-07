"""Reports and dashboard: run every report, check numbers move with the workflow and
that a rep's dashboard counts only what that rep may see."""

import frappe
from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal
from frappe.desk.query_report import run

from pakkmaxx_crm.api import dashboard
from pakkmaxx_crm.api.activities import log_interaction
from pakkmaxx_crm.tests.utils import CRM_MANAGER, REP_A, REP_B, PakkmaxxTestCase, as_user

REPORTS = {
	"Pakkmaxx Lead Source Attribution": [{}, {"group_by": "Campaign"}, {"group_by": "Sales Rep"}],
	"Pakkmaxx Lead Analysis": [{"group_by": g} for g in ("Source", "Status", "Sales Rep", "Month", "Week", "Day")],
	"Pakkmaxx Uncontacted Leads": [{}],
	"Pakkmaxx Follow-ups": [{"bucket": b} for b in ("Overdue", "Today", "Upcoming", "Completed", "All")],
	"Pakkmaxx Pipeline": [{"view": v, "status_type": "All"} for v in ("Stage", "Sales Rep", "Expected Close Month",
		"Source", "Detail")],
	"Pakkmaxx Customers": [{}, {"group_by": "Source"}, {"group_by": "Segment"}, {"group_by": "Lifecycle Stage"}],
	"Pakkmaxx Sales Performance": [{}],
	"Pakkmaxx AI Qualification Overview": [{}],
	"Pakkmaxx AI vs Human": [{}, {"only_overrides": 1}],
}


def rows(report, filters=None):
	return run(report, filters=filters or {}, ignore_prepared_report=True)["result"]


class TestReportsAndDashboard(PakkmaxxTestCase):
	def _won_whatsapp_customer(self, value=20000):
		lead = self.new_lead(user=REP_A, source="WhatsApp")
		log_interaction("CRM Lead", lead.name, "Chatted on WhatsApp", "WhatsApp Conversation")
		lead.reload()
		self.qualify(lead)
		deal = frappe.get_doc("CRM Deal", convert_to_deal(lead=lead.name))
		deal.status = "Won"
		deal.deal_value = value
		deal.save()
		return lead, deal.reload()

	def test_all_reports_run_for_every_role(self):
		self._won_whatsapp_customer()
		for user in (REP_A, CRM_MANAGER, "Administrator"):
			as_user(user)
			for report, variants in REPORTS.items():
				for filters in variants:
					with self.subTest(user=user, report=report, filters=filters):
						rows(report, filters)

	def test_dashboard_and_performance_update(self):
		as_user(REP_A)
		before_won = dashboard.won_value()["value"]
		before_perf = {r["sales_rep"]: r for r in rows("Pakkmaxx Sales Performance")}.get(REP_A, {})

		lead, deal = self._won_whatsapp_customer(value=20000)

		as_user(REP_A)
		self.assertEqual(dashboard.won_value()["value"], before_won + 20000)
		self.assertGreaterEqual(dashboard.active_customers()["value"], 1)

		perf = {r["sales_rep"]: r for r in rows("Pakkmaxx Sales Performance")}[REP_A]
		self.assertEqual(perf["won"], before_perf.get("won", 0) + 1)
		self.assertEqual(perf["won_value"], before_perf.get("won_value", 0) + 20000)

		attribution = {r["group"]: r for r in rows("Pakkmaxx Lead Source Attribution")}
		self.assertGreaterEqual(attribution["WhatsApp"]["customers"], 1)
		self.assertGreaterEqual(attribution["WhatsApp"]["won_value"], 20000)

		customers = [r["name"] for r in rows("Pakkmaxx Customers")]
		self.assertIn(deal.pkx_customer, customers)

	def test_rep_dashboard_is_scoped(self):
		self._won_whatsapp_customer(value=33333)
		as_user(REP_B)
		detail = rows("Pakkmaxx Pipeline", {"view": "Detail", "status_type": "All"})
		self.assertFalse([r for r in detail if r.get("deal_owner") == REP_A], "rep B cannot see rep A's deals")
		perf_reps = {r["sales_rep"] for r in rows("Pakkmaxx Sales Performance")}
		self.assertNotIn(REP_A, perf_reps)
		as_user(CRM_MANAGER)
		perf_reps = {r["sales_rep"] for r in rows("Pakkmaxx Sales Performance")}
		self.assertIn(REP_A, perf_reps)

	def test_overdue_follow_up_shows_on_dashboard(self):
		lead = self.new_lead(user=REP_A)
		before = dashboard.overdue_follow_ups()["value"]
		task = frappe.get_doc({"doctype": "CRM Task", "title": "Send rates", "pkx_task_type": "Follow-up",
			"due_date": frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-2), "status": "Todo",
			"reference_doctype": "CRM Lead", "reference_docname": lead.name}).insert()
		self.assertEqual(dashboard.overdue_follow_ups()["value"], before + 1)
		overdue = [r["name"] for r in rows("Pakkmaxx Follow-ups", {"bucket": "Overdue"})]
		self.assertIn(task.name, overdue)
