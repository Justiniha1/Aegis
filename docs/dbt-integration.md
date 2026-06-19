# Publishing dbt test results to Comet

Comet can show your dbt test results on your dashboard — with history and failure
alerting — without connecting to your warehouse. You keep running dbt exactly as you
do today; Comet just reads the results dbt already produces.

## How it works

After any `dbt build` or `dbt test`, dbt writes `run_results.json` and `manifest.json`
into your project's `target/` directory. The `comet dbt publish` command reads those two
files, translates each test outcome into a Comet result, and posts them to your
dashboard under a dedicated `dbt` profile. Comet never connects to your database for
this — it only reads those JSON files.

## Setup

1. Install the Comet CLI: `pip install comet-dq`.
2. Set your API key (from the dashboard Settings): `export COMET_API_KEY=<your-key>`.

## Usage

Run from your dbt project root, after your dbt step:

```bash
dbt build
comet dbt publish
```

Options:
- `--target-dir <path>` — point at a specific dbt `target/` directory.
- `--project-dir <path>` — dbt project root; artifacts are read from `<path>/target`.

Comet also honors dbt's `DBT_TARGET_PATH` environment variable.

## In a pipeline (Airflow / CI)

Add one step after your existing dbt step, e.g. a single shell command:

```bash
dbt build && comet dbt publish
```

## What you'll see

Your dbt tests appear on the dashboard under the `dbt` profile, each tagged by kind
(`dbt: Not Null`, `dbt: Unique`, `dbt: Relationships`, `dbt: Accepted Values`, or
`dbt: Test` for custom/singular tests), with pass/fail status, history across runs, and
failure alerting. A dbt `warn` is shown as failed, since the data still violated your
rule.

Note: Comet shows the tests dbt ran. Tables with no dbt tests are not covered here — for
those, configure Comet's own checks.
