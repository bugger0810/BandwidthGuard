<div align="center">

<img src="src/bandwidthguard/assets/icon.png" width="110" alt="BandwidthGuard Logo">

# BandwidthGuard

**Bandbreite einzelner Programme unter Windows begrenzen und überwachen.**

[English](README.md) · Deutsch

</div>

> 🤖 **Vibe-coded.** Dieses Projekt wurde komplett per KI-gestütztem „Vibe Coding“ mit
> [Claude](https://www.anthropic.com/claude) von Anthropic erstellt. Der Code ist kommentiert und offen
> einsehbar – Feedback und Pull Requests sind willkommen.

## Wozu?

Windows kann pro Programm von Haus aus nur den *Upload* drosseln. BandwidthGuard schließt diese Lücke:
Programm auswählen, Limit setzen (z. B. **13 Mbit/s** bei einer 16-Mbit/s-Leitung) – der Rest deiner
Leitung bleibt für alles andere frei.

## Funktionen

- 🎯 **Download-Limit pro Programm** (Mbit/s oder MB/s)
- 📊 **Live-Traffic-Anzeige** mit Download/Upload, Gesamtmenge und 60-Sekunden-Diagramm
- 👀 **„Nur messen“-Modus**, um zu sehen, was ein Programm wirklich zieht
- 🔎 Programmliste mit **Suche, Icons und Verbindungsanzahl**
- 🌗 Modernes Design mit **Dunkel / Hell / System**
- 🪟 **Infobereich (Tray)** und optionaler **Autostart mit Windows**
- 🌍 **10 Sprachen** (Setup und Programm starten in deiner Windows-Sprache)
- 💾 Einstellungen werden gespeichert

## Installation

1. `BandwidthGuard-Setup-<Version>.exe` von der [Releases](../../releases)-Seite herunterladen.
2. Starten, Sprache wählen, dem Assistenten folgen.

> **SmartScreen-Warnung?** Das Setup ist nicht code-signiert (Zertifikate kosten Geld). Klicke bei
> „Der Computer wurde durch Windows geschützt“ auf **Weitere Informationen → Trotzdem ausführen**.

BandwidthGuard braucht **Administratorrechte**, da es einen Paketfilter-Treiber nutzt.

## Benutzung

1. BandwidthGuard starten und ein Programm in der Liste auswählen.
2. Limit eingeben (z. B. `13`) und Einheit wählen.
3. **Start** klicken. Mit **Stopp** ist sofort wieder alles normal.

Beim Schließen des Fensters läuft das Programm im Infobereich weiter (in den Einstellungen änderbar).

## Bekannte Einschränkungen

- Die Genauigkeit liegt bei wenigen Prozent Abweichung (inkl. Paket-Header).
- **Nicht zusammen mit Spielen mit Anti-Cheat verwenden.**
- Manche Virenscanner melden WinDivert-Tools fälschlich – ggf. Ausnahme hinzufügen.
- Nur Windows 10/11, 64 Bit.

## Selbst bauen

```bat
git clone https://github.com/bugger0810/BandwidthGuard.git
cd BandwidthGuard
build.bat
```

Dafür sind Python 3.10–3.12 und [Inno Setup 6](https://jrsoftware.org/isdl.php) nötig. Das fertige Setup liegt
danach in `installer\Output\`. Alternativ baut GitHub das Setup automatisch, sobald du einen Tag wie `v1.0.0` pushst
(siehe [CONTRIBUTING.md](CONTRIBUTING.md)).

## Einstellungen & Deinstallation

Einstellungen: `%APPDATA%\BandwidthGuard\settings.json`. Die Deinstallation entfernt Programm und Autostart-Eintrag;
den Einstellungsordner kannst du bei Bedarf manuell löschen.

## Lizenz

[MIT](LICENSE) © 2026 bugger0810 · Drittkomponenten: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
