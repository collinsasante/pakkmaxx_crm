// Desk "AI Qualification" panel for CRM Lead. Data comes from pakkmaxx_crm.ai.api (server-side);
// the browser never talks to the AI provider.
frappe.provide("pakkmaxx_crm");

pakkmaxx_crm.ai_panel = function (frm) {
	if (frm.is_new()) return;
	frm.add_custom_button(__("AI Qualification"), () => pakkmaxx_crm.show_ai_panel(frm));
};

pakkmaxx_crm.show_ai_panel = async function (frm) {
	const r = await frappe.call({ method: "pakkmaxx_crm.ai.api.get_ai_panel", args: { lead: frm.docname } });
	const data = r.message;
	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
	const lines = (v) => (v ? esc(v).replace(/\n/g, "<br>") : `<span class="text-muted">-</span>`);
	const colors = { "High Value": "purple", Qualified: "green", "Needs Follow-up": "orange", Unqualified: "red" };
	const latest = data.latest;
	const ov = data.override || {};
	let html = "";
	if (!data.enabled) html += `<div class="alert alert-warning">${__("AI qualification is turned off in Pakkmaxx CRM Settings.")}</div>`;
	if (data.pending) html += `<div class="alert alert-info">${__("AI analysis pending…")}</div>`;
	if (ov.pkx_ai_human_classification) {
		html += `<div class="alert alert-secondary"><b>${__("Human decision")}:</b> ${esc(ov.pkx_ai_human_classification)}
			${ov.pkx_ai_human_score != null ? ` (${esc(ov.pkx_ai_human_score)}/100)` : ""} – ${esc(ov.pkx_ai_override_reason)}
			<div class="small text-muted">${esc(ov.pkx_ai_overridden_by)} · ${esc(frappe.datetime.str_to_user(ov.pkx_ai_overridden_on))}</div></div>`;
	}
	if (latest) {
		const facts = [
			["Intent", latest.intent], ["Service", latest.service_interest], ["Product", latest.product_category],
			["Origin", latest.origin], ["Destination", latest.destination], ["Quantity", latest.quantity],
			["Volume", latest.estimated_volume], ["Expected shipment", latest.expected_shipping_date], ["Value", latest.estimated_value],
		].filter(([, v]) => v);
		html += `
			<div style="display:flex;gap:16px;align-items:baseline;flex-wrap:wrap">
				<span class="indicator-pill ${colors[latest.classification] || "gray"}" style="font-size:14px">${esc(latest.classification)}</span>
				<span><b>${esc(latest.score)}</b> / 100</span>
				<span class="text-muted">${__("Confidence")} ${esc(Math.round(latest.confidence))}%</span>
				<span class="text-muted small">${esc(latest.model)} · ${esc(frappe.datetime.str_to_user(latest.analyzed_at))}</span>
			</div>
			<p style="margin-top:10px">${esc(latest.summary)}</p>
			<div class="row">
				<div class="col-sm-6"><h6>${__("Recommended next action")}</h6><p>${esc(latest.recommended_next_action)}</p>
					<h6>${__("Still missing")}</h6><p>${lines(latest.missing_information)}</p></div>
				<div class="col-sm-6"><h6>${__("Buying signals")}</h6><p>${lines(latest.buying_signals)}</p>
					<h6>${__("Negative signals")}</h6><p>${lines(latest.negative_signals)}</p></div>
			</div>
			${facts.length ? `<table class="table table-sm small">${facts.map(([k, v]) => `<tr><td class="text-muted" style="width:40%">${__(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>` : ""}
			${latest.evidence ? `<details><summary class="small">${__("Evidence")}</summary><p class="small">${lines(latest.evidence)}</p></details>` : ""}`;
	} else if (!data.pending) {
		html += `<p class="text-muted">${__("Not analysed yet.")}</p>`;
	}
	if (data.history.length) {
		html += `<h6 style="margin-top:16px">${__("History")}</h6><table class="table table-sm small"><tr><th>${__("When")}</th><th>${__("Trigger")}</th><th>${__("Status")}</th><th>${__("Result")}</th></tr>
			${data.history.map((h) => `<tr><td>${esc(frappe.datetime.str_to_user(h.analyzed_at || h.creation))}</td><td>${esc(h.trigger)}</td>
				<td>${esc(h.status)}${h.error && h.status !== "Completed" ? `<div class="text-muted">${esc(h.error)}</div>` : ""}</td>
				<td>${h.classification ? `${esc(h.classification)} (${esc(h.score)})` : ""}</td></tr>`).join("")}</table>`;
	}
	const d = new frappe.ui.Dialog({
		title: __("AI Qualification"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "body", options: html }],
	});
	if (data.can_write && data.enabled) {
		const run = (reanalyze) =>
			frappe.call({ method: "pakkmaxx_crm.ai.api.analyze_lead", args: { lead: frm.docname, reanalyze } }).then((res) => {
				frappe.show_alert({ message: res.message.queued ? __("AI analysis queued") : esc(res.message.message), indicator: res.message.queued ? "blue" : "orange" });
				d.hide();
			});
		d.set_primary_action(latest ? __("Re-analyse") : __("Analyze Lead"), () => run(Boolean(latest)));
		if (latest) d.set_secondary_action_label(__("Analyse if changed")), d.set_secondary_action(() => run(false));
	}
	d.show();
};
