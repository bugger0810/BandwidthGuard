# Third-party software

BandwidthGuard itself is released under the [MIT License](LICENSE).
It uses the following open-source components. Please refer to each project for
the full license text.

| Component | Purpose | License |
|-----------|---------|---------|
| [Qt for Python (PySide6)](https://www.qt.io/qt-for-python) | User interface | LGPL-3.0 |
| [WinDivert](https://reqrypt.org/windivert.html) | Windows packet capture driver | LGPL-3.0 / GPL-2.0 |
| [pydivert](https://github.com/ffalcinelli/pydivert) | Python bindings for WinDivert (ships a WinDivert build) | LGPL-3.0 |
| [psutil](https://github.com/giampaolo/psutil) | Process and connection information | BSD-3-Clause |
| [PyInstaller](https://pyinstaller.org/) | Packaging into an .exe | GPL-2.0 with bootloader exception |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Installer | Inno Setup License |

**LGPL note:** The Windows build is deliberately a *folder* ("one-dir") build, not a single-file
executable. Qt and WinDivert therefore remain separate, replaceable library files next to
`BandwidthGuard.exe`, as the LGPL requires.
