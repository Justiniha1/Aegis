# A5 Audit — CLI (`comet`) + client SDK (`comet_dq`) + Airflow operator

Read-only audit. No source files were modified. Scope: `cli/*`, `cli/commands/*`,
`comet_dq/*`, `comet_dq/airflow/*`. Tests under `tests/test_cli/*` and
`tests/test_comet_dq/*` were read for coverage analysis.

## Summary

The CLI and SDK are small, readable, and mostly correct. The `comet_dq` SDK is well
designed: a clean public surface (`run_checks`, two exception types), a fixed baked-in
hosted URL, env-var credential resolution, monotonic-clock timeout handling, and good
test coverage. The biggest risks are operational rather than catastrophic: every HTTP
call raises a raw `requests.HTTPError` whose `str()` is surfaced verbatim to end users
(poor error UX, and the URL — though not the key — leaks into messages); there are no
retries on transient 5xx/network errors despite the SDK polling a hosted service over the
internet; and there is duplicated, divergent HTTP-client code between `cli/api_client.py`
and `comet_dq/_client.py`. There is also a real consistency bug: `comet init` writes a
`database_connection.yaml` template (`type/path`) whose schema does not match the on-disk
template (`type/connection_url`) that `comet push` expects. Credential handling is
reasonable (key only in env/.env, never printed), but `.env` is created world-readable and
the SDK does not set `verify=` explicitly (relies on the requests default, which is True —
acceptable but worth an explicit note). The `cli`/`commands`/`api_client`/`config` split is
mildly over-fragmented for five thin commands but is defensible; the genuine duplication is
between the two HTTP clients, not within the CLI package.

## Findings

### [High] `comet init` writes a connection-profile template that `comet push` cannot use
Location: `cli/commands/init.py:8-25` (inline `_DATABASE_CONNECTION_YAML`) vs
`cli/templates/database_connection.yaml:13-15` and the documented schema at
`cli/templates/database_connection.yaml:4-8`.
What & why: `init_cmd` does NOT copy the on-disk `templates/database_connection.yaml`; it
writes a hard-coded inline string that uses `type: sqlite` + `path: ./data/your_database.db`.
The on-disk template (and the push contract, per the header comment "Each profile needs a
`connection_url` in SQLAlchemy URL format") uses `connection_url:`. So a user who runs
`comet init` then `comet push` uploads a profile with a `path` key and no `connection_url`.
Depending on the server's `/api/v1/profiles/sync` validation this either errors or creates an
unusable profile. The two templates have silently diverged. By contrast `test_definitions.yaml`
IS copied from disk (`init.py:38`), so only the connection file is inconsistent.
Recommendation: Make `init_cmd` copy `templates/database_connection.yaml` from disk (same
pattern as the test-definitions file) and delete the inline string, OR fix the inline string to
emit `connection_url:`. Confirm against the server's expected profile schema before choosing.
Disposition: ask-first (changes the scaffold output and must match the server contract).

### [High] Raw `requests` exceptions surfaced to users; no friendly error layer
Location: `cli/api_client.py:11,16,21` (`raise_for_status`); consumed at
`cli/commands/pull.py:20-22`, `push.py:25-27,36-37`, `run_cmd.py:55-57,70-72`,
`status.py:15-17`; SDK at `comet_dq/_client.py:50,60` and `comet_dq/_run.py` (docstring
admits `requests.HTTPError` escapes).
What & why: Every command does `except Exception as e: typer.echo(f"... {e}")`. For an HTTP
error `str(e)` is the full requests message, e.g. `401 Client Error: Unauthorized for url:
https://.../api/v1/runs`. This is not actionable for a client user (a 401 should say "check
your COMET_API_KEY"; a 404 profile should say "profile not found"). It also dumps the full URL
(not secret, but noisy) and, on connection errors, a stack-style message. Per CLI conventions,
domain errors should map to friendly messages and diagnostics go to logs/stderr
([zircote 2026](https://zircote.com/blog/2026/04/cli-error-messages-are-a-dual-consumer-problem/)).
Recommendation: Add a small error-translation helper (map 401/403 -> key guidance, 404 ->
profile/run guidance, 5xx -> "server error, retry later", `ConnectionError`/`Timeout` ->
network guidance). Keep raw detail behind a `--verbose`/`COMET_DEBUG` flag.
Disposition: ask-first (changes user-visible copy and message format that tests/users depend on).

### [Medium] CLI writes all command output (including errors) to stdout, not stderr
Location: `cli/commands/*` — every `typer.echo(...)` for error/diagnostic lines, e.g.
`pull.py:21`, `push.py:26,37`, `run_cmd.py:56,71,86`, `status.py:16`, `config.py:27`.
What & why: Errors and progress narration go to stdout. `typer.echo` supports `err=True` to
route to stderr. Convention is stdout = data (pipeable), stderr = narration/errors
([Localytics](https://eng.localytics.com/exploring-cli-best-practices/)). As written, piping
`comet status` mixes the table with any error banner, and scripting around exit codes is the
only reliable signal. `config.py:27` ("COMET_API_KEY not set") is the most important one to fix.
Recommendation: Pass `err=True` to `typer.echo` for all error/diagnostic lines; keep real
data (status table in `status.py:23-28`, run table) on stdout.
Disposition: ask-first (behavior change — output stream differs; some tests assert on
`result.output` which in CliRunner mixes streams by default, so confirm no test breakage).

### [Medium] No retry / backoff on transient errors; SDK polls a hosted service over the internet
Location: `comet_dq/_client.py:44-51,55-61` (no retries); `cli/api_client.py:9-22`; polling
loops `comet_dq/_client.py:87-96` and `cli/commands/run_cmd.py:67-89`.
What & why: A single transient 502/503 or dropped connection during a long poll raises
immediately and aborts the run wait (CLI exits 1 at `run_cmd.py:72`; SDK/operator raises
`HTTPError`, failing the Airflow task). For a tool whose core job is polling a remote run to
completion, one network blip should not fail an otherwise-healthy DAG run. There is no
`requests.Session` with a `urllib3 Retry` adapter, and `requests.get/post` is called fresh
each time (`_client.py`, `api_client.py`) so no connection pooling either.
Recommendation: Use a module-level `requests.Session` with a `Retry`
(`total=3`, `backoff_factor`, `status_forcelist=[502,503,504]`, idempotent methods) mounted on
an `HTTPAdapter`. At minimum, tolerate transient failures inside the poll loop (retry the poll a
few times before giving up) rather than aborting on the first error.
Disposition: ask-first (changes failure semantics — a previously-failing run may now succeed;
must preserve the "FAILED run still raises" behavior exactly).

### [Medium] `comet run` polling overwrites the prior line but never clears it (Windows carriage-return artifact)
Location: `cli/commands/run_cmd.py:77-78`.
What & why: The progress line is printed then `typer.echo("\r", nl=False)` returns the cursor to
column 0 without clearing. When a longer line (`RUNNING — 1/2 tests`) is followed by a shorter
one, trailing characters from the previous render remain. The two `typer.echo` calls also split
the write, and on Windows terminals the bare `\r` behavior with buffered stdout is unreliable; if
stdout is redirected to a file you get a pile of `\r`-separated fragments rather than a clean log.
Recommendation: Build one string, pad/truncate to a fixed width (or append spaces), and write it
in a single `typer.echo(..., nl=False)` ending with `\r`; emit a final newline before the
terminal message. Consider `rich` (already a dependency, `pyproject.toml:16`) `Live`/`status` for
clean progress, or skip the carriage-return trick entirely when stdout is not a TTY.
Disposition: auto-fix-safe (purely cosmetic terminal rendering; no API/exit-code change), but
verify the test `test_run_triggers_api_and_polls_complete` uses `--no-wait` (it does,
`test_run.py:30`) so the poll-render path is currently untested.

### [Medium] `.env` created with default (world-readable) permissions; key stored in plaintext
Location: `cli/commands/init.py:41-44` (`env_path.write_text(...)`).
What & why: `comet init` writes `.env` containing the API key placeholder with whatever umask
default applies. On POSIX this is typically `0644` (readable by other local users). The CLI/SDK
store the key only in env / `.env` (good — never in a tracked config file, and `.gitignore:9`
ignores `.env`), and the key is never printed (`config.py` prints only guidance). Plaintext `.env`
is the conventional Python pattern, so this is Medium not High, but a created secrets file should
be owner-only. Note: on Windows `os.chmod` has limited effect, so this is mainly a POSIX hardening.
Recommendation: After writing, best-effort `os.chmod(env_path, 0o600)` (guard for Windows where
it is a no-op). Optionally document that production credentials belong in a secret manager / Airflow
Variable rather than `.env`.
Disposition: ask-first (touches file permissions; confirm desired behavior on Windows).

### [Low] TLS verification relies on requests default; not asserted explicitly
Location: `comet_dq/_client.py:44-61`, `cli/api_client.py:10,15,20`.
What & why: No `verify=` is passed, so requests' default (`True`) applies — TLS IS verified
against the hosted HTTPS URL (`_client.py:14`). This is correct, but because nothing pins it, a
future `**kwargs` caller (`api_client.py:9,14,19` forward `**kwargs` into `requests`) could pass
`verify=False` and silently disable TLS. Worth a guard / comment for a security-sensitive client.
Recommendation: Either set `verify=True` explicitly, or drop the `**kwargs` passthrough in
`CometClient` so callers cannot inject `verify=False`/`proxies` unintentionally.
Disposition: auto-fix-safe (explicit `verify=True` is behavior-preserving).

### [Low] `client.get("/api/v1/runs?limit=...")` builds the query string by hand
Location: `cli/commands/status.py:14` and `run_cmd.py:69`.
What & why: `status.py` interpolates `limit` directly into the path. `limit` is a typed
`int` Typer option (`status.py:7`) so injection is not possible here, but hand-built query
strings bypass `requests`' `params=` encoding and break if the value ever becomes a string.
`CometClient.get` already forwards `**kwargs` to requests, so `params=` is available.
Recommendation: Use `client.get("/api/v1/runs", params={"limit": limit})`.
Disposition: auto-fix-safe (equivalent request; encoding-safe).

### [Low] `run_cmd` accesses `resp["run_id"]` / `status["status"]` with hard `[]` indexing
Location: `cli/commands/run_cmd.py:59,74-76` and `comet_dq/_client.py:51` (`["run_id"]`).
What & why: If the server returns a 200 with an unexpected body shape (missing `run_id`,
`status`, `completed_tests`, or `total_tests`), the command dies with a `KeyError` traceback
rather than a friendly message — the `except` blocks above only wrap the HTTP call, not the
dict access. `status.py:26-28` similarly indexes `r['id']`, `r['status']`, `r['profile']`.
Recommendation: Use `.get(...)` with sensible fallbacks for display fields, and validate the
presence of `run_id`/`status` with a clear error if absent.
Disposition: ask-first (changes error message on malformed responses; low real-world likelihood).

### [Low] `comet_dq.airflow` requires Airflow at import yet ships in the base package
Location: `comet_dq/airflow/__init__.py:8-14`; declared as extra in `pyproject.toml:22-25`.
What & why: The guard is correct (clear ImportError with install hint). Minor: the
`CometDQRunTimeout` raised by `run_checks` is documented in the operator docstring
(`_operator.py:31-34,92-94`) but the operator only catches `CometDQChecksFailed`
(`_operator.py:112`); a timeout propagates uncaught (which is fine for Airflow — it fails the
task) but is not logged with the operator's `self.log.error` context like the failure path is.
Recommendation: Optionally add an `except CometDQRunTimeout` branch that logs run_id/deadline
before re-raising, mirroring the `CometDQChecksFailed` handler for consistent operator logs.
Disposition: auto-fix-safe (adds logging only; still re-raises, so task-failure behavior is
identical).

### [Low] `comet_dq/airflow/_operator.py` uses `context: dict` type hint for `execute`
Location: `comet_dq/airflow/_operator.py:85`.
What & why: Airflow's `execute(self, context)` receives a `Context` (a `TypedDict`-like
mapping), not a plain `dict`; the annotation is cosmetically wrong but harmless. `template_fields`
(`_operator.py:44`) correctly lists `profile` and `max_wait_seconds`. Note `max_wait_seconds` is
templated as a string by Jinja but `run_checks`/`wait_for_run` compare it numerically
(`_client.py:84-85,92`) — a Jinja-rendered `max_wait_seconds="60"` would break the
`time.monotonic() + max_wait_seconds` arithmetic with a `TypeError`. Only triggers if a user
templates it from a string source; still a latent bug.
Recommendation: Coerce `max_wait_seconds` to `int` in the operator `__init__`/`execute` (after
templating) before passing to `run_checks`, e.g. `int(x) if x is not None`.
Disposition: ask-first (defensive coercion; verify it does not mask a legitimately-typed None).

## Simplification & structure

- Duplicated HTTP clients. `cli/api_client.py:CometClient` (timeout 15s, `X-Api-Key`,
  `get`/`post`/`get_text`) and `comet_dq/_client.py:CometAPIClient` (timeout 30s, retries none,
  poll loop) are two hand-rolled wrappers over `requests` with the same auth header and URL
  joining. The CLI commands (`run`, `status`) re-implement trigger+poll logic that already exists
  in `comet_dq._run.run_checks` / `CometAPIClient.wait_for_run`. Best simplification: have the CLI
  depend on `comet_dq` (it already imports `DEFAULT_API_URL` from it in `config.py:5`) and call
  `run_checks` / a shared client instead of `cli/api_client.py`. That removes a whole file, unifies
  timeouts/retries, and means one place to add the Session+Retry from the Medium finding above.
  Caveat: the CLI client also needs `get_text` (YAML pull) and the raw `/tests/sync`,
  `/profiles/sync`, `/runs?limit=` calls that the SDK does not expose — so either widen the SDK's
  internal client or keep a thin CLI client but have it subclass/wrap the SDK one. A behavior-
  preserving refactor must keep the CLI's 15s timeout vs SDK's 30s unless intentionally unified.

- CLI package fragmentation. Five one-function command modules + `cli.py` + `api_client.py` +
  `config.py` is on the verbose side for ~150 lines of command logic, but it is a conventional
  Typer layout and each file is genuinely a separate command, so this is acceptable and NOT the
  thing to consolidate. `cli/__init__.py` and `cli/commands/__init__.py` are empty — fine.

- `config.py` is now a 30-line function that only reads one env var and returns three constants
  (two of them hard-coded). Given COMET_API_URL and config.yaml are intentionally ignored (tests
  confirm), `load_config` could arguably be inlined or reduced, but keeping it as the single
  credential-resolution chokepoint is reasonable. Leave as-is.

- `comet_dq` public/private split (`_client`, `_run`, leading underscores; `__all__` in
  `__init__.py:14`) is good SDK hygiene — the public surface is exactly `run_checks` + two
  exceptions + `airflow.CometDQOperator`. No change recommended.

## Test gaps & proposed tests

Existing coverage is solid for the SDK happy/failure/timeout paths and the CLI trigger/push/pull
config paths. Characterization tests to add BEFORE any refactor (each pins current behavior):

1. CLI poll-to-completion render path. Current `test_run.py` tests only use `--no-wait`
   (`test_run.py:30,50`) or the FAILED branch (`test_run.py:39`). Add a test that runs WITHOUT
   `--no-wait`, mocks `time.sleep`, and feeds `get.side_effect = [QUEUED, RUNNING, COMPLETE]` to
   exercise `run_cmd.py:66-84` and assert the final "complete" message and exit 0. This pins the
   progress loop before touching the carriage-return rendering (Medium finding).

2. `comet init` scaffold output. No test invokes `init`. Add one that runs `comet init` in a
   tmp dir and asserts: `comet/test_definitions.yaml` exists, `comet/database_connection.yaml`
   exists, `.env` created with the placeholder, and — critically — asserts the connection YAML's
   schema (`connection_url` vs `path`). This test will FAIL today and document the High finding;
   write it as a characterization test of current (buggy) output, then flip the assertion when the
   bug is fixed.

3. `comet init` is idempotent / non-destructive. Test that running `init` when `comet/` already
   exists prints "Nothing to do" and exits 0 without overwriting (`init.py:32-34`), and that an
   existing `.env` is not clobbered (`init.py:42`).

4. CLI HTTP error UX. Add tests (using `requests_mock` like `test_config.py:82-88`) asserting the
   exact message/exit for `push`/`pull`/`run`/`status` on 401, 404, 500, and a `ConnectionError`.
   This pins current raw-error output before the friendly-error refactor (High finding) so the
   refactor's intended message change is explicit and reviewable.

5. SDK transient-error behavior. Add a test that `wait_for_run` / `run_checks` currently raises
   `requests.HTTPError` on a single 503 mid-poll (no retry). Pins current no-retry behavior before
   adding Session+Retry (Medium finding), so the change in semantics is intentional and tested.

6. `status` output formatting. `test_status_prints_last_run` only asserts `"COMPLETE" in output`.
   Add assertions on column layout / `started_at` truncation (`status.py:27` `[:19].replace("T"," ")`)
   and the empty-list "No runs yet" branch (`status.py:19-21`), which is currently untested.

7. Operator credential resolution order. No test exercises `CometDQOperator._resolve`
   (`_operator.py:69-83`). Add tests: constructor arg wins; Airflow `Variable.get` used when arg
   absent; `Variable.get` raising falls through to None (so env var is used). Mock `Variable`.

8. Operator `max_wait_seconds` string coercion. Add a test passing `max_wait_seconds="60"`
   (simulating a Jinja-rendered string) to assert current behavior, documenting the latent
   `TypeError` (Low finding) before adding coercion.

9. `pull` with malformed/empty server YAML. `pull.py:29,38` use `(yaml.load(...) or {})`; add a
   test where the server returns `""` or non-mapping YAML to pin the fallback behavior.

Sources:
- [Typer CLI Best Practices — projectrules.ai](https://www.projectrules.ai/rules/typer)
- [Exploring CLI Best Practices — Localytics](https://eng.localytics.com/exploring-cli-best-practices/)
- [CLI Error Messages Are a Dual-Consumer Problem — zircote](https://zircote.com/blog/2026/04/cli-error-messages-are-a-dual-consumer-problem/)
- [Testing — Typer docs](https://typer.tiangolo.com/tutorial/testing/)
