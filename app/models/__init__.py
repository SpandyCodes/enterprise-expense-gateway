"""Import all models here so Alembic's autogenerate can discover them
via Base.metadata."""
from app.models.approval_audit import Approval, AuditResult, AuditRule  # noqa: F401
from app.models.expense import ExpenseItem, ExpenseReport, ExpenseType  # noqa: F401
from app.models.integration import IdempotencyRecord, IntegrationLog  # noqa: F401
from app.models.user import User  # noqa: F401
