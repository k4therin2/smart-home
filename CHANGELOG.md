# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Log Viewer UI with filtering, search, and export (WP-6.1)
- CI/CD Pipeline with GitHub Actions (WP-6.2)
- Pre-commit hooks for code quality
- Ruff linter configuration

## [0.5.0] - 2025-12-18

### Added
- Phase 5: Self-Monitoring & Intelligence
  - Continuous Improvement System (WP-5.5)
  - Self-Healing Infrastructure (WP-5.4)
  - Time & Date Query Capabilities (WP-3.4)

### Changed
- Unified NATS message bus on colby via Tailscale
- Standardized roadmap terminology for agent clarity

### Security
- Added security monitoring and test suite
- Implemented slash commands and agents

## [0.4.0] - 2025-12-15

### Added
- Phase 4: Productivity & Routines
  - Todo Lists & Reminders (WP-4.1)
  - Simple Automation Creation (WP-4.2)
  - Timer & Alarm Management (WP-4.3)

### Changed
- Improved caching system for better performance
- Enhanced device organization

## [0.3.0] - 2025-12-10

### Added
- Phase 3: Advanced Device Integration
  - Spotify Integration
  - Location-Aware Features
  - Music Education Context

### Changed
- Improved blinds integration
- Enhanced voice control capabilities

## [0.2.0] - 2025-12-05

### Added
- Phase 2: Security & Device Integration
  - Application Security Baseline
  - HTTPS/TLS Configuration
  - Vacuum Control (Dreame)

### Security
- Implemented Flask-Login authentication
- Added CSRF protection
- Rate limiting on all endpoints

## [0.1.0] - 2025-12-01

### Added
- Initial release
- Natural language command processing with Claude Sonnet 4
- Philips Hue light control
- Web UI with mobile optimization
- Voice input support (Web Speech API)
- PWA capabilities with service worker

[Unreleased]: https://github.com/username/smarthome/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/username/smarthome/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/username/smarthome/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/username/smarthome/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/username/smarthome/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/username/smarthome/releases/tag/v0.1.0
