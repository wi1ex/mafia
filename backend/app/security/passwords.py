from __future__ import annotations
import base64
import hashlib
import hmac
import secrets
from typing import Tuple

PBKDF2_ALGO = "sha256"
PBKDF2_ITER = 200_000
SALT_BYTES = 16
KEY_BYTES = 32


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(raw: str) -> bytes:
    return base64.b64decode(raw.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, PBKDF2_ITER, dklen=KEY_BYTES)
    return f"pbkdf2_{PBKDF2_ALGO}${PBKDF2_ITER}${_b64e(salt)}${_b64e(dk)}"


def _parse_hash(encoded: str) -> Tuple[str, int, bytes, bytes] | None:
    parts = (encoded or "").split("$")
    if len(parts) != 4:
        return None

    algo = parts[0].replace("pbkdf2_", "")
    try:
        iters = int(parts[1])
        salt = _b64d(parts[2])
        ref = _b64d(parts[3])
    except Exception:
        return None

    if not algo or iters <= 0 or not salt or not ref:
        return None

    return algo, iters, salt, ref


def verify_password(password: str, encoded: str) -> bool:
    parsed = _parse_hash(encoded)
    if not parsed:
        return False

    algo, iters, salt, ref = parsed
    try:
        dk = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, iters, dklen=len(ref))
    except Exception:
        return False

    return hmac.compare_digest(dk, ref)


def make_temp_password(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    length = max(8, min(32, int(length)))
    return "".join(secrets.choice(alphabet) for _ in range(length))
