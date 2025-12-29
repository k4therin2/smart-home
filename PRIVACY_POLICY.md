# SmartHome Privacy Policy

**Last Updated:** 2025-12-29

This Privacy Policy describes how the SmartHome assistant system ("the System") collects, uses, and protects your personal information.

## Overview

SmartHome is a **self-hosted, privacy-focused** smart home assistant designed as an open-source alternative to commercial voice assistants. The system is designed with privacy as a core principle:

- **Local-first**: All user data is stored locally on your hardware
- **Minimal cloud dependencies**: Only essential third-party services are used
- **No telemetry**: No usage data is sent to the project developers
- **Open source**: Full code transparency

---

## Data We Collect

### 1. Device Registry
- **What**: Device names, entity IDs, room assignments, capabilities
- **Why**: To control your smart home devices
- **Storage**: Local SQLite database (`data/smarthome.db`)
- **Retention**: Permanent until you delete the database

### 2. Command History
- **What**: Voice and text commands you issue, results, response times
- **Why**: To provide command history, track costs, and improve reliability
- **Storage**: Local SQLite database
- **Retention**: Permanent unless you clear history

### 3. API Usage Statistics
- **What**: Token counts, request counts, costs per day/model
- **Why**: Cost tracking and budget alerts
- **Storage**: Local SQLite database
- **Retention**: Permanent unless you clear usage data

### 4. Device State History
- **What**: Snapshots of device states over time
- **Why**: To show trends and patterns in device usage
- **Storage**: Local SQLite database
- **Retention**: Configurable (default: 30 days)

### 5. System Settings
- **What**: User preferences, configuration options
- **Why**: To remember your preferences
- **Storage**: Local SQLite database and `.env` file
- **Retention**: Permanent until changed

---

## Third-Party Data Sharing

SmartHome integrates with the following third-party services. Data is only shared when you use these features:

### OpenAI API
- **What's shared**: Your voice/text commands are sent to OpenAI's API for natural language processing
- **Why**: To interpret commands and generate responses
- **OpenAI's privacy**: [OpenAI Privacy Policy](https://openai.com/privacy/)
- **Note**: OpenAI does NOT train on API data (see their terms)

### Spotify API (Optional)
- **What's shared**: Music playback commands, playlist requests
- **Why**: To control music via voice commands
- **Spotify's privacy**: [Spotify Privacy Policy](https://www.spotify.com/legal/privacy-policy/)
- **Note**: Requires your Spotify account authorization

### Home Assistant
- **What's shared**: Device commands sent to your Home Assistant instance
- **Why**: To control devices via the HA API
- **Note**: Home Assistant runs locally on your network

### Slack Webhooks (Optional)
- **What's shared**: System alerts (cost warnings, health status)
- **Why**: To notify you of system events
- **Note**: Only enabled if you configure Slack integration

---

## Data We Do NOT Collect

- No audio recordings are permanently stored
- No personally identifiable information (name, email, etc.) is required
- No browsing history or app usage is tracked
- No data is sold or shared for advertising
- No analytics or telemetry is sent to project developers

---

## Data Security

### Local Storage
- All data is stored in SQLite databases on your local machine
- Database files are created with standard filesystem permissions
- Encryption at rest is available via filesystem encryption (LUKS, FileVault)

### API Key Security
- API keys are stored in environment variables (`.env` file)
- Never committed to version control (`.gitignore`)
- Keys are transmitted over HTTPS

### Network Security
- All API communications use HTTPS/TLS encryption
- Home Assistant connection uses your local network
- No ports are exposed to the internet by default

---

## Your Rights

### Access
You can access all your data directly in the SQLite database or via the web UI.

### Export
Use the `/api/export` endpoint to download all your data in JSON or CSV format.

### Deletion
- Delete individual command history via the database or API
- Delete all data by removing the `data/smarthome.db` file
- Revoke third-party access by removing API keys from `.env`

### Modification
All settings can be modified via the web UI or by editing configuration files.

---

## Data Retention Defaults

| Data Type | Default Retention | Configurable |
|-----------|------------------|--------------|
| Command History | Permanent | Yes (via database) |
| Device States | 30 days | Yes |
| API Usage Stats | Permanent | Yes (via database) |
| Settings | Permanent | N/A |

---

## Children's Privacy

SmartHome does not knowingly collect information from children under 13. As a self-hosted system, parental controls are your responsibility.

---

## Changes to This Policy

We may update this Privacy Policy as the system evolves. Material changes will be noted in the CHANGELOG.

---

## Contact

For privacy concerns related to this open-source project:
- GitHub Issues: https://github.com/k4therin2/smarthome/issues
- Security issues: Use GitHub's private vulnerability reporting

---

## Summary

| Question | Answer |
|----------|--------|
| Is my data stored locally? | Yes, all data is on your machine |
| Is data sold to third parties? | No, never |
| Can I delete my data? | Yes, fully within your control |
| Is telemetry collected? | No telemetry to developers |
| What cloud services are used? | OpenAI, Spotify (optional), Slack (optional) |
| Is my data encrypted? | In transit (HTTPS), at rest (your choice) |
