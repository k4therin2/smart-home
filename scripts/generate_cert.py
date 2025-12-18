#!/usr/bin/env python3
"""
Generate self-signed SSL certificate for Smart Home Assistant.

Usage:
    python scripts/generate_cert.py [--force] [--cn COMMON_NAME]

This script generates a self-signed certificate for local HTTPS use.
The certificate will be valid for 365 days and include SANs for
localhost, local network IPs, and the specified common name.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security.ssl_config import (
    generate_self_signed_cert,
    check_cert_expiry,
    certificates_exist,
    CERT_FILE,
    KEY_FILE,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate self-signed SSL certificate for Smart Home Assistant"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing certificate"
    )
    parser.add_argument(
        "--cn", "--common-name",
        default="smarthome.local",
        help="Certificate Common Name (default: smarthome.local)"
    )
    parser.add_argument(
        "--org", "--organization",
        default="Smart Home Assistant",
        help="Certificate Organization"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Certificate validity in days (default: 365)"
    )

    args = parser.parse_args()

    if certificates_exist() and not args.force:
        expiry = check_cert_expiry()
        print(f"Certificate already exists at: {CERT_FILE}")
        if expiry:
            print(f"Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nUse --force to regenerate.")
        return 0

    print("Generating self-signed SSL certificate...")
    print(f"  Common Name: {args.cn}")
    print(f"  Organization: {args.org}")
    print(f"  Validity: {args.days} days")

    try:
        cert_path, key_path = generate_self_signed_cert(
            common_name=args.cn,
            organization=args.org,
            validity_days=args.days,
            force=args.force
        )

        expiry = check_cert_expiry()

        print("\nCertificate generated successfully!")
        print(f"  Certificate: {cert_path}")
        print(f"  Private Key: {key_path}")
        if expiry:
            print(f"  Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n--- IMPORTANT ---")
        print("This is a self-signed certificate. Browsers will show a security warning.")
        print("To bypass the warning:")
        print("  1. Chrome: Click 'Advanced' -> 'Proceed to localhost (unsafe)'")
        print("  2. Firefox: Click 'Advanced' -> 'Accept the Risk and Continue'")
        print("  3. Safari: Click 'Show Details' -> 'visit this website'")
        print("")
        print("For production use, consider using Let's Encrypt or a proper CA certificate.")

        return 0

    except Exception as error:
        print(f"Error generating certificate: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
