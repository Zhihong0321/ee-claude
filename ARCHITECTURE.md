# EE Finance Agent — Architecture

> **Status:** Approved design, pre-implementation.
> **Last updated:** 2026-07-06
> **Read this first.** Every coding session on this project must load this file before making changes.

## 1. Goal (non-negotiable)

An AI "Finance Department" where a **non-coder** tells the AI commission rules in plain
language. The AI **interviews** the user until the rule specification is complete, then
**reads real invoice/payment data** from the company's existing PostgreSQL database,
**calculates commissions deterministically**, **records results** in its own database,
and **produces reports** humans can review — with full memory of every rule, decision,
and run so far, accessible through a **chat interface** and a **document interface**.

## 2. Core design principle: the LLM never does money math

The single most important rule of this system:

> **The AI captures rules and writes code. Deterministic code calculates money.**

An LLM computing commissions at runtime is non-reproducible and non-auditable. Instead:

1. **Interview → Rule Spec.** The agent interviews the user and produces a versioned,
   human-readable specification document.
2. **Spec → Generated code.** The agent generates a deterministic Python rule module
   from the approved spec, with unit tests derived from the interview's worked examples.
3. **Code → Report.** The commission engine runs the rule module against real DB data.
   Same inputs always produce the same output. Every number traces to specific invoices,
   a specific spec version, and a specific code version.

Consequences:
- Chat is for capturing intent. Documents (specs, reports, decision log) are what the
  system *knows*. The "finance memory" IS the document library.
- A commission report can always be regenerated and explained line-by-line.
- Changing a rule means a new spec version + new generated module — history is preserved.

## 3. Decisions already made (do not re-litigate)

| Decision | Choice | Why |
|---|---|---|
| Source finance DB | Existing **PostgreSQL**, read-only | Production data; agent must never write to it |
| Agent's own DB | **New PostgreSQL database** (separate DB, agent-owned) | Records specs, runs, ledger, documents |
| Deployment | **This Windows PC**, web UI served on LAN | User's choice; staff access via browser on office network |
| Users | Owner + 2–5 finance staff | Simple session login with roles: `admin`, `finance`, `viewer` |
| Recording model | **Auto-record, review later** | Reports are recorded immediately as official; humans audit and can **void/correct** — never edit or delete. Append-only ledger, accounting-style |
| LLM | **Claude Sonnet (Anthropic API)** via user-provided key | Runs the agent through the Claude Agent SDK |
| Agent framework | **Claude Agent SDK (Python)** | Matches user's request; Python fits the rest of the stack |
| Backend | **FastAPI** | Serves web UI, chat websocket, document/report APIs |
| Calculation language | **Python rule modules**, versioned on disk + hashed in DB | Deterministic, testable, reviewable |

## 4. System components

```
┌─────────────────────────────  Windows PC (LAN)  ─────────────────────────────┐
│                                                                              │
│  Web UI (browser, staff PCs)                                                 │
│  ├── Chat pane        — talk to the Finance Agent                            │
│  ├── Documents pane   — specs, decision log, memory docs (view/search)       │
│  └── Reports pane     — commission reports, run history, void/correct        │
│                                                                              │
│  FastAPI backend ──────────────────────────────────────────────┐             │
│  │                                                             │             │
│  ├── Finance Agent (Claude Agent SDK, Sonnet)                  │             │
│  │   Tools:                                                    │             │
│  │   • query_finance_db   — SELECT-only against source PG      │             │
│  │   • docs_read / docs_write — document library               │             │
│  │   • memory_read / memory_write — instruction memory         │             │
│  │   • spec_workflow      — create/version rule specs          │             │
│  │   • codegen_rule       — generate + test rule modules       │             │
│  │   • run_engine         — trigger a commission run           │             │
│  │   • ledger_query       — read runs/lines/corrections        │             │
│  │                                                             │             │
│  └── Commission Engine (plain Python, NO LLM)                  │             │
│      loads approved rule module → queries source DB →          │             │
│      computes lines → writes run + report to app DB            │             │
│                                                                │             │
│  App DB (new PostgreSQL) ◄─────────────────────────────────────┘             │
│  Source finance DB (existing PostgreSQL) ◄── read-only role, SELECT only     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Finance Agent (Claude Agent SDK)

- One long-lived agent definition; each chat session gets a fresh context that loads:
  `FINANCE_MEMORY.md` (index) + active spec summaries + recent decision log entries.
- **Interview protocol** (the "very good interview skill") is a system-prompt skill with a
  mandatory checklist. For any commission rule the agent must pin down:
  - Who earns it (person, role, team, splits between people)
  - Base amount (invoice total? paid amount? before/after tax and discounts?)
  - Trigger timing (invoice issued vs. payment received vs. fully paid; period assignment)
  - Rate structure (flat, tiered, tiered-marginal vs. tiered-total, per-product overrides)
  - Partial payments, refunds, credit notes, clawbacks
  - Caps, floors, minimums, kickers
  - Currency and rounding (per line or per total; round half-up?)
  - Effective dates and what happens to in-flight invoices when rules change
  - Edge cases the user hasn't thought of — the agent must proactively probe
- **Confirmation by worked example is mandatory** before a spec is finalized: the agent
  computes 2–3 concrete examples with real-looking numbers and the user must confirm
  each ("Invoice #1024, RM10,000, 50% paid → Alice earns RM250 this month — correct?").
  Confirmed examples become the unit tests for the generated rule module.

### 4.2 Rule spec lifecycle

```
draft ──interview complete──► confirmed ──codegen + tests pass──► active
active ──user changes rule──► superseded (new version created as draft)
```

- Specs are markdown files in `workspace/specs/` with YAML frontmatter
  (`spec_id`, `version`, `status`, `effective_from`, `confirmed_examples`).
- Generated modules live in `rules/` as `<spec_id>_v<version>.py`, each with a
  matching test file. A module is only activatable if its tests pass.
- The app DB stores spec metadata + SHA-256 of spec text and module code, so any
  run can prove exactly which rule text and code produced it.

### 4.3 Commission Engine (deterministic, no LLM)

- Input: rule module version + period (e.g., 2026-06) + source DB snapshot query.
- Output: a **run** (immutable) containing commission **lines**, each line linking
  `invoice/payment IDs → salesperson → amount → rule version`.
- Auto-record model: runs are official when written. Corrections are new ledger
  entries referencing the original line (`void`, `adjustment`) — original rows are
  never updated or deleted.
- Every run stores: timestamps, spec version, code hash, input row count, input data
  hash. Re-running the same period with the same rule version must reproduce the
  same numbers or the engine flags source-data drift.

### 4.4 Memory architecture

Three layers, all visible in the Document Interface:

1. **Instruction memory** — `workspace/memory/FINANCE_MEMORY.md` index + one file per
   fact (company conventions, "always exclude delivery fees from commission base",
   user preferences). Loaded into every agent session.
2. **Spec library** — the active rule specs. The authoritative "what are our rules".
3. **Operational history** — decision log (`workspace/decisions/`, one entry whenever
   the user makes a ruling in chat) + run ledger in the app DB.

The agent has search tools over all three. "AI must be aware of the entire finance
memory" = index-in-context + on-demand retrieval, not stuffing everything into context.

### 4.5 Web application

- **Chat pane** — streaming chat with the agent; sessions persisted in app DB.
- **Documents pane** — browse/search specs, memory, decisions; render markdown;
  show spec version diffs.
- **Reports pane** — run history, report detail (per-salesperson, per-invoice drill-down),
  export (xlsx/pdf), and the review queue: mark reviewed, void, or correct lines
  (corrections require an `admin`/`finance` role and a reason, logged to audit).
- **Auth** — username/password sessions, roles `admin` (rules + corrections),
  `finance` (run engine, review), `viewer` (read reports). Served on LAN
  (`http://<pc-ip>:8080`), auto-started via Windows Task Scheduler / NSSM service.

### 4.6 Databases

**Source DB (existing PostgreSQL)** — accessed only through a dedicated read-only role.
The `query_finance_db` tool additionally rejects anything that is not a single SELECT.
On first connection the agent explores the schema and writes `workspace/DB_SCHEMA.md`
(tables, meanings, quirks) — the user confirms/corrects it, and it becomes memory.

**App DB (new PostgreSQL)** — owned by this system:

| Table | Purpose |
|---|---|
| `specs`, `spec_versions` | Rule specs + status + text hash |
| `rule_modules` | Generated code metadata + code hash + test status |
| `runs` | Immutable commission runs (period, spec version, hashes) |
| `commission_lines` | Per-person per-invoice amounts, source row references |
| `corrections` | Void/adjustment entries referencing original lines |
| `documents` | Document library metadata (files live on disk in `workspace/`) |
| `chat_sessions`, `chat_messages` | Persisted conversations |
| `users`, `audit_log` | Auth + every state-changing action |

## 5. Build phases

Each phase ends with something the user can actually use.

- **Phase 0 — Access & discovery.** Read-only PG role + Anthropic API key wired up
  (stored in Hermes vault). Agent explores source schema → `DB_SCHEMA.md` → user
  confirms it. *Deliverable: verified data access + confirmed schema map.*
- **Phase 1 — Chat + finance Q&A.** FastAPI app, login, chat pane, agent with
  `query_finance_db`. User can ask "total unpaid invoices for June?" and get real
  answers. *Deliverable: useful finance chat on real data.*
- **Phase 2 — Memory + documents.** Memory tools, decision log, Documents pane.
  *Deliverable: the agent remembers rulings across sessions; docs are browsable.*
- **Phase 3 — Rule spec workflow.** Interview protocol, spec lifecycle, codegen with
  tests from confirmed examples. *Deliverable: first active commission rule.*
- **Phase 4 — Engine + reports.** Commission engine, runs/lines/corrections, Reports
  pane with review queue and export. *Deliverable: first official commission report.*
- **Phase 5 — Hardening.** Windows service auto-start, nightly app-DB backup,
  audit-log review view, scheduled monthly run reminder.

## 6. What the user must provide (blocking items)

1. **Anthropic API key** (Sonnet) → add to Hermes vault as `anthropic-finance-agent`.
2. **Source PostgreSQL access**: host/port/db + a **read-only role** credential
   → Hermes vault as `finance-source-db`.
3. **App PostgreSQL**: either a new database on the same server or a local install
   → Hermes vault as `finance-app-db`.

## 7. Known risks (accepted)

- **Single-PC deployment**: if this PC is off, the system is down; app DB backups must
  be copied off this machine. Revisit VPS deployment if uptime becomes a problem.
- **Auto-record model**: wrong rules produce official wrong numbers until reviewed.
  Mitigated by mandatory worked-example confirmation before any rule goes active, and
  by the append-only correction workflow.
