import pytest

from app.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password,
    verify_password,
)


def test_password_hash_verifies_and_is_not_plaintext():
    encoded = hash_password("correct horse battery")

    assert encoded != "correct horse battery"
    assert verify_password("correct horse battery", encoded) is True


def test_same_password_hashes_differ_due_to_random_salt():
    assert hash_password("correct horse battery") != hash_password("correct horse battery")


@pytest.mark.parametrize("password", ["", "   ", "short"])
def test_invalid_password_policy(password):
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_password_policy_allows_spaces_without_trimming():
    password = "  twelve chars  "

    assert validate_password(password) == password


def test_password_policy_rejects_more_than_128_characters():
    with pytest.raises(PasswordPolicyError):
        validate_password("a" * 129)
