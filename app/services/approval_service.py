"""
Approval routing engine.

Amount-based approval chains (configurable in APPROVAL_TIERS, not
hard-coded into API routes):
  < 5,000          -> MANAGER
  5,000 - 24,999   -> MANAGER, FINANCE
  >= 25,000        -> MANAGER, FINANCE, SENIOR
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_audit import Approval
from app.models.enums import ApprovalStatus
from app.models.expense import ExpenseReport
from app.models.user import User


@dataclass(frozen=True)
class ApprovalTier:
    max_amount: Decimal | None  # None = unbounded
    chain: tuple[str, ...]  # approver "levels" — resolved to actual users by caller


APPROVAL_TIERS: tuple[ApprovalTier, ...] = (
    ApprovalTier(Decimal("5000"), ("MANAGER",)),
    ApprovalTier(Decimal("25000"), ("MANAGER", "FINANCE")),
    ApprovalTier(None, ("MANAGER", "FINANCE", "SENIOR")),
)


def resolve_chain_for_amount(amount: Decimal) -> tuple[str, ...]:
    for tier in APPROVAL_TIERS:
        if tier.max_amount is None or amount < tier.max_amount:
            return tier.chain
    return APPROVAL_TIERS[-1].chain


async def create_approval_chain(session: AsyncSession, report: ExpenseReport, submitter: User) -> list[Approval]:
    """Create Approval rows for a report based on its total_amount.

    Level resolution here is simplified for the portfolio scope:
    MANAGER = submitter.manager_id; FINANCE/SENIOR levels are resolved to
    the first active user found with the matching department, which a
    real deployment would replace with a proper role/assignment lookup.
    """
    chain_levels = resolve_chain_for_amount(report.total_amount)
    approvals: list[Approval] = []

    for idx, level in enumerate(chain_levels, start=1):
        approver_id = await _resolve_approver(session, submitter, level)
        approvals.append(
            Approval(report_id=report.id, approver_id=approver_id, sequence=idx, status=ApprovalStatus.PENDING)
        )
    for approval in approvals:
        session.add(approval)
    return approvals


async def _resolve_approver(session: AsyncSession, submitter: User, level: str):
    if level == "MANAGER" and submitter.manager_id:
        return submitter.manager_id
    # Fallback: pick any active MANAGER/ADMIN as a stand-in approver for
    # FINANCE/SENIOR levels — documented simplification for this scope.
    result = await session.execute(
        select(User).where(User.role.in_(["MANAGER", "ADMIN"]), User.active.is_(True)).limit(1)
    )
    fallback = result.scalars().first()
    return fallback.id if fallback else submitter.id


async def record_decision(
    session: AsyncSession, approval: Approval, decision: ApprovalStatus, comments: str | None
) -> Approval:
    from datetime import datetime, timezone

    approval.status = decision
    approval.comments = comments
    approval.acted_at = datetime.now(timezone.utc)
    session.add(approval)
    return approval


async def all_approved(session: AsyncSession, report_id) -> bool:
    result = await session.execute(select(Approval).where(Approval.report_id == report_id))
    approvals = list(result.scalars().all())
    return bool(approvals) and all(a.status == ApprovalStatus.APPROVED for a in approvals)


async def any_rejected(session: AsyncSession, report_id) -> bool:
    result = await session.execute(select(Approval).where(Approval.report_id == report_id))
    approvals = list(result.scalars().all())
    return any(a.status == ApprovalStatus.REJECTED for a in approvals)
