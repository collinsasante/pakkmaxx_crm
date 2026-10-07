# 6. API & future integrations

## Authentication
Use a dedicated **API user** per integration (e.g. `whatsapp-bot@pakkmaxx…`) with the minimum role
profile it needs (lead intake: *Pakkmaxx CRM Manager* or a custom role with CRM Lead create), and an
API key/secret (User → API Access → Generate Keys):

```
Authorization: token <api_key>:<api_secret>
```

Never call these from a browser with embedded keys; call from your server/bot. All endpoints reject
guests. Every endpoint checks Frappe permissions on the records it touches.

## Pakkmaxx endpoints (`/api/method/...`)

| Method | HTTP | Purpose |
|---|---|---|
| `pakkmaxx_crm.api.leads.capture_lead` | POST | Intake from website forms, WhatsApp Business bot, ads. Idempotent: returns the existing lead/customer if the phone, WhatsApp or email is known (and attaches the new message as a note), otherwise creates an **unassigned** lead with source + UTM. Args: `first_name`, `mobile_no` / `whatsapp_no` / `email`, `last_name`, `organization`, `source`, `city`, `message`, `services` (list), `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `landing_page`. |
| `pakkmaxx_crm.api.leads.check_duplicates` | GET | Records already using a phone / WhatsApp / email (IDs and owner only). |
| `pakkmaxx_crm.api.activities.log_interaction` | POST | Log a WhatsApp chat, meeting, call summary or note on a lead / opportunity / customer. |
| `pakkmaxx_crm.api.activities.get_timeline` | GET | Unified history of a lead, opportunity or customer (notes, tasks, calls, emails, status/owner/value changes). |
| `pakkmaxx_crm.api.followups.create_follow_up` | POST | Follow-up with due date, priority, reminder (managers may assign to others). |
| `pakkmaxx_crm.api.followups.complete_follow_up` | POST | Mark done with outcome. |
| `pakkmaxx_crm.api.followups.my_follow_ups` | GET | Current user's overdue / today / upcoming follow-ups (for a mobile app). |
| `pakkmaxx_crm.api.customers.convert_to_customer` | POST | Create/link the customer for a won opportunity (idempotent; normally automatic). |
| `pakkmaxx_crm.api.customers.create_opportunity` | POST | New opportunity for an existing customer. |
| `pakkmaxx_crm.api.dashboard.summary` | GET | All KPI numbers for the current user. `…dashboard.<card>` return single cards. |
| `crm.fcrm.doctype.crm_lead.crm_lead.convert_to_deal` | POST | (Frappe CRM) convert lead → opportunity. |

Standard REST also works with the same permissions: `GET/POST/PUT /api/resource/CRM Lead`,
`CRM Deal`, `Pakkmaxx Customer`, `CRM Task`, `FCRM Note`, `Contact`, …

Example — WhatsApp bot pushes a new chat:

```bash
curl -X POST https://crm.pakkmaxx.example/api/method/pakkmaxx_crm.api.leads.capture_lead \
  -H "Authorization: token $KEY:$SECRET" -H "Content-Type: application/json" \
  -d '{"first_name":"Abena","whatsapp_no":"0244123456","source":"WhatsApp",
       "message":"How much to ship 2 CBM from Guangzhou?","services":["Sea Freight"]}'
```

## WhatsApp
Now: WhatsApp number on leads/opportunities/contacts/customers, click-to-chat buttons (`wa.me`),
WhatsApp conversation notes, contact tracking, `capture_lead` for a bot.

Later — WhatsApp Business (Cloud) API: install Frappe's `frappe_whatsapp` app on the same bench;
Frappe CRM already shows its *WhatsApp Message* records on leads/deals, and Pakkmaxx CRM's
`WhatsApp Message` hook updates contact dates automatically. Store Meta credentials only in that app's
settings (encrypted Password fields) — never in this repository or in client-side code.

## Future Pakkmaxx modules
Build each as its own Frappe app on the same bench (e.g. `pakkmaxx_freight`, `pakkmaxx_warehouse`,
`pakkmaxx_billing`, `pakkmaxx_portal`) with `required_apps = ["pakkmaxx_crm"]`:

| Future module | Link to |
|---|---|
| Shipments, packages, shipping marks, warehouse arrivals | `Pakkmaxx Customer` (customer ID `PKX-CUS-#####` is stable and can seed shipping marks) and optionally the `CRM Deal` that won the job |
| Invoices, payments | `Pakkmaxx Customer` |
| Customer portal | `Pakkmaxx Customer.portal_user` (reserved field) — portal pages must filter by the logged-in user's customer; CRM notes, tasks and internal data have no web routes |
| Customer activity | call `pakkmaxx_crm.events.activity.touch_contact("Pakkmaxx Customer", name)` and set `last_activity_on`, so shipments keep customers out of *Dormant* |
| Lifetime value from invoices | extend `pakkmaxx_crm.customers.recompute_customer` |

Do not add these features to `pakkmaxx_crm`; keep it the CRM.

## Multi-currency
Values are GHS. Frappe CRM stores `currency` and `exchange_rate` per opportunity; Pakkmaxx reports convert
non-GHS opportunities with that rate. To quote in USD/CNY later, enable those currencies, set an exchange
rate provider in FCRM Settings and keep GHS as the reporting currency.
