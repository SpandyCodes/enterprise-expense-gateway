# Testing strategy

## Layout

```
tests/
  unit/         pure logic, no DB (state machine, retry policy, adapter, idempotency hashing)
  integration/  real PostgreSQL session (audit engine, approval routing)
  api/          FastAPI TestClient/httpx contract tests
  security/     authn/authz + mTLS trust-boundary tests
  failure/      idempotency replay, malformed payloads, invalid transitions
  test_data/    shared fixture payloads
```

## Running

```bash
# start a test database (or point TEST_DATABASE_URL at any isolated Postgres)
docker compose up -d postgres

# run the full suite
pytest -v

# with coverage
pytest --cov=app --cov-report=term-missing
```

By default, DB-backed fixtures connect to
`postgresql+asyncpg://expense_user:expense_pw@localhost:5432/expense_gateway_test`.
Override with `TEST_DATABASE_URL` to point at a different isolated
schema/database — tests never run against the development database.

Each `db_session` fixture creates all tables at the start of the test
and drops them at the end, so tests are isolated and do not depend on
execution order.

## Manual verification (not automated in pytest)

The mTLS **TLS handshake itself** (rather than the app-layer header
check, which *is* covered by `tests/security/test_mtls_boundary.py`) is
verified manually once certificates exist and Nginx is running:

```bash
./scripts/generate_certs.sh
docker compose up -d nginx

# should be rejected (no client cert)
curl -k https://localhost:8443/internal/integrations/expense-sync -d '{}'

# should be accepted
curl --cert certs/client/client.crt --key certs/client/client.key \
     --cacert certs/ca/ca.crt \
     https://localhost:8443/internal/integrations/expense-sync -d '{}'
```

## Coverage target

Target: **>= 85%** overall coverage for business logic
(`app/audit`, `app/services`, `app/workflows`, `app/integrations`,
`app/security`). Record the actual measured percentage from
`pytest --cov=app --cov-report=term-missing` in the README once the
suite has been run against a live PostgreSQL instance — this scaffold
ships the test suite and fixtures but the exact percentage depends on
your environment's run.
