# Security

## OAuth 2.0-style authentication (local demonstration)

`POST /auth/token` accepts `{"username": ..., "password": ...}` and, if
valid, returns a short-lived JWT bearer access token:

```json
{"access_token": "...", "token_type": "bearer", "expires_in": 1800}
```

All other API routes require `Authorization: Bearer <token>`. Tokens are
validated (signature + expiry) on every request via a FastAPI
dependency, and the decoded `role` claim drives role-based authorization
(`require_roles(...)`).

**This is explicitly NOT a production-grade OAuth 2.0 authorization
server.** It does not implement: authorization code flow, PKCE, refresh
token rotation/revocation, client registration, consent screens, or
scope negotiation. It demonstrates the bearer-token validation and
role-based authorization pattern that a real OAuth2 resource server
would also implement, using a simplified local token issuer suitable for
a portfolio project.

## Roles and permissions

| Role | Permissions |
|---|---|
| EMPLOYEE | create expense reports, modify own drafts, submit own reports |
| MANAGER | view reports requiring approval, approve/reject |
| AUDITOR | inspect audit results, configure audit rules |
| ADMIN | manage users, expense types, configuration |
| INTEGRATION_SERVICE | invoke integration endpoints |

## mTLS for service-to-service integration

`POST /internal/integrations/expense-sync` is protected by mutual TLS,
terminated at Nginx (`nginx/nginx.conf`, `ssl_verify_client on`).
Requests without a valid client certificate signed by the local dev CA
are rejected by Nginx before they ever reach the application. Nginx then
forwards the verified certificate's Common Name via `X-Client-Cert-CN`,
which the FastAPI handler requires — so even a request that somehow
reached the app directly (e.g. in local dev without going through Nginx)
is rejected without that header.

Generate local certificates with:

```bash
./scripts/generate_certs.sh
```

This creates a local CA, a server certificate for Nginx, and a client
certificate for the integration caller under `certs/`. **Never commit
the generated `.key` files** — they're excluded via `.gitignore`.

### mTLS vs OAuth 2.0 — why both exist

- **mTLS authenticates the connection/machine**: it proves which service
  is talking to which service at the TLS layer, using X.509
  certificates issued by a trusted CA. It says nothing about *which
  user* is acting.
- **OAuth 2.0 bearer tokens authenticate the principal**: they carry a
  claim about *who* (or which service account) is making the request,
  and what they're authorized to do (`role`).
- **They coexist** because a service-to-service integration channel
  needs both: mTLS ensures only trusted infrastructure can even open a
  connection to the internal endpoint, while the application-layer
  identity (e.g. the `INTEGRATION_SERVICE` role) still governs what that
  connection is allowed to do. Using only one would leave a gap: mTLS
  alone can't express fine-grained user/role permissions; bearer tokens
  alone can't guarantee the caller is a trusted network peer.

## Secrets handling

No secrets are hard-coded. `.env.example` documents required variables;
`.env` (with real values) is git-ignored. JWT signing key, database
credentials, and TLS private keys are all supplied via environment
variables or mounted volumes, never committed.

## What is never logged

Passwords, access tokens, private keys, and client secrets are excluded
from structured logs (see `app/main.py` request-logging middleware,
which only logs request metadata: method, path, status, duration,
correlation/request IDs).
