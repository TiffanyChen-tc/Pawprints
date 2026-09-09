import hmac

import pytest

from pawprints_common.internal_auth import InternalAuthError, verify_internal_request


def test_verify_internal_request_uses_constant_time_comparison(monkeypatch):
    called = False

    def fake_compare(left: str, right: str) -> bool:
        nonlocal called
        called = True
        return left == right

    monkeypatch.setattr(hmac, "compare_digest", fake_compare)

    caller = verify_internal_request(
        "media-service",
        "token-a",
        {"media-service"},
        {"media-service": "token-a"},
    )

    assert caller.service_name == "media-service"
    assert called is True


def test_verify_internal_request_rejects_disallowed_endpoint_caller():
    with pytest.raises(InternalAuthError):
        verify_internal_request(
            "auth-service",
            "token-a",
            {"media-service"},
            {"auth-service": "token-a"},
        )


def test_verify_internal_request_rejects_wrong_token():
    with pytest.raises(InternalAuthError):
        verify_internal_request(
            "media-service",
            "wrong-token",
            {"media-service"},
            {"media-service": "token-a"},
        )
