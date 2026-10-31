import base64
import urllib.parse
import sys
import os
import csv
import io
from typing import List, Dict
from core import database, device

# ==============================================================================
# Google Authenticator Bulk QR Code Decoder (Protobuf Engine)
# Decodes otpauth-migration:// Protobuf payloads and imports all accounts into Vault
# Supports:
# 1. Folder of screenshots (qr_images/)
# 2. Direct ADB Screen Capture from live USB connected phone
# 3. Direct raw otpauth-migration URI string
# ==============================================================================

def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    res = 0
    shift = 0
    while True:
        if offset >= len(data):
            break
        b = data[offset]
        offset += 1
        res |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return res, offset

def parse_otp_parameters(data: bytes) -> dict:
    offset = 0
    param = {}
    while offset < len(data):
        tag_wire, offset = read_varint(data, offset)
        tag = tag_wire >> 3
        wire = tag_wire & 0x07

        if wire == 2:  # length-delimited
            length, offset = read_varint(data, offset)
            val = data[offset:offset + length]
            offset += length
            if tag == 1:  # secret
                param['secret_base32'] = base64.b32encode(val).decode('utf-8').replace("=", "")
            elif tag == 2:  # name / email
                param['name'] = val.decode('utf-8', errors='ignore')
            elif tag == 3:  # issuer
                param['issuer'] = val.decode('utf-8', errors='ignore')
        elif wire == 0:  # varint
            val, offset = read_varint(data, offset)
            if tag == 5:  # digits
                param['digits'] = val
        elif wire == 1:  # 64-bit
            offset += 8
        elif wire == 5:  # 32-bit
            offset += 4
        else:
            break
    return param

def decode_migration_payload(raw_uri_or_b64: str) -> list[dict]:
    # Extract data param if full URI given
    if "data=" in raw_uri_or_b64:
        query = urllib.parse.urlparse(raw_uri_or_b64).query
        params = urllib.parse.parse_qs(query)
        data_b64 = params.get('data', [''])[0]
    else:
        data_b64 = raw_uri_or_b64.strip()

    # URL-safe base64 unpad & decode
    data_b64 += '=' * ((4 - len(data_b64) % 4) % 4)
    data = base64.urlsafe_b64decode(data_b64)

    offset = 0
    extracted_accounts = []
    while offset < len(data):
        tag_wire, offset = read_varint(data, offset)
        tag = tag_wire >> 3
        wire = tag_wire & 0x07

        if wire == 2:
            length, offset = read_varint(data, offset)
            sub_data = data[offset:offset + length]
            offset += length
            if tag == 1:  # OtpParameters message
                otp_info = parse_otp_parameters(sub_data)
                if 'secret_base32' in otp_info and 'name' in otp_info:
                    extracted_accounts.append(otp_info)
        elif wire == 0:
            _, offset = read_varint(data, offset)
        elif wire == 1:
            offset += 8
        elif wire == 5:
            offset += 4
        else:
            break

    return extracted_accounts

def scan_images_for_qr(folder_or_file: str) -> List[tuple]:
    """Scan image files using zxingcpp to extract otpauth-migration URIs."""
    import zxingcpp
    from PIL import Image

    uris = []
    targets = []
    if os.path.isfile(folder_or_file):
        targets.append(folder_or_file)
    elif os.path.isdir(folder_or_file):
        for fname in os.listdir(folder_or_file):
            if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                targets.append(os.path.join(folder_or_file, fname))

    for img_path in targets:
        try:
            img = Image.open(img_path)
            results = zxingcpp.read_barcodes(img)
            for r in results:
                if r.text and "otpauth-migration" in r.text:
                    uris.append((os.path.basename(img_path), r.text))
        except Exception as e:
            print(f"  [!] Could not read image {img_path}: {e}")
    return uris

def capture_qr_from_phone() -> List[str]:
    """Capture current phone screen via ADB and decode QR code without manual saving."""
    try:
        import zxingcpp
        from PIL import Image

        png = device.capture_screenshot()
        if not png:
            return []
        img = Image.open(io.BytesIO(png))
        results = zxingcpp.read_barcodes(img)
        return [r.text for r in results if r.text and "otpauth-migration" in r.text]
    except Exception as e:
        print(f"ADB screen QR decode error: {e}")
        return []

def main():
    print("=" * 68)
    print("   ⚡ Google Authenticator Bulk QR Export Decoder (Protobuf) ⚡   ")
    print("=" * 68)

    qr_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_images")
    os.makedirs(qr_folder, exist_ok=True)

    extracted_payloads = []

    # Check 1: Did user pass path via argument?
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        print(f"\n[+] Scanning images in: {sys.argv[1]}...")
        scanned = scan_images_for_qr(sys.argv[1])
        for src, uri in scanned:
            print(f"  ✓ Found QR Code in: {src}")
            extracted_payloads.append(uri)

    # Check 2: Are there images inside qr_images/ folder?
    if not extracted_payloads and os.path.exists(qr_folder):
        img_files = [f for f in os.listdir(qr_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if img_files:
            print(f"\n[+] Found {len(img_files)} screenshots in qr_images/ folder! Scanning...")
            scanned = scan_images_for_qr(qr_folder)
            for src, uri in scanned:
                print(f"  ✓ Found QR Code in: {src}")
                extracted_payloads.append(uri)

    # Check 3: Check connected phone screen via ADB
    if not extracted_payloads:
        connected = device.get_connected_device()
        if connected:
            print(f"\n[+] Connected Phone Detected: {connected['name']}")
            print("    Checking if Google Authenticator Export QR is visible on phone screen...")
            from_phone = capture_qr_from_phone()
            if from_phone:
                print("  ✓ Found QR Code directly from live phone screen!")
                extracted_payloads.extend(from_phone)

    # Check 4: Interactive prompt if nothing auto-detected
    if not extracted_payloads:
        print("\nOptions to decode:")
        print(f"  A) Save all your QR screenshots into: {qr_folder}")
        print("  B) Open Authenticator Export on USB-connected phone and re-run this script")
        print("  C) Or paste an otpauth-migration:// text directly below:\n")
        user_input = input("Paste Export Data (or press Enter if screenshots are in qr_images): ").strip()
        if user_input:
            extracted_payloads.append(user_input)
        elif os.path.exists(qr_folder):
            scanned = scan_images_for_qr(qr_folder)
            for src, uri in scanned:
                print(f"  ✓ Found QR in: {src}")
                extracted_payloads.append(uri)

    if not extracted_payloads:
        print("[!] No QR code data found. Place screenshots in qr_images/ or open export on phone.")
        return

    # Process all payloads
    all_accounts = []
    for payload in extracted_payloads:
        try:
            accs = decode_migration_payload(payload)
            all_accounts.extend(accs)
        except Exception as e:
            print(f"[!] Error decoding payload: {e}")

    print(f"\n[+] SUCCESS! Successfully extracted total {len(all_accounts)} accounts:")
    print("-" * 68)

    # Save to CSV and Database
    csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authenticator_extracted.csv")
    database.init_db()

    cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    default_pwd = "Abidali@2xx"
    if os.path.exists(cfg_file):
        try:
            import json
            with open(cfg_file, "r", encoding="utf-8") as cf:
                cfg_data = json.load(cf)
                if cfg_data.get("passwords_waterfall"):
                    default_pwd = cfg_data["passwords_waterfall"][0]
        except Exception:
            pass

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Email / Name", "Issuer", "Base32 Secret Key"])

        for acc in all_accounts:
            name = acc.get('name', 'Unknown')
            issuer = acc.get('issuer', 'Google')
            secret = acc.get('secret_base32', '')
            writer.writerow([name, issuer, secret])
            print(f"  • {name} | Secret: {secret}")

            clean_email = name.replace("Google:", "").strip()
            database.add_account(clean_email, default_pwd, secret, f"Imported via Authenticator Export ({issuer})")

    print("-" * 68)
    print(f"[+] All {len(all_accounts)} accounts saved to: {csv_file}")
    print(f"[+] All accounts imported directly into Vortex Vault Database!")

if __name__ == "__main__":
    main()
