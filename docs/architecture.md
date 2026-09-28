# Architecture

## Overview

The Enterprise Expense Integration Gateway is a FastAPI service that
demonstrates enterprise integration patterns — REST APIs, OAuth2-style
auth, mTLS, middleware-style data transformation, retry/idempotency, an
audit engine, and Power BI-ready reporting — inspired by common expense
management (SAP Concur-style) workflows. It is an independent
educational project, not an official SAP Concur integration.

## Component diagram

```
Client / External Expense System
          |
          | REST/JSON
          v
       Nginx  (reverse proxy on :8080, mTLS listener on :8443)
          |
          v
   FastAPI Integration Gateway
          |
     +----+----------------+
     |                     |
 Authentication       Integration Layer
     |                     |
 OAuth 2.0 (JWT)         Validation (Pydantic)
 mTLS (via Nginx)        Transformation (ExternalExpenseAdapter)
                         Routing
                         Retry (exponential backoff)
                         Idempotency
                              |
                              v
                         PostgreSQL
                              |
                    +---------+---------+
                    |                   |
               Audit Engine        Reporting Views
                    |                   |
                    v                   v
              Audit Results        Power BI / CSV export
```

## Sequence: submit -> audit -> approve -> process

```
Employee          API                 AuditService       ApprovalService     DB
   |               |                       |                   |             |
   |--POST submit->|                       |                   |             |
   |               |--validate transition->|                   |             |
   |               |----------------------UPDATE status--------------------->|
   |<--200 SUBMITTED------------------------|                   |            |
   |               |                       |                   |            |
Auditor            |                       |                   |            |
   |--POST audit-->|                       |                   |            |
   |               |--evaluate_report()--->|                   |            |
   |               |<--AuditResults--------|                   |            |
   |               |--(no ERROR) create_approval_chain()------>|            |
   |               |                       |                   |--INSERT--->|
   |<--200 PENDING_APPROVAL----------------|                   |            |
   |               |                       |                   |            |
Manager            |                       |                   |            |
   |--POST approve>|                       |                   |            |
   |               |----------------------record_decision()--->|            |
   |               |----------------------all_approved()?------>|            |
   |<--200 APPROVED (once all levels done)-|                   |            |
```

## Sequence: external integration ingest (retry + idempotency)

```
External system        Nginx :8080        API :8000        PostgreSQL
      |                    |                  |                 |
      |--POST /integrations/expenses -------->|                 |
      |   Idempotency-Key: abc123             |                 |
      |                    |                  |--check_or_reserve()-->|
      |                    |                  |  (key seen before?)   |
      |                    |                  |<--no------------------|
      |                    |                  |--adapt() (validate+transform)
      |                    |                  |--INSERT IntegrationLog-->|
      |                    |                  |--store_response()------>|
      |<--202 ACCEPTED-------------------------|                 |
      |                                        |                 |
      |--(retry with same key, e.g. after timeout)-------------->|
      |                    |                  |--check_or_reserve()-->|
      |                    |                  |<--existing record----|
      |<--202 ACCEPTED (replayed, no duplicate work)--------------|
```

## Why these boundaries

- **Nginx** terminates TLS for both listeners, and additionally performs
  mutual-TLS client certificate verification for the internal
  service-to-service listener before any request reaches the app.
- **FastAPI** owns request validation (Pydantic), authorization (JWT
  role checks), business rules (workflow/audit/approval services), and
  persistence (SQLAlchemy).
- **Services are separated from routes**: `app/audit`, `app/services`,
  `app/workflows`, and `app/integrations` contain the business logic;
  `app/api/routes` only wires HTTP concerns to those services.

## Known simplifications (documented, not hidden)

- Approval-chain level resolution for FINANCE/SENIOR tiers falls back to
  "any active MANAGER/ADMIN" rather than a full department/role
  assignment table — documented in `approval_service.py`.
- EXCEPTION and REJECTED are terminal states in this scope; no
  reopen/correction workflow is implemented (the spec explicitly allows
  this simplification).
- The JWT-based auth is a **local OAuth2-style demonstration**, not a
  production OAuth2 authorization server (no refresh tokens, consent
  screens, client registration, or PKCE).
