import bcrypt


BCRYPT_ROUNDS = 12
BCRYPT_MAX_PASSWORD_BYTES = 72


def _encode_password(password: str) -> bytes:
    if not password:
        raise ValueError("Password must not be empty.")

    encoded_password = password.encode("utf-8")

    if len(encoded_password) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must not exceed {BCRYPT_MAX_PASSWORD_BYTES} UTF-8 bytes."
        )

    return encoded_password


def hash_password(password: str) -> str:
    encoded_password = _encode_password(password)
    password_hash = bcrypt.hashpw(
        encoded_password,
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    )

    return password_hash.decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        encoded_password = _encode_password(password)
        encoded_hash = password_hash.encode("ascii")
        return bcrypt.checkpw(encoded_password, encoded_hash)
    except (UnicodeEncodeError, ValueError):
        return False
