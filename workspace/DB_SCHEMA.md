---
status: confirmed (structure only — no commission rules)
last_verified: 2026-07-06
source: prod_main (PostgreSQL, via Railway REST proxy, read-only)
---

# Finance DB Schema Map

This documents the raw structure of the tables relevant to finance data, confirmed
by direct querying of production data on 2026-07-06. The source DB has 137 tables
total (migrated from a Bubble.io app — most tables are unrelated app features:
CRM, calendar, chat, SEDA/TNB solar-specific reference data, etc). Everything
outside this doc is out of scope unless later work pulls it in.

**This document is purely descriptive: what tables/columns exist and how they
join.** It intentionally contains no commission rules or business-logic
decisions (eligibility, crediting, rates, etc.) — those are taught to the AI
Finance Agent directly by the user through the app's own interview process and
stored as versioned Rule Specs (see ARCHITECTURE.md), not decided during
development.

## Row counts (2026-07-06)
- `invoice`: 7,884
- `payment`: 3,629
- `agent`: 192
- `customer`: 6,861

## Tables

### `invoice`
One row per invoice. ~150 columns total (Bubble migration artifact); only the
columns below are catalogued. **id** is the internal integer PK; **bubble_id**
is a UUID used as the join key from `payment`.

| Column | Notes |
|---|---|
| `id` | internal PK (integer) |
| `bubble_id` | UUID join key — matches `payment.linked_invoice` |
| `invoice_number` | human-readable invoice number, e.g. `INV-1009964` |
| `linked_agent` | join key → `agent.bubble_id` |
| `linked_customer` | join key → `customer.bubble_id` |
| `total_amount` | invoice total field |
| `amount` | older invoice total field — `NULL` on all recently created invoices sampled, while `total_amount` is populated on the same rows |
| `paid_amount` | cumulative paid field on the invoice record itself (not necessarily kept in sync with actual `payment` rows — see below) |
| `balance_due` | remaining balance field on the invoice record itself (same caveat) |
| `paid` | boolean |
| `status` | text field — observed values include `draft`, `deleted`, `payment_submitted`, `test`, and `null`. Distribution is skewed: most rows of every `paid` value are `status='draft'`, including 860 rows where `status='draft'` and `paid=true` |
| `linked_payment` | array of `payment.bubble_id` — reverse link to payments |
| `invoice_date` | invoice issue date |
| `full_payment_date`, `last_payment_date`, `1st_payment_date` | payment milestone dates |
| `is_deleted`, `deleted_at` | soft-delete flags |
| `customer_name_snapshot`, `customer_email_snapshot`, `customer_phone_snapshot`, `customer_address_snapshot` | denormalized customer info at invoice time — usable without joining `customer` |
| `discount_percent`, `discount_fixed` | discount fields |
| `normal_commission`, `amount_eligible_for_comm`, `special_comm`, `commission_paid`, `commission_finalized`, `final_comm_payment_amount`, `perf_tier_commission` | commission-related columns populated by the old (pre-migration) system |

### `payment`
One row per payment record.

| Column | Notes |
|---|---|
| `id` | internal PK |
| `bubble_id` | join key, e.g. `pay_82bec8de8d15c634` |
| `linked_invoice` | join key → `invoice.bubble_id` |
| `linked_agent` | join key → `agent.bubble_id` |
| `linked_customer` | join key → `customer.bubble_id` |
| `amount` | payment amount field |
| `payment_date` | date field |
| `payment_method` / `payment_method_v2` | observed values include CREDIT CARD, EPP, E-Wallet, Online Transfer |
| `verified_by` | text field, e.g. "System Admin" |
| `epp_month`, `epp_type`, `epp_cost` | installment-plan (EPP) related fields |
| `bank_charges` | fee field |

Note: on 106 of 3,594 sampled payments (~3%), `payment.linked_agent` differs
from the `linked_agent` on the invoice it points to. This is a raw data
observation, not a rule about which one to use for anything.

### `submit_payment` / `submitted_payment`
Two additional payment-shaped tables with mostly overlapping columns to
`payment`. `submitted_payment` additionally has a `status` column (observed
values: `deleted`, `pending`); `submit_payment` doesn't. Relationship/lifecycle
between these three payment tables not fully catalogued beyond the column list.

### `agent`
Salesperson/agent directory.

| Column | Notes |
|---|---|
| `id` | internal PK |
| `bubble_id` | join key — confirmed 500/500 match against `invoice.linked_agent` and `payment.linked_agent` in sampling. Mixed ID formats exist in this column across records (older rows use raw Bubble IDs like `1739157787604x944826037874196500`, newer rows use `agent_<hex>`) — historical migration artifact; join on `bubble_id` works regardless of format. |
| `name` | agent display name |
| `agent_type` | distinct values (of 192 agents): `null` (134), `internal` (18), `Sales Agent` (15), `outsource` (10), `block` (5), `FULL TIME` (3), `''` empty string (2), `Referral Partner` (2), `Strategic Partner` (1), `Branch Manager` (1), `manual` (1) |
| `agent_code` | short code, often null |
| `commission` | integer field, values seen: `3`, `4`, `5` (57 agents), `null` (135 agents) |
| `group_member`, `group_name`, `introducer` | text fields, possible hierarchy/referral structure — meaning not catalogued |

## Join map (confirmed by sampling)

```
payment.linked_invoice  = invoice.bubble_id
invoice.linked_payment  ⊇ payment.bubble_id   (redundant array, reverse of above)
invoice.linked_agent    = agent.bubble_id
payment.linked_agent    = agent.bubble_id
```
