; ============================================================================
;  BandwidthGuard – Inno Setup script
;  Build:  ISCC.exe /DMyAppVersion=1.0.0 installer\BandwidthGuard.iss
;  (build.bat and the GitHub Actions workflow do this for you)
;  Needs Inno Setup 6.3 or newer: https://jrsoftware.org/isinfo.php
; ============================================================================

#define MyAppName      "BandwidthGuard"
#define MyAppExeName   "BandwidthGuard.exe"
#define MyAppPublisher "bugger0810"
#define MyAppURL       "https://github.com/bugger0810/BandwidthGuard"

; The version normally comes from the command line (/DMyAppVersion=...).
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
; Unique ID of this application (never change it, or updates will install side by side).
AppId={{8B2F5C3E-4A1D-4E7B-9C6A-2D5F7E1A3B90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppCopyright=Copyright (c) 2026 {#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}

; The app needs administrator rights (packet filtering driver), so install for all users.
PrivilegesRequired=admin
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Look and feel
WizardStyle=modern
SetupIconFile=..\src\bandwidthguard\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE

; Language dialog is shown at start; the entry matching the Windows display
; language is preselected automatically.
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage

; Output
OutputDir=Output
OutputBaseFilename=BandwidthGuard-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes

; Refuse to install/uninstall while the program is running (mutex is created by the app).
AppMutex=BandwidthGuardMutex
CloseApplications=yes

; ---------------------------------------------------------------------------
;  Languages. The name ("de", "fr", ...) is also the language code of the app:
;  it is written to install_lang.txt so BandwidthGuard starts in that language.
; ---------------------------------------------------------------------------
[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

; Texts that are not part of Inno Setup's built-in translations.
[CustomMessages]
en.AutostartTask=Start BandwidthGuard with Windows
de.AutostartTask=BandwidthGuard mit Windows starten
fr.AutostartTask=Démarrer BandwidthGuard avec Windows
es.AutostartTask=Iniciar BandwidthGuard con Windows
it.AutostartTask=Avvia BandwidthGuard con Windows
nl.AutostartTask=BandwidthGuard met Windows starten
pl.AutostartTask=Uruchamiaj BandwidthGuard z systemem Windows
tr.AutostartTask=BandwidthGuard'ı Windows ile başlat
pt.AutostartTask=Iniciar o BandwidthGuard com o Windows
ru.AutostartTask=Запускать BandwidthGuard вместе с Windows

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart";   Description: "{cm:AutostartTask}";      GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Everything PyInstaller produced (exe, Qt libraries, WinDivert driver, translations, ...).
Source: "..\dist\BandwidthGuard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Optional autostart: the app registers a scheduled task (runs elevated at logon).
Filename: "{app}\{#MyAppExeName}"; Parameters: "--enable-autostart"; Flags: runhidden waituntilterminated; Tasks: autostart
; Offer to start the program when the wizard finishes.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove the autostart task again (harmless if it was never created).
Filename: "{app}\{#MyAppExeName}"; Parameters: "--disable-autostart"; Flags: runhidden; RunOnceId: "RemoveAutostart"

[UninstallDelete]
Type: files; Name: "{app}\install_lang.txt"

[Code]
{ After the files are copied, remember which language was chosen in the wizard.
  The app reads this file on its first start to pick its own language. }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\install_lang.txt'), ActiveLanguage, False);
end;
