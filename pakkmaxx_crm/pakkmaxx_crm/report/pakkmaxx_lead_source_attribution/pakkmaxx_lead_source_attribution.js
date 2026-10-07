// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Lead Source Attribution"] = {
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
	   "Campaign",
	   "Sales Rep"
	  ],
	  "default": "Source"
	 },
	 {
	  "fieldname": "sales_rep",
	  "label": "Sales Rep",
	  "fieldtype": "Link",
	  "options": "User"
	 },
	 {
	  "fieldname": "campaign",
	  "label": "Campaign",
	  "fieldtype": "Link",
	  "options": "UTM Campaign"
	 }
	],
};
