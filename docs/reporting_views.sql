-- Reporting views consumed by /reports/* endpoints and directly by Power BI
-- (Power BI can connect straight to PostgreSQL and query these views).
--
-- Apply via a dedicated Alembic migration, e.g.:
--   alembic revision -m "reporting views"
-- and paste each CREATE VIEW below into op.execute(...) in upgrade(),
-- with matching DROP VIEW statements in downgrade().

CREATE OR REPLACE VIEW expense_summary AS
SELECT
    er.id                AS report_id,
    er.report_number,
    u.employee_id,
    u.name                AS employee_name,
    u.department,
    er.status,
    er.currency,
    er.total_amount,
    er.submitted_at,
    er.approved_at,
    er.created_at
FROM expense_reports er
JOIN users u ON u.id = er.user_id;


CREATE OR REPLACE VIEW expense_by_type AS
SELECT
    et.code               AS expense_type_code,
    et.name                AS expense_type_name,
    et.category,
    COUNT(ei.id)            AS item_count,
    SUM(ei.amount)           AS total_amount
FROM expense_items ei
JOIN expense_types et ON et.id = ei.expense_type_id
GROUP BY et.code, et.name, et.category;


CREATE OR REPLACE VIEW expense_by_department AS
SELECT
    u.department,
    COUNT(DISTINCT er.id)    AS report_count,
    SUM(er.total_amount)      AS total_amount
FROM expense_reports er
JOIN users u ON u.id = er.user_id
GROUP BY u.department;


CREATE OR REPLACE VIEW audit_exception_summary AS
SELECT
    ar.severity,
    ru.rule_type,
    ru.name                 AS rule_name,
    COUNT(*)                  AS occurrence_count
FROM audit_results ar
JOIN audit_rules ru ON ru.id = ar.rule_id
WHERE ar.result = 'FAILED'
GROUP BY ar.severity, ru.rule_type, ru.name;


CREATE OR REPLACE VIEW integration_failure_summary AS
SELECT
    date_trunc('day', created_at) AS day,
    error_code,
    COUNT(*)                       AS failure_count,
    AVG(retry_count)                AS avg_retry_count,
    AVG(duration_ms)                AS avg_duration_ms
FROM integration_logs
WHERE status = 'FAILED'
GROUP BY date_trunc('day', created_at), error_code
ORDER BY day DESC;
