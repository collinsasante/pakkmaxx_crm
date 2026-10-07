def before_tests():
	import frappe

	from pakkmaxx_crm.install import setup

	setup()
	frappe.db.commit()
