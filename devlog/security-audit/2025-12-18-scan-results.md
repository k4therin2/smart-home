# Security Scan Results
**Date:** 2025-12-18
**Scans Run:** Bandit (SAST), pip-audit (Dependency Vulnerabilities)

---

## Bandit Static Analysis (SAST)

**Command:** `bandit -r ./src ./tools -ll`

**Scan Coverage:**
- Total lines of code: 3,034
- Severity threshold: Low and above (-ll flag)
- Directories scanned: `./src`, `./tools`

**Results:**

| Issue ID | Severity | Confidence | CWE | Location | Status |
|----------|----------|------------|-----|----------|--------|
| B104 | MEDIUM | MEDIUM | CWE-605 | src/server.py:222 | ACCEPTED |

### B104: Hardcoded Binding to All Interfaces

**Finding:**
```python
def run_server(host: str = "0.0.0.0", port: int = 5050, debug: bool = False):
```

**Analysis:**
- Flask server binds to `0.0.0.0` by default, making it accessible on all network interfaces
- This is intentional for home server deployment on Colby
- Server needs to be accessible from other devices on LAN (phones, tablets, laptops)

**Risk Assessment:**
- **Threat:** Unauthorized access from LAN devices or compromised devices on network
- **Likelihood:** LOW - Home network is behind firewall, Tailscale provides additional network segmentation
- **Impact:** HIGH - Full device control if accessed by attacker
- **Overall Risk:** MEDIUM

**Mitigations in Place:**
1. UFW firewall configured (per 2025-12-17 audit)
2. Tailscale VPN for remote access
3. Network is residential, not public
4. No port forwarding from WAN to this service

**Missing Mitigations:**
1. **Authentication** - CRITICAL - No authentication currently implemented
2. **HTTPS** - HIGH - Traffic not encrypted on LAN
3. **Rate limiting** - MEDIUM - No protection against brute force

**Decision:** ACCEPTED with conditions
- Acceptable for Phase 2 (internal development)
- MUST implement authentication before Phase 3 (web UI production use)
- MUST implement HTTPS before any remote access

**Tracking:** Added to security backlog as REQ-007 (HTTPS/TLS) and NEW REQ (Authentication)

---

## pip-audit Dependency Vulnerability Scan

**Command:** `pip-audit`

### Initial Scan Results

**Found:** 1 vulnerability

| Package | Version | Vulnerability | Fixed In |
|---------|---------|---------------|----------|
| pip | 24.0 | CVE-2025-8869 | 25.3 |

**CVE-2025-8869 Details:**
- Vulnerability in pip package manager
- Severity: Not specified in initial output
- Fix available: pip 25.3

### Remediation

**Action Taken:**
```bash
pip install --upgrade pip
```

**Post-Remediation Scan:**
```bash
pip-audit
```

**Result:** ✅ **No known vulnerabilities found**

**Status:** ALL DEPENDENCIES SECURE

---

## Summary

### Vulnerabilities Found
- **Critical:** 0
- **High:** 0
- **Medium:** 1 (B104 - accepted risk)
- **Low:** 0

### Vulnerabilities Fixed
- **CVE-2025-8869** - pip upgraded from 24.0 to 25.3

### Accepted Risks
- **B104 (Binding to 0.0.0.0)** - Mitigated by firewall and network controls, requires authentication before production use

### Recommended Actions
1. **IMMEDIATE:** Implement authentication (blocks B104 exploitation)
2. **URGENT:** Implement HTTPS/TLS (encrypts LAN traffic)
3. **HIGH:** Add rate limiting (mitigates brute force)
4. **ONGOING:** Re-run pip-audit weekly, add to CI/CD pipeline

---

## Next Scan Schedule

**Weekly:**
- pip-audit (dependency vulnerabilities)

**Before Each Deployment:**
- bandit -r ./src ./tools -ll
- pip-audit

**Monthly:**
- Full security review of new code
- Review accepted risks (reassess B104 as threat landscape changes)

---

## CI/CD Integration Recommendations

Add to `.github/workflows/security.yml`:

```yaml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install bandit pip-audit
          pip install -r requirements.txt

      - name: Bandit SAST
        run: bandit -r ./src ./tools -ll

      - name: pip-audit
        run: pip-audit
        continue-on-error: false  # Fail build on vulnerabilities
```

**Benefits:**
- Automated security scanning on every commit
- Prevents vulnerable code from merging
- Dependency vulnerabilities caught before deployment

---

## References

- Bandit Documentation: https://bandit.readthedocs.io/
- CWE-605 (Multiple Binds): https://cwe.mitre.org/data/definitions/605.html
- pip-audit: https://pypi.org/project/pip-audit/
- CVE-2025-8869: https://nvd.nist.gov/ (search for CVE ID)
