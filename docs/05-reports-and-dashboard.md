# 5. Reports & dashboard

All reports and cards use the viewer's permissions: a rep sees their own numbers, a Sales Manager their
team's, managers everything. Money is GHS (other currencies are converted with the deal's exchange rate).

## Dashboard — `/app/pakkmaxx-crm`
- **Follow-ups**: Today's, Overdue, Upcoming (7 days), Uncontacted Leads
- **Leads**: Total, New, Qualified, Unassigned
- **Sales**: Pipeline Value, Weighted Pipeline, Won Value, Average Deal Value, Open / Won / Lost
  Opportunities, Win Rate, Lead → Customer Conversion Rate, Average Days to Convert
- **Customers**: Active, Dormant
- **Charts**: Leads by Source, Leads by Status, New Leads Trend (weekly), Opportunity Value by Stage,
  Customers by Source, Customers by Lifecycle
- Links to every report and setup page.

`/crm` also has Frappe CRM's own dashboard and Kanban pipeline views.

## Reports (Desk → Pakkmaxx CRM → Reports)

| Report | Answers | Options |
|---|---|---|
| **Lead Source Attribution** | Where do customers come from? Source → leads → contacted → qualified → opportunities → won → customers, lead→customer %, opportunity & won value (GHS), won value per lead | group by Source / Campaign / Sales Rep; dates, rep, campaign |
| **Lead Analysis** | Leads by source, status, salesperson, business type, lifecycle, month/week/day | only unqualified/lost; dates, source, rep, status |
| **Uncontacted Leads** | New leads nobody has contacted, oldest first, waiting hours | min hours waiting |
| **Follow-ups** | Overdue / today / upcoming / completed (with on-time flag) | assigned to, include ordinary tasks |
| **Pipeline** | Count, value, weighted value, average by stage / rep / expected close month / source, or every opportunity | open / won / lost / all |
| **Customers** | New, active, repeat, dormant customers; by source, segment, lifecycle, rep; days inactive | customer since, lifecycle, segment |
| **Sales Performance** | Per rep: leads, contacted %, qualified, unqualified, lost, opportunities, won, win rate, won value, open pipeline, customers, lead→customer %, follow-up completion %, average days to win | dates, rep |

Where leads get stuck: *Lead Analysis* grouped by Status, *Uncontacted Leads*, *Follow-ups → Overdue*, and
*Pipeline* by Stage.

Brief → report mapping: leads by source/salesperson/status/date, qualified, lost → Lead Analysis;
uncontacted → Uncontacted Leads; overdue follow-ups → Follow-ups; pipeline, by stage/salesperson, won,
lost, value, expected close → Pipeline; new/repeat/active/dormant/by source/by segment → Customers;
performance, conversion, follow-up completion, win rate, conversion time → Sales Performance.

## Notifications
- **Pakkmaxx Opportunity Won** → CRM Managers and Sales Managers (system notification)
- **Pakkmaxx Hot Lead** → lead owner and CRM Managers when a lead turns Hot
- Follow-up reminders → assignee (CRM bell + Desk bell), every 5 minutes
- Daily 07:00 digest → each user: follow-ups due today, overdue, uncontacted leads
- Frappe CRM's own: assignment, mentions, task assignment
Email delivery of these requires an outgoing Email Account to be configured.
