// Copyright (c) 2026, Pakkmaxx and contributors
// For license information, please see license.txt

{% include "pakkmaxx_crm/public/js/contact_actions.js" %}

const KIND_LABELS = {
	note: __("Note"),
	task: __("Task"),
	call: __("Call"),
	email: __("Email"),
	change: __("Change"),
};

frappe.ui.form.on("Pakkmaxx Customer", {
	refresh(frm) {
		pakkmaxx_crm.add_contact_actions(frm);
		pakkmaxx_crm.show_overdue_banner(frm);
		if (frm.is_new()) return;

		frm.add_custom_button(__("New Opportunity"), () => new_opportunity(frm));
		frm.add_custom_button(__("Opportunities"), () =>
			frappe.set_route("List", "CRM Deal", { pkx_customer: frm.doc.name }), __("View"));
		if (frm.doc.original_lead) {
			frm.add_custom_button(__("Original Lead"), () =>
				frappe.set_route("Form", "CRM Lead", frm.doc.original_lead), __("View"));
		}
		const colors = { "Active Customer": "green", "Repeat Customer": "blue", Customer: "gray", Dormant: "red" };
		frm.page.set_indicator(__(frm.doc.lifecycle_stage), colors[frm.doc.lifecycle_stage] || "gray");
		render_timeline(frm);
	},
});

function new_opportunity(frm) {
	const d = new frappe.ui.Dialog({
		title: __("New Opportunity for {0}", [frm.doc.customer_name]),
		fields: [
			{ fieldname: "deal_value", label: __("Estimated Value (GHS)"), fieldtype: "Currency", options: "GHS" },
			{ fieldname: "services", label: __("Services"), fieldtype: "MultiSelectList",
				get_data: (txt) => frappe.db.get_link_options("Pakkmaxx Service", txt) },
			{ fieldname: "expected_closure_date", label: __("Expected Close"), fieldtype: "Date" },
			{ fieldname: "next_step", label: __("Next Step"), fieldtype: "Data" },
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.call({
				method: "pakkmaxx_crm.api.customers.create_opportunity",
				args: { customer: frm.doc.name, ...values },
				freeze: true,
			}).then((r) => {
				d.hide();
				frappe.set_route("Form", "CRM Deal", r.message);
			});
		},
	});
	d.show();
}

function render_timeline(frm) {
	const wrapper = frm.get_field("timeline_html").$wrapper;
	wrapper.html(`<div class="text-muted">${__("Loading activity...")}</div>`);
	frappe.call({
		method: "pakkmaxx_crm.api.activities.get_timeline",
		args: { reference_doctype: frm.doctype, reference_name: frm.docname },
	}).then((r) => {
		const items = r.message || [];
		if (!items.length) {
			wrapper.html(`<div class="text-muted">${__("No activity yet.")}</div>`);
			return;
		}
		const rows = items.map((i) => {
			const when = i.at ? frappe.datetime.str_to_user(i.at) : "";
			const who = i.by ? frappe.user.full_name(i.by) : "";
			const body = i.content ? `<div class="small text-muted">${frappe.utils.escape_html(frappe.utils.html2text(i.content).slice(0, 300))}</div>` : "";
			const link = i.doctype && i.name && !["Version"].includes(i.doctype)
				? `<a href="/app/${frappe.router.slug(i.doctype)}/${encodeURIComponent(i.name)}">${frappe.utils.escape_html(i.title || i.name)}</a>`
				: frappe.utils.escape_html(i.title || "");
			return `<div class="pkx-timeline-row" style="padding:8px 0;border-bottom:1px solid var(--border-color)">
				<span class="indicator-pill gray">${KIND_LABELS[i.kind] || i.kind}${i.type ? " · " + frappe.utils.escape_html(i.type) : ""}</span>
				${link}
				<div class="small text-muted">${when}${who ? " · " + frappe.utils.escape_html(who) : ""} · ${frappe.utils.escape_html(i.on || "")}</div>
				${body}
			</div>`;
		});
		wrapper.html(rows.join(""));
	});
}
