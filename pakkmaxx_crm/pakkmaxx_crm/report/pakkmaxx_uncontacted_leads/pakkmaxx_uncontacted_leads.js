// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Uncontacted Leads"] = {
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
	  "fieldname": "source",
	  "label": "Source",
	  "fieldtype": "Link",
	  "options": "CRM Lead Source"
	 },
	 {
	  "fieldname": "sales_rep",
	  "label": "Sales Rep",
	  "fieldtype": "Link",
	  "options": "User"
	 },
	 {
	  "fieldname": "older_than_hours",
	  "label": "Waiting More Than (hours)",
	  "fieldtype": "Int"
	 }
	],
};
