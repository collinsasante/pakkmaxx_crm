// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Pipeline"] = {
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
	  "fieldname": "view",
	  "label": "View",
	  "fieldtype": "Select",
	  "options": [
	   "Stage",
	   "Sales Rep",
	   "Expected Close Month",
	   "Source",
	   "Detail"
	  ],
	  "default": "Stage"
	 },
	 {
	  "fieldname": "status_type",
	  "label": "Opportunities",
	  "fieldtype": "Select",
	  "options": [
	   "Open",
	   "Won",
	   "Lost",
	   "All"
	  ],
	  "default": "Open"
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
	 }
	],
};
