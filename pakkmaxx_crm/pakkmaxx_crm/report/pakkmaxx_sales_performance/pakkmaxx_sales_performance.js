// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Sales Performance"] = {
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
	  "fieldname": "sales_rep",
	  "label": "Sales Rep",
	  "fieldtype": "Link",
	  "options": "User"
	 }
	],
};
