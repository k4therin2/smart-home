# Security Backlog Analysis
**Date:** 2025-12-18
**Analyst:** Agent-Security-Reviewer
**Scope:** Review planned security requirements and identify gaps

---

## Executive Summary

The project has **one formal security requirement (REQ-007)** planned for Phase 7 (deferred indefinitely), but lacks comprehensive security coverage across application and infrastructure layers. The existing security audit (2025-12-17) identified **10 infrastructure issues** (4 critical/high), but no formal application security requirements exist.

**Key Finding:** Security is treated as a single, deferred feature rather than a cross-cutting concern integrated throughout the development lifecycle.

**Risk Level:** HIGH - Production deployment without authentication, HTTPS, input validation, or security headers creates significant attack surface.

---

## Planned Security Requirements (From Backlog)

### REQ-007: Secure Remote Access
- **Status:** NOT_STARTED
- **Priority:** HIGH (but deferred to Phase 7)
- **Phase:** 7+ (Post-launch)
- **Dependencies:** REQ-001, REQ-015
- **Acceptance Criteria:**
  - [ ] HTTPS enabled for web UI
  - [ ] Authentication required for access
  - [ ] VPN or secure tunnel for remote access
  - [ ] Failed login attempt monitoring
  - [ ] Session timeout after inactivity
  - [ ] Security audit completed and documented

**Analysis:**
- **Good:** Covers remote access security fundamentals (HTTPS, auth, VPN)
- **Gap:** Doesn't address local network security (anyone on LAN has full access currently)
- **Gap:** No specifics on authentication method (basic auth? session tokens? OAuth?)
- **Gap:** No password policy, MFA, or account lockout requirements
- **Timing Issue:** Deferred to Phase 7 means web UI launches without authentication in Phase 3

### REQ-008: Multi-User Support
- **Status:** NOT_STARTED
- **Priority:** MEDIUM (deferred to Phase 7)
- **Dependencies:** REQ-007, REQ-015
- **Acceptance Criteria:**
  - [ ] Guest mode with basic controls
  - [ ] User profiles (owner, resident, guest)
  - [ ] Per-user preferences and history
  - [ ] Simple guest access via password-protected URL
  - [ ] Guest sessions expire after configurable time

**Analysis:**
- Builds on REQ-007 for authentication
- Basic RBAC concept (owner/resident/guest)
- No mention of least privilege, authorization checks, or secure direct object references

### REQ-035: Secure E-Commerce Integration
- **Status:** NOT_STARTED (DEFERRED INDEFINITELY)
- **Priority:** LOW
- **Dependencies:** REQ-006, REQ-007
- **Acceptance Criteria:**
  - [ ] Amazon account authentication (OAuth)
  - [ ] Read-only access by default
  - [ ] Multi-step confirmation for purchases
  - [ ] Transaction logging
  - [ ] Rate limiting
  - [ ] Emergency kill switch
  - [ ] No stored payment information

**Analysis:**
- Appropriately deferred due to high risk
- Good security-first design (read-only default, multi-step confirm, audit trail)
- Correctly avoids storing payment info

### REQ-036: Comprehensive Logging
- **Status:** COMPLETED (infrastructure exists, UI integration deferred)
- **Acceptance Criteria:**
  - [x] All system operations logged with timestamps
  - [x] Log levels implemented
  - [ ] User-facing log viewer in web UI (deferred)
  - [x] Privacy-aware logging (no passwords in logs)
  - [x] Log rotation to prevent disk issues

**Analysis:**
- Good foundation exists (`src/logging_config.py`)
- Privacy-aware logging mentioned but needs verification
- No structured logging for security events (failed auth, permission denials)
- No log monitoring/alerting planned

---

## Critical Security Gaps (NOT in Backlog)

### Application Security (Python/Flask)

#### 1. **NO AUTHENTICATION OR AUTHORIZATION**
- **Severity:** CRITICAL
- **Current State:** Flask web server on 0.0.0.0:5050 with no authentication
- **Risk:** Anyone on local network can control all devices, read command history, execute arbitrary commands via LLM
- **OWASP:** A01:2021 - Broken Access Control
- **Missing Requirements:**
  - Basic authentication for web UI
  - Session management (secure cookies, HttpOnly, SameSite)
  - CSRF protection for state-changing operations
  - Authorization checks before device control

#### 2. **NO HTTPS/TLS**
- **Severity:** HIGH
- **Current State:** HTTP only (per REQ-007, HTTPS deferred to Phase 7)
- **Risk:** API keys, commands, device states transmitted in cleartext on local network
- **OWASP:** A02:2021 - Cryptographic Failures
- **Missing Requirements:**
  - TLS certificate generation/management (Let's Encrypt or self-signed)
  - HTTP→HTTPS redirect enforcement
  - HSTS header configuration

#### 3. **NO INPUT VALIDATION FRAMEWORK**
- **Severity:** HIGH
- **Current State:** No schema validation on `/api/command` endpoint
- **Risk:** Command injection, XSS, malformed input crashes
- **OWASP:** A03:2021 - Injection
- **Missing Requirements:**
  - Pydantic or Marshmallow schema validation for all API inputs
  - Output encoding/escaping for command history display
  - File upload validation (if/when file features added)

#### 4. **NO SECURITY HEADERS**
- **Severity:** MEDIUM
- **Current State:** Flask default (no security headers)
- **Risk:** XSS, clickjacking, MIME sniffing attacks
- **OWASP:** A05:2021 - Security Misconfiguration
- **Missing Requirements:**
  - Content-Security-Policy
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Referrer-Policy
  - Permissions-Policy

#### 5. **NO RATE LIMITING**
- **Severity:** MEDIUM
- **Current State:** No rate limiting on `/api/command` or `/api/status`
- **Risk:** API abuse, LLM cost explosion, DoS
- **Missing Requirements:**
  - Per-IP rate limiting (flask-limiter or slowapi)
  - Per-user rate limiting (once auth implemented)
  - Cost tracking integration with rate limits

#### 6. **SECRETS MANAGEMENT GAPS**
- **Severity:** MEDIUM (partially mitigated)
- **Current State:**
  - ✅ `.env` file with 600 permissions (fixed per 2025-12-17 audit)
  - ✅ `.env` in `.gitignore`
  - ⚠️ No secrets rotation policy
  - ⚠️ API keys in plaintext on disk
- **Risk:** Compromise of server exposes all API keys permanently
- **Missing Requirements:**
  - Secrets rotation documentation/policy
  - Consider encrypted secrets (age, sops, Ansible Vault)
  - Key rotation for HA long-lived token

#### 7. **NO SQL INJECTION PROTECTION VERIFICATION**
- **Severity:** MEDIUM
- **Current State:** Using SQLite with direct SQL queries in `src/utils.py` and `src/server.py`
- **Risk:** If user input ever reaches SQL queries, injection possible
- **Analysis Needed:** Verify all queries use parameterization, not f-strings
- **Missing Requirements:**
  - Code review to verify parameterized queries everywhere
  - Static analysis (bandit, semgrep) to detect SQL injection patterns

#### 8. **DEBUG MODE IN PRODUCTION**
- **Severity:** MEDIUM
- **Current State:** `server.py` line 203: `run_server(debug=True)` when run as `__main__`
- **Risk:** Stack traces leak implementation details, debug endpoints exposed
- **Missing Requirements:**
  - Environment-based debug flag (never True in production)
  - Production WSGI server (Gunicorn, uWSGI) instead of Flask dev server

#### 9. **NO ERROR HANDLING SECURITY**
- **Severity:** LOW
- **Current State:** Generic exception handlers return `str(error)` to client
- **Risk:** Information disclosure (stack traces, file paths, config values in errors)
- **Missing Requirements:**
  - Generic error messages for production
  - Detailed errors only logged server-side
  - No stack traces in API responses

#### 10. **NO DEPENDENCY SCANNING**
- **Severity:** LOW
- **Current State:** No automated dependency vulnerability scanning
- **Risk:** Using vulnerable dependencies (anthropic, flask, requests)
- **Missing Requirements:**
  - `safety check` or `pip-audit` in CI/CD
  - Dependabot or Renovate for automated updates
  - Regular manual review of `requirements.txt`

---

### Infrastructure Security (Ubuntu/Colby)

**Note:** Infrastructure audit completed 2025-12-17. Key issues from that audit:

#### Remediated Issues (per previous audit)
- ✅ SEC-005: `.env` permissions fixed to 600

#### Outstanding Issues (from 2025-12-17 audit)
- ❌ SEC-001: Passwordless sudo (CRITICAL)
- ❌ SEC-002: SSH password auth enabled (HIGH)
- ❌ SEC-003: No fail2ban (HIGH)
- ❌ SEC-004: Root SSH not explicitly disabled (HIGH)
- ❌ SEC-010: No SSH MFA (HIGH)
- ⚠️ SEC-006: NATS on all interfaces (MEDIUM)
- ⚠️ SEC-007: Home Assistant host networking (MEDIUM)

#### Additional Infrastructure Gaps (NOT in 2025-12-17 audit)

**11. NO DOCKER SECURITY HARDENING**
- **Severity:** MEDIUM
- **Current State:** Home Assistant running in Docker with host networking
- **Missing Requirements:**
  - AppArmor/SELinux profiles for containers
  - Non-root user in containers
  - Read-only root filesystem where possible
  - Resource limits (memory, CPU)
  - Image vulnerability scanning (Trivy)

**12. NO INTRUSION DETECTION**
- **Severity:** LOW
- **Current State:** No HIDS (host intrusion detection)
- **Missing Requirements:**
  - AIDE or Tripwire for file integrity monitoring
  - Log aggregation (Loki/Grafana or ELK stack)
  - Anomaly detection for unusual command patterns

**13. NO BACKUP SECURITY**
- **Severity:** LOW (deferred per REQ-006)
- **Current State:** Backups deferred to later phase
- **Missing Requirements:**
  - Encrypted backups (age, restic, borgbackup)
  - 3-2-1 backup strategy
  - Regular restore testing
  - Backup integrity verification

---

## Recommended Security Requirements (Missing from Backlog)

### NEW REQ: Application Security Baseline (Phase 3 - URGENT)
**Priority:** CRITICAL
**Phase:** 3 (before web UI widespread use)
**Effort:** M (2-3 weeks)

**Acceptance Criteria:**
- [ ] Basic authentication for web UI (session-based or token-based)
- [ ] CSRF protection for all POST endpoints
- [ ] Pydantic schema validation on all API inputs
- [ ] Security headers middleware (CSP, X-Frame-Options, etc.)
- [ ] Debug mode disabled in production
- [ ] Generic error messages (no stack traces to client)
- [ ] Rate limiting on `/api/command` (10 req/min per IP)

**Rationale:** Web UI launching in Phase 3 without these is unacceptable security posture.

### NEW REQ: HTTPS/TLS Configuration (Phase 3 - URGENT)
**Priority:** HIGH
**Phase:** 3 (parallel with web UI work)
**Effort:** S (1 week)

**Acceptance Criteria:**
- [ ] Self-signed certificate generation for local network use
- [ ] Let's Encrypt certificate for domain (if applicable)
- [ ] HTTP→HTTPS redirect enforced
- [ ] HSTS header configured (max-age=31536000)
- [ ] TLS 1.2+ only, strong cipher suites
- [ ] Certificate renewal automation

**Rationale:** Passwords and API keys should never traverse network in cleartext.

### NEW REQ: Security Monitoring & Alerting (Phase 5)
**Priority:** MEDIUM
**Phase:** 5 (with self-monitoring features)
**Effort:** M (2 weeks)

**Acceptance Criteria:**
- [ ] Security event logging (failed auth, permission denials, unusual commands)
- [ ] Alert on repeated failed auth attempts (5+ in 10 min)
- [ ] Alert on high API cost (>$5/day)
- [ ] Daily usage summary email/notification
- [ ] Log retention policy (30 days minimum)
- [ ] Log export for forensic analysis

**Rationale:** Integrate with REQ-021 (self-monitoring) for security visibility.

### NEW REQ: Dependency Security Management (Phase 6 - Pre-Community)
**Priority:** MEDIUM
**Phase:** 6 (before public repository)
**Effort:** S (1 week)

**Acceptance Criteria:**
- [ ] `pip-audit` or `safety check` in CI/CD pipeline
- [ ] Fail build on high/critical vulnerabilities
- [ ] Automated dependency updates (Dependabot/Renovate)
- [ ] Monthly manual security review
- [ ] Document all dependencies in requirements.txt with version pins

**Rationale:** Community users will trust dependency security posture.

### NEW REQ: Secrets Rotation Policy (Phase 6 - Pre-Community)
**Priority:** LOW
**Phase:** 6 (documentation for community)
**Effort:** S (1 week documentation)

**Acceptance Criteria:**
- [ ] Document how to rotate Anthropic API key
- [ ] Document how to rotate HA long-lived token
- [ ] Recommend 90-day rotation schedule
- [ ] Script to regenerate HA token via HA API
- [ ] Backup old secrets before rotation

---

## Infrastructure Security Roadmap

### Immediate (Week 1-2)
1. **Run 2025-12-17 hardening script** (from previous audit)
   - Fix passwordless sudo (SEC-001)
   - Disable SSH password auth (SEC-002)
   - Install fail2ban (SEC-003)
   - Disable root SSH (SEC-004)
   - Effort: 2 hours + testing

2. **Set up SSH MFA** (SEC-010)
   - Google Authenticator PAM
   - Test before enforcing
   - Effort: 1 hour + testing

### Phase 3 (Parallel with Web UI work)
3. **NATS localhost binding** (SEC-006)
   - Bind to 127.0.0.1 only
   - Update systemd service
   - Effort: 30 minutes

4. **Docker security review** (NEW)
   - Review HA container security
   - Add resource limits
   - Effort: 2 hours

### Phase 6 (Pre-Community Launch)
5. **Set up Trivy container scanning**
   - Scan HA container weekly
   - Alert on high/critical CVEs
   - Effort: 1 hour

6. **Document security baseline**
   - Server hardening guide
   - Security best practices for users
   - Effort: 4 hours

---

## Priority Recommendations

### CRITICAL (Blocking for Production Use)
1. **Application authentication** (NEW REQ - Phase 3)
2. **HTTPS/TLS** (REQ-007 partial - Phase 3, not Phase 7)
3. **SSH hardening** (SEC-001 through SEC-004 from 2025-12-17 audit)

### HIGH (Should Complete Before Community Launch)
4. **Input validation framework** (NEW REQ - Phase 4)
5. **Security headers** (NEW REQ - Phase 3)
6. **Rate limiting** (NEW REQ - Phase 4)
7. **SSH MFA** (SEC-010 from 2025-12-17 audit)

### MEDIUM (Nice to Have)
8. **Security monitoring** (NEW REQ - Phase 5)
9. **Dependency scanning** (NEW REQ - Phase 6)
10. **Docker hardening** (NEW - Phase 3)

### LOW (Post-Launch)
11. **Secrets rotation policy** (NEW REQ - Phase 6)
12. **Intrusion detection** (NEW - Phase 7+)
13. **Encrypted backups** (REQ-006 deferred criteria)

---

## Quick Wins (High Impact, Low Effort)

These can be implemented immediately with minimal disruption:

1. **Fix debug mode** (5 minutes)
   ```python
   # src/server.py line 203
   if __name__ == "__main__":
       import os
       debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
       run_server(debug=debug)
   ```

2. **Add security headers** (30 minutes)
   ```python
   # Flask middleware
   @app.after_request
   def add_security_headers(response):
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'DENY'
       response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
       return response
   ```

3. **Generic error messages** (15 minutes)
   ```python
   # In exception handlers
   if not app.debug:
       return jsonify({"success": False, "error": "Internal server error"}), 500
   ```

4. **Run bandit SAST** (10 minutes)
   ```bash
   pip install bandit
   bandit -r ./src ./tools ./agent.py -ll
   ```

5. **Run pip-audit** (5 minutes)
   ```bash
   pip install pip-audit
   pip-audit
   ```

---

## Comparison: Planned vs. Needed

| Security Domain | Planned (REQ-007) | Needed (Analysis) |
|-----------------|-------------------|-------------------|
| Authentication | ✅ Mentioned | ❌ No specifics, deferred to Phase 7 |
| HTTPS/TLS | ✅ Mentioned | ⚠️ Should be Phase 3, not Phase 7 |
| Input Validation | ❌ Not mentioned | ✅ Critical need |
| Security Headers | ❌ Not mentioned | ✅ High need |
| Rate Limiting | ❌ Not mentioned | ✅ High need (cost control) |
| CSRF Protection | ❌ Not mentioned | ✅ High need |
| Session Security | ⚠️ "Session timeout" only | ⚠️ Needs HttpOnly, Secure, SameSite |
| Dependency Scanning | ❌ Not mentioned | ✅ Medium need |
| SSH Hardening | ❌ Not mentioned | ✅ Critical need (per 2025-12-17 audit) |
| Secrets Rotation | ❌ Not mentioned | ✅ Low need |
| Logging Security Events | ⚠️ Generic logging only | ✅ Medium need |

**Summary:** REQ-007 covers ~30% of needed security controls and is deferred too late (Phase 7).

---

## Actionable Next Steps

### For Agent-Security-Reviewer (This Agent)
1. ✅ Complete this analysis document
2. Post findings to #coordination channel
3. If approved, begin implementing Quick Wins (items 1-3 above)
4. Create NEW-REQ drafts for:
   - Application Security Baseline
   - HTTPS/TLS Configuration
   - Security Monitoring

### For Project Manager
1. Review this analysis
2. Prioritize new security requirements
3. Integrate into Phase 3 roadmap (not Phase 7)
4. Allocate agent resources for security work

### For User (Katherine)
1. Run infrastructure hardening script from 2025-12-17 audit
2. Set up SSH MFA on colby
3. Approve Quick Wins implementation

---

## Conclusion

The project has **solid infrastructure foundations** (UFW, Tailscale, AppArmor, unattended-upgrades) but **critical application security gaps**. The single planned security requirement (REQ-007) is necessary but insufficient, and its Phase 7 placement is dangerously late.

**Recommendation:** Promote security to a **Phase 3 priority** with new requirements for authentication, HTTPS, and input validation. The web UI should not be used in production without these controls.

**Immediate Risk:** Current Flask server on 0.0.0.0:5050 with no authentication is acceptable for local development but unacceptable for any production use or community deployment.
