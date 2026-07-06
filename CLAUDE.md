# EE-Finance-Agent

Read `ARCHITECTURE.md` before any work — it has the full project design.

Read `workspace/DB_SCHEMA.md` before writing any query, rule, or code that
touches the production Eternalgy DB (`prod_main`, via the `finance-prod-db-proxy`
credential). It documents confirmed table structure, join keys, and data quirks
learned by direct sampling — don't rediscover this from scratch, and don't
guess at joins that aren't documented there (several tables use non-obvious or
inconsistent join conventions).

Commission rules (rates, eligibility, crediting logic) are never decided or
hardcoded during development — they are taught to the deployed agent in-app by
the user and stored as versioned Rule Specs. `DB_SCHEMA.md` is intentionally
structural/descriptive only.
