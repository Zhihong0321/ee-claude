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

**This document is purely descriptive: what tables/columns exist, how they join,
and confirmed operational facts about data quality.** It intentionally contains no
commission rules or business-logic decisions (eligibility, crediting, rates, etc.)
— those are taught to the AI Finance Agent directly by the user through the app's
own interview process and stored as versioned Rule Specs (see ARCHITECTURE.md),
not decided during development.

## Row counts (2026-07-06)
- `invoice`: 7,888
- `payment`: 3,629
- `agent`: 192
- `customer`: 6,861
- `user`: 175
- `submitted_payment`: 916
- `submit_payment`: 3
- `seda_registration`: 11,274
- `referral`: 284
- `referal_contact`: 0
- `et_leads`: 11
- `invoice_new`: 158

## Sales Agent (`agent` vs `user`)

- **`agent`** (192 rows): the traditional agent-profile record. Key columns: `bubble_id`, `name`, `commission` (int, values 3/4/5, null on 135/192), `agent_type` (free text: `internal`, `Sales Agent`, `outsource`, `block`, `FULL TIME`, `Referral Partner`, `Strategic Partner`, `Branch Manager`, `manual`, null on 134/192), `group_member`/`group_name`/`introducer` (possible hierarchy, meaning unconfirmed). `bubble_id` has mixed formats (older rows: raw Bubble IDs like `1739157787604x944826037874196500`; newer rows: `agent_<hex>`) — join on `bubble_id` works regardless of format.
- **`user`** (175 rows): the login/account record. Significant column overlap with `agent` (`introducer`, `banker`, `bankin_account`, `ic_front`/`ic_back`, `address`). Links to `agent` via `user.linked_agent_profile` → `agent.bubble_id` (confirmed 175/175 populated).
- **Company direction (confirmed 2026-07-06):** most of Eternalgy's other ERP/Agent OS systems already no longer read/write/depend on `agent` — they depend on `user` instead. Plan is to eventually disable `agent` entirely, with everything (including join keys currently on `agent.bubble_id`) moving to `user.bubble_id`. **Not yet true in this DB's actual join columns** (see below) — don't assume `agent` is gone, but don't build new logic that assumes it's permanent either.
- **Current reality (confirmed by direct join testing 2026-07-06):** `invoice.linked_agent` and `payment.linked_agent` still exclusively resolve against `agent.bubble_id` — 100% of populated rows match `agent.bubble_id`, **zero** match `user.bubble_id` directly. `agent.bubble_id` remains the correct join key for invoice/payment today.

## `invoice`

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
| `total_amount` | invoice total field — use this, not `amount` |
| `amount` | older invoice total field — `NULL` on all recently created invoices sampled, while `total_amount` is populated on the same rows |
| `paid_amount` | cumulative paid field on the invoice record itself — not reliably kept in sync with actual `payment` rows, don't trust over summing `payment` |
| `balance_due` | remaining balance field on the invoice record itself (same caveat) |
| `paid` | boolean |
| `status` | text field — unreliable for lifecycle filtering. Observed values include `draft`, `deleted`, `payment_submitted`, `test`, and `null`. Most rows of every `paid` value are `status='draft'`, including 860 rows where `status='draft'` and `paid=true`. Use `paid`/summed `payment` rows instead of `status`, and always exclude `status='deleted'` |
| `linked_payment` | array of `payment.bubble_id` — reverse link to payments |
| `invoice_date` | invoice issue date |
| `full_payment_date`, `last_payment_date`, `1st_payment_date` | payment milestone dates |
| `is_deleted`, `deleted_at` | soft-delete flags |
| `customer_name_snapshot`, `customer_email_snapshot`, `customer_phone_snapshot`, `customer_address_snapshot` | denormalized customer info at invoice time — usable without joining `customer` |
| `discount_percent`, `discount_fixed` | discount fields |
| `normal_commission`, `amount_eligible_for_comm`, `special_comm`, `commission_paid`, `commission_finalized`, `final_comm_payment_amount`, `perf_tier_commission` | commission-related columns from the OLD pre-migration system — intentionally ignored, the new engine recomputes from scratch and never reads these as input |

**`invoice_new` (158 rows) — confirmed experimental/testing table, NOT part of
the real system data at all (explicit user confirmation, 2026-07-06).** `agent_id`
is NULL on every row; date range is only Dec 2025–Jan 2026. Ignore entirely for
finance purposes; do not treat as a newer version of `invoice`.

## `payment` vs `submit_payment` vs `submitted_payment`

- **`payment`** (3,629 rows): the authoritative confirmed-money-received table — this is what calculations should sum/use.
- **`submitted_payment`** (916 rows): a pre-verification submission queue. `status` distribution: 907 `deleted`, 9 `pending`. **Confirmed (2026-07-06, per user): `status='deleted'` means the submission was approved and copied into `payment`**, not rejected/voided — this is the normal, successful path, not data loss.
- **`submit_payment`** (only 3 rows): essentially dead/unused — likely an earlier or abandoned version of the submission-queue feature. Don't build logic around it.
- **Payment date:** `payment.payment_date` (and `submitted_payment.payment_date`) is the real date money was received (confirmed 2026-07-06, per user) — use it over `created_at`/`modified_date`, which are just record bookkeeping timestamps.

| Column (`payment`) | Notes |
|---|---|
| `id` | internal PK |
| `bubble_id` | join key, e.g. `pay_82bec8de8d15c634` |
| `linked_invoice` | join key → `invoice.bubble_id` |
| `linked_agent` | join key → `agent.bubble_id` |
| `linked_customer` | join key → `customer.bubble_id` |
| `amount` | payment amount field |
| `payment_date` | real date money was received — see above |
| `payment_method` / `payment_method_v2` | observed values include CREDIT CARD, EPP, E-Wallet, Online Transfer |
| `verified_by` | text field, e.g. "System Admin" — correspondence to any staff/user record unconfirmed |
| `epp_month`, `epp_type`, `epp_cost` | installment-plan (EPP) related fields |
| `bank_charges` | fee field |

Note: on 106 of 3,594 sampled payments (~3%), `payment.linked_agent` differs
from the `linked_agent` on the invoice it points to. This is a raw data
observation, not a rule about which one to use for anything — commission is
always credited to the invoice's agent regardless.

## SEDA Registration

`seda_registration` (11,274 rows) tracks the SEDA/NEM solar registration &
approval process per installation — mostly document/compliance fields (IC
copies, TNB bills, drawings, roof images, etc).

**Non-obvious join chain (confirmed 2026-07-06 by direct testing):**
`seda_registration.agent` does **not** match `agent.bubble_id` directly (0
matches tested). It matches through `user`:

```
seda_registration.agent  = user.bubble_id
user.linked_agent_profile = agent.bubble_id
```

Confirmed 11,172/11,274 (99%) match on the full chain. If you ever need to
attribute a SEDA record to an agent, go through `user`, not straight to `agent`.

`seda_status` distribution: null (8,607), `Pending` (2,455), `Submitted` (189),
`Approved` (10), `DEMO` (9), `APPROVED BY SEDA` (4) — most registrations never
reach a terminal status.

**Confirmed (2026-07-06, per user): SEDA registration status is purely
operational/compliance tracking and is NOT relevant to commission calculation.**
Don't gate or adjust commission logic on `seda_status`.

`seda_agent_identity_backup_20260428` is a one-off backup table (2,186 rows)
from an agent-identity remap done 2026-04-28; its `old_agent`/`new_agent`
values are stale raw Bubble IDs that don't match current `agent.bubble_id` or
`seda_registration.agent` either — historical artifact only, not part of any
live join path.

## Referral (and leads)

**`referral`** (284 rows) is a newer, still-early-stage in-house feature, **not
yet driving real commission payouts** (confirmed 2026-07-06, per user). Evidence:
`deal_value`/`commission_earned` are 0.00 on every sampled row, and only 7/284
rows are `status='Successful'` (262 `Pending`, 14 `Contacted`, 1 `Declined`).

It uses its **own ID scheme**, separate from the legacy Bubble-migration world:
`bubble_id` values look like `ref_xxxxx`, `linked_customer_profile` values look
like `cust_xxxxx` — these do **not** match `customer_profile.bubble_id` (which
is still the old raw Bubble format, e.g. `1695099251636x...`). Only 10/284
`linked_invoice` values match real `invoice.bubble_id` rows.

**Different join key convention than every other table:** `referral.linked_agent`
matches `agent.id` (the plain integer PK, e.g. `94`, `101`), **not**
`agent.bubble_id` like invoice/payment do (confirmed 146/284 non-null values
match on `::int = agent.id`).

**`referal_contact`** (note the typo in the table name) has **0 rows** —
appears to be a dead/abandoned earlier version of the referral feature. Safe
to ignore.

**`et_leads`** (WhatsApp-bot lead capture, only 11 rows, all `stage='NEW'`, no
agent-assignment column at all) — **confirmed out of scope for now** (2026-07-06,
per user). It has no `linked_agent`/similar column, so "which agent a lead is
assigned to" is not currently captured here at all. Don't assume this table
answers agent-assignment questions.

## Join map (confirmed by sampling)

```
payment.linked_invoice     = invoice.bubble_id
invoice.linked_payment     ⊇ payment.bubble_id           (redundant array, reverse of above)
invoice.linked_agent       = agent.bubble_id
payment.linked_agent       = agent.bubble_id
user.linked_agent_profile  = agent.bubble_id
seda_registration.agent    = user.bubble_id              (NOT agent.bubble_id directly)
referral.linked_agent      = agent.id  (integer PK, NOT bubble_id — unique to this table)
```

## Not yet catalogued (known gaps)

- `agent.group_member`/`group_name`/`introducer` — possible referral/hierarchy structure among agents, meaning unconfirmed.
- Whether `submitted_payment.verified_by` corresponds to any staff/user record, or is just free text.
