#!/usr/bin/env bash
# Convenience wrapper: apply migrations, then generate synthetic data.
# Run inside the app container (has DATABASE_URL configured):
#   docker compose run --rm app scripts/seed_database.sh
set -euo pipefail

echo "==> Applying migrations"
alembic upgrade head

echo "==> Generating synthetic data"
python scripts/generate_data.py --users 100 --reports 300 --items 1000 --seed 42

echo "==> Done."
