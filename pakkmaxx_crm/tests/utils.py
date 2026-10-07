import random

import frappe
from frappe.tests import IntegrationTestCase

DOMAIN = "pkx.test"
ADMIN = f"crm.admin@{DOMAIN}"
CRM_MANAGER = f"crm.manager@{DOMAIN}"
TEAM_MANAGER = f"team.manager@{DOMAIN}"
REP_A = f"rep.a@{DOMAIN}"
REP_B = f"rep.b@{DOMAIN}"
READ_ONLY = f"viewer@{DOMAIN}"

PROFILES = {
	ADMIN: "Pakkmaxx CRM Administrator",
	CRM_MANAGER: "Pakkmaxx CRM Manager",
	TEAM_MANAGER: "Pakkmaxx Sales Manager",
	REP_A: "Pakkmaxx Sales Representative",
	REP_B: "Pakkmaxx Sales Representative",
	READ_ONLY: "Pakkmaxx CRM Read Only",
}


def random_mobile() -> str:
	"""A Ghana-format local number, e.g. 024 123 4567."""
	return "02" + str(random.choice([4, 5, 7])) + " " + str(random.randint(100, 999)) + " " + str(
		random.randint(1000, 9999)
	)


def make_user(email: str, profile: str):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0,
				"role_profiles": [{"role_profile": profile}]}
		)
		user.insert(ignore_permissions=True)
	return frappe.get_doc("User", email)


def node(user: str, reports_to: str | None = None, is_group: int = 0) -> str:
	existing = frappe.db.get_value("CRM Sales Hierarchy", {"user": user})
	if existing:
		return existing
	return frappe.get_doc(
		{"doctype": "CRM Sales Hierarchy", "user": user, "reports_to": reports_to, "is_group": is_group}
	).insert(ignore_permissions=True).name


def setup_team():
	"""Team manager manages rep A. Rep B is on another team. CRM manager is outside the tree (sees all)."""
	for email, profile in PROFILES.items():
		make_user(email, profile)
	frappe.db.set_single_value("FCRM Settings", "enable_sales_hierarchy", 1)
	mgr = node(TEAM_MANAGER, is_group=1)
	node(REP_A, reports_to=mgr)
	node(REP_B)


def as_user(user: str):
	frappe.set_user(user)
	frappe.local.request_cache.clear() if hasattr(frappe.local, "request_cache") else None
	frappe.clear_cache(user=user)


class PakkmaxxTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		setup_team()

	def tearDown(self):
		as_user("Administrator")

	def new_lead(self, user=REP_A, **values):
		as_user(user)
		doc = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": values.pop("first_name", "Ama"),
				"last_name": values.pop("last_name", "Mensah"),
				"mobile_no": values.pop("mobile_no", random_mobile()),
				"source": values.pop("source", "WhatsApp"),
				**values,
			}
		)
		return doc.insert()

	def qualify(self, lead):
		lead.update(
			{
				"pkx_is_genuine": "Yes",
				"pkx_products_description": "Ladies clothing and handbags",
				"pkx_origin_city": "Guangzhou",
				"pkx_destination_city": "Accra",
				"pkx_shipping_frequency": "Monthly",
				"pkx_est_monthly_volume_cbm": 3,
				"pkx_budget": 8000,
				"pkx_expected_ship_date": frappe.utils.add_days(frappe.utils.nowdate(), 14),
				"pkx_decision_maker": "Herself (owner)",
			}
		)
		if not lead.pkx_services:
			lead.append("pkx_services", {"service": "Sea Freight"})
		lead.status = "Qualified"
		lead.save()
		return lead
