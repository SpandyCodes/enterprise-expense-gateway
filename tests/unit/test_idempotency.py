import pytest

from app.integrations.idempotency import hash_request

pytestmark = pytest.mark.unit


def test_hash_is_deterministic_for_same_body():
    body = {"a": 1, "b": {"c": 2}}
    assert hash_request(body) == hash_request(body)


def test_hash_is_order_independent():
    body_a = {"a": 1, "b": 2}
    body_b = {"b": 2, "a": 1}
    assert hash_request(body_a) == hash_request(body_b)


def test_hash_differs_for_different_bodies():
    assert hash_request({"a": 1}) != hash_request({"a": 2})
