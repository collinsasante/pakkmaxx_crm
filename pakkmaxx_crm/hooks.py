app_name = "pakkmaxx_crm"
app_title = "Pakkmaxx CRM"
app_publisher = "Pakkmaxx"
app_description = "CRM for Pakkmaxx China to Ghana freight forwarding"
app_email = "mr.asanteeprog@gmail.com"
app_license = "mit"

# Pakkmaxx CRM extends the official Frappe CRM app; it does not fork it.
required_apps = ["crm"]

# Installation
# ------------

before_install = "pakkmaxx_crm.install.before_install"
after_install = "pakkmaxx_crm.install.after_install"
after_migrate = ["pakkmaxx_crm.install.after_migrate"]

# Desk form scripts (WhatsApp / call / follow-up actions in Desk)
# ---------------------------------------------------------------

doctype_js = {
	"CRM Lead": "public/js/crm_lead.js",
	"CRM Deal": "public/js/crm_deal.js",
}

# Permissions (record level; combined with Frappe CRM's own rules using AND)
# --------------------------------------------------------------------------

permission_query_conditions = {
	"Pakkmaxx Customer": "pakkmaxx_crm.permissions.customer_query",
	"FCRM Note": "pakkmaxx_crm.permissions.note_query",
	"CRM Task": "pakkmaxx_crm.permissions.task_query",
	"CRM Call Log": "pakkmaxx_crm.permissions.call_log_query",
	"Contact": "pakkmaxx_crm.permissions.contact_query",
	"CRM Organization": "pakkmaxx_crm.permissions.organization_query",
	"Pakkmaxx AI Qualification": "pakkmaxx_crm.permissions.ai_qualification_query",
}

has_permission = {
	"Pakkmaxx Customer": "pakkmaxx_crm.permissions.customer_permission",
	"FCRM Note": "pakkmaxx_crm.permissions.note_permission",
	"CRM Task": "pakkmaxx_crm.permissions.task_permission",
	"CRM Call Log": "pakkmaxx_crm.permissions.call_log_permission",
	"Contact": "pakkmaxx_crm.permissions.contact_permission",
	"CRM Organization": "pakkmaxx_crm.permissions.organization_permission",
	"Pakkmaxx AI Qualification": "pakkmaxx_crm.permissions.ai_qualification_permission",
	"CRM Lead Status": "pakkmaxx_crm.permissions.config_permission",
	"CRM Deal Status": "pakkmaxx_crm.permissions.config_permission",
	"CRM Lead Source": "pakkmaxx_crm.permissions.config_permission",
	"CRM Lost Reason": "pakkmaxx_crm.permissions.config_permission",
	"CRM Industry": "pakkmaxx_crm.permissions.config_permission",
	"CRM Territory": "pakkmaxx_crm.permissions.config_permission",
	"CRM Communication Status": "pakkmaxx_crm.permissions.config_permission",
}

# Document Events
# ---------------

doc_events = {
	"CRM Lead": {
		"before_validate": "pakkmaxx_crm.events.lead.before_validate",
		"validate": "pakkmaxx_crm.events.lead.validate",
		"on_update": "pakkmaxx_crm.events.lead.on_update",
		"after_insert": "pakkmaxx_crm.ai.triggers.on_lead_insert",
		"on_change": "pakkmaxx_crm.events.lead.on_change",
	},
	"CRM Deal": {
		"before_validate": "pakkmaxx_crm.events.deal.before_validate",
		"validate": "pakkmaxx_crm.events.deal.validate",
		"after_insert": "pakkmaxx_crm.events.deal.after_insert",
		"on_update": "pakkmaxx_crm.events.deal.on_update",
	},
	"CRM Task": {
		"validate": "pakkmaxx_crm.followups.validate_task",
		"on_update": "pakkmaxx_crm.followups.on_task_change",
		"after_delete": "pakkmaxx_crm.followups.on_task_delete",
	},
	"FCRM Note": {
		"after_insert": "pakkmaxx_crm.events.activity.on_note_insert",
	},
	"CRM Call Log": {
		"on_update": "pakkmaxx_crm.events.activity.on_call_log_update",
	},
	"Communication": {
		"after_insert": "pakkmaxx_crm.events.activity.on_communication_insert",
	},
	# only fires when the optional frappe_whatsapp app is installed
	"WhatsApp Message": {
		"after_insert": "pakkmaxx_crm.events.activity.on_whatsapp_message_update",
	},
	"Contact": {
		"validate": "pakkmaxx_crm.events.contact.validate",
	},
	"ToDo": {
		"validate": "pakkmaxx_crm.events.assignment.validate_todo",
		"on_trash": "pakkmaxx_crm.events.assignment.on_todo_trash",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["pakkmaxx_crm.followups.send_due_reminders"],
		"*/15 * * * *": ["pakkmaxx_crm.ai.triggers.analyze_quiet_conversations"],
		"0 7 * * *": ["pakkmaxx_crm.followups.send_daily_digest"],
	},
	"daily_long": ["pakkmaxx_crm.customers.refresh_all_lifecycles", "pakkmaxx_crm.ai.service.clear_old_raw_responses"],
}

# VerzChat (verzchat_crm) calls these after each processed message event
verzchat_message_handlers = ["pakkmaxx_crm.ai.triggers.on_verzchat_message"]

# Testing
# -------

before_tests = "pakkmaxx_crm.tests.before_tests"
