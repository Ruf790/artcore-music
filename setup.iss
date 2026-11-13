; ArtCore Music installer — Inno Setup 6.3+
; Build: run build.bat (libmpv + PyInstaller first, then this script).
; Expects the PyInstaller output in dist\ArtCoreMusic\.

#define AppName      "ArtCore Music"
#define AppVersion   "1.1.0"
#define AppPublisher "ArtCore"
#define AppURL       "https://github.com/Ruf790/artcore-music"
#define AppExe       "ArtCoreMusic.exe"
#define ProgId       "ArtCoreMusic.audio"
#define ProgIdList   "ArtCoreMusic.playlist"
#define CapKey       "Software\ArtCore\ArtCore Music\Capabilities"

[Setup]
; Never change AppId: Windows uses it to find the installed copy for updates/uninstall
AppId={{713130CD-51C0-4789-A4C1-FF81BED0DAE9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=installer
OutputBaseFilename=ArtCoreMusic-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
AppCopyright=Copyright (C) 2026 Ruf790 — GNU GPL v3
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex=ArtCoreMusicMutex
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
ShowLanguageDialog=auto
UsedUserAreasWarning=no

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ru.GroupIntegration=Интеграция с Windows:
en.GroupIntegration=Windows integration:
ru.OpenWith=Добавить в «Открыть с помощью» для аудиофайлов, .cue и .m3u
en.OpenWith=Add to "Open with" for audio files, .cue and .m3u
ru.FolderMenu=Пункты «Воспроизвести / Добавить в ArtCore Music» в меню папок
en.FolderMenu="Play / Add to ArtCore Music" in the folder menu
ru.AudioFile=Аудиофайл
en.AudioFile=Audio file
ru.PlaylistFile=Плейлист
en.PlaylistFile=Playlist
ru.PlayIn=Воспроизвести в ArtCore Music
en.PlayIn=Play in ArtCore Music
ru.AddTo=Добавить в ArtCore Music
en.AddTo=Add to ArtCore Music
ru.MakeDefault=Сделать плеером по умолчанию (откроются Параметры Windows)
en.MakeDefault=Make it the default player (opens Windows Settings)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "openwith";    Description: "{cm:OpenWith}";          GroupDescription: "{cm:GroupIntegration}"
Name: "foldermenu";  Description: "{cm:FolderMenu}";        GroupDescription: "{cm:GroupIntegration}"

[Files]
Source: "dist\ArtCoreMusic\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "THIRD-PARTY.md"; DestDir: "{app}"; DestName: "THIRD-PARTY.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "ArtCore.Music"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; HKA = HKLM for "all users", HKCU for "just me"
; ── the file types the player offers (never forced on the user: Windows asks / Settings → Apps → Default apps)
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "{cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgIdList}"; ValueType: string; ValueName: ""; ValueData: "{cm:PlaylistFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgIdList}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgIdList}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Audio player (mpv): FLAC, DSD, 5.1, CUE"; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "{#CapKey}"; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4b\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m4b"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m4b"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.alac\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".alac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".alac"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ogg"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.oga\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".oga"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".oga"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".opus"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wav"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wv\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wv"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wv"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ape\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ape"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ape"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dsf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dsf"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dsf"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dff\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dff"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dff"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wma"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aif\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aif"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aif"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aiff\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aiff"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aiff"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aifc\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aifc"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aifc"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ac3\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ac3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ac3"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.eac3\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".eac3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".eac3"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ec3\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ec3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ec3"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dts\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dts"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dts"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dtshd\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dtshd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dtshd"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.thd\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".thd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".thd"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.truehd\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".truehd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".truehd"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mlp\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mlp"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mlp"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mka\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mka"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mka"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tak\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".tak"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".tak"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tta\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".tta"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".tta"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mpc\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mpc"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mpc"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp2\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mp2"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mp2"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.spx\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".spx"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".spx"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.caf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".caf"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".caf"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.w64\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".w64"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".w64"; ValueData: "{#ProgId}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u\OpenWithProgids"; ValueType: string; ValueName: "{#ProgIdList}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m3u"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m3u"; ValueData: "{#ProgIdList}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u8\OpenWithProgids"; ValueType: string; ValueName: "{#ProgIdList}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m3u8"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m3u8"; ValueData: "{#ProgIdList}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.cue\OpenWithProgids"; ValueType: string; ValueName: "{#ProgIdList}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".cue"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".cue"; ValueData: "{#ProgIdList}"; Tasks: openwith
; ── folders: «Play in / Add to ArtCore Music»
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.play"; ValueType: string; ValueName: ""; ValueData: "{cm:PlayIn}"; Flags: uninsdeletekey; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.play"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.play\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.add"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Flags: uninsdeletekey; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.add"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ArtCoreMusic.add\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: foldermenu

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; silent update from the player itself: start it again afterwards
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; Check: WizardSilent
Filename: "ms-settings:defaultapps?registeredAppUser={#AppName}"; Description: "{cm:MakeDefault}"; Flags: shellexec nowait postinstall skipifsilent unchecked; Tasks: openwith

[UninstallDelete]
; Settings and the playlist in %APPDATA%\ArtCoreMusic are kept on purpose.
Type: filesandordirs; Name: "{app}"
