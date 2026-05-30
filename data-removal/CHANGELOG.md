# Changelog

## [1.0.1] - 2026-05-30

### Changed
- User profiles are now managed entirely through the web UI — personal info fields removed from addon configuration
- `seed_default_user()` is a no-op; first-run shows a prompt to add a profile via the dashboard

### Added
- Optional web UI password (`web_password` addon config option) — leave blank for open access
- Lock button in the navbar when password protection is enabled
- Refresh button on the dashboard findings table
- Addon icon — dark navy shield with teal keyhole

### Fixed
- Removed env-var fallbacks for personal info; all user data lives in the database

## [1.0.0] - 2026-05-30

### Added
- Initial release as a Home Assistant addon
- Monitor 35 data broker sites for personal information
- Automated opt-out requests with progress tracking
- Multi-user support — each person gets separate scan history
- Live scan progress bar
- Site enable/disable toggle
- Copy-to-clipboard for generated email opt-out templates
- Site edit form for maintaining opt-out URLs
- Add custom sites via the web dashboard
- Persistent data storage in /data across addon restarts
- All personal data stays local — never sent externally
