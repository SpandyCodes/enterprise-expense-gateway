"""
Expense report workflow state machine.

DRAFT -> SUBMITTED -> AUDIT_PENDING -> (EXCEPTION | PENDING_APPROVAL)
PENDING_APPROVAL -> (APPROVED | REJECTED)
APPROVED -> PROCESSED

Any transition not explicitly listed in ALLOWED_TRANSITIONS is rejected.
Reopen/correction flows (e.g. EXCEPTION -> DRAFT) are intentionally NOT
implemented in this portfolio scope; see docs/architecture.md.
"""
from app.models.enums import ReportStatus


class InvalidTransitionError(Exception):
    def __init__(self, current: ReportStatus, target: ReportStatus):
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition expense report from {current} to {target}")


ALLOWED_TRANSITIONS: dict[ReportStatus, set[ReportStatus]] = {
    ReportStatus.DRAFT: {ReportStatus.SUBMITTED},
    ReportStatus.SUBMITTED: {ReportStatus.AUDIT_PENDING},
    ReportStatus.AUDIT_PENDING: {ReportStatus.EXCEPTION, ReportStatus.PENDING_APPROVAL},
    ReportStatus.EXCEPTION: set(),  # terminal in this scope; requires manual/administrative correction
    ReportStatus.PENDING_APPROVAL: {ReportStatus.APPROVED, ReportStatus.REJECTED},
    ReportStatus.REJECTED: set(),  # terminal in this scope
    ReportStatus.APPROVED: {ReportStatus.PROCESSED},
    ReportStatus.PROCESSED: set(),  # terminal
}


def validate_transition(current: ReportStatus, target: ReportStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target)


def can_transition(current: ReportStatus, target: ReportStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())
