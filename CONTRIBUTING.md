# Contributing

Thanks for your interest! Bug reports, translation fixes and pull requests are welcome.

## Development setup

```bat
git clone https://github.com/bugger0810/BandwidthGuard.git
cd BandwidthGuard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python run.py          :: asks for administrator rights (needed for WinDivert)
```

Run the checks before opening a pull request:

```bat
python tools\check_locales.py
python -m pytest
```

## Project layout

| Path | Content |
|------|---------|
| `src/bandwidthguard/engine.py` | Packet capture, measuring and throttling (no GUI code) |
| `src/bandwidthguard/main_window.py` | Main window, tray icon |
| `src/bandwidthguard/dialogs.py` | Settings and About dialogs |
| `src/bandwidthguard/widgets.py` | Custom widgets: switch, graph |
| `src/bandwidthguard/theme.py` | Dark / light palettes and stylesheet |
| `src/bandwidthguard/i18n.py`, `locales/*.json` | Translations |
| `src/bandwidthguard/autostart.py` | Autostart via scheduled task |
| `installer/BandwidthGuard.iss` | Inno Setup script |
| `tools/` | Build and maintenance scripts |

## Translations

Every language is one flat JSON file in `src/bandwidthguard/locales/`.

**Fix a translation:** edit the text in `<code>.json` and open a pull request.
Keep placeholders such as `{name}` or `{limit}` exactly as they are.

**Add a language:**
1. Copy `en.json` to `<code>.json` (e.g. `sv.json`) and translate the values.
2. Add the language to `LANGUAGES` in `src/bandwidthguard/i18n.py`
   (and to `_PRIMARY_LANG_IDS` if you want Windows language auto-detection).
3. Add a `[Languages]` line and an `AutostartTask` text in `installer/BandwidthGuard.iss`.
4. Run `python tools\check_locales.py`.

## Releasing (maintainers)

1. Update `__version__` in `src/bandwidthguard/__init__.py` and add an entry to `CHANGELOG.md`.
2. Commit, then create and push a tag: `git tag v1.0.1 && git push origin v1.0.1`.
3. The *Build & Release* workflow builds `BandwidthGuard-Setup-<version>.exe` and attaches it to a GitHub Release.

## Code style

Plain, well-commented Python. Explain the *why* in comments, keep functions small,
and keep GUI code and engine code separate.
