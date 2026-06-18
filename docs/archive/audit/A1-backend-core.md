# A1 Audit — Backend Data-Quality Engine

Scope (read in full): `backend/core/{config_loader,database_connector,result_handler,test_engine,__init__}.py`,
`backend/main.py`, `backend/__init__.py`, and `backend/tests/builtin/{custom_sql,duplicate_check,null_check,range_check,relationship_check,row_count,schema_check,unique_check,__init__}.py`.

Read-only audit. No source files were modified. The only file written is this report.

## Summary

Overall health: the engine is small, readable, and internally consistent — the 8 builtin checks follow a near-identical shape and `test_engine.py` has a genuinely good fail-safe design (per-test isolation, callback isolation, skip/error result rows instead of crashes). The biggest structural risk is **SQL identifier injection**: every check interpolates `table`/`column`/`query` values straight into SQL strings via f-strings with no quoting or allowlisting, and `custom_sql` additionally runs `eval()` on a config-supplied assertion. These are config-driven (the config is partly operator-controlled), but config now also flows from the Dashboard API (`load_config_from_api`), so the trust boundary is not purely local. Secondary risks: a `connection_url` escape hatch that bypasses the credential loud-fail (documented), a `range_check` that injects numeric bounds unquoted (breaks on non-numeric columns and is an injection vector), and broad `except Exception` blocks that flatten programming errors into "ERROR" result rows. The 8 checks duplicate a large amount of boilerplate (result dict, `_error`, count-query plumbing) that can be consolidated behind one helper without changing behavior. Test coverage of this area is thin: only `build_connection_url` is directly tested; the 8 checks, `TestEngine`, and the two config loaders have essentially no characterization tests.

## Findings

### [Critical] SQL identifier injection across all 8 builtin checks
- Location: `backend/tests/builtin/duplicate_check.py:17-27`; `null_check.py:15-19`; `range_check.py:20-31`; `relationship_check.py:24-32`; `row_count.py:56-58`; `unique_check.py:17-25`; `schema_check.py` (table only, via `get_columns`); `custom_sql.py:13`.
- What & why: `table`, `column(s)`, `source_table`/`target_table`/`source_column`/`target_column`, and `date_column` are taken from the test config and interpolated directly into SQL with f-strings — e.g. `f"SELECT COUNT(*) AS total FROM {table}"` and `", ".join(columns)`. There is no quoting, no allowlist, no `quoted_name`. A value like `users; DROP TABLE audit; --` or `(SELECT ...)` is executed verbatim. Identifiers cannot be passed as bind parameters, so the correct mitigation is identifier validation (allowlist `^[A-Za-z_][A-Za-z0-9_]*$`, optionally schema-qualified) and/or SQLAlchemy `quoted_name`/dialect `identifier_preparer.quote()`. The threat is mitigated *today* only by the assumption that test config is operator-authored, but config also arrives over the network via `load_config_from_api` (`config_loader.py:130-168`), so the boundary is not local-only. Industry norm for DQ engines and ORMs is: parameterize values, allowlist/quote identifiers, never string-format untrusted identifiers (see Sources).
- Recommendation: add a shared `_safe_identifier(name)` validator (allowlist regex, allow dotted `schema.table`) used by all checks, or quote via the engine's dialect preparer. Centralize in one helper module the checks import.
- Disposition: `ask-first` (behavioral — quoting/validation will reject identifiers that currently "work", e.g. names with spaces or reserved words; must be designed against current valid configs).

### [Critical] `custom_sql` runs `eval()` on the assertion string
- Location: `backend/tests/builtin/custom_sql.py:22-27`.
- What & why: `passed = bool(eval(assertion, {"__builtins__": {}}, local_vars))`. `__builtins__` is emptied, which blocks the most common escapes, but `eval` on attacker-influenced strings is not a robust sandbox (well-known bypasses via object attribute traversal, and the namespace still contains the DB result object whose type exposes attributes). The `query` is also passed straight to the DB (`custom_sql.py:13`). If a test definition can be authored by anyone less trusted than the runner operator (e.g. via the Dashboard API sync path), this is arbitrary expression execution.
- Recommendation: replace `eval` with a restricted comparison parser (e.g. `simpleeval`, or a hand-rolled `operator`-based comparator supporting `==,!=,<,<=,>,>=` against `result`). At minimum, document the trust assumption explicitly and validate the assertion against an allowlist of tokens.
- Disposition: `ask-first` (behavioral — a stricter evaluator may reject assertions that currently evaluate, e.g. arithmetic or `and`/`or` chains).

### [High] `range_check` interpolates bounds unquoted — breaks non-numeric columns and is an injection vector
- Location: `backend/tests/builtin/range_check.py:20-31`.
- What & why: `conditions.append(f"{column} < {min_value}")` and `... > {max_value}`. `min_value`/`max_value` come from config as arbitrary YAML/JSON scalars. If they are strings (e.g. a date `'2024-01-01'`), the generated SQL is `col < 2024-01-01` (unquoted) — a syntax/semantic error or silent wrong result, not a comparison. If a value is a string it is also a direct injection point (`max_value: "0 OR 1=1"`). Unlike identifiers, these *are* values and can and should be bound parameters.
- Recommendation: pass `min_value`/`max_value` as SQLAlchemy bind parameters (requires `execute_query` to accept params — see next finding), or at minimum reject non-numeric bounds with a clear ERROR.
- Disposition: `ask-first` (behavioral — would change handling of string/date bounds that may currently be relied on, and requires a parameterized query path).

### [High] `execute_query` has no parameter-binding path; values cannot be bound safely
- Location: `backend/core/database_connector.py:100-102`.
- What & why: `execute_query(self, sql: str)` accepts only a SQL string and does `pd.read_sql(text(sql), conn)`. There is no way for a check to pass bound parameters, which is *why* every check resorts to f-string interpolation. This is the root enabler of the injection findings above. `pd.read_sql(text(sql), conn)` with parameters would accept a `params=` dict.
- Recommendation: add an optional `params: dict | None = None` argument and forward to `pd.read_sql(text(sql), conn, params=params)`. This is additive and behavior-preserving for existing callers, and unblocks parameterizing `range_check` bounds and `custom_sql`.
- Disposition: `auto-fix-safe` (purely additive signature; existing zero-arg calls unaffected) — but the *callers* adopting it is `ask-first`.

### [High] DB engines are created without disposal — connection/engine leak per profile
- Location: `backend/core/database_connector.py:96-105`; `backend/core/test_engine.py:26-33`.
- What & why: `DatabaseConnector.__init__` calls `create_engine(url)` and stores `self._engine`, but there is no `dispose()`/`close()` and no context-manager support. `TestEngine` caches one connector per profile in `self._connectors` and never disposes them. Per-query connections are correctly closed (`with self._engine.connect()`), so this is an engine-pool lifetime leak, not a per-query leak — but for a long-lived or repeatedly-instantiated process (the API `run_executor` builds engines per run) pools accumulate. `create_engine` can also fail late.
- Recommendation: add a `close()`/`dispose()` on `DatabaseConnector` and call it from `TestEngine` after `run()` (or make `TestEngine` a context manager). Keep current behavior otherwise.
- Disposition: `ask-first` (changes engine lifetime; a later refactor must confirm `run_executor` and `main.py` still get fresh engines where they expect them).

### [Medium] Broad `except Exception` masks programming errors as data "ERROR" rows
- Location: `backend/core/test_engine.py:94-103`; `result_handler.py:49-50`; `config_loader.py:143-144`.
- What & why: `_run_one` catches *all* exceptions and turns them into an ERROR result with `message=str(e)`. This is intentional fail-safe behavior (good for data errors), but it also swallows `KeyError`/`TypeError`/`AttributeError` from bugs in a check module, and a bare `str(e)` for e.g. a `KeyError` yields an opaque message like `'column'`. `config_loader.load_config_from_api` wraps every failure (including `KeyError` on a malformed API payload) in a generic `RuntimeError("Could not fetch tests from API")`, hiding schema-shape bugs.
- Recommendation: keep the fail-safe catch but include the exception *type* in the message (`f"{type(e).__name__}: {e}"`), and consider letting `KeyboardInterrupt`/`SystemExit` propagate (they already do since those are `BaseException`, so this is minor). In the API loader, separate transport errors from payload-shape errors.
- Disposition: `auto-fix-safe` for prefixing the type name in the message (cosmetic, message-only); `ask-first` for changing which exceptions are caught.

### [Medium] `null_check` skips empty tables but `duplicate_check`/`unique_check`/`range_check` do not — inconsistent empty-table semantics
- Location: `null_check.py:22-31` (SKIPPED on `total == 0`) vs `duplicate_check.py`, `unique_check.py`, `range_check.py`, `relationship_check.py` (no skip; `relationship_check.py:35` guards division but still returns PASSED/FAILED).
- What & why: On an empty table, `null_check` returns SKIPPED, while the others return PASSED (0 duplicates, 0 outliers, etc.). This is an inconsistency in how the 8 checks treat the same edge case; it is defensible (PASS-on-empty is arguably correct) but undocumented and divergent. A later "consolidation" refactor could accidentally normalize this and change observable status for empty tables.
- Recommendation: decide and document one empty-table policy; if unifying, flag it as a behavior change. Until then, lock current behavior with characterization tests (below).
- Disposition: `ask-first` (behavioral — changing any check's empty-table status is observable).

### [Medium] `row_count` `_date_where` silently returns `""` for unknown dialect/timeframe — check silently widens scope
- Location: `backend/tests/builtin/row_count.py:4-32, 51-58`.
- What & why: `_date_where` returns `""` when the dialect is not one of sqlite/postgres/mysql/mssql, OR when `timeframe` is not daily/weekly/monthly. The caller (`row_count.py:51-54`) only invokes it when `timeframe != "all_time"`, so an unrecognized dialect (e.g. snowflake — which `database_connector.py` explicitly supports) produces an empty WHERE clause and the count silently covers *all rows* instead of the requested window. No error, no SKIP — a silently-wrong PASS/FAIL. Snowflake is a supported connection type (`database_connector.py:77`), so this is reachable.
- Recommendation: when `timeframe != "all_time"` and `_date_where` returns `""`, return ERROR ("timeframe X not supported for dialect Y") instead of silently counting all rows.
- Disposition: `ask-first` (behavioral — turns a silent PASS/FAIL into an ERROR).

### [Medium] `connection_url` escape hatch bypasses the credential loud-fail and accepts embedded secrets
- Location: `backend/core/database_connector.py:27-45`.
- What & why: The `${ENV}` loud-fail only matches a field whose *entire* value is `${VAR}`. A `connection_url` like `postgresql://u:${PW}@h/db` is neither resolved nor guarded, and a hardcoded password in `connection_url` is accepted as-is. This is documented in-code (the IN-02 note) and intentional, but it is a real credential-handling footgun: secrets can land in YAML and in error/log output via the raw URL.
- Recommendation: keep the escape hatch but (a) still scan `connection_url` for unresolved `${...}` and loud-fail, and (b) never log the raw URL. Document that structured fields are preferred (already noted).
- Disposition: `ask-first` (changes acceptance of currently-valid `connection_url` values containing `${...}`).

### [Medium] `result_handler.print(...)` couples the engine to stdout; failures are print-only
- Location: `backend/core/result_handler.py:43-50`; `backend/core/test_engine.py` (many `print`); `backend/main.py`.
- What & why: The engine and result handler communicate exclusively via `print`. There is no logging abstraction, so callers (API `run_executor`, tests) cannot capture or suppress output, and warnings about unreachable dashboards are invisible to structured logs. This is a separation-of-concerns issue, not a bug.
- Recommendation: migrate to the `logging` module (module-level logger). Behavior-preserving if default handler still writes to stdout, but output formatting will differ.
- Disposition: `ask-first` (changes observable stdout, which tests/CLI may scrape).

### [Low] `schema_check` validation ordering — emptiness checked before type check
- Location: `backend/tests/builtin/schema_check.py:26-30`.
- What & why: `expected_columns = test.get("expected_columns") or {}` then "must be provided and non-empty" is checked *before* the `isinstance(..., dict)` check. If `expected_columns` is a non-empty list, the `if not expected_columns` passes, then `isinstance` correctly errors — fine. But if it's an empty dict vs missing, both collapse to the same message. Minor; ordering is slightly illogical (type check should precede emptiness).
- Recommendation: check `isinstance(dict)` first, then non-empty. Message-only refinement.
- Disposition: `auto-fix-safe` (reorders two guards producing equivalent ERROR outcomes; verify both still ERROR).

### [Low] `null_count` SQL uses `SUM(CASE WHEN ... )` returning NULL on empty table — masked only by the empty-table guard
- Location: `backend/tests/builtin/null_check.py:15-20, 22`.
- What & why: `SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END)` returns `NULL` (not 0) when there are no rows; `int(df["null_count"].iloc[0])` would raise on `NULL`. This is currently safe *only* because the `total == 0` SKIP at line 22 returns before `null_count` is read (line 33). The ordering is load-bearing and undocumented; a refactor reordering these lines would crash on empty tables. Worth a comment + characterization test.
- Recommendation: add `COALESCE(SUM(...), 0)` defensively (behavior-preserving given the guard) and/or a test pinning the empty-table SKIP path.
- Disposition: `auto-fix-safe` (`COALESCE` cannot change results given the existing guard).

### [Low] `result_handler` is imported but its module-level `_API_URL`/`_API_KEY` are read once at import
- Location: `backend/core/result_handler.py:15-16`; `backend/main.py:14-15`.
- What & why: Env vars are captured at import time into module globals. Tests or runners that set env vars after import (common in pytest) will not see them; `monkeypatch.setenv` after import is a no-op for these. This is a testability/foot-gun issue, not a runtime bug in normal CLI use.
- Recommendation: read env vars inside the functions, or expose them as parameters. Behavior-preserving for the CLI entrypoint.
- Disposition: `ask-first` (changes when config is read; could affect a runner that relies on import-time capture).

### [Low] `_deduplicate_test_ids` mutates by sharing `tags`/`raw` references across the rebuilt object
- Location: `backend/core/config_loader.py:79-88`.
- What & why: When a collision is resolved, a new `TestDefinition` is built reusing the *same* `tags` list and `raw` dict objects from the original. If anything downstream mutates `raw` or `tags` (e.g. `test_engine._run_one` does `dict(test_def.raw)` — a shallow copy, so this is currently safe), aliasing could surprise. Currently benign because consumers copy. Worth noting before refactor.
- Recommendation: no change required; document that `raw`/`tags` are shared and treated read-only. If defensiveness is wanted, `copy` them — but that is a behavior-adjacent change.
- Disposition: `auto-fix-safe` only as a documenting comment; copying is `ask-first`.

### [Low] `datetime.now()` without timezone in saved results
- Location: `backend/core/test_engine.py:141, 145`.
- What & why: `datetime.now()` (naive local time) is used for both the filename timestamp and `run_timestamp`. The baseline (`docs/audit/_baseline.md`) already flags `datetime.utcnow()` deprecation warnings elsewhere; here the concern is naive local timestamps in persisted artifacts (ambiguous across timezones/DST). Not a correctness bug for single-host runs.
- Recommendation: use timezone-aware UTC (`datetime.now(timezone.utc)`); note the ISO string format changes (adds offset), which downstream parsers must tolerate.
- Disposition: `ask-first` (changes the persisted `run_timestamp` string and filename).

## Simplification & structure

Assessment of "too many files": for this area the file split is **mostly justified** — one module per check is a legitimate plugin pattern (`test_engine._run_one` does `importlib.import_module(f"backend.tests.builtin.{type}")`, so the filename *is* the registry). The structure is not the problem; the **duplication inside the 8 files** is. Each check repeats: the full result dict (10 lines), an identical `_error` helper (8 of them, byte-for-byte except the `"type"` literal), and the count-query plumbing (`int(df[...].iloc[0])`).

Concrete consolidation (all behavior-preserving if done carefully):

1. **One shared `_result(...)`/`_error(...)` builder** in a new `backend/tests/builtin/_common.py` (or in `core`), parameterized by `test`, `type`, `status`, `metrics`, `message`. Eliminates 8 duplicate `_error` functions and standardizes the result schema (currently re-typed by hand in every file — a drift risk). Disposition: `auto-fix-safe` if it produces byte-identical dicts; the `"type"` value must be passed per-check to preserve output.
2. **A `_scalar_count(connector, sql)` helper** wrapping `int(df[col].iloc[0])` — removes the repeated `execute_query` + `iloc[0]` boilerplate in 6 checks. `auto-fix-safe`.
3. **A single `_safe_identifier()` validator** (see Critical finding) imported by all checks — both a security fix and a dedup. `ask-first` (behavioral).
4. **Fold `STATUS_ICONS` + summary printing into a logging/reporter** (Medium finding) so the engine core has no `print`. `ask-first`.
5. `config_loader.py` has two near-parallel test-construction paths (`load_config` builds `TestDefinition` inline at lines 205-214; `load_config_from_api` uses `build_engine_test`). `load_config` should also call `build_engine_test` for a single construction path — the docstring of `build_engine_test` says it is meant to be that single source of truth, but `load_config` does not use it. `ask-first` (the two paths set `raw` differently — inline uses the original YAML dict, `build_engine_test` rebuilds it — so unifying could change `raw` contents).

Target structure for this area: keep one-file-per-check (registry pattern), add `backend/tests/builtin/_common.py` for the shared result/error/scalar/identifier helpers, route engine output through `logging`, and give `DatabaseConnector` a `params`-aware `execute_query` plus a `close()`.

## Test gaps & proposed characterization tests

Current coverage in this area: only `build_connection_url` is directly tested (`tests/test_comet_dq/test_build_connection_url.py`). The 8 checks, `TestEngine`, `_deduplicate_test_ids`, `_name_to_id`, `_resolve_env_vars`, `load_config`/`load_config_from_api`, and `result_handler.send_to_dashboard` have **no** direct characterization tests. These should be written BEFORE any refactor to lock current behavior. All check tests can run against an in-memory SQLite (`{"type":"sqlite","path":":memory:"}`) seeded via the engine.

Engine / config_loader:
- `test_name_to_id_normalizes_spaces_and_punctuation` — `"Customer Email Null Check"` -> `"customer_email_null_check"`; leading/trailing punctuation stripped.
- `test_deduplicate_appends_incrementing_suffix` — three tests named the same yield `id`, `id_2`, `id_3`.
- `test_deduplicate_skips_preexisting_suffix_collision` — a test already named `x_2` plus two `x` produce no duplicate id (covers the `while candidate in seen` branch at `config_loader.py:74-76`).
- `test_resolve_env_vars_leaves_unset_placeholder_verbatim` — `${MISSING}` stays `${MISSING}` (`config_loader.py:44`).
- `test_resolve_env_vars_recurses_dict_and_list` — substitution inside nested structures.
- `test_load_config_from_api_filters_disabled_tests` — `enabled: False` rows are dropped (`config_loader.py:165`).
- `test_load_config_from_api_raises_runtimeerror_on_unreachable` — transport failure -> `RuntimeError`.
- `test_engine_skips_test_when_profile_missing` — unknown profile yields a `SKIPPED` result row (not a crash) (`test_engine.py:60-75`).
- `test_engine_returns_error_for_unknown_test_type` — type with no module -> `ERROR` "not implemented yet" (`test_engine.py:84-93`).
- `test_engine_on_result_callback_exception_does_not_abort_run` — a raising `on_result` is logged and the run continues (`test_engine.py:51-55`).
- `test_engine_print_summary_orders_failures_by_severity` — CRITICAL before LOW (`test_engine.py:130-137`).
- `test_save_results_writes_summary_counts` — payload summary matches result statuses (`test_engine.py:144-158`).

Per-check (status + key metrics) on seeded SQLite:
- `test_null_check_pass_below_threshold` / `_fail_above_threshold` / `_skipped_on_empty_table` (locks the empty-table SKIP at `null_check.py:22-31`).
- `test_duplicate_check_counts_groups_not_rows` — distinguishes "duplicate groups" from total dup rows (`duplicate_check.py:18-25`).
- `test_duplicate_and_unique_accept_singular_column_and_columns_list` — both `column:` and `columns:` work (`duplicate_check.py:10-11`, `unique_check.py:10-11`).
- `test_unique_check_pass_when_fully_distinct` / `_fail_with_duplicate_count`.
- `test_range_check_counts_outliers_outside_bounds` / `_error_when_no_bounds_given` (`range_check.py:17-18`).
- `test_range_check_min_only_and_max_only` — single-sided WHERE construction.
- `test_relationship_check_counts_orphans` / `_error_lists_all_missing_fields` (`relationship_check.py:10-20`).
- `test_relationship_check_zero_orphans_on_empty_source` — division guard at `relationship_check.py:35`.
- `test_row_count_min_max_pass_fail` and `test_row_count_error_when_timeframe_without_date_column` (`row_count.py:48-49`).
- `test_row_count_all_time_ignores_date_column` and a regression test pinning the **current** silent-all-rows behavior for an unsupported dialect/timeframe (lock before fixing the Medium finding) (`row_count.py:51-58`).
- `test_schema_check_detects_missing_column_and_type_mismatch` plus `_error_when_expected_columns_empty` and `_error_when_expected_columns_not_a_dict` (`schema_check.py:26-30`).
- `test_schema_check_type_alias_matching` — `integer` matches `BIGINT`, `string` matches `VARCHAR(50)` (`schema_check.py:5-18`).
- `test_custom_sql_assertion_pass_fail` and `_error_on_empty_result` / `_error_on_bad_assertion` (`custom_sql.py:8-27`). Add `test_custom_sql_eval_namespace_has_no_builtins` to pin the current `__builtins__`-empty contract before replacing `eval`.

result_handler:
- `test_send_to_dashboard_returns_false_when_unconfigured` — no URL/key -> `False`, no request (`result_handler.py:31-32`).
- `test_sanitize_converts_numpy_scalars` — a dict containing `np.int64`/`np.float64` round-trips to native ints/floats (`result_handler.py:7-10`). This pins the np.int64 behavior the memory notes call out.
- `test_send_to_dashboard_swallows_connection_error` — mocked `ConnectionError` -> `False`, no raise (`result_handler.py:45-46`).

database_connector (beyond existing URL tests):
- `test_sqlite_relative_path_resolves_against_config_dir` (`database_connector.py:47-54`).
- `test_connection_url_override_returned_verbatim` (`database_connector.py:44-45`).
- `test_test_connection_returns_false_on_bad_url` (`database_connector.py:107-113`).

## Sources
- [Understand SQL Injection and Avoid It in Python with SQLAlchemy](https://towardsdatascience.com/understand-sql-injection-and-learn-to-avoid-it-in-python-with-sqlalchemy-2c0ba57733b2/)
- [SQL Injection in the Age of ORM: Risks, Mitigations, and Best Practices](https://afine.com/sql-injection-in-the-age-of-orm-risks-mitigations-and-best-practices)
- [Column Elements and Expressions — SQLAlchemy 2.0 (quoted_name / identifier quoting)](https://docs.sqlalchemy.org/en/20/core/sqlelement.html)
- [How to prevent SQL injection in SQLAlchemy](https://www.slingacademy.com/article/prevent-sql-injection-in-sqlalchemy/)
