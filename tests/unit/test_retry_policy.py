import pytest

from app.integrations.retry_policy import backoff_seconds, is_retryable, should_retry

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_transient_codes_are_retryable(code):
    assert is_retryable(code)


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_codes_are_not_retryable(code):
    assert not is_retryable(code)


def test_backoff_is_exponential():
    assert backoff_seconds(1, base_seconds=1) == 1
    assert backoff_seconds(2, base_seconds=1) == 2
    assert backoff_seconds(3, base_seconds=1) == 4


def test_should_retry_respects_max_retries():
    assert should_retry(503, attempt=1, max_retries=3)
    assert should_retry(503, attempt=3, max_retries=3)
    assert not should_retry(503, attempt=4, max_retries=3)


def test_should_retry_false_for_permanent_error_regardless_of_attempt():
    assert not should_retry(404, attempt=1, max_retries=3)
