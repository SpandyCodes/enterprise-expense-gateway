import enum


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    AUDITOR = "AUDITOR"
    ADMIN = "ADMIN"
    INTEGRATION_SERVICE = "INTEGRATION_SERVICE"


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUDIT_PENDING = "AUDIT_PENDING"
    EXCEPTION = "EXCEPTION"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Severity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AuditResultStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class IntegrationStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
