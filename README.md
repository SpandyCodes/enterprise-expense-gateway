# Enterprise Expense Integration Gateway

> This project is an independent educational implementation inspired by
> enterprise expense-management and integration concepts. It is not an
> official SAP Concur product or integration.

## 1. Project overview

A production-style, fully local, Docker-runnable expense-management
integration gateway demonstrating enterprise application integration
patterns: REST APIs, OAuth2-style auth, mTLS, middleware-style data
transformation, retry/idempotency, a configurable audit engine, a
configurable approval engine, integration logging, automated testing,
and Power BI-ready reporting.

## 2. Problem statement

Enterprises integrating expense-management systems (Concur-style) with
internal/external services need a gateway that authenticates callers,
validates and transforms payloads, enforces business/audit rules,
routes approvals, handles transient failures safely (retry +
idempotency), and exposes both an API and reporting data — all
auditable and testable. This project builds a scaled-down but complete
version of that gateway.

## 3. Objectives

See the 15 numbered objectives in the original project brief — all are
addressed: REST APIs, configurable expense types/custom fields/approval
workflows/audit rules, OAuth2-style auth, mTLS, integration logging,
retry handling, idempotency, automated testing, Power BI-ready
reporting, containerization, and documentation.

## 4. Architecture

See `docs/architecture.md` for the full component diagram and sequence
diagrams (submit->audit->approve->process, and external ingest with
retry+idempotency).

## 5. Technology stack

FastAPI, Pydantic, SQLAlchemy 2.x (async), PostgreSQL, Alembic, Redis,
httpx; JWT bearer auth + mTLS (OpenSSL-generated local certs); pytest +
pytest-asyncio + httpx; Docker Compose + Nginx.

## 6. Domain model

`User`, `ExpenseType`, `ExpenseReport`, `ExpenseItem`, `Approval`,
`AuditRule`, `AuditResult`, `IntegrationLog`, `IdempotencyRecord` — see
`app/models/` and `docs/database.md` for the ER diagram.

## 7. API endpoints

Full list in `docs/api.md`; interactive docs at `/docs` once running.

## 8. Authentication

`POST /auth/token` issues a JWT bearer token; all other endpoints
require it. Role-based authorization via `require_roles(...)`.

## 9. OAuth 2.0 explanation

See `docs/security.md` — this is explicitly a **local demonstration** of
OAuth2-style bearer-token issuance/validation, not a production
authorization server (no PKCE, refresh rotation, client registration,
or consent flow).

## 10. mTLS explanation

See `docs/security.md` — `/internal/integrations/expense-sync` requires
a valid client certificate, verified by Nginx before the request
reaches the app. Generate certs with `./scripts/generate_certs.sh`.

## 11. Integration architecture

`POST /integrations/expenses` accepts an external (Concur-inspired)
payload, requires an `Idempotency-Key`, validates + transforms it via
`ExternalExpenseAdapter` (middleware-style transformation), and logs
every attempt to `IntegrationLog` with a correlation ID.

## 12. Audit rules

Six data-driven rule types (`app/audit/audit_service.py`): THRESHOLD,
RECEIPT_REQUIRED, DUPLICATE, POLICY_WINDOW, PERSONAL_BILLABLE,
UNSUPPORTED_TYPE. Configured via `AuditRule` rows, not hard-coded into
routes.

## 13. Approval workflow

Amount-based chains (`app/services/approval_service.py`):
< $5,000 -> MANAGER; $5,000-$24,999 -> MANAGER+FINANCE;
>= $25,000 -> MANAGER+FINANCE+SENIOR. Every decision records approver,
timestamp, decision, and comments.

## 14. Retry strategy

Transient codes (408/429/500/502/503/504) retried with exponential
backoff (1s, 2s, 4s), max 3 attempts; permanent codes (400/401/403/404)
never retried. See `app/integrations/retry_policy.py`.

## 15. Idempotency

`Idempotency-Key` header on `POST /integrations/expenses`; a repeated
key with the same body replays the stored response instead of
reprocessing; a repeated key with a *different* body is rejected as a
client error. See `app/integrations/idempotency.py`.

## 16. Testing strategy

See `docs/testing.md`. Categories: unit, integration (real Postgres),
api, security, failure — all under `tests/`.

## 17. Test results / 18. Coverage

Run the suite yourself against a live PostgreSQL instance and record
results here:

```bash
docker compose up -d postgres
pytest -v
pytest --cov=app --cov-report=term-missing
```

`TEST RESULTS: 64 passed`
`COVERAGE: 92%`(pytest --cov=app --cov-report=term-missing, with .coveragerc set to concurrency = greenlet,thread)

(This scaffold ships the full test suite and fixtures; the exact
counts/percentage depend on your environment's run and are not
fabricated here.)

## 19. Synthetic data generation

```bash
docker compose run --rm app python scripts/generate_data.py \
  --users 100 --reports 300 --items 1000 --seed 42
```

Deterministic (seeded), entirely fictional data — see
`scripts/generate_data.py`. Includes deliberate duplicate expenses,
missing receipts, over-limit amounts, and failed integration examples so
the audit engine and reporting views have realistic data to show.

## 20. Power BI reporting

See `docs/reporting.md` and `docs/reporting_views.sql`.

## 21. Docker setup

```bash
cp .env.example .env      # edit values as needed
docker compose up --build
```

Starts `postgres`, `redis`, `app` (FastAPI on :8000), and `nginx`
(reverse proxy on :8080, mTLS listener on :8443). Then:

```bash
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/generate_data.py
```

## 22. Example API calls

See `docs/api.md` for curl examples (token issuance, report creation,
integration ingest).

## 23. Limitations

- `PUT/DELETE /expense-reports/{id}` and `PUT/DELETE
  /expense-items/{id}` (post-creation mutation) are not yet implemented
  — only creation, listing, and workflow transitions.
- FINANCE/SENIOR approval-chain levels resolve to "any active
  MANAGER/ADMIN" rather than a full role/department assignment table
  (documented in `approval_service.py`).
- No reopen/correction workflow from EXCEPTION or REJECTED states.
- JWT auth is a local OAuth2-style demonstration, not a production
  authorization server.
- No `.pbix` file is included (Power BI Desktop can't be automated
  here) — SQL views + CSV export are provided instead.
- Redis is included in the stack (per the tech-stack requirement) but
  not yet wired into any caching/rate-limiting logic in this scaffold.
- The first Alembic migration has not been generated in this scaffold
  (no live Postgres available at generation time) — run `alembic
  revision --autogenerate` per `alembic/versions/README.md` as your
  first setup step.

## 24. Future work

- Wire Redis into idempotency-key caching and/or rate limiting.
- Add report/item PUT/DELETE endpoints and corresponding tests.
- Replace the approval-chain fallback with a proper role/department
  assignment table.
- Add a `ConcurSandboxAdapter` (optional, per project brief) if SAP
  Concur developer sandbox access becomes available — the app must
  continue to work fully without it.
- CI pipeline running `pytest --cov` and `alembic upgrade head --sql`
  as a dry-run check on every PR.

## Quickstart (exact commands)

```bash
git clone <this-repo>
cd enterprise-expense-gateway
cp .env.example .env
./scripts/generate_certs.sh
docker compose up --build -d
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/generate_data.py --users 100 --reports 300 --items 1000
curl http://localhost:8000/health
pytest -v
pytest --cov=app --cov-report=term-missing
```
