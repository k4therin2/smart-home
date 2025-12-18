# Security Monitoring Quick Reference

## Current Status: 🔴 BLOCKED (Not Deployed)

**Existing Implementation:**
- 3 monitors built (SSH, API Cost, Service Health)
- Code complete in `src/security/monitors.py`
- Systemd services configured
- **BLOCKED ON:** User must create Slack webhooks

---

## Monitor Coverage Matrix

| Attack Vector | Current | Needed | Priority | Effort |
|--------------|---------|--------|----------|--------|
| SSH Brute Force | ✅ Built | Deploy | CRITICAL | User (10 min) |
| API Cost Abuse | ✅ Built | Deploy + tune | CRITICAL | User + 1 day |
| Service Failures | ✅ Built | Deploy + enhance | CRITICAL | User + 1 day |
| Port Scanning | ❌ Missing | UFW Monitor | CRITICAL | 2 days |
| Privilege Escalation | ❌ Missing | Sudo Monitor | CRITICAL | 1 day |
| Persistence/Backdoors | ❌ Missing | File Integrity | CRITICAL | 3 days |
| Unauthorized Access | ❌ Missing | HA Access Monitor | HIGH | 2 days |
| Resource DoS | ❌ Missing | Disk/Memory Monitor | HIGH | 1 day |
| Container Security | ❌ Missing | Docker Monitor | MEDIUM | 2 days |
| Malicious Processes | ❌ Missing | Process Monitor | MEDIUM | 2 days |
| Network Exfiltration | ❌ Missing | Network Monitor | LOW | Defer |

**Current Coverage:** 3/11 (27%)
**With Tier 1 Complete:** 7/11 (64%)

---

## Critical Alerts MISSING

### 1. UFW Firewall Monitoring ⚠️ HIGHEST PRIORITY
**Why:** Detects port scans, lateral movement, compromised IoT devices
**Alert Examples:**
- Port scan: 10+ unique ports from same IP in 1 minute
- External attack: Any non-LAN IP attempting connection
- Compromised device: 20+ blocks from internal IP in 5 minutes

**Implementation:** Parse `/var/log/ufw.log`, track source IPs and destination ports

---

### 2. Failed Sudo Attempts ⚠️ HIGH PRIORITY
**Why:** Privilege escalation attempts = strong attack signal
**Alert Examples:**
- User not in sudoers attempting sudo
- Failed password attempts (once SEC-001 fixed)
- Unauthorized accounts attempting root access

**Implementation:** Parse `/var/log/auth.log` for sudo failures (similar to SSH monitor)

---

### 3. File Integrity (Critical Configs) ⚠️ HIGH PRIORITY
**Why:** Backdoor detection - attackers modify configs for persistence
**Alert Examples:**
- `/etc/sudoers` modified
- SSH authorized_keys changed
- `.env` file altered
- Home Assistant config modified

**Implementation:** Hash-based monitoring of 10-15 critical files

---

### 4. Home Assistant Unauthorized Access ⚠️ HIGH PRIORITY
**Why:** HA controls physical devices, no authentication currently
**Alert Examples:**
- Entity state changes at unusual times
- API rate limiting triggered
- Service calls from unknown sources
- Failed login attempts (once auth implemented)

**Implementation:** Parse HA logs via journalctl, track anomalies

---

### 5. Disk & Memory Exhaustion ⚠️ MEDIUM PRIORITY
**Why:** Prevents service failures, detects DoS attacks or bugs
**Alert Examples:**
- Root filesystem 85% full (warning), 95% critical
- Memory usage >90% for 5 minutes
- Swap usage >50%
- Inodes 90% exhausted

**Implementation:** `shutil.disk_usage()` and `psutil` for system metrics

---

### 6. Docker Container Security ⚠️ MEDIUM PRIORITY
**Why:** Container escapes, resource abuse, crash loops
**Alert Examples:**
- Container restarted 3+ times in 10 minutes
- CPU usage >80% for 5 minutes
- Memory near limit (OOM risk)
- Container running as root

**Implementation:** `docker inspect` and `docker stats` API

---

## Threshold Analysis

### Current Thresholds
| Monitor | Threshold | Assessment | Recommendation |
|---------|-----------|------------|----------------|
| SSH Failed Logins | 5 in 10 min | ✅ Good (matches fail2ban) | Keep |
| API Cost | $5/day | ⚠️ Too high | Add $3 warning tier |
| Service Down Cooldown | 5 min | ⚠️ Too long for persistent failures | Exponential backoff |

### Recommended New Thresholds
| Monitor | Threshold | Rationale |
|---------|-----------|-----------|
| UFW Port Scan | 10 unique ports in 1 min | Industry standard for scan detection |
| UFW External IP | 1 attempt = immediate alert | LAN-only network, all external IPs suspicious |
| Failed Sudo | 1 attempt = immediate alert | Strong signal of compromise |
| File Integrity | ANY change = immediate alert | Critical files should rarely change |
| Disk Usage | 85% warning, 95% critical | Time to clean up before failure |

---

## Implementation Roadmap

### WEEK 0: UNBLOCK (User Action - 10 minutes)
**Deliverables:**
1. Create Slack app at https://api.slack.com/apps
2. Add 3 incoming webhooks (one per channel)
3. Add webhook URLs to `.env`:
   ```bash
   SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/...
   SLACK_COST_WEBHOOK=https://hooks.slack.com/services/...
   SLACK_HEALTH_WEBHOOK=https://hooks.slack.com/services/...
   ```
4. Deploy: `./deploy/setup-security-monitoring.sh`
5. Test: `python -m src.security.daemon --test`

**Done When:** Alerts posting to Slack channels successfully

---

### WEEK 1-2: Tier 1 Monitors (Agent Development)
**Deliverables:**
1. `UFWMonitor` class (2 days)
   - Parse `/var/log/ufw.log`
   - Port scan detection
   - External IP filtering
   - Integration with existing SlackNotifier

2. `SudoMonitor` class (1 day)
   - Reuse SSHMonitor pattern
   - Parse auth.log for sudo failures
   - Alert on unauthorized attempts

3. `FileIntegrityMonitor` class (3 days)
   - SHA-256 hash tracking
   - 10-15 critical files
   - User verification workflow

4. `HomeAssistantMonitor` class (2 days)
   - Parse HA logs via journalctl
   - Anomaly detection baseline
   - Foundation for future auth monitoring

**Done When:** 7/11 attack vectors covered, all Tier 1 monitors in production

---

### WEEK 3: Enhancements (Agent Development)
**Deliverables:**
1. Multi-tier API cost thresholds ($3, $5, $10)
2. Hourly spending projection calculation
3. Add Wyoming containers to service monitor
4. Exponential backoff for service alerts (0, 5, 15, 60 min)

**Done When:** Existing monitors enhanced, alert fatigue reduced

---

### WEEK 4: Resource Monitors (Agent Development)
**Deliverables:**
1. `ResourceMonitor` class (1 day)
   - Disk usage (/, /home, /var/log)
   - Memory usage
   - Inode exhaustion

2. `DockerSecurityMonitor` class (2 days)
   - Container restart loop detection
   - Resource usage per container
   - Security posture checks (root user, privileged mode)

3. `ProcessMonitor` class (2 days)
   - Suspicious process patterns
   - Known malware signatures
   - Unauthorized network listeners

**Done When:** 10/11 attack vectors covered, comprehensive home server monitoring

---

## Attack Detection Coverage

### MITRE ATT&CK Framework Mapping

**Currently Detected (20%):**
- ✅ T1078 - Valid Accounts (SSH brute force)
- ✅ T1485 - Data Destruction (service failures)

**After Tier 1 Implementation (60%):**
- ✅ T1078 - Valid Accounts (SSH + sudo)
- ✅ T1046 - Network Service Scan (UFW port scans)
- ✅ T1021 - Remote Services (UFW lateral movement)
- ✅ T1098 - Account Manipulation (file integrity)
- ✅ T1543 - Create/Modify Service (file integrity)
- ✅ T1548 - Abuse Elevation (sudo monitor)

**After Full Implementation (90%):**
- ✅ All of the above
- ✅ T1190 - Exploit Public App (HA access monitor)
- ✅ T1498 - DoS (resource monitor)
- ✅ T1562 - Impair Defenses (file integrity + process)

**Not Covered (10%):**
- ❌ T1071 - Application Layer Protocol (network anomalies - deferred)

---

## Alert Channel Strategy

### #colby-server-security (High-Severity, Immediate Action Required)
**Current:**
- SSH brute force (5+ attempts in 10 min)

**After Tier 1:**
- SSH brute force
- UFW port scans
- UFW external IP attempts
- Failed sudo attempts
- File integrity violations
- Home Assistant unauthorized access

**Characteristics:**
- CRITICAL alerts only
- Immediate human review required
- Low volume (expect <5/day in normal operation)

---

### #smarthome-costs (Budget Monitoring, Medium Severity)
**Current:**
- API cost >$5/day

**After Enhancements:**
- API cost warning >$3/day
- API cost critical >$5/day
- API cost emergency >$10/day
- Daily spending projections

**Characteristics:**
- Budget control
- Medium urgency (review within hours)
- Moderate volume (1-3/day if over budget)

---

### #smarthome-health (Service Reliability, Medium-Low Severity)
**Current:**
- Service down (home-assistant, nats-server, docker)

**After Full Implementation:**
- Service down alerts (all monitored services)
- Docker container restart loops
- Docker resource exhaustion
- Disk usage warnings
- Memory usage warnings

**Characteristics:**
- Reliability monitoring
- Lower urgency (review within hours/day)
- Moderate volume (expect 5-10/day including warnings)

---

## Example Alerts (What Success Looks Like)

### Security Channel Alert (Critical)
```
🚨 UFW Port Scan Detected
IP 192.168.1.45 attempted connections to 23 different ports in the last minute.

Source IP: 192.168.1.45
Unique Ports: 23 (22, 80, 443, 3389, 445, 8080, 8443, ...)
Total Blocks: 47
Timeframe: 60 seconds

ACTION REQUIRED:
1. Identify device: arp -a | grep 192.168.1.45
2. Check connections: sudo netstat -anp | grep 192.168.1.45
3. If compromised, block: sudo ufw deny from 192.168.1.45
4. Isolate device from network
```

### Cost Channel Alert (Warning)
```
⚠️ API Cost Warning
Daily API cost: $3.50 (75% over $2.00 target)

Current Spend: $3.50
Target: $2.00
Projected EOD: $4.20
Last Hour: $0.75
Requests Today: 142

Threshold: $3.00 warning
Next Alert: $5.00 critical (if reached)
```

### Health Channel Alert (Service Down)
```
🔴 Service Down
home-assistant container has stopped.

Service: home-assistant
Current Status: exited (code 137)
Previous Status: running
Downtime: 2 minutes

ACTION:
1. Check logs: docker logs homeassistant
2. Restart: docker restart homeassistant
3. If OOM (code 137): Check memory usage

Exit Code 137 = Out of Memory killed by kernel
```

---

## Cost-Benefit Summary

**Development Investment:**
- Week 0: User (10 min) + deployment testing (1 hour)
- Week 1-2: Agent (8 days) - Tier 1 monitors
- Week 3: Agent (3 days) - Enhancements
- Week 4: Agent (3 days) - Resource monitors
- **Total:** ~14 days of agent development + 10 min user setup

**Security Improvement:**
- Current: 27% attack vector coverage
- After Tier 1: 64% coverage (+137% improvement)
- After Full: 91% coverage (+237% improvement)

**Operational Benefit:**
- Earlier attack detection (minutes vs. hours/days)
- Prevent service failures (disk full, OOM)
- Budget control (API cost alerts before runaway spending)
- Compliance evidence (security event logging)

**Risk Reduction:**
- **High:** Privilege escalation, lateral movement, persistence
- **Medium:** Resource DoS, container escapes
- **Low:** Sophisticated attacks (network exfiltration, C2)

---

## Next Action: Deploy Existing System

**Waiting On:** User to create Slack webhooks (10 minutes)

**Instructions for User:**
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "Colby Security Alerts", choose your workspace
4. Navigate to "Incoming Webhooks" → Enable
5. Click "Add New Webhook to Workspace"
6. Create 3 webhooks for 3 channels:
   - `#colby-server-security` (or create new channel)
   - `#smarthome-costs` (or create new channel)
   - `#smarthome-health` (or create new channel)
7. Copy each webhook URL
8. Add to `/home/k4therin2/projects/Smarthome/.env`:
   ```bash
   SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/HERE
   SLACK_COST_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/HERE
   SLACK_HEALTH_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/HERE
   ```
9. Run: `cd ~/projects/Smarthome && ./deploy/setup-security-monitoring.sh`
10. Test: `./venv/bin/python -m src.security.daemon --test`

**Expected Result:** Test alerts appear in all 3 Slack channels.

Once deployed, agent can proceed with implementing missing monitors.
