"""Create demo/test users for local or staging (never production).

    bench --site <site> execute pakkmaxx_crm.scripts_demo.create_demo_users --kwargs '{"password": "..."}'

"""

import sys

import frappe
from frappe.utils.password import update_password

USERS = {
	"admin@pakkmaxx.local": "Pakkmaxx CRM Administrator",
	"manager@pakkmaxx.local": "Pakkmaxx CRM Manager",
	"teamlead@pakkmaxx.local": "Pakkmaxx Sales Manager",
	"kwame@pakkmaxx.local": "Pakkmaxx Sales Representative",
	"akua@pakkmaxx.local": "Pakkmaxx Sales Representative",
	"viewer@pakkmaxx.local": "Pakkmaxx CRM Read Only",
}


def create(password: str):
	for email, profile in USERS.items():
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0].title(),
				"send_welcome_email": 0, "role_profiles": [{"role_profile": profile}]}).insert(ignore_permissions=True)
		update_password(email, password)

	def node(user, parent=None, group=0):
		existing = frappe.db.get_value("CRM Sales Hierarchy", {"user": user})
		return existing or frappe.get_doc({"doctype": "CRM Sales Hierarchy", "user": user, "reports_to": parent,
			"is_group": group}).insert(ignore_permissions=True).name

	# teamlead manages kwame; akua is on another team
	lead = node("teamlead@pakkmaxx.local", group=1)
	node("kwame@pakkmaxx.local", lead)
	node("akua@pakkmaxx.local")
	frappe.db.commit()


if __name__ == "__main__":
	site, password = sys.argv[1], sys.argv[2]
	frappe.init(site=site, sites_path=".")
	frappe.connect()
	create(password)
	print("demo users ready")
