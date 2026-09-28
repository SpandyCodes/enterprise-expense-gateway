"""
ExternalExpenseAdapter: transforms an external (Concur-inspired) expense
payload into the internal ExpenseItem representation. This demonstrates
middleware-style data transformation, decoupled from routing/persistence.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class ExternalEmployee(BaseModel):
    employee_id: str


class ExternalExpensePayload(BaseModel):
    external_expense_id: str
    employee: ExternalEmployee
    expense_type: str
    vendor: str
    transaction_date: date
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    receipt_reference: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class InternalExpenseModel(BaseModel):
    external_expense_id: str
    employee_id: str
    expense_type_code: str
    vendor: str
    transaction_date: date
    amount: Decimal
    currency: str
    receipt_reference: str | None


class AdapterValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__(f"Payload failed validation: {errors}")


class ExternalExpenseAdapter:
    """Adapter: ExternalExpensePayload -> InternalExpenseModel."""

    @staticmethod
    def parse_external(raw: dict[str, Any]) -> ExternalExpensePayload:
        try:
            return ExternalExpensePayload.model_validate(raw)
        except ValidationError as exc:
            raise AdapterValidationError(exc.errors()) from exc

    @staticmethod
    def transform(external: ExternalExpensePayload) -> InternalExpenseModel:
        return InternalExpenseModel(
            external_expense_id=external.external_expense_id,
            employee_id=external.employee.employee_id,
            expense_type_code=external.expense_type,
            vendor=external.vendor,
            transaction_date=external.transaction_date,
            amount=external.amount,
            currency=external.currency.upper(),
            receipt_reference=external.receipt_reference,
        )

    @classmethod
    def adapt(cls, raw: dict[str, Any]) -> InternalExpenseModel:
        external = cls.parse_external(raw)
        return cls.transform(external)
