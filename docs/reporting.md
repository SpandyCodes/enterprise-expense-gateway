# Reporting / Power BI

## PostgreSQL views

See `docs/reporting_views.sql` for the view definitions:
`expense_summary`, `expense_by_type`, `expense_by_department`,
`audit_exception_summary`, `integration_failure_summary`.

## Connecting Power BI Desktop to PostgreSQL

1. Get Data -> More -> Database -> PostgreSQL database.
2. Server: `localhost`, Port: `5432` (or the mapped docker-compose port),
   Database: value of `POSTGRES_DB`.
3. Use the same credentials as `POSTGRES_USER` / `POSTGRES_PASSWORD`
   from your local `.env` (never share real credentials).
4. Select the five reporting views (not the raw tables) as your import
   or DirectQuery source — they're already aggregated/joined for
   dashboard use.

## Recommended dashboard visuals

- **Expense summary** (`expense_summary`): a matrix/table by department
  and status, with a card visual for total spend and a stacked bar of
  status distribution (DRAFT/SUBMITTED/.../PROCESSED).
- **Spend by category** (`expense_by_type`): a donut or bar chart of
  `total_amount` by `category`/`expense_type_name`.
- **Spend by department** (`expense_by_department`): a bar chart of
  `total_amount` by `department`, sorted descending.
- **Audit exceptions** (`audit_exception_summary`): a table or heatmap
  of `occurrence_count` by `rule_type` and `severity`, to spot
  recurring policy violations.
- **Integration health** (`integration_failure_summary`): a line chart
  of `failure_count` by `day`, split by `error_code`, to track
  integration reliability over time.

## CSV export

`GET /reports/export/csv` streams `expense_summary` as CSV for ad-hoc
import into Power BI, Excel, or any BI tool without a live DB
connection.

## No `.pbix` file is included

Power BI Desktop cannot be automated in this environment, so no `.pbix`
file is fabricated. The views + CSV export above are the reporting
contract Power BI (or any BI tool) is meant to consume; screenshots of
an actual dashboard can be added under `docs/screenshots/` once built
locally.
