import json

from pawprints_common.errors import error_response


def test_error_response_uses_common_envelope_without_details():
    response = error_response(
        "validation_failed",
        "Some fields are invalid.",
        422,
        "req-123",
    )

    assert response.status_code == 422
    assert json.loads(response.body) == {
        "error": {
            "code": "validation_failed",
            "message": "Some fields are invalid.",
            "request_id": "req-123",
        }
    }


def test_error_response_includes_sanitized_details_when_supplied():
    response = error_response(
        "validation_failed",
        "Some fields are invalid.",
        422,
        "req-123",
        details=[{"field": "title", "reason": "required"}],
    )

    assert json.loads(response.body) == {
        "error": {
            "code": "validation_failed",
            "message": "Some fields are invalid.",
            "request_id": "req-123",
            "details": [{"field": "title", "reason": "required"}],
        }
    }
