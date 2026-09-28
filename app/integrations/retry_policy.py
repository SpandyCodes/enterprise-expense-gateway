"""
Retry decision logic for transient integration failures.

Transient (retryable): 408, 429, 500, 502, 503, 504
Permanent (never retried): 400, 401, 403, 404 (and anything else not
explicitly listed as transient)

Exponential backoff: base * 2^(attempt-1), i.e. 1s, 2s, 4s for base=1s.
Max 3 retries by default (configurable via settings).
"""
from app.core.config import get_settings

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
PERMANENT_STATUS_CODES = {400, 401, 403, 404}


def is_retryable(status_code: int) -> bool:
    if status_code in PERMANENT_STATUS_CODES:
        return False
    return status_code in RETRYABLE_STATUS_CODES


def backoff_seconds(attempt: int, base_seconds: float | None = None) -> float:
    """attempt is 1-indexed (first retry = attempt 1)."""
    base = base_seconds if base_seconds is not None else get_settings().integration_backoff_base_seconds
    return base * (2 ** (attempt - 1))


def should_retry(status_code: int, attempt: int, max_retries: int | None = None) -> bool:
    limit = max_retries if max_retries is not None else get_settings().integration_max_retries
    return is_retryable(status_code) and attempt <= limit
