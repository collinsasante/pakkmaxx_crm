{% include "pakkmaxx_crm/public/js/contact_actions.js" %}
{% include "pakkmaxx_crm/public/js/ai_panel.js" %}

frappe.ui.form.on("CRM Lead", {
	refresh(frm) {
		pakkmaxx_crm.add_contact_actions(frm);
		pakkmaxx_crm.show_overdue_banner(frm);
		pakkmaxx_crm.ai_panel(frm);
	},
});
