"""
Smart Home Assistant - SSL/TLS Configuration

Provides HTTPS support with self-signed certificates for local network use.
Phase 2.2: HTTPS/TLS Configuration
"""

import os
import ssl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from src.config import DATA_DIR

# Certificate storage directory
SSL_DIR = DATA_DIR / "ssl"
SSL_DIR.mkdir(parents=True, exist_ok=True)

# Certificate file paths
CERT_FILE = SSL_DIR / "server.crt"
KEY_FILE = SSL_DIR / "server.key"

# Certificate validity period (days)
CERT_VALIDITY_DAYS = 365

# Certificate subject details
CERT_COMMON_NAME = os.getenv("SSL_COMMON_NAME", "smarthome.local")
CERT_ORGANIZATION = os.getenv("SSL_ORGANIZATION", "Smart Home Assistant")


def generate_self_signed_cert(
    common_name: Optional[str] = None,
    organization: Optional[str] = None,
    validity_days: int = CERT_VALIDITY_DAYS,
    force: bool = False
) -> Tuple[Path, Path]:
    """
    Generate a self-signed SSL certificate for local HTTPS.

    Args:
        common_name: Certificate CN (defaults to smarthome.local)
        organization: Certificate organization
        validity_days: Certificate validity in days
        force: Overwrite existing certificate

    Returns:
        Tuple of (certificate_path, key_path)
    """
    from OpenSSL import crypto

    if not force and CERT_FILE.exists() and KEY_FILE.exists():
        return CERT_FILE, KEY_FILE

    common_name = common_name or CERT_COMMON_NAME
    organization = organization or CERT_ORGANIZATION

    # Generate key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # Create self-signed certificate
    cert = crypto.X509()

    # Set subject
    subject = cert.get_subject()
    subject.C = "US"
    subject.ST = "Home"
    subject.L = "Local"
    subject.O = organization
    subject.OU = "Self-Signed"
    subject.CN = common_name

    # Set certificate details
    cert.set_serial_number(int(datetime.now().timestamp()))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validity_days * 24 * 60 * 60)
    cert.set_issuer(subject)
    cert.set_pubkey(key)

    # Add Subject Alternative Names for local network access
    san_list = [
        f"DNS:{common_name}",
        "DNS:localhost",
        "DNS:*.local",
        "IP:127.0.0.1",
        "IP:0.0.0.0",
    ]

    # Add local network IPs (common ranges)
    # This allows accessing via local IP without certificate warnings
    for ip_prefix in ["192.168.1.", "192.168.0.", "10.0.0."]:
        for last_octet in range(1, 255):
            san_list.append(f"IP:{ip_prefix}{last_octet}")

    # Limit SANs to avoid certificate size issues
    san_extension = crypto.X509Extension(
        b"subjectAltName",
        False,
        ", ".join(san_list[:100]).encode()  # Limit to first 100 SANs
    )
    cert.add_extensions([san_extension])

    # Sign the certificate
    cert.sign(key, "sha256")

    # Write certificate and key
    with open(CERT_FILE, "wb") as cert_f:
        cert_f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open(KEY_FILE, "wb") as key_f:
        key_f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    # Set restrictive permissions on key file
    os.chmod(KEY_FILE, 0o600)
    os.chmod(CERT_FILE, 0o644)

    return CERT_FILE, KEY_FILE


def get_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Get SSL context for Flask if certificates exist.

    Returns:
        SSLContext if certificates exist, None otherwise
    """
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(CERT_FILE), str(KEY_FILE))

    # Modern TLS settings
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers('ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20')

    return context


def check_cert_expiry() -> Optional[datetime]:
    """
    Check when the current certificate expires.

    Returns:
        Expiry datetime if certificate exists, None otherwise
    """
    if not CERT_FILE.exists():
        return None

    from OpenSSL import crypto

    with open(CERT_FILE, "rb") as cert_f:
        cert_data = cert_f.read()

    cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
    expiry_str = cert.get_notAfter()

    if expiry_str:
        return datetime.strptime(expiry_str.decode('ascii'), '%Y%m%d%H%M%SZ')

    return None


def cert_needs_renewal(days_before_expiry: int = 30) -> bool:
    """
    Check if certificate needs renewal.

    Args:
        days_before_expiry: Renew if expiring within this many days

    Returns:
        True if certificate needs renewal or doesn't exist
    """
    expiry = check_cert_expiry()

    if expiry is None:
        return True

    renewal_threshold = datetime.now() + timedelta(days=days_before_expiry)
    return expiry < renewal_threshold


def certificates_exist() -> bool:
    """Check if SSL certificates exist."""
    return CERT_FILE.exists() and KEY_FILE.exists()
