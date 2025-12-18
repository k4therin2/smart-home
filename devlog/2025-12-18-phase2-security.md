# Phase 2.1 & 2.2 Security Implementation

**Date:** 2025-12-18
**Agent:** Agent-Security-Phase2
**Status:** Complete

---

## Summary

Implemented application security baseline (Phase 2.1) and HTTPS/TLS configuration (Phase 2.2) for the Smart Home Assistant web interface.

---

## Phase 2.1: Application Security Baseline

### Features Implemented

#### 1. Session-Based Authentication
- **Module:** `src/security/auth.py`
- **Password hashing:** Argon2id (memory-hard, timing-safe)
- **Session management:** Flask-Login with secure session cookies
- **Login attempt logging:** Tracks failed attempts by IP for security monitoring
- **Rate limiting on login:** 5 failed attempts in 15 minutes triggers lockout
- **Initial setup flow:** First-time users create an admin account

**Templates:**
- `templates/auth/login.html` - Login form
- `templates/auth/setup.html` - Initial account creation

#### 2. CSRF Protection
- **Library:** Flask-WTF CSRFProtect
- **Token expiry:** 1 hour
- **Coverage:** All form submissions require CSRF tokens
- **API endpoint:** `/api/csrf-token` for programmatic access

#### 3. Input Validation (Pydantic)
- **Schema:** `CommandRequest` validates `/api/command` input
- **Constraints:** 1-1000 character command length
- **Error handling:** Returns 400 with validation error message

#### 4. Rate Limiting
- **Library:** Flask-Limiter
- **Limits:**
  - `/api/command`: 10 requests/minute per IP
  - `/api/status`: 30 requests/minute per IP
  - `/api/history`: 30 requests/minute per IP
  - Global: 200 requests/day, 50 requests/hour per IP

#### 5. Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: default-src 'self'; ...`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (when HTTPS)

#### 6. SQL Injection Prevention
- **Status:** Verified - all queries use parameterized queries (`?` placeholders)
- **Locations reviewed:**
  - `src/utils.py` - API usage tracking
  - `src/server.py` - Command history
  - `src/security/auth.py` - User authentication

---

## Phase 2.2: HTTPS/TLS Configuration

### Features Implemented

#### 1. Self-Signed Certificate Generation
- **Script:** `scripts/generate_cert.py`
- **Storage:** `data/ssl/server.crt` and `data/ssl/server.key`
- **Validity:** 365 days
- **SANs included:** localhost, *.local, 127.0.0.1, common local network IPs

**Usage:**
```bash
# Generate certificate
python scripts/generate_cert.py

# Force regenerate
python scripts/generate_cert.py --force

# Custom common name
python scripts/generate_cert.py --cn myhome.local
```

#### 2. HTTPS Server Configuration
- **TLS version:** TLS 1.2+ only
- **Cipher suites:** ECDHE+AESGCM, DHE+AESGCM, ECDHE+CHACHA20, DHE+CHACHA20
- **Session cookies:** `Secure` flag when FLASK_ENV=production

#### 3. HTTP to HTTPS Redirect
- Runs on port-1 (e.g., 5049 when HTTPS on 5050)
- Returns 301 Permanent Redirect
- Automatically started when HTTPS enabled

#### 4. HSTS Header
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Only sent over HTTPS connections or in production mode
- 1-year max-age enforces HTTPS for return visits

---

## Configuration

### Environment Variables

```bash
# Required for persistent sessions
FLASK_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">

# Set to 'production' for secure cookies
FLASK_ENV=development

# HTTPS settings
USE_HTTPS=true           # Enable HTTPS (falls back to HTTP if no certs)
HTTP_REDIRECT=true       # Enable HTTP->HTTPS redirect
SSL_COMMON_NAME=smarthome.local
SSL_ORGANIZATION=Smart Home Assistant
```

### Quick Start

```bash
# 1. Generate SSL certificate
python scripts/generate_cert.py

# 2. Set a secret key in .env
echo "FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env

# 3. Start server with HTTPS
python -m src.server

# 4. Access: https://localhost:5050
# (First visit: create admin account at /auth/setup)
```

---

## Security Checklist

### Phase 2.1 Checklist
- [x] Basic authentication for web UI (session-based)
- [x] CSRF protection for all POST endpoints
- [x] Pydantic schema validation on API inputs
- [x] Rate limiting on `/api/command` (10 req/min per IP)
- [x] Review all SQL queries for parameterization

### Phase 2.2 Checklist
- [x] Generate self-signed certificate for local network use
- [x] Configure Flask to use HTTPS
- [x] Add HTTP→HTTPS redirect
- [x] Configure HSTS header (max-age=31536000)
- [x] Document certificate generation process

---

## Files Changed

### New Files
- `src/security/auth.py` - Authentication module
- `src/security/ssl_config.py` - SSL/TLS configuration
- `scripts/generate_cert.py` - Certificate generation script
- `templates/auth/login.html` - Login page
- `templates/auth/setup.html` - Initial setup page

### Modified Files
- `src/server.py` - Added authentication, CSRF, rate limiting, HTTPS
- `requirements.txt` - Added security dependencies
- `.env.example` - Added security configuration variables

---

## Dependencies Added

```
flask-login>=0.6.3      # Session authentication
flask-wtf>=1.2.1        # CSRF protection
flask-limiter>=3.5.0    # Rate limiting
pydantic>=2.5.0         # Input validation
argon2-cffi>=23.1.0     # Password hashing
pyOpenSSL>=24.0.0       # SSL certificate generation
```

---

## Known Limitations

1. **Self-signed certificates** cause browser warnings - acceptable for local network use
2. **Single user** - no multi-user support yet (Phase 7 REQ-008)
3. **In-memory rate limiting** - resets on server restart
4. **No password recovery** - users must reset auth.db if password forgotten

---

## Future Improvements (Deferred)

- [ ] Let's Encrypt integration for valid certificates
- [ ] Multi-user support with roles (owner/resident/guest)
- [ ] MFA/TOTP for additional security
- [ ] OAuth2 integration for external authentication
- [ ] Redis-backed rate limiting for persistence
