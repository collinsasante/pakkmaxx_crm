// Shared Desk actions for Pakkmaxx CRM records: click-to-chat, click-to-call, logging and follow-ups.
frappe.provide("pakkmaxx_crm");

pakkmaxx_crm.add_contact_actions = function (frm) {
	if (frm.is_new()) return;
	const group = __("Contact");
	const wa = (frm.doc.pkx_whatsapp_no || frm.doc.whatsapp_no || frm.doc.mobile_no || "").replace(/[^0-9]/g, "");
	if (wa) {
		frm.add_custom_button(__("WhatsApp"), () => window.open("https://wa.me/" + wa, "_blank", "noopener"), group);
	}
	const phone = (frm.doc.mobile_no || frm.doc.phone || "").replace(/[^0-9+]/g, "");
	if (phone) {
		frm.add_custom_button(__("Call"), () => (window.location.href = "tel:" + phone), group);
	}
	frm.add_custom_button(__("Log WhatsApp Chat"), () => pakkmaxx_crm.log_interaction(frm, "WhatsApp Conversation"), group);
	frm.add_custom_button(__("Log Meeting / Call"), () => pakkmaxx_crm.log_interaction(frm, "Meeting"), group);
	frm.add_custom_button(__("Add Follow-up"), () => pakkmaxx_crm.add_follow_up(frm), group);
};

pakkmaxx_crm.log_interaction = function (frm, note_type) {
	const d = new frappe.ui.Dialog({
		title: __("Log Interaction"),
		fields: [
			{ fieldname: "note_type", label: __("Type"), fieldtype: "Select", default: note_type,
				options: ["WhatsApp Conversation", "Meeting", "Call Summary", "Sales", "Account", "General"] },
			{ fieldname: "interaction_at", label: __("When"), fieldtype: "Datetime", default: frappe.datetime.now_datetime() },
			{ fieldname: "summary", label: __("Summary"), fieldtype: "Small Text", reqd: 1 },
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			frappe.call({
				method: "pakkmaxx_crm.api.activities.log_interaction",
				args: { reference_doctype: frm.doctype, reference_name: frm.docname, ...values },
				freeze: true,
			}).then(() => {
				d.hide();
				frappe.show_alert({ message: __("Logged"), indicator: "green" });
				frm.reload_doc();
			});
		},
	});
	d.show();
};

pakkmaxx_crm.add_follow_up = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Add Follow-up"),
		fields: [
			{ fieldname: "reason", label: __("Reason / Next Action"), fieldtype: "Data", reqd: 1,
				description: __("e.g. Send sea freight rate and follow up") },
			{ fieldname: "due", label: __("Follow-up At"), fieldtype: "Datetime", reqd: 1,
				default: frappe.datetime.add_days(frappe.datetime.now_datetime(), 1) },
			{ fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: ["Low", "Medium", "High"], default: "Medium" },
			{ fieldname: "notes", label: __("Notes"), fieldtype: "Small Text" },
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.call({
				method: "pakkmaxx_crm.api.followups.create_follow_up",
				args: { reference_doctype: frm.doctype, reference_name: frm.docname, ...values },
				freeze: true,
			}).then(() => {
				d.hide();
				frappe.show_alert({ message: __("Follow-up created"), indicator: "green" });
				frm.reload_doc();
			});
		},
	});
	d.show();
};

pakkmaxx_crm.show_overdue_banner = function (frm) {
	const next = frm.doc.pkx_next_follow_up_on || frm.doc.next_follow_up_on;
	if (!frm.is_new() && next && frappe.datetime.str_to_obj(next) < new Date()) {
		frm.dashboard.set_headline_alert(
			__("Follow-up overdue since {0}", [frappe.datetime.str_to_user(next)]), "red");
	}
};
