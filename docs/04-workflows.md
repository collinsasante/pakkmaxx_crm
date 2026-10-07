# 4. Workflows

## The main flow: WhatsApp enquiry → repeat customer

1. **Lead arrives** — created in `/crm` (Leads → Create; Quick Entry has WhatsApp no., source, customer
   type, services, city, next action) or via the `capture_lead` API (website / WhatsApp bot). Phone and
   WhatsApp are normalised to +233…; WhatsApp defaults to the mobile number. Duplicates are blocked.
2. **Assign** — a manager sets *Lead Owner* (or uses Assign To). Reps' own leads are theirs automatically.
   API/integration leads arrive **unassigned** and show in *Unassigned Leads*.
3. **Contact** — WhatsApp / Call buttons on the lead (`/crm` and Desk). Log the conversation: `/crm` → Notes
   with type *WhatsApp Conversation*, *Meeting* or *Call Summary* (or Desk → Contact → Log WhatsApp Chat).
   Calls can be logged in Calls; emails sent from the CRM are tracked automatically. The first logged
   contact sets *First Contacted On* and moves the lead **New → Contacted**.
4. **Qualify** — fill the *Qualification* tab: genuine?, what they ship, origin, frequency, volume, services,
   budget, expected first shipment, decision maker. The qualification score updates on save; moving to
   **Qualified** is refused below the minimum (default 60%) or if not confirmed genuine. Lead score /
   temperature update from the engagement signals.
5. **Follow up** — `/crm` → Tasks → New, type **Follow-up**, due date/time, priority, reason (or Desk →
   Contact → Add Follow-up). A reminder is sent at *Remind At* (default 30 min before due) to the CRM bell
   and Desk bell; overdue follow-ups show a red banner on the lead and appear in *Overdue Follow-ups*.
   The lead's *Next Follow-up* field always shows the earliest open follow-up. Mark the task Done
   (optionally with an outcome) when completed.
6. **Create the opportunity** — `/crm` lead → **Convert to Deal**. Frappe CRM creates the Contact (and
   Organization for businesses) and the Opportunity; Pakkmaxx fields (WhatsApp, services, route, attribution,
   contact dates) carry over. The lead becomes **Converted**.
7. **Move through the pipeline** — Qualified → Requirement Collected → Quote/Proposal → Negotiation.
   Enter the estimated value in GHS; probability and weighted value follow the stage.
8. **Won** — requires a deal value. On Won, the **Pakkmaxx Customer** is created (or the existing one is
   linked — matched by contact, phone/WhatsApp, email, organization) with: original lead, source, campaign,
   sales rep, first opportunity, services, product categories, days lead→customer. The customer page shows
   the combined history of the lead and all its opportunities (notes, WhatsApp logs, tasks, calls, emails,
   stage changes).
9. **Repeat business** — on the customer: **New Opportunity** (Desk) or create a Deal with *Customer*
   set (`/crm`). Source becomes *Existing Customer*, contact details are pre-filled. A second won
   opportunity makes the customer a **Repeat Customer**.

## Other outcomes
- **Lost lead** — status Lost + lost reason (price, chose another forwarder, no response, …). Lost leads
  cannot be converted. Managers can reopen.
- **Unqualified lead** — status Unqualified + reason (fills Frappe CRM's lost reason automatically).
- **Lost opportunity** — stage Lost + lost reason; the customer (if any) is recalculated.

## Customer lifecycle (automatic, recalculated daily and on every change)
| Stage | Rule (defaults in settings) |
|---|---|
| Customer | at least one won opportunity, last win older than the active window |
| Active Customer | one won opportunity within the last 90 days |
| Repeat Customer | two or more won opportunities |
| Dormant | no won opportunity or logged contact for 120 days |

Leads show a matching *Lifecycle Stage*: Lead (New) → Prospect (Contacted / Follow-up) → Qualified
(Qualified → Converted) → the customer's stage once linked; Lost for lost/unqualified.

Segments (SME, Retailer, WhatsApp Seller, VIP, …) are chosen manually on the customer; *New Customer* is
added automatically on creation.

## Status mapping to the brief
| Brief | Frappe CRM / Pakkmaxx |
|---|---|
| Opportunity | CRM Deal |
| Task statuses Open / In Progress / Completed / Cancelled | CRM Task Todo (or Backlog) / In Progress / Done / Canceled |
| Follow-up | CRM Task with Type = Follow-up |
| Notes (general, sales, follow-up, account) | FCRM Note with Note Type |
| WhatsApp conversation / meeting activity | FCRM Note with Note Type, plus WhatsApp messages if the frappe_whatsapp app is installed |
| Customer | Pakkmaxx Customer (+ Contact / CRM Organization) |
