import pytest

from app.core.security import hash_password, verify_password
from app.core.tokens import generate_refresh_token, hash_refresh_token


def test_bcrypt_hashes_and_verifies_passwords() -> None:
    password = "a-secure-password"
    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash.startswith("$2b$")
    assert first_hash != password
    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert not verify_password("wrong-password", first_hash)


def test_password_validation_and_invalid_hashes() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("")

    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password("é" * 37)

    assert not verify_password("password", "not-a-bcrypt-hash")
    assert not verify_password("é" * 37, hash_password("valid-password"))


def test_refresh_tokens_are_random_and_hash_deterministically() -> None:
    first_token = generate_refresh_token()
    second_token = generate_refresh_token()

    assert first_token != second_token
    assert len(hash_refresh_token(first_token)) == 64
    assert hash_refresh_token(first_token) == hash_refresh_token(first_token)
    assert hash_refresh_token(first_token) != hash_refresh_token(second_token)
