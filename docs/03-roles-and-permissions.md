# 3. Roles & permissions

All rules are enforced on the server (document permission hooks, list query conditions, validation),
so they apply equally to Desk, `/crm`, REST (`/api/resource`), whitelisted methods, reports and imports.
Hiding a button is never the protection.

## Role profiles (assign one per user: User → Role Profiles)

| Profile | Roles | Sees | Can |
|---|---|---|---|
| **Pakkmaxx CRM Administrator** | CRM Administrator, CRM Manager, Sales Manager, Sales User | everything | everything incl. Pakkmaxx CRM Settings, workflow, layouts |
| **Pakkmaxx CRM Manager** | CRM Manager, Sales Manager, Sales User | everything | assign/reassign anyone, edit pipeline, statuses, sources, view all reports & performance |
| **Pakkmaxx Sales Manager** | Sales Manager, Sales User | own team (CRM Sales Hierarchy subtree) | assign/reassign within their team, reopen lost/unqualified leads and won/lost deals |
| **Pakkmaxx Sales Representative** | Sales Representative, Sales User | records they own or are assigned | create leads, work assigned leads/opportunities/customers, log activities, create follow-ups for themselves |
| **Pakkmaxx CRM Read Only** | CRM Read Only | records shared with them, or their subtree if placed in the hierarchy | view only |

`System Manager` remains the technical superuser; don't give it to sales staff.

## What "sees" means
- **Leads / Opportunities** — Frappe CRM's own rule: owner (`lead_owner`/`deal_owner`) or assigned (ToDo);
  for a Sales Manager in the hierarchy, anyone in their subtree. CRM Managers sit outside the tree.
- **Notes, Tasks/Follow-ups, Call Logs** — visible if the user can see the lead, opportunity or customer they
  belong to, or created/are assigned them (Pakkmaxx). New ones can only be attached to a visible record.
- **Contacts / Organizations** — visible if linked to a visible opportunity or customer, or created by the
  user/team (Pakkmaxx). Out of the box Frappe CRM let every Sales User read all of them.
- **Pakkmaxx Customers** — sales rep is the user/team, assigned, created by them, or linked to one of their
  visible opportunities.
- **Duplicate warnings** tell a rep that a number already exists and who owns it, but never reveal the
  other record's contact details.

## Guards
- Only managers can set or change `lead_owner`, `deal_owner`, a customer's `sales_rep`, or add/remove
  assignments on leads, opportunities and customers (team managers only within their team). On
  reassignment the previous owner's assignment and share are revoked.
- Reps cannot assign follow-ups/tasks to other users.
- Server-computed fields (score, temperature, qualification score, weighted value, won/lost dates,
  contact dates, customer stats & lifecycle, links to customers) ignore values sent by the browser.
- Only CRM Managers/Administrators can change lead statuses, deal stages, sources, lost reasons,
  industries, territories.
- Reps cannot reopen Won/Lost opportunities or Unqualified/Lost leads.
- Users cannot change their own roles (Frappe core).
- Every API method requires login or API key/secret; there are no guest endpoints.

## Audit trail
Version history (track changes) is on for leads, opportunities, customers, contacts, organizations, tasks
and call logs. Frappe CRM also keeps a status change log on leads and opportunities. Assignment and
reassignment, conversion and customer creation add timeline comments. Notes keep their author and time.

## Setting up a new salesperson
1. Desk → User → new user, email, Role Profiles = *Pakkmaxx Sales Representative*.
2. `/app/crm-sales-hierarchy` → add them under their Sales Manager.
3. They log in at `/crm`.

Verified by `pakkmaxx_crm/tests/test_permissions.py` (each role independently) and
`scripts/http_smoke_test.py` (live HTTP as real users).
