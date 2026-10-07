# 2. Configuration

Everything below is data, not code. Change it in the UI (Desk or `/crm` → Settings); migrations never
overwrite it.

## Lead sources
`CRM Lead Source` — WhatsApp, Facebook, Instagram, TikTok, Website, Referral, Existing Customer,
Advertisement, Google, Walk In, Phone Call, Event, Manual Entry, Other (+ Frappe CRM's Web Form, Campaign,
Email). Add or rename freely. Only CRM Managers / Administrators can edit sources.

Detailed attribution per lead (tab **Attribution**): Campaign (`UTM Campaign`), ad/post reference,
referred-by person or customer, landing page, UTM source / medium / campaign / content. First and last
contact dates are filled automatically.

## Lead lifecycle (statuses + workflow)
`CRM Lead Status` holds the statuses; **Workflow → Pakkmaxx Lead Workflow** holds the allowed transitions
and who may perform them.

| From | Allowed next (Sales User) |
|---|---|
| New | Contacted, Follow-up Required, Unqualified, Lost |
| Contacted / Follow-up Required | each other, Qualified, Unqualified, Lost |
| Qualified | Proposal/Quote Requested, Follow-up Required, Lost |
| Proposal/Quote Requested | Negotiation, Follow-up Required, Lost |
| Negotiation | Proposal/Quote Requested, Follow-up Required, Lost |
| Unqualified / Lost | Contacted (**Reopen** — Sales Manager / CRM Manager only) |
| → Converted | only by converting the lead to an opportunity |

Extra server rules: *Qualified* needs the qualification score ≥ the minimum and "Genuine Lead? = Yes";
*Unqualified* needs a reason; *Lost* needs a lost reason. The first logged contact (WhatsApp note,
meeting, call, email) moves a New lead to Contacted automatically.

To change the lifecycle: edit the statuses, then the workflow transitions. New leads (including imports)
must start in the workflow's first state (**New**).

## Opportunity pipeline
`CRM Deal Status` (CRM Settings → Deal Statuses in `/crm`), each with a type and probability:

Qualified (10%) → Requirement Collected (25%) → Quote/Proposal (50%) → Negotiation (70%) → **Won** (100%) /
**Lost** (0%).

Rename, add or reorder stages freely; keep exactly one *Won*-type and one *Lost*-type status. The server
sets probability from the stage and computes the weighted value (value × probability); reps cannot
override these, nor reopen Won/Lost opportunities.

## Services, product categories, business types, segments
Masters: `Pakkmaxx Service` (with a service group), `Pakkmaxx Product Category`, `Pakkmaxx Business Type`,
`Pakkmaxx Customer Segment` (with a colour). Disable instead of deleting once used.

## Pakkmaxx CRM Settings (`/app/pakkmaxx-crm-settings`)

| Tab | Setting | Default |
|---|---|---|
| Lead Scoring | Enable, Hot ≥ / Warm ≥ thresholds | on, 70, 40 |
| | Scoring rules: *signal, lead field, condition, value, points* | 13 rules (see below) |
| | Minimum qualification score / must be genuine | 60%, yes |
| Follow-ups | Reminder minutes before due, daily digest, uncontacted alert hours | 30, on, 24 |
| Customer Lifecycle | Active window, dormant after, high-value threshold (GHS) | 90 d, 120 d, 50,000 |
| Data Quality | Default calling code, block duplicate leads | 233, on |

Default scoring rules: phone +10, WhatsApp +10, email +5, responds on WhatsApp +15, requested quote +20,
requested callback +10, requested onboarding +15, engaged website +5, opened communication +5, business
customer +10, frequent importer (monthly or more) +15, ≥5 CBM/month +15, ≥GHS 20,000/month +10.
Conditions: is set, is not set, equals, not equals, >, ≥, <, ≤, in list. Total is capped 0–100 and written
to Frappe CRM's own `lead_score` / `lead_temperature` fields (shown in `/crm`). Rules are evaluated on the
server on every save — never in the browser.

## Sales teams
Enable **Sales Hierarchy** (on by default) and build the tree in `CRM Sales Hierarchy`: put each Sales
Manager as a group node and their reps under them. CRM Managers and Administrators stay **outside** the
tree (they see everything). See [roles](03-roles-and-permissions.md).

## Forms in /crm
Pakkmaxx sections were added to the CRM layouts (Quick Entry, Side Panel, Data tab) for leads, deals,
tasks, notes and contacts. Rearrange them in `/crm` → Settings → Fields Layout. The WhatsApp / Call buttons
come from the CRM Form Scripts "Pakkmaxx Contact Actions - CRM Lead/Deal".

## Tags
Frappe tags work on every CRM record (Desk sidebar → Tags) and are filterable in list views. Seeded:
China Importer, Clothing, Electronics, Cosmetics, Food Products, WhatsApp Seller, High Volume,
Price Sensitive, Urgent, Repeat Customer.

## Importing leads / customers
Use **Data Import** (Desk) on `CRM Lead` or `Pakkmaxx Customer`:
- phone numbers and emails are normalised on import (0244… → +233244…);
- rows matching an existing phone / WhatsApp / email are **rejected** as duplicates (set the column
  "Confirmed: Not a Duplicate" = 1 only for rows you have checked);
- keep `source` filled to preserve attribution; leads must be imported with status **New** (the workflow
  only allows the first state on creation) — move them on afterwards, or have an administrator
  temporarily deactivate the workflow for a historical import.
Run imports on staging first.
