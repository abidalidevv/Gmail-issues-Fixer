import base64
import hashlib
import hmac
import struct
import time

def generate_totp(secret: str, interval: int = 30) -> tuple[str, int]:
    """
    RFC 6238 Standard TOTP Generator.
    Returns (code_str, seconds_remaining).
    Zero external dependencies.
    """
    if not secret:
        return "------", 0
    cleaned = secret.replace(" ", "").strip().upper()
    missing_padding = len(cleaned) % 8
    if missing_padding:
        cleaned += '=' * (8 - missing_padding)
    try:
        key = base64.b32decode(cleaned, casefold=True)
    except Exception:
        return "ERR32", 0

    counter = int(time.time() // interval)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[19] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    remaining = interval - (int(time.time()) % interval)
    return f"{code:06d}", remaining
