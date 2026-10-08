// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx AI vs Human"] = {
	filters: [
 {
  "fieldname": "from_date",
  "label": "From Date",
  "fieldtype": "Date"
 },
 {
  "fieldname": "to_date",
  "label": "To Date",
  "fieldtype": "Date"
 },
 {
  "fieldname": "only_overrides",
  "label": "Only Leads Reviewed by a Person",
  "fieldtype": "Check",
  "default": 1
 }
],
};
