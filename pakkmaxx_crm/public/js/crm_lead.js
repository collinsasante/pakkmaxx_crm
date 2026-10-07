{% include "pakkmaxx_crm/public/js/contact_actions.js" %}

frappe.ui.form.on("CRM Lead", {
	refresh(frm) {
		pakkmaxx_crm.add_contact_actions(frm);
		pakkmaxx_crm.show_overdue_banner(frm);
	},
});
