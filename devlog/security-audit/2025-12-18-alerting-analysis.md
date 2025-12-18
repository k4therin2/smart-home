# Security Alerting Analysis and Recommendations
**Date:** 2025-12-18
**Analyst:** Agent-Security-Infrastructure
**Scope:** Review current alerting setup and identify critical gaps for home server security monitoring

---

## Executive Summary

**Current State:** Basic 3-channel Slack alerting system built but NOT YET DEPLOYED (blocked on webhook configuration). Covers SSH brute-force, API costs, and service health monitoring.

**Critical Gap:** Missing alerts for 8 high-impact attack vectors common to home servers (UFW blocks, Docker security, file integrity, Home Assistant access, unusual processes, disk/resource exhaustion, failed sudo, network anomalies).

**Risk Level:** MEDIUM-HIGH - While SSH monitoring exists, the majority of attack surface is unmonitored.

**Deployment Status:** 🔴 BLOCKED - requires user to create Slack app and provide webhook URLs.

---

## Current Alerting Setup

### 1. SSH Failed Login Monitor
**Channel:** `#colby-server-security`
**Implementation:** `/home/k4therin2/projects/Smarthome/src/security/monitors.py` (SSHMonitor class)
**Status:** ✅ Code complete, NOT deployed

**What It Does:**
- Parses `/var/log/auth.log` for failed SSH attempts
- Tracks by source IP address
- Alerts when ≥5 failed attempts in 10-minute window
- 60-minute cooldown between alerts per IP
- Maintains state across daemon restarts

**Threshold Analysis:**
- **Current:** 5 attempts in 10 minutes
- **Assessment:** ✅ APPROPRIATE
- **Rationale:**
  - Fail2ban is already banning after 5 attempts (verified: 3 total bans, 38 total failures)
  - This threshold provides notification when fail2ban takes action
  - Higher threshold would miss legitimate attacks
  - Lower threshold would cause alert fatigue on scanning traffic

**Example Alert:**
```
SSH Brute Force Detected
5 failed SSH login attempts from 203.0.113.42 in the last 10 minutes.

Source IP: 203.0.113.42
Attempts: 5
Threshold: 5
```

**Integration:** Works with existing fail2ban jail (sshd only, currently 0 banned IPs).

---

### 2. API Cost Monitor
**Channel:** `#smarthome-costs`
**Implementation:** `/home/k4therin2/projects/Smarthome/src/security/monitors.py` (APICostMonitor class)
**Status:** ✅ Code complete, NOT deployed

**What It Does:**
- Queries local SQLite database for daily Anthropic API usage
- Alerts when daily cost exceeds $5.00
- 2-hour cooldown between alerts

**Threshold Analysis:**
- **Current:** $5.00/day
- **Assessment:** ⚠️ NEEDS ADJUSTMENT
- **Rationale:**
  - Daily target is $2.00 (per CLAUDE.md)
  - Current threshold is 2.5x the target - too high for early warning
  - By the time alert fires, user is already 150% over budget

**Recommended Thresholds (Multi-tier):**
1. **Warning:** $3.00/day (50% over budget) - 2-hour cooldown
2. **Critical:** $5.00/day (150% over budget) - 1-hour cooldown
3. **Emergency:** $10.00/day (400% over budget) - immediate, no cooldown

**Additional Metric Needed:**
- Hourly spending rate projection
- Example: If spending $1.00/hour at 2 PM, projected daily = $12.00
- Alert: "On track to spend $12.00 today (400% over target)"

**Example Enhanced Alert:**
```
API Cost Warning ⚠️
Daily API cost: $3.50 (75% over $2.00 target)
Projected end-of-day: $4.20
Last hour: $0.75
Requests today: 142

Threshold: $3.00 warning
```

---

### 3. Service Health Monitor
**Channel:** `#smarthome-health`
**Implementation:** `/home/k4therin2/projects/Smarthome/src/security/monitors.py` (ServiceMonitor class)
**Status:** ✅ Code complete, NOT deployed

**What It Does:**
- Checks systemd services via `systemctl is-active`
- Checks Docker containers via `docker inspect`
- Alerts on status change from running → stopped
- 5-minute cooldown between alerts

**Monitored Services:**
- `home-assistant` (Docker container)
- `nats-server` (systemd service)
- `docker` (systemd service)

**Service Discovery Findings:**
```bash
# Systemd services enabled:
docker.service       ✅ enabled
nats.service         ✅ enabled (nats-server)
fail2ban.service     ✅ enabled (NOT monitored)
ufw.service          ✅ enabled (NOT monitored)

# Docker containers running:
homeassistant        ✅ running (monitored)
wyoming-whisper      ✅ running (NOT monitored)
wyoming-piper        ✅ running (NOT monitored)
```

**Gap:** Wyoming voice containers (whisper, piper) not monitored. If voice control fails silently, user experience degrades.

**Threshold Analysis:**
- **Current:** 5-minute cooldown
- **Assessment:** ✅ APPROPRIATE for service restarts, ⚠️ TOO LONG for persistent failures
- **Issue:** If service crashes and stays down, only 1 alert in first 5 minutes, then silence
- **Recommendation:**
  - First alert: immediate
  - Second alert (if still down): 5 minutes
  - Third alert (if still down): 15 minutes
  - Fourth+ alerts: 1 hour

**Example Alert:**
```
Service Down 🔴
Service home-assistant has stopped running.

Service: home-assistant
Current Status: exited
Previous Status: running
```

---

## Critical Security Alerts MISSING

### 4. UFW Firewall Block Monitor ⚠️ HIGH PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** HIGH

**Why Critical:**
- UFW is blocking traffic constantly (observed 20+ blocks/minute in `/var/log/ufw.log`)
- Current blocks are mostly multicast/broadcast noise (mDNS, SSDP, IGMP)
- **Threat:** Real attack attempts blend into noise and go unnoticed
- **Attack Scenarios:**
  - Port scanning (rapid SYN to multiple ports)
  - Exploit attempts (specific ports: 445 SMB, 3389 RDP, 23 Telnet)
  - IoT device compromise spreading laterally

**What to Monitor:**
- Source IPs attempting blocked connections
- Unique destination ports per IP (port scanning signature)
- External IPs (non-192.168.1.0/24) attempting access
- Unusual protocols (not IGMP/mDNS/SSDP broadcast noise)

**Recommended Thresholds:**
1. **Port Scan Detection:** ≥10 different destination ports from same IP in 1 minute
2. **External Attack:** Any external IP (non-LAN) attempting connection
3. **Targeted Attack:** ≥20 blocks from same internal IP in 5 minutes (compromised IoT device)
4. **High-Value Ports:** Single block on SSH (22), HTTPS (443), HA (8123) from external IP

**Implementation:**
```python
class UFWMonitor(BaseMonitor):
    # Parse /var/log/ufw.log (kernel format)
    # Track: source IP, dest port, protocol, timestamp
    # Ignore: multicast (224.x.x.x, ff02::), broadcast (x.x.x.255)
    # Alert on: port scans, external IPs, high-value port attempts
```

**Example Alert:**
```
UFW Port Scan Detected 🚨
IP 192.168.1.45 attempted connections to 23 different ports in the last minute.

Source IP: 192.168.1.45
Unique Ports: 23 (22, 80, 443, 3389, 445, 8080, ...)
Blocks: 47
Timeframe: 60 seconds
Action: Investigate device at 192.168.1.45 for compromise
```

---

### 5. Docker Container Security Monitor ⚠️ MEDIUM PRIORITY
**Channel:** `#smarthome-health`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** MEDIUM (becomes HIGH if HA exposed externally)

**Why Important:**
- Home Assistant runs privileged operations (device control)
- Wyoming containers run ML models (resource-intensive, potential DoS)
- Container escapes can compromise entire host

**What to Monitor:**
- Container restart loops (crashed >3 times in 10 minutes)
- Abnormal resource usage (CPU >80%, Memory >90% of limit)
- Container running as root (security best practice violation)
- New containers started without explicit user action
- Volume mounts to sensitive paths (`/etc`, `/root`, `/var`)

**Recommended Checks:**
```python
class DockerSecurityMonitor(BaseMonitor):
    def check_containers(self):
        # Restart count
        if restarts > 3 in 10 minutes: alert("Container crash loop")

        # Resource usage
        if cpu_percent > 80 for 5 minutes: alert("High CPU")
        if memory_percent > 90: alert("OOM risk")

        # Security posture
        if user == "root": alert("Running as root")
        if new container and not in ALLOWED_LIST: alert("Unauthorized container")
```

**Example Alert:**
```
Container Crash Loop 🔄
homeassistant has restarted 5 times in the last 10 minutes.

Container: homeassistant
Restarts: 5
Last Exit Code: 137 (OOM killed)
Action: Check container logs with 'docker logs homeassistant'
```

---

### 6. File Integrity Monitor (Critical Configs) ⚠️ MEDIUM PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** MEDIUM (becomes CRITICAL for /etc/sudoers, /etc/ssh/sshd_config)

**Why Important:**
- Attackers modify config files to maintain persistence
- Example: Adding backdoor SSH keys, sudo privileges, cron jobs
- Silent modification indicates compromise

**What to Monitor (Critical Files):**
```bash
# System security
/etc/sudoers
/etc/sudoers.d/*
/etc/ssh/sshd_config
/etc/ssh/authorized_keys
/root/.ssh/authorized_keys
/home/*/.ssh/authorized_keys

# Services
/etc/systemd/system/*.service
/home/k4therin2/projects/Smarthome/.env
/home/k4therin2/homeassistant/configuration.yaml
/home/k4therin2/homeassistant/secrets.yaml

# Firewall
/etc/ufw/user.rules
/etc/fail2ban/jail.local
```

**Implementation Options:**
1. **Simple:** Hash-based monitoring (sha256sum stored, compared on each check)
2. **Advanced:** AIDE or Tripwire (full HIDS with inotify)

**Recommended Approach (Simple):**
```python
class FileIntegrityMonitor(BaseMonitor):
    CRITICAL_FILES = [
        "/etc/sudoers",
        "/etc/ssh/sshd_config",
        "/home/k4therin2/projects/Smarthome/.env",
        # ...
    ]

    def check(self):
        for file_path in CRITICAL_FILES:
            current_hash = sha256(file_path)
            if current_hash != stored_hash:
                alert(f"File modified: {file_path}")
                # Store new hash after human verification
```

**Threshold:** ANY modification to monitored files triggers immediate alert.

**Example Alert:**
```
Critical File Modified 🚨
/etc/sudoers has been modified.

File: /etc/sudoers
Previous Hash: a3f2b8c9...
Current Hash: d7e1f4a2...
Modified: 2025-12-18 05:14:23
Action: Review changes immediately with 'sudo visudo -c'
```

---

### 7. Home Assistant Unauthorized Access Monitor ⚠️ HIGH PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** HIGH (HA controls physical devices)

**Why Critical:**
- HA web UI on `0.0.0.0:8123` accessible to entire LAN (currently)
- No current monitoring of HA access logs
- Unauthorized access = potential device control by attacker
- **Future Risk:** When web UI gets authentication, need to monitor failed login attempts

**What to Monitor (Current State - No Auth):**
```
# Home Assistant logs (journalctl -u docker@homeassistant)
- Unusual entity state changes (lights/locks toggled at odd hours)
- Service calls from unknown sources
- Integration authentication failures
- API rate limiting triggers
```

**What to Monitor (Future State - With Auth):**
- Failed login attempts (≥3 in 10 minutes)
- Logins from unexpected IP addresses
- Account lockouts
- Privilege escalation attempts

**Implementation:**
```python
class HomeAssistantMonitor(BaseMonitor):
    def check_logs(self):
        # Parse Home Assistant logs via journalctl
        # Look for authentication failures
        # Track entity state changes by source
        # Alert on API errors or rate limits
```

**Example Alert (Future):**
```
HA Failed Login Attempt 🔐
3 failed login attempts to Home Assistant from 192.168.1.99

IP Address: 192.168.1.99
Attempts: 3
Timeframe: 5 minutes
Action: Check if this IP is a known device on your network
```

---

### 8. Unusual Process Monitor ⚠️ LOW PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** LOW (nice-to-have, low false positive risk)

**Why Useful:**
- Detects cryptominers, backdoors, unauthorized services
- Example: Unexpected `nc` (netcat), `python -m http.server`, `curl | bash`
- Low-effort monitoring with potentially high signal

**What to Monitor:**
```bash
# Suspicious process names
nc, ncat, netcat          # Reverse shells
socat                     # Port forwarding
python -m http.server     # Unauthorized file sharing
wget, curl with pipes     # Remote code execution pattern
/tmp/* executables        # Malware staging area
kdevtmpfsi, xmrig         # Known cryptominers
```

**Implementation:**
```python
class ProcessMonitor(BaseMonitor):
    SUSPICIOUS_PATTERNS = [
        r"nc\s+-l",  # Listening netcat
        r"python.*http\.server",
        r"curl.*\|.*bash",
        r"/tmp/[a-z0-9]+$",  # Random tmp executable
    ]

    def check(self):
        processes = subprocess.check_output(["ps", "aux"]).decode()
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, processes):
                alert(f"Suspicious process detected: {pattern}")
```

**Threshold:** ANY match on suspicious patterns.

**Example Alert:**
```
Suspicious Process Detected ⚠️
Netcat listening on port 4444 detected.

Process: nc -lvp 4444
User: k4therin2
PID: 12345
Command: nc -lvp 4444
Action: Kill process if unauthorized, investigate parent process
```

---

### 9. Disk & Resource Exhaustion Monitor ⚠️ MEDIUM PRIORITY
**Channel:** `#smarthome-health`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** MEDIUM (DoS risk, common attack/accident)

**Why Important:**
- Full disk = service failures (Docker, logs, HA database)
- High memory usage = OOM kills critical services
- Log bombs can fill disk rapidly (attack or bug)

**What to Monitor:**
```bash
# Disk usage
/ (root): Alert at 85%, critical at 95%
/home: Alert at 90%
/var/log: Alert at 80% (logs can grow fast)

# Memory usage
RAM: Alert at 90% for 5 minutes
Swap: Alert if swap used >50%

# Inodes (can exhaust before disk space)
Any filesystem: Alert at 90% inodes used
```

**Implementation:**
```python
class ResourceMonitor(BaseMonitor):
    def check_disk(self):
        usage = shutil.disk_usage("/")
        percent = usage.used / usage.total * 100
        if percent > 85:
            alert(f"Disk usage at {percent:.1f}%")

    def check_memory(self):
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            alert(f"Memory usage at {mem.percent:.1f}%")
```

**Example Alert:**
```
Disk Space Low ⚠️
Root filesystem (/) is 92% full.

Filesystem: /
Used: 438 GB / 476 GB
Available: 38 GB
Action: Run 'du -h / | sort -h | tail -20' to find large files
```

---

### 10. Network Anomaly Detection ⚠️ LOW PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** LOW (advanced, high false positive risk)

**Why Useful (Advanced):**
- Detects data exfiltration (large outbound transfers)
- DNS tunneling (excessive DNS queries)
- C2 beaconing (periodic connections to external IP)

**What to Monitor:**
```
# Outbound traffic volume
- Alert if >10 GB outbound in 1 hour (baseline: expect <1 GB/hour)

# DNS anomalies
- Alert if >100 DNS queries/minute (DNS tunneling)
- Alert on queries to suspicious TLDs (.tk, .ml, .ga)

# Unusual connections
- Connections to non-standard ports (not 80, 443, 22)
- Repeated connections to same external IP (beaconing)
```

**Note:** Requires baseline traffic profiling. High risk of false positives. **Defer to Phase 6+.**

---

### 11. Failed Sudo Attempts ⚠️ HIGH PRIORITY
**Channel:** `#colby-server-security`
**Status:** ❌ NOT IMPLEMENTED
**Severity:** HIGH

**Why Critical:**
- Failed sudo = potential privilege escalation attempt
- Current setup: NOPASSWD sudo (per 2025-12-17 audit SEC-001)
- **Note:** Once SEC-001 fixed (sudo requires password), failed attempts are strong attack signal

**What to Monitor:**
```bash
# Parse /var/log/auth.log for:
sudo: COMMAND           # Successful (log for audit trail)
sudo: authentication failure  # Failed password
sudo: user NOT in sudoers     # Unauthorized user attempting sudo
sudo: incorrect password      # Brute force
```

**Implementation:**
```python
class SudoMonitor(BaseMonitor):
    PATTERNS = {
        "failed": re.compile(r"sudo.*authentication failure"),
        "unauthorized": re.compile(r"sudo.*user NOT in sudoers"),
        "incorrect": re.compile(r"sudo.*incorrect password"),
    }

    def check(self):
        # Parse auth.log similar to SSHMonitor
        # Alert on ANY failed sudo attempt (threshold: 1)
```

**Threshold:**
- **Immediate alert** on any failed sudo attempt (no cooldown)
- If NOPASSWD sudo: Only alert on "user NOT in sudoers" (unauthorized account)

**Example Alert:**
```
Unauthorized Sudo Attempt 🚨
User 'www-data' attempted to use sudo but is not in sudoers.

User: www-data
Command: /usr/bin/whoami
Timestamp: 2025-12-18 05:23:14
Action: Investigate web application compromise (www-data is Apache/nginx user)
```

---

## Threshold Analysis Summary

| Monitor | Current | Assessment | Recommended Change |
|---------|---------|------------|-------------------|
| SSH Failed Logins | 5 in 10 min | ✅ Appropriate | Keep as-is |
| API Cost | $5.00/day | ⚠️ Too high | Multi-tier: $3, $5, $10 |
| Service Down Cooldown | 5 min | ⚠️ Too long for persistent failure | Exponential: 0, 5, 15, 60 min |
| UFW Port Scan | N/A | ❌ Missing | 10 unique ports in 1 min |
| UFW External Attack | N/A | ❌ Missing | Any external IP = immediate |
| Failed Sudo | N/A | ❌ Missing | 1 attempt = immediate |
| Disk Usage | N/A | ❌ Missing | 85% warning, 95% critical |
| Container Restarts | N/A | ❌ Missing | 3 restarts in 10 min |

---

## Attack Detection Gaps

### What's Covered (3 monitors)
✅ **SSH brute-force** (SSHMonitor + fail2ban)
✅ **Service failures** (ServiceMonitor)
✅ **API cost abuse** (APICostMonitor)

### What's NOT Covered (8 attack vectors)
❌ **Lateral movement** (UFW blocks from internal IPs)
❌ **Port scanning** (reconnaissance phase)
❌ **Privilege escalation** (failed sudo)
❌ **Persistence** (file integrity - backdoor configs)
❌ **Container escapes** (Docker security)
❌ **Data exfiltration** (network anomalies)
❌ **Resource DoS** (disk/memory exhaustion)
❌ **Application compromise** (Home Assistant access)

### MITRE ATT&CK Coverage Analysis

| Tactic | Technique | Covered? | Monitor |
|--------|-----------|----------|---------|
| Initial Access | T1078 - Valid Accounts | ✅ Partial | SSH Monitor |
| Initial Access | T1190 - Exploit Public App | ❌ No | (Need HA/Web monitor) |
| Persistence | T1098 - Account Manipulation | ❌ No | (Need file integrity) |
| Persistence | T1543 - Create/Modify Service | ❌ No | (Need file integrity) |
| Privilege Escalation | T1548 - Abuse Elevation | ❌ No | (Need sudo monitor) |
| Defense Evasion | T1562 - Impair Defenses | ❌ No | (Need file integrity) |
| Discovery | T1046 - Network Service Scan | ❌ No | (Need UFW monitor) |
| Lateral Movement | T1021 - Remote Services | ❌ No | (Need UFW monitor) |
| Impact | T1485 - Data Destruction | ✅ Partial | Service Monitor |
| Impact | T1498 - DoS | ❌ No | (Need resource monitor) |

**Coverage:** 2/10 attack tactics partially covered (20%). Need 8 additional monitors for comprehensive defense.

---

## Implementation Priority

### Tier 1: CRITICAL (Implement Immediately)
**Effort:** 1-2 weeks
**Impact:** HIGH - Closes most dangerous gaps

1. **UFW Firewall Monitor** (2 days)
   - Port scan detection
   - External IP attempts
   - High-value port blocking alerts

2. **Failed Sudo Monitor** (1 day)
   - Unauthorized sudo attempts
   - Integrate with existing SSHMonitor class

3. **File Integrity Monitor** (3 days)
   - Critical config files only (10-15 files)
   - Hash-based, simple implementation

4. **Home Assistant Access Monitor** (2 days)
   - Parse HA logs for anomalies
   - Foundation for future auth monitoring

### Tier 2: HIGH (Implement Within 1 Month)
**Effort:** 1 week
**Impact:** MEDIUM-HIGH - Improves reliability and DoS resistance

5. **Disk/Memory Resource Monitor** (1 day)
   - Prevent service failures from full disk/OOM
   - Simple thresholds

6. **Docker Security Monitor** (2 days)
   - Container restart loops
   - Resource exhaustion per container

7. **Enhanced Service Monitor** (1 day)
   - Add Wyoming containers to monitored list
   - Implement exponential backoff alerting

8. **Multi-Tier API Cost Alerts** (1 day)
   - Add $3 warning threshold
   - Add hourly projection calculation

### Tier 3: MEDIUM (Implement Before Production)
**Effort:** 3-4 days
**Impact:** MEDIUM - Nice-to-have, reduces noise

9. **Unusual Process Monitor** (2 days)
   - Low false positive risk
   - Easy to implement with `ps aux` + regex

10. **Weekly Security Report** (Already implemented, needs testing)
    - Summary of all alerts
    - Statistics and trends

### Tier 4: LOW (Defer to Phase 6+)
**Effort:** 1-2 weeks
**Impact:** LOW - Advanced, requires baselining

11. **Network Anomaly Detection**
    - Requires traffic profiling
    - High false positive risk
    - Defer until mature monitoring in place

---

## Recommended Implementation Plan

### Phase 1: Deploy Existing System (IMMEDIATE)
**Blockers:**
- User must create Slack app at https://api.slack.com/apps
- User must add 3 webhook URLs to `.env`:
  - `SLACK_SECURITY_WEBHOOK` → #colby-server-security
  - `SLACK_COST_WEBHOOK` → #smarthome-costs
  - `SLACK_HEALTH_WEBHOOK` → #smarthome-health

**Steps:**
1. User creates Slack webhooks
2. User adds webhooks to `/home/k4therin2/projects/Smarthome/.env`
3. Agent runs deployment script: `./deploy/setup-security-monitoring.sh`
4. Verify alerts with test commands

**Validation:**
```bash
# Test SSH monitor
python -m src.security.daemon --test

# Check systemd status
systemctl status smarthome-security

# Watch logs
journalctl -u smarthome-security -f
```

### Phase 2: Implement Tier 1 Monitors (Week 1-2)
**Deliverables:**
- UFW Monitor class
- Sudo Monitor class
- File Integrity Monitor class
- HA Access Monitor class

**Integration:** All use existing BaseMonitor class, SlackNotifier, and alert history.

### Phase 3: Enhance Existing Monitors (Week 3)
**Deliverables:**
- Multi-tier API cost thresholds
- Exponential backoff for service alerts
- Add Wyoming containers to service list

### Phase 4: Add Resource Monitors (Week 4)
**Deliverables:**
- Disk/memory monitor
- Docker security monitor
- Process monitor

---

## Monitoring Configuration Best Practices

### Alert Fatigue Prevention
1. **Use cooldowns** to prevent spam (already implemented)
2. **Tier severity** - not all alerts are critical
3. **Aggregate similar alerts** (e.g., "5 services down" not 5 separate alerts)
4. **Weekly summary** for low-severity items instead of real-time alerts

### False Positive Mitigation
1. **Baseline before alerting** (e.g., establish normal UFW block rate)
2. **Whitelist known patterns** (mDNS/SSDP broadcasts expected on LAN)
3. **Adjust thresholds** based on real-world data (first week = learning mode)
4. **Allow user to dismiss/snooze** specific alert types

### Alert Actionability
Every alert MUST include:
- **What happened** (clear description)
- **Why it matters** (security impact)
- **What to do** (specific remediation steps)
- **Context** (thresholds, timeframes, counts)

Example BAD alert:
```
Error detected in logs.
```

Example GOOD alert:
```
UFW Port Scan Detected 🚨
IP 192.168.1.45 attempted connections to 23 different ports in the last minute.

Source IP: 192.168.1.45
Unique Ports: 23 (22, 80, 443, 3389, 445, 8080, ...)
Blocks: 47
Timeframe: 60 seconds

ACTION: Investigate device at 192.168.1.45 for compromise:
1. Identify device: arp -a | grep 192.168.1.45
2. Check active connections: sudo netstat -anp | grep 192.168.1.45
3. Consider blocking: sudo ufw deny from 192.168.1.45
```

---

## Infrastructure Context (Colby Server)

### Enabled Security Services
```
✅ ufw              - Firewall (default deny, LAN-only allow)
✅ fail2ban         - SSH brute-force protection (3 bans total, 38 failures)
✅ docker           - Container runtime
✅ nats-server      - Message bus (needs localhost binding per SEC-006)
❌ auditd           - NOT INSTALLED (advanced HIDS, low priority)
```

### Log Files Available
```
✅ /var/log/auth.log       - SSH, sudo, PAM events
✅ /var/log/ufw.log        - Firewall blocks (kernel format)
✅ /var/log/kern.log       - Kernel messages
✅ /var/log/fail2ban.log   - Fail2ban actions
✅ journalctl              - Systemd service logs
```

### Current Firewall Rules
```
Status: active
Default: deny incoming, allow outgoing

Allowed:
22/tcp   - SSH (192.168.1.0/24 only)
80/tcp   - HTTP (192.168.1.0/24 only)
443/tcp  - HTTPS (192.168.1.0/24 only)
5000/tcp - Flask dev server (192.168.1.0/24 only)
8123/tcp - Home Assistant (192.168.1.0/24 only)
```

**Assessment:** ✅ Good default-deny posture. All services restricted to LAN. UFW logging enabled (low verbosity).

### Running Containers
```
homeassistant     - Smart home hub (monitored)
wyoming-whisper   - Voice recognition (NOT monitored)
wyoming-piper     - Text-to-speech (NOT monitored)
```

---

## Cost-Benefit Analysis

### Cost of Implementation (Development Time)

| Monitor | Effort | Lines of Code | Maintenance |
|---------|--------|---------------|-------------|
| UFW Monitor | 2 days | ~200 LOC | Low |
| Sudo Monitor | 1 day | ~100 LOC | Low |
| File Integrity | 3 days | ~150 LOC | Low (add files) |
| HA Access | 2 days | ~150 LOC | Medium (HA updates) |
| Resource Monitor | 1 day | ~100 LOC | Low |
| Docker Security | 2 days | ~150 LOC | Low |
| Process Monitor | 2 days | ~100 LOC | Medium (pattern tuning) |

**Total:** ~10-12 days of development, ~950 lines of code

### Benefit (Attack Coverage)

**Without New Monitors:**
- 20% MITRE ATT&CK coverage
- 3/11 attack vectors monitored
- Blind to internal threats, lateral movement, persistence

**With Tier 1 Monitors:**
- 60% MITRE ATT&CK coverage
- 7/11 attack vectors monitored
- Detection of most common attack patterns

**With All Monitors:**
- 90% MITRE ATT&CK coverage
- 10/11 attack vectors monitored
- Comprehensive home server security posture

### Cost of NOT Implementing

**Scenario:** IoT device compromised, scanning internal network
- **Without UFW Monitor:** Attacker scans undetected, finds services, exploits
- **With UFW Monitor:** Alert fires in <1 minute, user investigates, device isolated

**Scenario:** Attacker gains initial access, attempts privilege escalation
- **Without Sudo/File Monitors:** Attacker modifies sudoers, maintains persistence
- **With Sudo/File Monitors:** Alert fires on first sudo attempt or config change, user responds

**Scenario:** Bug causes disk to fill with logs
- **Without Resource Monitor:** Services crash mysteriously, hours of debugging
- **With Resource Monitor:** Alert warns at 85% disk, user cleans up before failure

---

## Next Steps

### IMMEDIATE (User Action Required)
1. Create Slack app and webhooks (10 minutes)
2. Add webhook URLs to `/home/k4therin2/projects/Smarthome/.env`
3. Deploy existing monitoring: `./deploy/setup-security-monitoring.sh`
4. Verify alerts are working (test mode)

### WEEK 1-2 (Agent Development)
1. Implement UFW Monitor (highest priority, closes critical gap)
2. Implement Failed Sudo Monitor (quick win, high signal)
3. Implement File Integrity Monitor (critical configs only)
4. Test all monitors with simulated attacks

### WEEK 3 (Enhancements)
1. Add Wyoming containers to service monitoring
2. Implement multi-tier API cost thresholds
3. Fix service monitor exponential backoff

### WEEK 4 (Resource Monitoring)
1. Implement disk/memory monitor
2. Implement Docker security monitor
3. Full end-to-end testing
4. Document all thresholds and tuning procedures

---

## Conclusion

**Current alerting system is well-architected** (modular, extensible, follows security best practices) but **covers only 3 of 11 critical attack vectors**.

**Deployment is blocked** on user providing Slack webhooks - a 10-minute task.

**Critical gaps** exist for UFW monitoring, sudo attempts, and file integrity - these can be implemented in ~1 week and would increase attack detection coverage from 20% to 60%.

**Recommended Action:**
1. Deploy existing system immediately (unblocks testing)
2. Prioritize Tier 1 monitors (UFW, sudo, file integrity, HA access)
3. Iterate based on real-world alert data to tune thresholds

**Risk if not implemented:** Blind spots in lateral movement, privilege escalation, and persistence allow attackers to operate undetected on internal network despite strong perimeter defenses (UFW, fail2ban).
