// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Customers"] = {
	filters: [
	 {
	  "fieldname": "from_date",
	  "label": "Customer Since (From)",
	  "fieldtype": "Date"
	 },
	 {
	  "fieldname": "to_date",
	  "label": "Customer Since (To)",
	  "fieldtype": "Date"
	 },
	 {
	  "fieldname": "group_by",
	  "label": "Group By",
	  "fieldtype": "Select",
	  "options": [
	   "",
	   "Source",
	   "Lifecycle Stage",
	   "Segment",
	   "Sales Rep"
	  ]
	 },
	 {
	  "fieldname": "lifecycle_stage",
	  "label": "Lifecycle",
	  "fieldtype": "Select",
	  "options": [
	   "",
	   "Customer",
	   "Active Customer",
	   "Repeat Customer",
	   "Dormant"
	  ]
	 },
	 {
	  "fieldname": "segment",
	  "label": "Segment",
	  "fieldtype": "Link",
	  "options": "Pakkmaxx Customer Segment"
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
