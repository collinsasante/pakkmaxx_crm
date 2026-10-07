// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Lead Analysis"] = {
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
	  "fieldname": "group_by",
	  "label": "Group By",
	  "fieldtype": "Select",
	  "options": [
	   "Source",
	   "Status",
	   "Sales Rep",
	   "Business Type",
	   "Lifecycle Stage",
	   "Month",
	   "Week",
	   "Day"
	  ],
	  "default": "Source"
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
	  "fieldname": "status",
	  "label": "Status",
	  "fieldtype": "Link",
	  "options": "CRM Lead Status"
	 },
	 {
	  "fieldname": "only_unqualified_or_lost",
	  "label": "Only Unqualified / Lost",
	  "fieldtype": "Check"
	 }
	],
};
