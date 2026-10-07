import frappe
from frappe import _
from frappe.utils import escape_html, now_datetime

from pakkmaxx_crm.api import require

NOTE_TYPES = ("General", "Sales", "Follow-up", "Account", "WhatsApp Conversation", "Meeting", "Call Summary")


@frappe.whitelist(methods=["POST"])
def log_interaction(
	reference_doctype: str,
	reference_name: str,
	summary: str,
	note_type: str = "WhatsApp Conversation",
	interaction_at: str | None = None,
) -> str:
	"""Log a WhatsApp chat, meeting, call summary or internal note on a lead/deal/customer."""
	require(reference_doctype, reference_name, "read")
	if note_type not in NOTE_TYPES:
		frappe.throw(_("Invalid note type"))
	if not (summary or "").strip():
		frappe.throw(_("Summary is required"))
	note = frappe.get_doc(
		{
			"doctype": "FCRM Note",
			"title": f"{note_type}: {summary.strip()[:60]}",
			"content": "<p>" + escape_html(summary.strip()).replace("\n", "<br>") + "</p>",
			"pkx_note_type": note_type,
			"pkx_interaction_at": interaction_at or now_datetime(),
			"reference_doctype": reference_doctype,
			"reference_docname": reference_name,
		}
	)
	note.insert()  # permission-checked (note_permission hook)
	return note.name


@frappe.whitelist()
def get_timeline(reference_doctype: str, reference_name: str) -> list[dict]:
	"""Unified history for a lead, opportunity or customer.

	For a customer it merges the customer's own notes/tasks plus everything logged on its
	original lead and all its opportunities. Only records the user may read are returned.
	"""
	require(reference_doctype, reference_name, "read")
	refs = [(reference_doctype, reference_name)]
	if reference_doctype == "Pakkmaxx Customer":
		deals = frappe.get_all("CRM Deal", filters={"pkx_customer": reference_name}, fields=["name", "lead"],
			ignore_permissions=True)
		refs += [("CRM Deal", d.name) for d in deals]
		leads = {d.lead for d in deals if d.lead}
		if lead := frappe.db.get_value("Pakkmaxx Customer", reference_name, "original_lead"):
			leads.add(lead)
		refs += [("CRM Lead", lead) for lead in leads]
	elif reference_doctype == "CRM Deal":
		if lead := frappe.db.get_value("CRM Deal", reference_name, "lead"):
			refs.append(("CRM Lead", lead))

	# only records this user may read (a customer can have opportunities owned by other reps)
	refs = [(dt, name) for dt, name in dict.fromkeys(refs) if frappe.has_permission(dt, "read", name)]

	items = []
	for dt, name in refs:
		if dt in ("CRM Lead", "CRM Deal"):
			for log in frappe.get_all("CRM Status Change Log", filters={"parenttype": dt, "parent": name},
					fields=["from", "to", "to_date", "from_date", "log_owner", "name"], order_by="idx asc"):
				items.append({"kind": "change", "type": "status",
					"title": f"{_(dt)} status: {log['from'] or '-'} → {log['to']}",
					"at": log.to_date or log.from_date, "by": log.log_owner, "doctype": dt, "name": name,
					"on": f"{dt} {name}"})
		ref = {"reference_doctype": dt, "reference_docname": name}
		for n in frappe.get_list("FCRM Note", filters=ref,
				fields=["name", "title", "content", "pkx_note_type", "pkx_interaction_at", "owner", "creation"]):
			items.append({"kind": "note", "type": n.pkx_note_type or "General", "title": n.title,
				"content": n.content, "at": n.pkx_interaction_at or n.creation, "by": n.owner,
				"doctype": "FCRM Note", "name": n.name, "on": f"{dt} {name}"})
		for t in frappe.get_list("CRM Task", filters=ref,
				fields=["name", "title", "status", "due_date", "pkx_task_type", "assigned_to", "creation",
					"pkx_outcome"]):
			items.append({"kind": "task", "type": t.pkx_task_type, "title": t.title, "status": t.status,
				"content": t.pkx_outcome, "at": t.due_date or t.creation, "by": t.assigned_to,
				"doctype": "CRM Task", "name": t.name, "on": f"{dt} {name}"})
		for c in frappe.get_list("CRM Call Log", filters=ref,
				fields=["name", "type", "status", "duration", "start_time", "creation", "caller", "receiver"]):
			items.append({"kind": "call", "type": c.type, "title": f"{c.type} call ({c.status})",
				"at": c.start_time or c.creation, "by": c.caller or c.receiver, "doctype": "CRM Call Log",
				"name": c.name, "on": f"{dt} {name}"})
		for e in frappe.get_all("Communication",
				filters={"reference_doctype": dt, "reference_name": name, "communication_type": "Communication"},
				fields=["name", "subject", "communication_medium", "sent_or_received", "communication_date",
					"sender"]):
			items.append({"kind": "email", "type": e.sent_or_received, "title": e.subject,
				"at": e.communication_date, "by": e.sender, "doctype": "Communication", "name": e.name,
				"on": f"{dt} {name}"})
		for v in frappe.get_all("Version", filters={"ref_doctype": dt, "docname": name},
				fields=["name", "data", "owner", "creation"], order_by="creation desc", limit=50):
			data = frappe.parse_json(v.data or "{}")
			for field, old, new in data.get("changed", []):
				if field in ("lead_owner", "deal_owner", "deal_value", "sales_rep", "pkx_customer"):
					items.append({"kind": "change", "type": field, "title": f"{field}: {old or '-'} → {new}",
						"at": v.creation, "by": v.owner, "doctype": "Version", "name": v.name,
						"on": f"{dt} {name}"})
	items.sort(key=lambda i: str(i["at"] or ""), reverse=True)
	return items
