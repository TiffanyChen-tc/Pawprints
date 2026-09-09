from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_cookie_secure_is_required_in_production():
    with pytest.raises(ValidationError):
        Settings(
            AUTH_DATABASE_URL="postgresql+psycopg://example",
            ENVIRONMENT="production",
            JWT_PRIVATE_KEY_PATH="jwt-private.pem",
            COOKIE_SECURE=False,
        )
