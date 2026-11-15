<div align="center">

<img src="src/bandwidthguard/assets/icon.png" width="110" alt="BandwidthGuard logo">

# BandwidthGuard

**Limit and monitor the bandwidth of individual programs on Windows.**

[![CI](https://github.com/bugger0810/BandwidthGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/bugger0810/BandwidthGuard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4)

English · [Deutsch](README.de.md)

</div>

> 🤖 **Vibe-coded.** This project was created entirely through AI-assisted "vibe coding" with
> [Claude](https://www.anthropic.com/claude) by Anthropic. The code is commented and open for review –
> feedback and pull requests are very welcome.

<!-- Add a screenshot: save it as docs/screenshot.png and uncomment the next line
![BandwidthGuard screenshot](docs/screenshot.png)
-->

## Why?

Windows can only throttle *upload* traffic per program out of the box. BandwidthGuard
fills the gap: pick a program, set a limit such as **13 Mbit/s** on your 16 Mbit/s line,
and the rest of your connection stays free for everything else.

## Features

- 🎯 **Per-program download limit** (Mbit/s or MB/s)
- 📊 **Live traffic monitor** – download/upload speed, totals and a 60-second graph
- 👀 **"Measure only" mode** to see what a program really uses, without limiting it
- 🔎 Program list with **search, icons and connection counts**
- 🌗 Modern interface with **dark / light / system** theme
- 🪟 **System tray** support, optional **autostart with Windows**
- 🌍 **10 languages** – Deutsch, English, Français, Español, Italiano, Nederlands, Polski, Português, Русский, Türkçe
  (the installer and the app default to your Windows language)
- 💾 Remembers your settings

## Installation

1. Download `BandwidthGuard-Setup-<version>.exe` from the [Releases](../../releases) page.
2. Run it, choose your language and follow the wizard.

> **Windows SmartScreen warning?** The installer is not code-signed (certificates cost money), so
> Windows may show "Windows protected your PC". Click **More info → Run anyway**.
> You can inspect the complete source code here and even build the installer yourself.

BandwidthGuard needs **administrator rights** because it uses a packet-filter driver.

## Usage

1. Start BandwidthGuard.
2. Select a program in the list (use the search box; programs without network activity are hidden by default).
3. Enter the limit (e.g. `13`) and pick the unit.
4. Click **Start**. Click **Stop** to return to normal at any time.

Closing the window keeps BandwidthGuard running in the system tray (can be changed in *Settings*).

## How it works

BandwidthGuard uses [WinDivert](https://reqrypt.org/windivert.html) to intercept network packets.
It maps your chosen program to its network ports (via `psutil`), counts the traffic and releases
incoming packets at the configured rate. Excess packets are dropped, which makes TCP slow the
sender down on its own. Details are in [`engine.py`](src/bandwidthguard/engine.py).

## Known limitations

- Accuracy is "good", not "exact": expect a few percent deviation, measured including packet headers.
- A program's new connections are detected within ~0.5 s.
- **Do not use it together with games that have anti-cheat software.** Packet-filter drivers can trigger it.
- Some antivirus programs flag WinDivert-based tools (false positive). Add an exception if needed.
- Windows 10 / 11, 64-bit only.

## Build from source

```bat
git clone https://github.com/bugger0810/BandwidthGuard.git
cd BandwidthGuard
build.bat
```

`build.bat` creates a virtual environment, installs the dependencies, builds the program with
PyInstaller and – if [Inno Setup 6](https://jrsoftware.org/isdl.php) is installed – the setup:
`installer\Output\BandwidthGuard-Setup-<version>.exe`.

To just run it from source: `pip install -r requirements.txt` and `python run.py`.

### Automatic releases

Push a tag like `v1.0.0` and the [release workflow](.github/workflows/release.yml) builds the installer
on GitHub and attaches it to a release. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Settings & uninstall

Settings live in `%APPDATA%\BandwidthGuard\settings.json`. Uninstalling via *Apps & features* removes the
program and the autostart entry; delete that folder as well if you want to remove your settings.

## Translations

Translations were written with AI assistance and are not reviewed by native speakers.
Corrections are very welcome – every language is a single JSON file in
[`src/bandwidthguard/locales`](src/bandwidthguard/locales). See [CONTRIBUTING.md](CONTRIBUTING.md#translations).

## License

[MIT](LICENSE) © 2026 bugger0810. Third-party components: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
