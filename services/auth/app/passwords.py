from __future__ import annotations

from pwdlib import PasswordHash


MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128

_password_hash = PasswordHash.recommended()


class PasswordPolicyError(ValueError):
    pass


def validate_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError("password must be at least 6 characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError("password must be at most 128 characters")
    if password.strip() == "":
        raise PasswordPolicyError("password cannot be empty")
    return password


def hash_password(password: str) -> str:
    return _password_hash.hash(validate_password(password))


def verify_password(password: str, encoded_hash: str) -> bool:
    return _password_hash.verify(password, encoded_hash)
