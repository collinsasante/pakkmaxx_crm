import frappe

from pakkmaxx_crm.setup import crm_ui, custom_fields, defaults


def before_install():
	# DocPerms in this app reference these roles
	defaults.create_roles()


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	"""Idempotent: safe on every migrate; never overwrites administrator changes."""
	defaults.create_roles()
	defaults.create_role_profiles()
	custom_fields.setup_custom_fields()
	defaults.setup_masters()
	defaults.setup_pipeline()
	defaults.setup_currency()
	defaults.setup_settings()
	defaults.setup_workflow()
	crm_ui.setup_layouts()
	crm_ui.setup_form_scripts()
	crm_ui.setup_ai_form_script()
	frappe.clear_cache()
