"""
Audit engine: evaluates data-driven AuditRule records against an
ExpenseReport's items and produces AuditResult records.

Supported rule_type values (configuration schema per type):
  THRESHOLD        - {"category": str | None}  amount > rule.threshold
  RECEIPT_REQUIRED - {}  flags items missing receipt_reference where the
                      expense type requires one
  DUPLICATE        - {}  same user + vendor + amount + transaction_date
  POLICY_WINDOW     - {"max_days_after_transaction": int}
  PERSONAL_BILLABLE - {}  personal=True and billable=True
  UNSUPPORTED_TYPE  - {}  expense_type.active is False
"""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_audit import AuditResult, AuditRule
from app.models.enums import AuditResultStatus, Severity
from app.models.expense import ExpenseItem, ExpenseReport, ExpenseType


async def evaluate_report(session: AsyncSession, report: ExpenseReport) -> list[AuditResult]:
    """Evaluate all enabled audit rules against a report's items and
    persist AuditResult rows. Returns the list of created results."""
    rules_result = await session.execute(select(AuditRule).where(AuditRule.enabled.is_(True)))
    rules = list(rules_result.scalars().all())

    items_result = await session.execute(select(ExpenseItem).where(ExpenseItem.report_id == report.id))
    items = list(items_result.scalars().all())

    type_ids = {i.expense_type_id for i in items}
    types_result = await session.execute(select(ExpenseType).where(ExpenseType.id.in_(type_ids))) if type_ids else None
    types_by_id = {t.id: t for t in types_result.scalars().all()} if types_result else {}

    results: list[AuditResult] = []

    for rule in rules:
        if rule.rule_type == "THRESHOLD":
            results.extend(_check_threshold(rule, report, items, types_by_id))
        elif rule.rule_type == "RECEIPT_REQUIRED":
            results.extend(_check_receipt_required(rule, report, items, types_by_id))
        elif rule.rule_type == "DUPLICATE":
            results.extend(_check_duplicates(rule, report, items))
        elif rule.rule_type == "POLICY_WINDOW":
            results.extend(_check_policy_window(rule, report, items))
        elif rule.rule_type == "PERSONAL_BILLABLE":
            results.extend(_check_personal_billable(rule, report, items))
        elif rule.rule_type == "UNSUPPORTED_TYPE":
            results.extend(_check_unsupported_type(rule, report, items, types_by_id))
        # Unknown rule_type values are ignored, not fatal — new rule types
        # can be added by extending this dispatcher.

    for result in results:
        session.add(result)
    return results


def _pass_or_none(rule: AuditRule, report: ExpenseReport, item: ExpenseItem | None, passed: bool, message: str) -> AuditResult | None:
    if passed:
        return None  # only persist failures + explicit passes if desired; here we record failures only
    return AuditResult(
        report_id=report.id,
        expense_item_id=item.id if item else None,
        rule_id=rule.id,
        result=AuditResultStatus.FAILED,
        severity=rule.severity,
        message=message,
    )


def _check_threshold(rule, report, items, types_by_id) -> list[AuditResult]:
    out = []
    category = (rule.configuration or {}).get("category")
    for item in items:
        etype = types_by_id.get(item.expense_type_id)
        if category and (not etype or etype.category != category):
            continue
        if rule.threshold is not None and item.amount > rule.threshold:
            r = _pass_or_none(
                rule, report, item, False,
                f"Item amount {item.amount} exceeds category threshold {rule.threshold}",
            )
            if r:
                out.append(r)
    return out


def _check_receipt_required(rule, report, items, types_by_id) -> list[AuditResult]:
    out = []
    for item in items:
        etype = types_by_id.get(item.expense_type_id)
        if etype and etype.requires_receipt and not item.receipt_reference:
            out.append(_pass_or_none(rule, report, item, False, "Receipt required but missing"))
    return out


def _check_duplicates(rule, report, items) -> list[AuditResult]:
    out = []
    seen: dict[tuple, list[ExpenseItem]] = defaultdict(list)
    for item in items:
        key = (report.user_id, item.vendor, item.amount, item.transaction_date)
        seen[key].append(item)
    for key, group in seen.items():
        if len(group) > 1:
            for item in group:
                out.append(_pass_or_none(rule, report, item, False, "Potential duplicate expense (same vendor/amount/date)"))
    return out


def _check_policy_window(rule, report, items) -> list[AuditResult]:
    out = []
    max_days = (rule.configuration or {}).get("max_days_after_transaction", 90)
    today = date.today()
    for item in items:
        days = (today - item.transaction_date).days
        if days > max_days:
            out.append(_pass_or_none(rule, report, item, False, f"Submitted {days}d after transaction (policy max {max_days}d)"))
    return out


def _check_personal_billable(rule, report, items) -> list[AuditResult]:
    out = []
    for item in items:
        if item.personal and item.billable:
            out.append(_pass_or_none(rule, report, item, False, "Personal expense marked billable"))
    return out


def _check_unsupported_type(rule, report, items, types_by_id) -> list[AuditResult]:
    out = []
    for item in items:
        etype = types_by_id.get(item.expense_type_id)
        if not etype or not etype.active:
            out.append(_pass_or_none(rule, report, item, False, "Unsupported or inactive expense type"))
    return out
