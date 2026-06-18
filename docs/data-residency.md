# Comet — Data Residency & What the Dashboard Receives

This document states precisely what Comet does and does not do with a client's data, for
use in security and compliance review.

## Deployment model (current): connected, read-only, consent-based egress ("agentless")
Comet connects to the client's database with **read-only, least-privilege** credentials and
runs checks. Queries execute inside the client's database engine; Comet receives only what a
check needs to produce a result. **Only metadata leaves**: test outcomes (pass/fail), counts,
and aggregate metrics. No raw record values are transmitted or stored. (custom_sql currently
emits only its pass/fail outcome — see below; a deliberate way to surface chosen outputs may
be designed later.)

This is the same "agentless" model used by Monte Carlo's and Bigeye's default deployments:
the vendor connects read-only, pushes the queries into the customer's database, and only
aggregated metadata comes back.

### The three dimensions a security review separates
- **Access** — Comet connects with read-only, least-privilege credentials (scoped to only the
  schemas/tables/views the checks need). This bounds what Comet *could* read.
- **Egress** — only metadata leaves the client's database; raw record values are not
  transmitted.
- **Storage** — Comet stores only results/metrics; raw records are never persisted.

> Accurate claim to use publicly:
> *"Comet connects to your database with read-only, least-privilege access. It transmits to
> the dashboard only your test results, metrics, and alert summaries. No raw records from your
> database are read into the dashboard, transmitted, or stored."*
>
> Do NOT claim "the engine runs entirely inside your infrastructure" or "Comet never connects
> to your database" in this model — those describe the agent / in-VPC tier (below).

## What each check emits (the only things stored/shown)
| Check | Emitted to dashboard | Raw data? |
|---|---|---|
| null_check | total rows, null count, null %, threshold | No (aggregates) |
| duplicate_check | total rows, duplicate groups, columns checked | No |
| unique_check | total rows, distinct count, duplicate count | No |
| range_check | total rows, outlier count, configured min/max | No |
| row_count | row count, configured min/max, timeframe | No |
| relationship_check | source rows, orphan count, orphan % | No |
| schema_check | declared expected columns, which are missing, type mismatches | No — and the full table column list is **not** enumerated |
| custom_sql | pass/fail + assertion text only; result value **not transmitted** | No |

Table and column names that appear come from the client-authored test definitions (config),
not from data pulled out of the database.

## custom_sql — result handling
custom_sql runs an operator-authored query and asserts on the first returned value.
- The assertion is evaluated locally to produce pass/fail — the only thing transmitted
  (alongside the operator-authored assertion text).
- The query's **result value is never placed in metrics or the message**, so a raw record
  value cannot leak.

A deliberate mechanism for surfacing a chosen output (a metric) to the dashboard is planned
but not yet implemented — to be designed so the operator explicitly controls any such egress.

## Required: read-only, least-privilege database credentials
The credentials Comet uses **must be read-only and least-privilege** — scoped to only the
schemas/tables/views the checks need, so that even a compromised Comet could not read beyond
them. The client enforces this when provisioning the database user; Comet cannot enforce it
server-side. Read-only matters especially for `custom_sql`, which executes arbitrary
operator-authored SQL — read-only credentials guarantee such a query can never modify data.
Secrets are supplied as `${ENV}` references and are never stored in plaintext (rejected at
upload). This least-privilege scoping is the lever that turns "we only read what we need"
into "we *cannot* read beyond what we need."

## Residual considerations
- In this connected model, the value of a custom_sql query is transiently held in Comet's
  process memory while the assertion is evaluated, then dropped — never logged, stored, or
  transmitted onward. The only way Comet never even momentarily receives a value is the agent
  model below.
- Database error messages surfaced into a result `message` describe SQL/schema problems, not
  row contents; run-level error reasons are sanitized.

## Future: agent / in-VPC tier (strictest)
For clients who cannot grant any external access, the engine can run as an always-on worker
inside the client's own environment (container / Airflow / cron / serverless). Comet holds no
credentials and never connects; only result metadata is posted out. This supports the
stronger claim *"the monitoring engine runs entirely inside your infrastructure; your data
never leaves your environment."* The dashboard (Run button, scheduling) can still drive it via
a pull model (the agent polls for requested runs). Not yet implemented.
