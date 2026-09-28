import random
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_service import evaluate_report
from app.core.database import get_db
from app.core.errors import bad_request, not_found
from app.models.approval_audit import AuditResult, Approval
from app.models.enums import ApprovalStatus, AuditResultStatus, ReportStatus, Severity, UserRole
from app.models.expense import ExpenseItem, ExpenseReport
from app.models.user import User
from app.schemas.expense import (
    ExpenseItemCreate,
    ExpenseItemOut,
    ExpenseReportCreate,
    ExpenseReportOut,
)
from app.security.dependencies import get_current_claims, require_roles
from app.services.approval_service import all_approved, create_approval_chain, record_decision
from app.workflows.state_machine import InvalidTransitionError, validate_transition

router = APIRouter(tags=["expense-reports"])


def _new_report_number() -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"ER-{datetime.now(timezone.utc):%Y%m}-{suffix}"


async def _get_report_or_404(db: AsyncSession, report_id: uuid.UUID) -> ExpenseReport:
    report = await db.get(ExpenseReport, report_id)
    if not report:
        raise not_found(f"Expense report {report_id} not found")
    return report


@router.post("/expense-reports", response_model=ExpenseReportOut, status_code=201)
async def create_report(
    payload: ExpenseReportCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    report = ExpenseReport(
        report_number=_new_report_number(),
        user_id=uuid.UUID(claims["sub"]),
        title=payload.title,
        currency=payload.currency,
        status=ReportStatus.DRAFT,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/expense-reports", response_model=list[ExpenseReportOut])
async def list_reports(db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    if claims.get("role") in (UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER):
        result = await db.execute(select(ExpenseReport))
    else:
        result = await db.execute(select(ExpenseReport).where(ExpenseReport.user_id == uuid.UUID(claims["sub"])))
    return result.scalars().all()


@router.get("/expense-reports/{report_id}", response_model=ExpenseReportOut)
async def get_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_claims)):
    return await _get_report_or_404(db, report_id)


@router.post("/expense-reports/{report_id}/items", response_model=ExpenseItemOut, status_code=201)
async def add_item(
    report_id: uuid.UUID,
    payload: ExpenseItemCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    report = await _get_report_or_404(db, report_id)
    if report.status != ReportStatus.DRAFT:
        raise bad_request("Items can only be added while the report is in DRAFT status")

    item = ExpenseItem(report_id=report.id, **payload.model_dump())
    db.add(item)
    report.total_amount = (report.total_amount or 0) + payload.amount
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/expense-reports/{report_id}/items", response_model=list[ExpenseItemOut])
async def list_items(report_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_claims)):
    await _get_report_or_404(db, report_id)
    result = await db.execute(select(ExpenseItem).where(ExpenseItem.report_id == report_id))
    return result.scalars().all()


# --- Workflow transitions -------------------------------------------------


@router.post("/expense-reports/{report_id}/submit", response_model=ExpenseReportOut)
async def submit_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    report = await _get_report_or_404(db, report_id)
    try:
        validate_transition(report.status, ReportStatus.SUBMITTED)
    except InvalidTransitionError as exc:
        raise bad_request(str(exc)) from exc
    report.status = ReportStatus.SUBMITTED
    report.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)
    return report


@router.post("/expense-reports/{report_id}/audit", response_model=ExpenseReportOut)
async def audit_report(
    report_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    _=Depends(require_roles(UserRole.AUDITOR, UserRole.ADMIN, UserRole.INTEGRATION_SERVICE)),
):
    report = await _get_report_or_404(db, report_id)
    try:
        validate_transition(report.status, ReportStatus.AUDIT_PENDING)
    except InvalidTransitionError as exc:
        raise bad_request(str(exc)) from exc
    report.status = ReportStatus.AUDIT_PENDING

    results = await evaluate_report(db, report)
    has_error = any(r.severity == Severity.ERROR for r in results)

    submitter = await db.get(User, report.user_id)
    if has_error:
        validate_transition(report.status, ReportStatus.EXCEPTION)
        report.status = ReportStatus.EXCEPTION
    else:
        validate_transition(report.status, ReportStatus.PENDING_APPROVAL)
        report.status = ReportStatus.PENDING_APPROVAL
        await create_approval_chain(db, report, submitter)

    await db.commit()
    await db.refresh(report)
    return report


@router.get("/expense-reports/{report_id}/audit-results")
async def get_audit_results(report_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_claims)):
    await _get_report_or_404(db, report_id)
    result = await db.execute(select(AuditResult).where(AuditResult.report_id == report_id))
    return result.scalars().all()


@router.post("/expense-reports/{report_id}/approve", response_model=ExpenseReportOut)
async def approve_report(
    report_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    report = await _get_report_or_404(db, report_id)
    result = await db.execute(
        select(Approval).where(Approval.report_id == report_id, Approval.approver_id == uuid.UUID(claims["sub"]), Approval.status == ApprovalStatus.PENDING)
    )
    approval = result.scalars().first()
    if not approval:
        raise bad_request("No pending approval found for this approver on this report")

    await record_decision(db, approval, ApprovalStatus.APPROVED, comments=None)

    if await all_approved(db, report_id):
        validate_transition(report.status, ReportStatus.APPROVED)
        report.status = ReportStatus.APPROVED
        report.approved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(report)
    return report


@router.post("/expense-reports/{report_id}/reject", response_model=ExpenseReportOut)
async def reject_report(
    report_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    report = await _get_report_or_404(db, report_id)
    result = await db.execute(
        select(Approval).where(Approval.report_id == report_id, Approval.approver_id == uuid.UUID(claims["sub"]), Approval.status == ApprovalStatus.PENDING)
    )
    approval = result.scalars().first()
    if not approval:
        raise bad_request("No pending approval found for this approver on this report")

    await record_decision(db, approval, ApprovalStatus.REJECTED, comments=None)
    validate_transition(report.status, ReportStatus.REJECTED)
    report.status = ReportStatus.REJECTED
    report.rejected_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(report)
    return report


@router.post("/expense-reports/{report_id}/process", response_model=ExpenseReportOut)
async def process_report(
    report_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    _=Depends(require_roles(UserRole.ADMIN, UserRole.INTEGRATION_SERVICE)),
):
    report = await _get_report_or_404(db, report_id)
    try:
        validate_transition(report.status, ReportStatus.PROCESSED)
    except InvalidTransitionError as exc:
        raise bad_request(str(exc)) from exc
    report.status = ReportStatus.PROCESSED
    await db.commit()
    await db.refresh(report)
    return report
