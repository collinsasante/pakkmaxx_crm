# Airtable → Pakkmaxx CRM migration map

**Status: Phase B — DRAFT from the documented schema. Not yet verified against the live Airtable base. No data has been read or imported.**

One-way, one-time migration of legacy Airtable data into Pakkmaxx CRM (Frappe). Airtable is never modified. VerzChat stays the live source of WhatsApp leads; nothing here may duplicate a lead or customer that VerzChat already created.

## 1. Where the Airtable data comes from (discovery)

| Source | What it is | Evidence | Access |
|---|---|---|---|
| **Pakkmaxx shipping base** (`AIRTABLE_BASE_ID`) | Pakkmaxx's operational system: customers, warehouse items, containers, invoices, support tickets, status history, users | `~/Movezz-shipping/AIRTABLE_SCHEMA.md` (titled "Pakkmaxx — Airtable Base Schema", 8 tables), app `collinsasante/Movezz-shipping` (Next.js on Cloudflare, Firebase Auth, Cloudinary photos) | Key only in GitHub Actions / Cloudflare secrets — **not readable**. Needs a read-only token (see §8). |
| **VerzChat → Airtable lead push** | VerzChat posts each new WhatsApp lead to one Airtable table: `Name, Phone, Source='VerzChat', Date, Status='New Lead', First Message` | `apps/backend/src/conversations/airtable.service.ts` (`pushNewLead`), per-workspace settings `airtableEnabled / airtableBaseId / airtableTableName / airtableApiKey` | Stored in VerzChat's database (server not accessible). Unknown whether Pakkmax enabled it or which base/table. |

Not Pakkmaxx (ignored): `glam-delivery-tracking`, `glam-design`, `Glampack-HR` (Packaging Glamour). `pakkmax-scratch` only contains the same VerzChat lead push and a product-catalog import (not CRM data).

## 2. Tables, purpose and proposed destination

Record counts: **unknown until the live base is read** (filled in by the dry run).

| # | Airtable table | Purpose | Migrate? | Destination in Frappe | Why |
|---|---|---|---|---|---|
| 1 | **Customers** | Shipping customers (shipping mark, address, status) | **Yes** | **Pakkmaxx Customer** (+ Frappe **Contact** for phone/email) | These are real customers, i.e. the CRM's customer entity — not leads. |
| 3 | **Orders** | Invoices per customer (GHS amount, Pending/Paid) | **Yes, as history** | Customer financial history: `lifetime_value`, `first_won_on`, `last_won_on`, `won_deals_count` on Pakkmaxx Customer + one **FCRM Note** per order (ref, amount, status, date). **Decision needed** whether each order should instead become a **CRM Deal** (Won/Open) — see §6 D2. | Orders are billing records of completed shipments, not sales opportunities. |
| 8 | **SupportTickets** | Customer support conversations (JSON messages, Firebase file URLs) | **Yes, as notes** | **FCRM Note** on the customer's record, transcript as text (one note per ticket) | Historical customer communication; no CRM ticket entity exists. |
| 2 | **Items** | Warehouse items (photos, weights, dimensions, carton, tracking) | **No (default)** | — (optional summary: item count / last item date on the customer note) | Operational warehouse data, not CRM; stays in the shipping app. |
| 4 | **Containers** | Container shipments | **No** | — | Logistics, not CRM. |
| 5 | **StatusHistory** | Status changes of items/containers/orders | **No** | — | Operational audit trail. |
| 6 | **ActivityLogs** | App audit log (incl. IP addresses) | **No** | — | App security log; contains personal data with no CRM purpose. |
| 7 | **Users** | Firebase logins (super_admin / warehouse_staff / customer) | **No** | — (`portal_user` stays empty) | Authentication data; never migrate credentials/roles. |
| — | **VerzChat lead table** (name unknown) | Copy of VerzChat leads | **No** | — | Same leads already synced from VerzChat (3,180 leads). Only used as a cross-check in the dry run if accessible. |

## 3. Field maps

### Customers → Pakkmaxx Customer (+ Contact)

| Airtable | Frappe | Transformation | Required? | Notes |
|---|---|---|---|---|
| record id (`rec…`) | **new field `airtable_record_id`** (Pakkmaxx Customer, unique) | as is | yes | Idempotency key; no existing external-id field fits (checked). |
| Name | `customer_name` | trim | **yes** | Missing → *Invalid* (unless phone present → review). |
| Phone | `mobile_no`, `whatsapp_no` (+ Contact phone) | normalise to `+233…` with the same `normalize_phone` used by the VerzChat sync | strongly preferred | Primary match key (§4). |
| Email | `email` (+ Contact email) | lower-case, validate | no | Secondary match key. |
| ShippingMark | new field `shipping_mark` (Data) **or** FCRM Note | as is | no | **D3**: no existing field means "shipping mark". |
| ShippingAddress | `location` | as is | no | Check content first (may be the warehouse address, not the customer's). |
| FirebaseUID | — | not migrated | — | Auth identifier. |
| Status (active/inactive) | `disabled` (inactive → 1) and `lifecycle_stage` | active → "Customer" (or "Active Customer"/"Repeat Customer" from order history) | no | **D4** confirm lifecycle rule. |
| Notes | FCRM Note "Airtable notes" | text | no | |
| CreatedAt | new field `airtable_created_at` (Datetime) | ISO → site time zone | no | Frappe `creation` is **not** faked. |
| CreatedBy | in the note header | text | no | Staff email; not mapped to a user. |
| — | `source` | "Airtable (legacy)" lead source | — | New CRM Lead Source entry. |
| — | `integration_note` | "Imported from Airtable on …, run <id>" | — | Visible provenance. |

### Orders → customer history (default) — see D2

| Airtable | Frappe | Transformation |
|---|---|---|
| OrderRef, InvoiceAmount, Status, InvoiceDate, Notes | FCRM Note on the customer: "Order ORD-… — GHS … — Paid — 2024-…" | currency GHS as is |
| InvoiceAmount where Status = Paid | add to `lifetime_value` | sum |
| min / max InvoiceDate where Paid | `first_won_on` / `last_won_on`; count → `won_deals_count` | |
| Customer (link) | the customer's record | via `airtable_record_id` |

### SupportTickets → FCRM Note

| Airtable | Frappe | Transformation |
|---|---|---|
| TicketRef, Subject, Status | note title "Support SUP-… — Subject (open/resolved)" | |
| Messages (JSON) | note body: one line per message "date — sender: text"; files listed by name only (§7) | parse JSON; invalid JSON → *Invalid* (kept in report) |
| CreatedAt / UpdatedAt | in the note body | not faked as `creation` |

## 4. Matching (no duplicates with VerzChat data)

For each Airtable customer, in order:

1. **Already migrated**: Pakkmaxx Customer with the same `airtable_record_id` → *Existing* (re-runs are no-ops).
2. **Normalised phone** (`+233…`, last 9 digits then exact, same function as the VerzChat sync):
   - exactly one **Pakkmaxx Customer** → *Update* (fill empty fields only, never overwrite).
   - no customer but exactly one **CRM Lead** (typically from VerzChat) → *New customer linked to that lead* (`original_lead`, and the lead's `pkx_customer`) — the lead itself is **not** changed (status stays New, per the boss's decision).
   - more than one candidate → *Needs review*.
3. **Normalised email**, same rules as phone.
4. **Name only** is never enough. Name + city/company is used only to *flag* possible matches for review, never to merge.
5. Phone and email point to **different** existing records → *Needs review*.

Also detected: two Airtable customers with the same phone/email → *Duplicate* (both listed; the oldest is the candidate to keep).

## 5. Dry run / preview categories (Phase C–D)

New · Existing (no action) · Update (fills empty fields) · Linked to existing lead · Duplicate (within Airtable) · Needs review · Invalid (with reason). Every Airtable record lands in exactly one category; nothing is silently skipped. The dry run writes **nothing** to the CRM; it produces this report with real counts and per-record CSVs for review.

## 6. Decisions needed from the business (ambiguities)

- **D1** Confirm the Pakkmaxx base is the right/only Airtable source (and whether VerzChat's Airtable lead push is enabled; if so, which table).
- **D2** Orders: history on the customer (default) **or** one CRM Deal per order?
- **D3** Shipping mark: new field on Pakkmaxx Customer (recommended — it identifies the customer's goods) or note only?
- **D4** Lifecycle: "Repeat Customer" when ≥2 paid orders, "Active Customer" when an order in the last N months, else "Customer"? `inactive` → disabled?
- **D5** Items/Containers: confirm they stay out of the CRM (optional: per-customer item count in a note).
- **D6** Owner (`sales_rep`): Airtable has no salesperson field → leave empty?

## 7. Attachments plan

- **Items.Photos** (Airtable attachments): not migrated by default (Items not migrated). If wanted later: count/size first; Airtable attachment URLs expire after ~2 h, so files must be downloaded server-side during the run and stored as **private** Frappe files.
- **SupportTickets** files are **Firebase Storage** URLs inside the JSON. Not downloaded by default: the note lists file name/type/size only (no URL is copied into the CRM). If needed: assess volume and access, then download server-side to private files.
- No Airtable or Firebase URL is ever stored or exposed in the CRM.

## 8. To proceed (Phase B completion)

Needed from the user: a **read-only Airtable personal access token** for the Pakkmaxx base only — scopes `data.records:read` and `schema.bases:read`, access limited to that base — saved privately the same way as the DeepSeek key:

```
read -s "?Airtable token: " K && printf %s "$K" > ~/pakkmaxx-crm/secrets/airtable_token && chmod 600 ~/pakkmaxx-crm/secrets/airtable_token && unset K && echo saved
```
plus the base id (`app…`, not secret). With that, discovery reads the live schema (`GET /v0/meta/bases/{base}/tables`) and counts records (read-only, paged), and this document is updated with real fields and counts before any dry run.

## 9. Import design (Phase E, only after the dry run is approved)

Idempotent by `airtable_record_id`; resumable (cursor per table in the run log); batches of 100 with commit per batch; per-record audit (**Airtable Migration Log**: run id, table, record id, destination doctype/name, action created/updated/linked/skipped/review/failed, error, timestamp) and run summary (started/finished/initiated by/counts); database backup before the production run; non-destructive (only fills empty fields; never deletes); Frappe permissions respected (run as System Manager via a whitelisted, System-Manager-only method).
