import pytest

from app.models.enums import ReportStatus
from app.workflows.state_machine import InvalidTransitionError, can_transition, validate_transition

pytestmark = pytest.mark.unit


def test_draft_to_submitted_allowed():
    validate_transition(ReportStatus.DRAFT, ReportStatus.SUBMITTED)  # should not raise


def test_full_happy_path_chain():
    chain = [
        (ReportStatus.DRAFT, ReportStatus.SUBMITTED),
        (ReportStatus.SUBMITTED, ReportStatus.AUDIT_PENDING),
        (ReportStatus.AUDIT_PENDING, ReportStatus.PENDING_APPROVAL),
        (ReportStatus.PENDING_APPROVAL, ReportStatus.APPROVED),
        (ReportStatus.APPROVED, ReportStatus.PROCESSED),
    ]
    for current, target in chain:
        assert can_transition(current, target)


@pytest.mark.parametrize(
    "current,target",
    [
        (ReportStatus.PROCESSED, ReportStatus.DRAFT),
        (ReportStatus.REJECTED, ReportStatus.APPROVED),
        (ReportStatus.APPROVED, ReportStatus.SUBMITTED),
        (ReportStatus.DRAFT, ReportStatus.APPROVED),
    ],
)
def test_invalid_transitions_rejected(current, target):
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransitionError):
        validate_transition(current, target)
