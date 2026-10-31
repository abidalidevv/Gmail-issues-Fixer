"""
VORTEX SUITE — Portable Release Packager & Builder
Excludes pycache, temporary files, logs, and sensitive session tokens while packaging
the complete ready-to-run suite (platform-tools portable ADB, core, static, docs, launcher bats).
"""
import os
import shutil
import zipfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ZIP = os.path.join(SCRIPT_DIR, "VORTEX_SUITE_PORTABLE_LATEST.zip")

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "vault_sessions",
    "tests"
}

EXCLUDE_EXTS = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp"
}

EXCLUDE_FILES = {
    "VORTEX_SUITE_PORTABLE_LATEST.zip",
    "Launch_Suite.zip",
    "VORTEX_PORTABLE_BUILD.zip"
}

def clean_pycache():
    print("[*] Cleaning pycache directories...")
    for root, dirs, files in os.walk(SCRIPT_DIR):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)

def build_zip():
    print("=" * 68)
    print("      [+] BUILDING VORTEX PORTABLE ENTERPRISE ZIP PACKAGE [+]      ")
    print("=" * 68)
    clean_pycache()

    if os.path.exists(OUTPUT_ZIP):
        try:
            os.remove(OUTPUT_ZIP)
        except Exception:
            pass

    print(f"[*] Compressing suite into: {os.path.basename(OUTPUT_ZIP)}...")
    file_count = 0
    total_size = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(SCRIPT_DIR):
            # Prune excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, SCRIPT_DIR)
                zipf.write(full_path, rel_path)
                file_count += 1
                total_size += os.path.getsize(full_path)

    zip_size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    raw_size_mb = total_size / (1024 * 1024)

    print("-" * 68)
    print(f"[SUCCESS] Packaged {file_count} files successfully!")
    print(f"  Uncompressed Size : {raw_size_mb:.2f} MB")
    print(f"  Compressed Size   : {zip_size_mb:.2f} MB")
    print(f"  Output Archive    : {OUTPUT_ZIP}")
    print("=" * 68)

if __name__ == "__main__":
    build_zip()
