# Migrations

No migration has been generated yet in this scaffold. Once the `app`
container can reach PostgreSQL (e.g. after `docker compose up -d postgres`),
generate the initial migration with:

```bash
docker compose run --rm app alembic revision --autogenerate -m "initial schema"
docker compose run --rm app alembic upgrade head
```

This will create tables for every model in `app/models/`. After that,
add a second migration for the reporting views (see `docs/reporting.md`
for the view SQL) — Alembic autogenerate does not manage raw SQL views,
so create them with `op.execute(...)` in a dedicated migration, e.g.:

```bash
docker compose run --rm app alembic revision -m "reporting views"
```
