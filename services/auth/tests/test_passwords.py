import pytest

from app.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password,
    verify_password,
)


def test_password_hash_verifies_and_is_not_plaintext():
    encoded = hash_password("demo123")

    assert encoded != "demo123"
    assert verify_password("demo123", encoded) is True


def test_same_password_hashes_differ_due_to_random_salt():
    assert hash_password("demo123") != hash_password("demo123")


@pytest.mark.parametrize("password", ["", "   ", "short"])
def test_invalid_password_policy(password):
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_password_policy_accepts_six_characters():
    assert validate_password("demo12") == "demo12"


def test_password_policy_accepts_longer_normal_passwords():
    assert validate_password("correct horse battery") == "correct horse battery"


def test_password_policy_allows_spaces_without_trimming():
    password = " demo1 "

    assert validate_password(password) == password


def test_password_policy_rejects_more_than_128_characters():
    with pytest.raises(PasswordPolicyError):
        validate_password("a" * 129)
