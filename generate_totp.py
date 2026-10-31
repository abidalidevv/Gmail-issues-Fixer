import base64
import hashlib
import hmac
import struct
import time
import sys

def get_totp(secret: str, interval: int = 30) -> str:
    """Generate 6-digit TOTP code from Base32 secret without any third-party dependencies."""
    cleaned_secret = secret.replace(" ", "").replace("-", "").replace("=", "").strip().upper()
    # Add padding if missing
    missing_padding = len(cleaned_secret) % 8
    if missing_padding:
        cleaned_secret += '=' * (8 - missing_padding)
    
    key = base64.b32decode(cleaned_secret, casefold=True)
    counter = int(time.time() // interval)
    msg = struct.pack(">Q", counter)
    
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[19] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    
    # Calculate seconds remaining
    remaining = interval - (int(time.time()) % interval)
    return f"{code:06d}", remaining

if __name__ == "__main__":
    print("=" * 55)
    print("   Live 2FA / Google Authenticator Code Generator   ")
    print("=" * 55)
    
    if len(sys.argv) > 1:
        secret_input = sys.argv[1]
    else:
        secret_input = input("\nEnter account Base32 2FA Secret Key: ").strip()
        
    if not secret_input:
        print("[!] Secret key cannot be empty.")
        sys.exit(1)
        
    try:
        code, secs_left = get_totp(secret_input)
        print(f"\n[+] Current 6-digit Code : {code}")
        print(f"[+] Valid for next      : {secs_left} seconds\n")
    except Exception as e:
        print(f"[!] Error decoding secret: {e}")
        print("Tip: Ensure your secret contains only Base32 characters (A-Z, 2-7).")
