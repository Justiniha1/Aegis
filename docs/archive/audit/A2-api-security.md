# A2 — API Security Audit (auth / credentials / tenant isolation)

Scope: `dashboard_api/auth.py`, `dashboard_api/limiter.py`, `dashboard_api/connection_source.py`,
`dashboard_api/profile_loader.py`, `dashboard_api/__init__.py`. Context read: `dashboard_api/models.py`,
`dashboard_api/database.py`, plus the consuming routers (`auth_routes.py`, `clients.py`, `profiles.py`,
`runs.py`) and `backend/core/config_loader.py` to trace credential flow. Read-only audit; no source modified.

## Summary

Overall posture is **moderate**. The core auth primitives are mostly sound: passwords are bcrypt-hashed,
JWTs are HS256-signed with a 24h expiry, and tenant isolation in the data routers is consistently enforced
by `client_id == client.id` filters (verified across runs, tests, results, schedules, profiles). The JWT
secret has a defensible fail-safe (random key when unset/placeholder) rather than a hard-coded fallback.

The biggest risks are about **credentials**, not access control:
1. **Connection-config secrets can be stored in the DB in plaintext.** `ConnectionConfig.yaml_text` is an
   unencrypted `Text` column; the "secrets stay as `${ENV}`" rule is a convention, not enforced, and the
   upload endpoint accepts any YAML including literal passwords.
2. **`get_client_any_auth` silently swallows bad/expired JWTs and falls through**, weakening the auth
   contract and obscuring failures.
3. **Rate limiting is keyed on an attacker-controllable header with no signature**, and is in-memory only
   (resets on restart, not shared across replicas).
4. JWTs have **no `iat`/`nbf`/`iss`/`aud`, no jti/revocation, and no logout** — a leaked token is valid for
   a full 24h with no way to invalidate it.

Tenant isolation: **appears sound** for application data (every query is client-scoped, `delete_client`
checks ownership). Credential encryption: **NOT sound** — connection YAML (and thus any embedded secrets)
is stored unencrypted at rest.

## Findings

### [High] Connection-config secrets stored unencrypted at rest, "${ENV}-only" not enforced
- **Location:** `dashboard_api/connection_source.py:15-27` (read), `dashboard_api/routers/profiles.py:37-57`
  (write via `/profiles/sync`), `dashboard_api/models.py:80-86` (`ConnectionConfig.yaml_text` plaintext `Text`).
- **What & why:** The module docstring (`connection_source.py:1-7`) and `profile_loader.py:1-6` assert that
  only profile *names* are exposed and that "secrets remain `${ENV}`." That is true for what is *returned*
  to clients, but the *storage* path (`sync_profiles`) writes the raw uploaded YAML verbatim into
  `ConnectionConfig.yaml_text`. Nothing validates that the YAML contains only `${ENV}` placeholders — a
  client (or `comet push`) that embeds a literal password/host/DSN persists it unencrypted in the dashboard
  DB. `_resolve_env_vars` (`config_loader.py:39-50`) only substitutes `${VAR}` and leaves literals untouched,
  so literal secrets flow straight through to the run executor too. OWASP Cryptographic Storage guidance and
  multi-tenant SaaS practice both require connection credentials to be encrypted at rest (AES/Fernet or a
  secrets manager). `cryptography` is already a dependency elsewhere in the repo, so the primitive exists.
- **Recommendation:** Either (a) encrypt `yaml_text` at rest with a Fernet/AES key from env (KMS in prod), or
  (b) enforce a server-side check at upload that rejects any value resolving to a non-`${ENV}` secret in
  known credential keys (`password`, `dsn`, `url`, `secret`, `account`, `token`). Document which approach is
  the contract. Note for the refactor: option (b) changes upload behavior (previously-accepted YAML may now
  be rejected) — not behavior-preserving.
- **Disposition:** `ask-first`.

### [High] `get_client_any_auth` swallows invalid/expired JWTs and falls through silently
- **Location:** `dashboard_api/auth.py:87-110`.
- **What & why:** On the JWT branch, `jwt.decode` failures are caught with `except jwt.PyJWTError: pass`
  (line 107-108). A request that presents a *valid bearer header with an expired or tampered token* does not
  get a clear `401 "Invalid or expired token"`; instead it falls through to the generic
  `401 "Authentication required"` at line 110, conflating "no credentials" with "bad credentials." Worse,
  the API-key branch (lines 93-97) only returns when a client is *found*; if `x_api_key` is present but
  wrong, it silently proceeds to try the JWT branch. This differs from the stricter
  `get_current_client_jwt` (lines 70-84) which raises on decode failure. The divergence is a correctness and
  observability hazard and makes auth-failure metrics/logging unreliable.
- **Recommendation:** Distinguish "credential present but invalid" from "no credential." If a token is
  present and fails to decode, raise 401 immediately rather than falling through. Behavior note: returning a
  different (more specific) error/status for a *present-but-invalid* token changes observable responses —
  treat as `ask-first` so the frontend's error handling is reviewed.
- **Disposition:** `ask-first`.

### [Medium] JWT lacks iat/nbf/iss/aud, jti, and any revocation/logout path
- **Location:** `dashboard_api/auth.py:65-67` (`create_access_token`), `auth.py:70-84` / `auth.py:99-108`
  (decode).
- **What & why:** Tokens carry only `sub` + `exp`. There is no `iat`/`nbf` (replay/clock-skew hardening),
  no `iss`/`aud` (so a token minted for any service sharing the secret is accepted), and no `jti` or
  server-side denylist. There is no logout endpoint (confirmed: `auth_routes.py` exposes only `/login`).
  A leaked token is therefore usable for the full 24h with no mitigation. Password change / account
  compromise cannot invalidate outstanding tokens.
- **Recommendation:** Add `iat`, and `aud`/`iss` claims and validate them on decode. Consider shortening
  `_EXPIRE_HOURS` (24h is long for a no-refresh, no-revocation token) and/or adding a refresh + denylist.
  Adding claims that are then *validated* will reject pre-existing tokens — `ask-first`.
- **Disposition:** `ask-first`.

### [Medium] Rate limit keyed on unauthenticated, attacker-controlled header; in-memory only
- **Location:** `dashboard_api/limiter.py:14-37`, applied at `dashboard_api/routers/runs.py:52`.
- **What & why:** `_api_key_or_ip` derives the rate-limit bucket from the raw `X-Api-Key` header *before any
  authentication*. The header is never validated here, so an attacker can rotate arbitrary
  `X-Api-Key` values to get a fresh quota bucket per value, trivially bypassing the per-client limit on
  `POST /runs` (an expensive endpoint that spawns background runs). The IP fallback is the only real
  backstop, and only when the header is absent. Additionally, SlowAPI's default storage is in-memory: the
  limit resets on every restart and is not shared across replicas (the app currently assumes single-process,
  per `main.py:20-26`, but this is a scaling landmine). Note also the dual `.get("x-api-key")` /
  `.get("X-Api-Key")` lookup (lines 17-18) is redundant — Starlette headers are case-insensitive.
- **Recommendation:** Key the limiter on the *authenticated* client id (resolved after auth) rather than the
  raw header, falling back to IP only for unauthenticated routes. Move to a shared backend (Redis) before
  multi-replica. Functional note: keying on client id changes which requests share a bucket — `ask-first`.
- **Disposition:** `ask-first`.

### [Medium] CORS allows credentials with wildcard methods/headers; no startup guard on insecure secret
- **Location:** `dashboard_api/__init__.py` (empty), `dashboard_api/main.py:53-82`, and JWT secret handling
  at `dashboard_api/auth.py:39-50`.
- **What & why:** Two related insecure-default concerns. (1) CORS sets `allow_credentials=True` with
  `allow_methods=["*"]` and `allow_headers=["*"]` (`main.py:79-81`). Origins are correctly restricted via env
  (good), but wildcard methods/headers alongside credentialed requests is broader than needed. (2) The JWT
  secret fail-safe (`auth.py:41-50`) generates a *random* key when unset/placeholder and only emits a
  `warnings.warn`. In production this silently lets the service boot with tokens that die on every restart
  and that differ per replica (so JWTs minted by one replica are rejected by another) — a `warnings.warn`
  is easy to miss and there is no hard fail or distinct prod gate. `_KNOWN_INSECURE` only covers `""` and
  one placeholder string, so a weak-but-nonempty secret passes silently.
- **Recommendation:** Tighten CORS `allow_methods`/`allow_headers` to the actual set used. For the secret:
  in a production mode (e.g. when `ENV=production`) fail hard if `JWT_SECRET_KEY` is unset/known-insecure
  rather than warning; optionally enforce a minimum length/entropy. Hard-failing on startup changes boot
  behavior — `ask-first`.
- **Disposition:** `ask-first`.

### [Low] API-key hashing is unsalted SHA-256 (acceptable, but document the rationale)
- **Location:** `dashboard_api/auth.py:17-18` (`hash_key`), used at `auth.py:26-31`, `auth.py:94-95`,
  `routers/clients.py:42-47`.
- **What & why:** Keys are generated with `secrets.token_urlsafe(32)` (~256 bits entropy — strong) and
  stored as plain SHA-256 with no per-key salt. Per OWASP, fast unsalted hashing is *acceptable* for
  high-entropy API keys (unlike passwords) because brute force is infeasible regardless of hash speed, so
  this is not a vulnerability. Two minor notes: lookup is by DB-indexed equality on the hash (`auth.py:29`,
  `auth.py:95`), so the raw-key comparison is not a Python byte-compare and the classic per-character timing
  attack on the key does not apply here. However, there is no salt, so identical keys (won't happen with
  random gen, but) would collide-detect; and the password `verify_password` path correctly uses
  `bcrypt.checkpw` (constant-time) — fine.
- **Recommendation:** No change required; add a one-line comment in `hash_key` recording the OWASP rationale
  (high-entropy key, fast hash acceptable) so a future refactor doesn't "upgrade" it to bcrypt and tank
  auth latency on every engine request.
- **Disposition:** `auto-fix-safe` (comment only).

### [Low] `is_website_schedulable` strips a trailing slash that `profile_types` never produces
- **Location:** `dashboard_api/connection_source.py:92-97`, fed by `profile_types` at lines 78-89.
- **What & why:** `is_website_schedulable` does `db_type.lower().rstrip("/")` before the set lookup, but
  `profile_types` already lowercases and never appends a slash to the `type` label. The `rstrip("/")` is
  dead defensive code — harmless, but it hides intent and would silently mask a malformed type like
  `"postgres/"` as schedulable. Low impact (schedulability is a capability flag, not an authz gate).
- **Recommendation:** Either drop the `rstrip("/")` or document why it exists. Behavior-preserving for all
  real inputs. `auto-fix-safe` if removed with a test pinning current outputs first.
- **Disposition:** `ask-first` (security-adjacent capability flag; pin behavior with a test first).

### [Low] `delete_client` deletes results + definitions but orphans runs/schedules/connection_config
- **Location:** `dashboard_api/routers/clients.py:19-27`, vs `dashboard_api/models.py:23-110`.
- **What & why:** Not a tenant-isolation breach (the 403 ownership check at line 22 is correct), but on
  account deletion only `TestResult` and `TestDefinition` rows are removed (lines 24-25). `Run`, `Schedule`,
  and `ConnectionConfig` rows for that client are left behind. The leftover `ConnectionConfig` is the
  security-relevant one: it can contain connection YAML (see High finding) and now persists with no owning
  client. The `Client` model's `cascade="all, delete-orphan"` (models.py:20) only covers
  `test_definitions`, not these tables.
- **Recommendation:** Delete (or cascade) `Run`, `Schedule`, and especially `ConnectionConfig` on account
  deletion. This changes what rows survive a delete — `ask-first`.
- **Disposition:** `ask-first`.

## Simplification & structure

- `dashboard_api/limiter.py:17-18`: the two-case `.get("x-api-key") or .get("X-Api-Key")` is redundant —
  Starlette `request.headers` is case-insensitive; collapse to one lookup.
- `dashboard_api/auth.py`: the API-key lookup logic is duplicated three times
  (`get_current_client` lines 26-31, `get_client_any_auth` lines 93-97, plus `hash_key` callers). Extract a
  single `_client_by_api_key(db, key) -> Optional[Client]` helper and a `_client_by_jwt(db, token)` helper;
  `get_current_client`, `get_current_client_jwt`, and `get_client_any_auth` then compose them. Reduces drift
  (the silent-fallthrough bug above stems from this duplication).
- `dashboard_api/auth.py:39-50`: the module-import-time secret bootstrap with `warnings.warn` is hard to
  test and to gate by environment. Move into a small `_load_secret()` function so tests can exercise the
  insecure/placeholder/valid branches without re-importing the module.
- `connection_source.py` mixes read (`get_yaml_text`), parse, name/type extraction, and capability predicate
  in one module — acceptable, but the capability helpers (lines 71-97) could move next to the schedule logic
  they serve.

## Test gaps & proposed tests

No tests currently exercise auth, JWT, API-key, login, or `ConnectionConfig` storage (confirmed: `tests/`
has no `conftest.py` and no file references `jwt`/`Bearer`/`create_access_token`/`get_client_any_auth`/
`hash_password`). Write these characterization/security tests **before** any refactor:

1. **Tenant isolation (regression guard):** client A's JWT/API key cannot read or mutate client B's runs,
   results, test definitions, schedules, or profiles — assert 403/404/empty for each router. Pin the current
   `client_id == client.id` behavior.
2. **`delete_client` authz + cleanup:** (a) client cannot delete another client's account (expect 403);
   (b) after self-delete, assert which rows survive — this *documents* the current orphan behavior (High/Low
   finding) so a cleanup fix is a deliberate, tested change.
3. **JWT lifecycle:** valid token authenticates; expired token (`exp` in past) → 401; tampered signature →
   401; token signed with a different secret → 401; `sub` referencing a deleted client → 401 "Client not
   found". Run against both `get_current_client_jwt` and `get_client_any_auth` to pin their *current*
   divergence before fixing.
4. **`get_client_any_auth` fall-through:** present-but-invalid `x-api-key` + valid JWT → authenticates;
   present-but-invalid JWT + no key → current behavior is generic 401 (pin it, then change deliberately);
   valid API key short-circuits before JWT.
5. **Login:** wrong password → 401; nonexistent email → 401 (assert *identical* response/body/timing to wrong
   password, to guard against user-enumeration); client with `password_hash = NULL` → 401 (line 18 guard).
6. **Password hashing:** `hash_password`/`verify_password` round-trip; verify against a wrong password fails;
   stored hash is never the plaintext.
7. **Secret bootstrap:** with `JWT_SECRET_KEY` unset and `="change-me-in-production"`, a random secret is
   used and a warning is emitted; with a real secret, that secret is used. (Enables the proposed prod
   hard-fail without breaking dev.)
8. **Rate limiting bypass:** rotating `X-Api-Key` header values resets the bucket (demonstrates the bypass);
   pin current behavior, then re-test after keying on client id.
9. **Credential storage:** upload YAML containing a literal password via `/profiles/sync`, then read
   `ConnectionConfig.yaml_text` directly and assert it is stored as given (documents the plaintext-at-rest
   gap); and assert `/profiles` GET returns only names, never secret values (pins the no-leak contract).
10. **CORS:** preflight from a disallowed origin is rejected; allowed origin (from `ALLOWED_ORIGINS`) gets
    `Access-Control-Allow-Origin`; a 429 still carries CORS headers (the middleware-order invariant in
    `main.py:72-75`).

## Sources

- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Timing-safe auth with Web Crypto](https://www.arun.blog/timing-safe-auth-web-crypto/)
- [How to Secure SaaS Database Connections in Multi-Tenant Environments](https://www.ratomir.com/blog/how-to-secure-saas-database-connections-in-multi-tenant-environments-without-performance-overhead/)
- [Architecting Secure Multi-Tenant Data Isolation](https://medium.com/@justhamade/architecting-secure-multi-tenant-data-isolation-d8f36cb0d25e)
