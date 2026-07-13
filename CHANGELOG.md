# Changelog

## 1.0.1b1

- Keep generating `eversolo.zip` as a GitHub release asset.
- Let HACS install release source files instead of the ZIP asset.
- Preserve prerelease support without falling back to commit-only ZIP downloads.

## 1.0.0b1

- Updated development and runtime dependencies for Home Assistant 2026.7 and Python 3.14.
- Added a bounded asynchronous API client with device-status error mapping.
- Reduced polling load by separating real-time playback from slower settings.
- Added dynamic model capabilities and preserved device-provided I/O indexes and tags.
- Fixed unmute, source refresh, UTC media position timestamps, and Wake-on-LAN ports.
- Moved runtime state to ConfigEntry.runtime_data.
- Added unique device configuration, reconfiguration, mDNS discovery, and standby options.
- Added repeat, shuffle, rich audio metadata, artwork proxying, queue browsing, favorites, playlists, and library search.
- Added dynamic streaming-app discovery, app icons, remote launch, and the Eversolo cross-service favorites launcher.
- Added diagnostics, English/French translations, entity icons, and local light/dark brand assets.
- Disabled redundant legacy command buttons by default while preserving unique IDs.
- Added Ruff formatting, grouped Dependabot updates, and an initial API test suite.
