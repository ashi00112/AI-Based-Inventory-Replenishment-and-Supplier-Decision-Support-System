import pytest
from app.core.security import hash_password, verify_password


def test_hash_password_does_not_return_original_password():
    """
    Ensure hash_password does not return plain-text password.
    """
    plain = "SuperSecretP@ssw0rd!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert plain not in hashed


def test_valid_password_verifies_successfully():
    """
    Ensure correct password verifies against generated hash.
    """
    password = "CorrectHorseBatteryStaple123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_incorrect_password_fails_verification():
    """
    Ensure wrong password fails verification.
    """
    password = "MyCorrectPassword"
    wrong_password = "WrongPassword123"
    hashed = hash_password(password)
    assert verify_password(wrong_password, hashed) is False


def test_hashing_same_password_twice_produces_different_hashes():
    """
    Ensure distinct salts are generated for successive hashing calls.
    """
    password = "IdenticalPasswordToHash"
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_password_hash_uses_argon2id_algorithm():
    """
    Ensure the generated hash uses the secure Argon2id format.
    """
    password = "AlgorithmicCheckPassword"
    hashed = hash_password(password)
    # Argon2id hashes begin with $argon2id$
    assert hashed.startswith("$argon2id$")


@pytest.mark.parametrize(
    "malformed_hash",
    [
        "not_a_valid_hash",
        "$argon2id$invalid_formatting_structure",
        "",
        "$2b$12$malformed_or_unsupported_prefix",
        "1234567890",
        " ",
    ],
)
def test_malformed_hash_handled_safely(malformed_hash: str):
    """
    Ensure malformed or unrecognized hash values do not raise unhandled exceptions.
    """
    assert verify_password("AnyPassword123", malformed_hash) is False


def test_invalid_types_handled_safely():
    """
    Ensure non-string and empty inputs to verify_password fail gracefully.
    """
    hashed = hash_password("ValidPassword123")
    assert verify_password("", hashed) is False
    assert verify_password(None, hashed) is False  # type: ignore[arg-type]
    assert verify_password("ValidPassword123", None) is False  # type: ignore[arg-type]
