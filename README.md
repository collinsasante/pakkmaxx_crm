# Pakkmaxx CRM

CRM for **Pakkmaxx**, a China → Ghana freight forwarding business. It turns conversations
(mostly WhatsApp) into shipping customers and repeat business:

**Lead → Conversation → Qualification → Follow-up → Opportunity → Customer → Repeat Business**

Built on **Frappe Framework v16** and the official **Frappe CRM** app (v1.86), extended — not forked —
by this app (`pakkmaxx_crm`).

| | |
|---|---|
| Daily sales work (mobile friendly) | `/crm` — Frappe CRM app with Pakkmaxx fields, WhatsApp/Call buttons |
| Dashboard, reports, setup | `/app/pakkmaxx-crm` — Desk workspace |
| Currency | Ghana Cedi (GHS) |

## What Pakkmaxx CRM adds to Frappe CRM

- **Shipping profile on leads**: WhatsApp number, customer/business type, services (air, sea, express,
  consolidation, door-to-door, warehousing, sourcing, repacking), product categories, China origin,
  Ghana destination, monthly volume (CBM/kg), spend, frequency, current forwarder.
- **Lead lifecycle workflow** (New → Contacted → Follow-up Required → Qualified → Proposal/Quote Requested →
  Negotiation → Converted, or Unqualified / Lost), enforced on the server.
- **Qualification gate** (genuine? what, from where, how often, how much, which service, budget, when,
  decision maker) and **configurable lead scoring** (Hot / Warm / Cold).
- **Attribution**: source, campaign, ad, referral, landing page, UTM source/medium/campaign/content.
- **Duplicate detection** on phone / WhatsApp / email across leads, contacts and customers
  (numbers normalised to +233…).
- **Pakkmaxx Customer**: created or linked automatically when an opportunity is won; keeps original lead,
  source, salesperson, history; lifecycle Customer → Active → Repeat → Dormant; segments.
- **Follow-ups** with reminders (CRM + Desk bell), overdue banners, daily digest.
- **Record-level security** for notes, tasks, calls, contacts, organizations and customers; ownership and
  assignment guards; pipeline configuration limited to managers.
- **Reports & dashboard**: source attribution (source → customer → GHS won), pipeline, follow-ups,
  uncontacted leads, customers, salesperson performance; 20 KPI cards.
- **Authenticated API** for future website / WhatsApp Business / mobile integrations.

## Documentation

1. [Installation (local development)](docs/01-installation.md)
2. [Configuration](docs/02-configuration.md) — lead sources, pipeline, services, scoring, segments
3. [Roles & permissions](docs/03-roles-and-permissions.md)
4. [Workflows](docs/04-workflows.md) — lead, qualification, follow-ups, opportunity, customer conversion
5. [Reports & dashboard](docs/05-reports-and-dashboard.md)
6. [API & future integrations](docs/06-api-and-integrations.md)
7. [Deployment: staging & production on Contabo](docs/07-deployment-contabo.md)

## Tests

```bash
bench --site test.pakkmaxx.localhost run-tests --app pakkmaxx_crm   # 29 tests
PKX_PASSWORD=... python3 scripts/http_smoke_test.py                  # 25 live HTTP checks
```

## Scope

This app is **CRM only**. Freight operations, warehouse, shipment tracking, invoicing, payments and the
customer portal are future Pakkmaxx modules; they should link to `Pakkmaxx Customer` and `CRM Deal`
(see [future integrations](docs/06-api-and-integrations.md#future-pakkmaxx-modules)).

License: MIT
