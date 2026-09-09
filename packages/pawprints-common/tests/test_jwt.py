from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pawprints_common.jwt import JWTValidationError, verify_access_token


@pytest.fixture()
def rsa_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


def make_token(private_key_pem: str, **overrides: object) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "iss": "pawprints-auth",
        "aud": "pawprints-api",
        "exp": now + timedelta(minutes=15),
        "iat": now,
    }
    payload.update(overrides)
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def test_verify_access_token_accepts_rs256_with_expected_issuer_audience(rsa_key_pair):
    private_key_pem, public_key_pem = rsa_key_pair
    user_id = uuid4()
    token = make_token(private_key_pem, sub=str(user_id))

    claims = verify_access_token(token, public_key_pem, "pawprints-auth", "pawprints-api")

    assert claims.user_id == user_id


def test_verify_access_token_rejects_wrong_audience(rsa_key_pair):
    private_key_pem, public_key_pem = rsa_key_pair
    token = make_token(private_key_pem, aud="other-api")

    with pytest.raises(JWTValidationError):
        verify_access_token(token, public_key_pem, "pawprints-auth", "pawprints-api")


def test_verify_access_token_rejects_expired_token(rsa_key_pair):
    private_key_pem, public_key_pem = rsa_key_pair
    token = make_token(private_key_pem, exp=datetime.now(timezone.utc) - timedelta(seconds=1))

    with pytest.raises(JWTValidationError):
        verify_access_token(token, public_key_pem, "pawprints-auth", "pawprints-api")


def test_verify_access_token_rejects_non_uuid_subject(rsa_key_pair):
    private_key_pem, public_key_pem = rsa_key_pair
    token = make_token(private_key_pem, sub="not-a-uuid")

    with pytest.raises(JWTValidationError):
        verify_access_token(token, public_key_pem, "pawprints-auth", "pawprints-api")
