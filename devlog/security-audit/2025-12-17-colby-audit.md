# Security Audit: Colby Home Server
**Date:** 2025-12-17
**Auditor:** Agent-Security-Lead
**Target:** colby (Ubuntu 24.04.3 LTS, i7-6700K, 16GB RAM)

---

## Executive Summary

The colby home server has a solid foundation with UFW firewall, Tailscale VPN, AppArmor, and unattended upgrades. However, several **critical and high-severity issues** require immediate attention, primarily around SSH authentication and sudo configuration.

**Risk Level:** HIGH - Compromise of user account leads to full root access with no barriers.

---

## Findings

### CRITICAL

#### SEC-001: Passwordless Sudo for Primary User
- **Severity:** Critical
- **CWE:** CWE-250 (Execution with Unnecessary Privileges)
- **Finding:** `/etc/sudoers.d/` contains `k4therin2 ALL=(ALL) NOPASSWD: ALL`
- **Risk:** Any compromise of the k4therin2 account (malware, stolen session, SSH exploit) grants immediate, silent root access to the entire system.
- **Proof of Concept:** Attacker gains shell as k4therin2 → `sudo su -` → root, no password required
- **Remediation:**
  ```bash
  sudo visudo -f /etc/sudoers.d/k4therin2
  # Change to require password:
  k4therin2 ALL=(ALL:ALL) ALL
  # Or for specific commands only:
  k4therin2 ALL=(ALL) NOPASSWD: /usr/bin/docker, /bin/systemctl restart homeassistant
  ```

---

### HIGH

#### SEC-002: SSH Password Authentication Enabled
- **Severity:** High
- **CWE:** CWE-287 (Improper Authentication)
- **Finding:** SSH config uses defaults - password authentication is enabled
- **Risk:** Combined with weak password, vulnerable to brute-force attacks. Current password "plsdontbreak" is dictionary-attackable.
- **Remediation:**
  ```bash
  sudo nano /etc/ssh/sshd_config.d/hardening.conf
  ```
  ```
  PasswordAuthentication no
  PubkeyAuthentication yes
  PermitRootLogin no
  AllowUsers k4therin2
  MaxAuthTries 3
  ```
  ```bash
  # First, ensure SSH key is set up:
  ssh-copy-id k4therin2@colby
  # Then apply and restart:
  sudo systemctl restart sshd
  ```

#### SEC-003: No Fail2ban Protection
- **Severity:** High
- **CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)
- **Finding:** `fail2ban-client status` returns "not installed"
- **Risk:** No protection against SSH brute-force attacks while password auth is enabled
- **Remediation:**
  ```bash
  sudo apt install fail2ban -y
  sudo systemctl enable fail2ban
  sudo systemctl start fail2ban

  # Configure SSH jail
  sudo nano /etc/fail2ban/jail.local
  ```
  ```ini
  [sshd]
  enabled = true
  port = 22
  filter = sshd
  logpath = /var/log/auth.log
  maxretry = 3
  bantime = 3600
  findtime = 600
  ```
  ```bash
  sudo systemctl restart fail2ban
  ```

#### SEC-004: Root Login Not Explicitly Disabled
- **Severity:** High
- **CWE:** CWE-250
- **Finding:** `PermitRootLogin` commented out, defaults to `prohibit-password`
- **Risk:** If someone adds a root SSH key, root login becomes possible
- **Remediation:** Add to `/etc/ssh/sshd_config.d/hardening.conf`:
  ```
  PermitRootLogin no
  ```

#### SEC-010: No Multi-Factor Authentication for SSH
- **Severity:** High
- **CWE:** CWE-308 (Use of Single-factor Authentication)
- **Finding:** SSH login only requires password or key - no second factor
- **Risk:** Stolen key or password grants immediate access
- **Remediation:** Install Google Authenticator PAM for TOTP-based 2FA:
  ```bash
  sudo apt install libpam-google-authenticator -y

  # Run as k4therin2 to set up TOTP:
  google-authenticator -t -d -f -r 3 -R 30 -w 3
  # -t: time-based, -d: disallow reuse, -f: force write
  # -r 3 -R 30: rate limit 3 logins per 30 sec
  # -w 3: allow 3 codes either side for clock skew

  # Scan QR code with authenticator app (Authy, Google Auth, etc.)
  # Save backup codes securely!

  # Configure PAM:
  sudo nano /etc/pam.d/sshd
  # Add at top: auth required pam_google_authenticator.so

  # Configure SSH:
  sudo nano /etc/ssh/sshd_config.d/hardening.conf
  # Add:
  #   ChallengeResponseAuthentication yes
  #   AuthenticationMethods publickey,keyboard-interactive

  sudo systemctl restart sshd
  ```

---

### MEDIUM

#### SEC-005: Secrets Files World-Readable
- **Severity:** Medium
- **CWE:** CWE-732 (Incorrect Permission Assignment)
- **Finding:**
  - `.env` has permissions `664` (group and world readable)
  - `secrets.yaml` has permissions `664`
- **Risk:** Any process or user on the system can read API keys
- **Remediation:**
  ```bash
  chmod 600 ~/projects/Smarthome/.env
  chmod 600 ~/projects/Smarthome/ha-config/secrets.yaml
  chmod 600 ~/homeassistant/secrets.yaml 2>/dev/null
  ```

#### SEC-006: NATS Server Exposed on All Interfaces
- **Severity:** Medium
- **CWE:** CWE-668 (Exposure of Resource to Wrong Sphere)
- **Finding:** NATS listening on `*:4222` (all interfaces)
- **Risk:** If UFW is misconfigured or bypassed, NATS becomes externally accessible
- **Current Mitigation:** UFW does not have port 4222 open (good)
- **Remediation:** Bind NATS to localhost only:
  ```bash
  sudo nano /etc/systemd/system/nats.service
  # Change ExecStart to include: -a 127.0.0.1
  # Or use nats.conf:
  ```
  ```
  # /etc/nats/nats.conf
  host: 127.0.0.1
  port: 4222
  jetstream {
    store_dir: /var/lib/nats
  }
  ```

#### SEC-007: Home Assistant Using Host Networking
- **Severity:** Medium
- **CWE:** CWE-668
- **Finding:** HA container running with `--network=host`
- **Risk:** Container has access to all host network interfaces, reduces isolation
- **Current Mitigation:** Not running privileged (good)
- **Recommendation:** Consider bridge networking with explicit port mapping if feasible, though host mode is common for HA due to mDNS/discovery requirements.

#### SEC-008: go2rtc WebRTC Exposed
- **Severity:** Medium
- **Finding:** Port 18555 listening on all interfaces
- **Risk:** WebRTC streams potentially accessible if firewall bypassed
- **Current Mitigation:** UFW doesn't allow this port externally
- **Recommendation:** Monitor, ensure stays internal-only

---

### LOW / INFO

#### SEC-009: Strong Points (No Action Required)
- **UFW Firewall:** Active, default deny, only local network (192.168.1.0/24) allowed
- **Tailscale:** Secure VPN for remote access instead of port forwarding
- **AppArmor:** Running with 25 profiles enforced including docker-default
- **Unattended Upgrades:** Installed and running
- **Docker:** Not running privileged containers
- **SSH on standard port:** Consider non-standard port for reduced noise (optional)

---

## Remediation Priority

| Priority | ID | Issue | Effort |
|----------|-----|-------|--------|
| 1 | SEC-010 | Set up SSH 2FA (TOTP) | S |
| 2 | SEC-002 | Disable SSH password auth | S |
| 3 | SEC-003 | Install fail2ban | S |
| 4 | SEC-004 | Disable root SSH login | S |
| 5 | SEC-001 | Fix passwordless sudo | S |
| 6 | SEC-005 | Fix secrets file permissions | S |
| 7 | SEC-006 | Bind NATS to localhost | S |
| 8 | SEC-007 | Review HA networking | M |
| 9 | SEC-008 | Monitor go2rtc exposure | - |

**Recommended Order:** SSH Key Setup → SEC-010 (2FA) → SEC-002 → SEC-003 → SEC-004 → SEC-001 → SEC-005 → SEC-006

---

## Immediate Action Script

Run this on colby to fix critical issues:

```bash
#!/bin/bash
# COLBY SECURITY HARDENING - Run as k4therin2

set -e

echo "=== Step 1: Ensure SSH key exists ==="
if [ ! -f ~/.ssh/authorized_keys ] || [ ! -s ~/.ssh/authorized_keys ]; then
    echo "ERROR: No SSH key found. Add your public key first:"
    echo "  From your Mac: ssh-copy-id k4therin2@colby"
    exit 1
fi

echo "=== Step 2: Install fail2ban ==="
sudo apt update && sudo apt install -y fail2ban

echo "=== Step 3: Configure fail2ban ==="
sudo tee /etc/fail2ban/jail.local > /dev/null << 'FAIL2BAN'
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
FAIL2BAN

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

echo "=== Step 4: Harden SSH ==="
sudo tee /etc/ssh/sshd_config.d/hardening.conf > /dev/null << 'SSHCONF'
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers k4therin2
MaxAuthTries 3
SSHCONF

echo "=== Step 5: Fix secrets permissions ==="
chmod 600 ~/projects/Smarthome/.env 2>/dev/null || true
chmod 600 ~/projects/Smarthome/ha-config/secrets.yaml 2>/dev/null || true
chmod 600 ~/homeassistant/secrets.yaml 2>/dev/null || true

echo "=== Step 6: Restart SSH (TEST IN NEW TERMINAL FIRST!) ==="
echo "Before restarting SSH, open a NEW terminal and test:"
echo "  ssh k4therin2@colby"
echo "If that works with your key, press Enter to continue..."
read

sudo systemctl restart sshd
echo "SSH hardened. Password auth disabled."

echo "=== Step 7: Fix sudo (MANUAL - requires password) ==="
echo "Run: sudo visudo -f /etc/sudoers.d/k4therin2"
echo "Change: k4therin2 ALL=(ALL) NOPASSWD: ALL"
echo "To:     k4therin2 ALL=(ALL:ALL) ALL"
echo ""
echo "=== HARDENING COMPLETE ==="
```

---

## Next Steps

1. Generate SSH key on Mac if needed: `ssh-keygen -t ed25519`
2. Copy to colby: `ssh-copy-id k4therin2@colby`
3. Test key-based login works
4. Run hardening script
5. Update password to something strong (for sudo): `passwd`
6. Consider changing NATS to localhost-only binding
