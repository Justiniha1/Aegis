# C3 — Move browser auth token off localStorage (deferred migration plan)

Status: DEFERRED (decided 2026-06-15). High blast radius + Railway deploy risk; needs
its own focused effort with manual verification of the deployed login flow.

## Problem
The JWT and client identity are stored in `localStorage` (`frontend/src/lib/auth.tsx:30,49`).
Any injected script (XSS) can read the token, and there is no expiry/refresh handling on
the client. Tokens are also long-lived (24h, `dashboard_api/auth.py:52`) with no revocation.

## Why it is risky to change now
- Frontend and API are deployed on **separate Railway domains** (cross-origin). HttpOnly
  cookies across origins require `SameSite=None; Secure` and exact domain/CORS config; a
  misconfiguration silently breaks login in production but not locally.
- It touches the entire authenticated surface: login, every `apiGet/apiPost`, logout,
  CORS (`dashboard_api/main.py:79-81`), and adds CSRF protection requirements.
- There are currently no end-to-end auth tests; verification is manual.

## Recommended target design (httpOnly cookie + lightweight identity)
1. **Backend**
   - On `POST /api/v1/auth/login`: set the JWT in an httpOnly, `Secure`, `SameSite=None`
     cookie (e.g. `comet_token`) instead of (or in addition to) returning it in the body.
   - Add a `GET /api/v1/auth/me` returning `{client_id, client_name}` so the SPA can show
     identity without reading the token (httpOnly cookies are invisible to JS).
   - Accept the cookie in the auth dependencies (extend `get_current_client_jwt` /
     `get_client_any_auth` to read the cookie as a fallback to the `Authorization` header,
     so the engine's API-key/bearer paths are unaffected).
   - Add CSRF protection (double-submit cookie or `SameSite=Strict` where origin allows).
   - `POST /api/v1/auth/logout` clears the cookie.
   - Tighten CORS to the exact frontend origin with `allow_credentials=True` (cannot use
     `*` with credentials).
   - Consider shortening token lifetime + adding a refresh cookie; add `iat`/`jti` claims
     to enable revocation later.
2. **Frontend** (`src/lib/auth.tsx`, `src/lib/api.ts`)
   - Remove all `localStorage` token handling.
   - Send requests with `credentials: "include"`.
   - Restore identity on mount via `GET /auth/me` instead of reading storage.
   - Keep only non-sensitive display data (client name) in memory/state.
3. **Deploy / env**
   - Set the frontend origin in an allowlist env var on the API.
   - Verify `Secure`/`SameSite=None` works on the Railway HTTPS domains.

## Verification checklist (must be manual against the deployed stack)
- Login sets the cookie; refresh keeps the session; logout clears it.
- A second browser/incognito cannot reuse the token from JS (`document.cookie` omits it).
- Cross-origin requests succeed with credentials; CORS preflight passes.
- The engine's API-key and bearer-header flows are unchanged (regression check).

## Interim mitigations already in place
- `get_client_any_auth` no longer silently swallows invalid tokens (H4, done).
- Literal DB credentials are rejected at upload so they never persist (H3, done).
