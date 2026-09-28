import pytest

from app.integrations.adapter import AdapterValidationError, ExternalExpenseAdapter

pytestmark = pytest.mark.unit

VALID_PAYLOAD = {
    "external_expense_id": "EXT-10001",
    "employee": {"employee_id": "EMP001"},
    "expense_type": "MEALS",
    "vendor": "Example Restaurant",
    "transaction_date": "2026-09-20",
    "amount": 1250.00,
    "currency": "inr",
    "receipt_reference": "receipt-10001",
}


def test_adapt_transforms_external_to_internal():
    internal = ExternalExpenseAdapter.adapt(VALID_PAYLOAD)
    assert internal.employee_id == "EMP001"
    assert internal.expense_type_code == "MEALS"
    assert internal.currency == "INR"  # uppercased by transform
    assert internal.amount == 1250


def test_adapt_rejects_negative_amount():
    bad = {**VALID_PAYLOAD, "amount": -5}
    with pytest.raises(AdapterValidationError):
        ExternalExpenseAdapter.adapt(bad)


def test_adapt_rejects_missing_required_field():
    bad = {k: v for k, v in VALID_PAYLOAD.items() if k != "vendor"}
    with pytest.raises(AdapterValidationError):
        ExternalExpenseAdapter.adapt(bad)
