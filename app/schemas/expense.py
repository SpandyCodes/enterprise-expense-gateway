import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReportStatus, UserRole


class UserCreate(BaseModel):
    employee_id: str
    name: str
    email: str
    department: str
    manager_id: uuid.UUID | None = None
    role: UserRole = UserRole.EMPLOYEE
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: str
    name: str
    email: str
    department: str
    role: UserRole
    active: bool


class ExpenseReportCreate(BaseModel):
    title: str
    currency: str = "USD"


class ExpenseReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_number: str
    title: str
    currency: str
    status: ReportStatus
    total_amount: Decimal
    created_at: datetime


class ExpenseItemCreate(BaseModel):
    expense_type_id: uuid.UUID
    transaction_date: date
    vendor: str
    amount: Decimal
    currency: str = "USD"
    description: str | None = None
    receipt_reference: str | None = None
    custom_fields: dict = {}
    billable: bool = False
    personal: bool = False


class ExpenseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_id: uuid.UUID
    expense_type_id: uuid.UUID
    transaction_date: date
    vendor: str
    amount: Decimal
    currency: str
    receipt_reference: str | None
    billable: bool
    personal: bool
