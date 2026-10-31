"""
VORTEX SUITE — ixBrowser Diagnostic & Profile Mapper
Tests connectivity to ixBrowser Local API v2 on http://127.0.0.1:53200
Fetches all profiles and allows mapping ixBrowser profiles to accounts in vault.db.
"""
import sys
import os
import json

from core import ixbrowser, database

def main():
    print("=" * 65)
    print("   VORTEX SUITE — ixBrowser Local API Diagnostic & Discovery   ")
    print("=" * 65)

    is_online, status_msg = ixbrowser.check_api_status()
    print(f"\n[1] API Status: {status_msg}")

    if not is_online:
        print("\n[!] ixBrowser is currently not responding on port 53200.")
        print("    Instructions:")
        print("    1. Launch the ixBrowser desktop application on your PC.")
        print("    2. Go to Settings > Advanced > Developer Tools.")
        print("    3. Ensure 'Local API' is enabled (Port: 53200).")
        print("    4. Re-run this script to verify connection.")
        return

    print("\n[2] Querying ixBrowser Profiles (API v2)...")
    profiles = ixbrowser.get_all_profiles(page=1, limit=500)
    print(f"    Total Profiles Discovered: {len(profiles)}")

    if not profiles:
        print("    No profiles found in ixBrowser.")
        return

    print("\n[3] Profile Roster Preview:")
    print("-" * 65)
    matched = 0
    accounts = database.get_all_accounts()
    account_emails = {a["email"].lower(): a for a in accounts}

    for p in profiles[:25]: # Show first 25
        pid = p.get("profile_id") or p.get("id")
        pname = p.get("name") or p.get("remark") or p.get("username") or "Unnamed"
        
        # Check if email is inside profile name
        matched_email = None
        for em in account_emails:
            if em in pname.lower() or em.split("@")[0] in pname.lower():
                matched_email = em
                break
        
        if matched_email:
            matched += 1
            database.update_account(matched_email, ixbrowser_profile_id=str(pid))
            print(f"  ✓ Profile ID {pid:4d} | Name: {pname:<30} -> Linked to: {matched_email}")
        else:
            print(f"  • Profile ID {pid:4d} | Name: {pname:<30}")

    if len(profiles) > 25:
        print(f"  ... and {len(profiles) - 25} more profiles.")

    print("-" * 65)
    print(f"\n[4] Database Sync Complete: {matched} accounts mapped to ixBrowser profiles.")
    print("    ixBrowser engine is ready for automated recovery!")

if __name__ == "__main__":
    main()
