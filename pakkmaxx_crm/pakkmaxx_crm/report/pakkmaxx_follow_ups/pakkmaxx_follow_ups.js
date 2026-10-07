// Copyright (c) 2026, Pakkmaxx and contributors

frappe.query_reports["Pakkmaxx Follow-ups"] = {
	filters: [
	 {
	  "fieldname": "bucket",
	  "label": "Show",
	  "fieldtype": "Select",
	  "options": [
	   "Overdue",
	   "Today",
	   "Upcoming",
	   "Completed",
	   "All"
	  ],
	  "default": "Overdue"
	 },
	 {
	  "fieldname": "assigned_to",
	  "label": "Assigned To",
	  "fieldtype": "Link",
	  "options": "User"
	 },
	 {
	  "fieldname": "include_tasks",
	  "label": "Include Ordinary Tasks",
	  "fieldtype": "Check"
	 }
	],
};
