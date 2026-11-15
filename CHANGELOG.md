# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/), versions follow [SemVer](https://semver.org/).

## [1.0.1]

### Added
- **Limit several programs at the same time**, each with its own independent limit, live speed,
  totals and graph ("Active limits" list). A limit can be changed on the fly ("Update limit").
- Programs with an active limit are highlighted in the program list.

### Changed
- The tray tooltip shows the combined speed of all active limits; the tray menu stops all limits at once.

### Fixed
- Controls (limit field, unit buttons, Start button, ...) could be cut off right after opening the window.
  The window now never gets smaller than its content needs.
- Windows notifications showed "bugger0810.BandwidthGuard" as the app name; they now show "BandwidthGuard".

## [1.0.0] – Initial release

### Added
- Limit the **download speed of a single program** (e.g. 13 Mbit/s on a 16 Mbit/s line).
- Live **traffic monitor** (download / upload, totals, 60-second graph); "measure only" mode.
- Modern Qt interface with **dark / light / system** theme.
- Program list with search, icons and connection counts.
- **System tray** icon; optional "keep running when the window is closed".
- **Autostart with Windows** (via an elevated scheduled task – no UAC prompt at logon).
- **10 languages**: DE, EN, FR, ES, IT, NL, PL, TR, PT, RU. Default follows Windows.
- Settings are remembered between runs.
- Windows installer (Inno Setup) with language selection and optional desktop icon / autostart.
- GitHub Actions workflows for CI and automatic release builds.
