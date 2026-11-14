; ArtCore Music installer — Inno Setup 6.3+
; Build: run build.bat (libmpv + PyInstaller first, then this script).
; Expects the PyInstaller output in dist\ArtCoreMusic\.

#define AppName      "ArtCore Music"
#define AppVersion   "1.6.0"
#define AppPublisher "ArtCore"
#define AppURL       "https://github.com/Ruf790/artcore-music"
#define AppExe       "ArtCoreMusic.exe"
#define OldProg      "ArtCoreMusic.audio"
#define OldProgList  "ArtCoreMusic.playlist"
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
ru.OpenWith=Добавить в «Открыть с помощью» для аудиофайлов, .cue, .m3u и .pls
en.OpenWith=Add to "Open with" for audio files, .cue, .m3u and .pls
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
Source: "assets\formats\*.ico"; DestDir: "{app}\formats"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "ArtCore.Music"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; HKA = HKLM for "all users", HKCU for "just me"
; ── the file types the player offers (never forced on the user: Windows asks / Settings → Apps → Default apps)
; every format has its own ProgId and its own icon ({app}\formats\<ext>.ico, tools/make_format_icons.py);
; the shared ProgIds of 1.0–1.3 are removed
Root: HKA; Subkey: "Software\Classes\{#OldProg}"; ValueType: none; Flags: deletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#OldProgList}"; ValueType: none; Flags: deletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Audio player (mpv): FLAC, DSD, 5.1, CUE"; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\{#AppExe}"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "{#CapKey}"; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp3"; ValueType: string; ValueName: ""; ValueData: "MP3 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\mp3.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp3\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp3\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.mp3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "ArtCoreMusic.mp3"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.flac"; ValueType: string; ValueName: ""; ValueData: "FLAC — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.flac\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\flac.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.flac\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.flac\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.flac\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.flac"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "ArtCoreMusic.flac"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4a"; ValueType: string; ValueName: ""; ValueData: "M4A — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4a\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\m4a.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4a\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4a\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4a\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.m4a"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "ArtCoreMusic.m4a"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4b"; ValueType: string; ValueName: ""; ValueData: "M4B — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4b\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\m4b.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4b\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4b\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m4b\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4b\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4b\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.m4b"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m4b"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m4b"; ValueData: "ArtCoreMusic.m4b"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.alac"; ValueType: string; ValueName: ""; ValueData: "ALAC — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.alac\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\alac.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.alac\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.alac\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.alac\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.alac\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.alac\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.alac"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".alac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".alac"; ValueData: "ArtCoreMusic.alac"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aac"; ValueType: string; ValueName: ""; ValueData: "AAC — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aac\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\aac.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aac\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aac\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aac\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.aac"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aac"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "ArtCoreMusic.aac"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ogg"; ValueType: string; ValueName: ""; ValueData: "OGG — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ogg\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\ogg.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ogg\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ogg\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ogg\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.ogg"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ogg"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "ArtCoreMusic.ogg"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.oga"; ValueType: string; ValueName: ""; ValueData: "OGA — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.oga\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\oga.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.oga\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.oga\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.oga\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.oga\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.oga\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.oga"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".oga"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".oga"; ValueData: "ArtCoreMusic.oga"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.opus"; ValueType: string; ValueName: ""; ValueData: "OPUS — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.opus\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\opus.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.opus\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.opus\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.opus\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.opus"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".opus"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "ArtCoreMusic.opus"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wav"; ValueType: string; ValueName: ""; ValueData: "WAV — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wav\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\wav.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wav\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wav\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wav\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.wav"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wav"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "ArtCoreMusic.wav"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wv"; ValueType: string; ValueName: ""; ValueData: "WV — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wv\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\wv.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wv\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wv\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wv\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wv\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wv\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.wv"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wv"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wv"; ValueData: "ArtCoreMusic.wv"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ape"; ValueType: string; ValueName: ""; ValueData: "APE — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ape\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\ape.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ape\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ape\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ape\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ape\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ape\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.ape"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ape"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ape"; ValueData: "ArtCoreMusic.ape"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dsf"; ValueType: string; ValueName: ""; ValueData: "DSF — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dsf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\dsf.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dsf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dsf\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dsf\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dsf\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dsf\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.dsf"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dsf"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dsf"; ValueData: "ArtCoreMusic.dsf"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dff"; ValueType: string; ValueName: ""; ValueData: "DFF — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dff\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\dff.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dff\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dff\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dff\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dff\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dff\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.dff"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dff"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dff"; ValueData: "ArtCoreMusic.dff"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wma"; ValueType: string; ValueName: ""; ValueData: "WMA — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wma\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\wma.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wma\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wma\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.wma\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.wma"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".wma"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "ArtCoreMusic.wma"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aif"; ValueType: string; ValueName: ""; ValueData: "AIFF — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aif\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\aif.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aif\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aif\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aif\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aif\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aif\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.aif"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aif"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aif"; ValueData: "ArtCoreMusic.aif"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aiff"; ValueType: string; ValueName: ""; ValueData: "AIFF — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aiff\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\aiff.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aiff\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aiff\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aiff\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aiff\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aiff\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.aiff"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aiff"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aiff"; ValueData: "ArtCoreMusic.aiff"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aifc"; ValueType: string; ValueName: ""; ValueData: "AIFC — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aifc\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\aifc.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aifc\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aifc\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.aifc\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aifc\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.aifc\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.aifc"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".aifc"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".aifc"; ValueData: "ArtCoreMusic.aifc"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ac3"; ValueType: string; ValueName: ""; ValueData: "AC3 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ac3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\ac3.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ac3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ac3\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ac3\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ac3\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ac3\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.ac3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ac3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ac3"; ValueData: "ArtCoreMusic.ac3"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.eac3"; ValueType: string; ValueName: ""; ValueData: "EAC3 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.eac3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\eac3.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.eac3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.eac3\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.eac3\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.eac3\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.eac3\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.eac3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".eac3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".eac3"; ValueData: "ArtCoreMusic.eac3"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ec3"; ValueType: string; ValueName: ""; ValueData: "EC3 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ec3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\ec3.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ec3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ec3\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.ec3\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ec3\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ec3\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.ec3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".ec3"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".ec3"; ValueData: "ArtCoreMusic.ec3"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dts"; ValueType: string; ValueName: ""; ValueData: "DTS — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dts\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\dts.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dts\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dts\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dts\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dts\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dts\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.dts"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dts"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dts"; ValueData: "ArtCoreMusic.dts"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dtshd"; ValueType: string; ValueName: ""; ValueData: "DTS-HD — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dtshd\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\dtshd.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dtshd\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dtshd\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.dtshd\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dtshd\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dtshd\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.dtshd"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".dtshd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".dtshd"; ValueData: "ArtCoreMusic.dtshd"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.thd"; ValueType: string; ValueName: ""; ValueData: "THD — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.thd\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\thd.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.thd\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.thd\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.thd\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.thd\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.thd\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.thd"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".thd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".thd"; ValueData: "ArtCoreMusic.thd"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.truehd"; ValueType: string; ValueName: ""; ValueData: "TrueHD — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.truehd\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\truehd.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.truehd\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.truehd\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.truehd\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.truehd\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.truehd\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.truehd"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".truehd"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".truehd"; ValueData: "ArtCoreMusic.truehd"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mlp"; ValueType: string; ValueName: ""; ValueData: "MLP — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mlp\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\mlp.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mlp\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mlp\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mlp\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mlp\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mlp\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.mlp"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mlp"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mlp"; ValueData: "ArtCoreMusic.mlp"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mka"; ValueType: string; ValueName: ""; ValueData: "MKA — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mka\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\mka.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mka\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mka\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mka\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mka\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mka\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.mka"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mka"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mka"; ValueData: "ArtCoreMusic.mka"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tak"; ValueType: string; ValueName: ""; ValueData: "TAK — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tak\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\tak.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tak\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tak\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tak\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tak\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tak\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.tak"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".tak"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".tak"; ValueData: "ArtCoreMusic.tak"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tta"; ValueType: string; ValueName: ""; ValueData: "TTA — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tta\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\tta.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tta\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tta\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.tta\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tta\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tta\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.tta"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".tta"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".tta"; ValueData: "ArtCoreMusic.tta"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mpc"; ValueType: string; ValueName: ""; ValueData: "MPC — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mpc\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\mpc.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mpc\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mpc\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mpc\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mpc\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mpc\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.mpc"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mpc"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mpc"; ValueData: "ArtCoreMusic.mpc"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp2"; ValueType: string; ValueName: ""; ValueData: "MP2 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp2\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\mp2.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp2\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp2\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.mp2\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp2\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mp2\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.mp2"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mp2"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".mp2"; ValueData: "ArtCoreMusic.mp2"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.spx"; ValueType: string; ValueName: ""; ValueData: "SPX — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.spx\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\spx.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.spx\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.spx\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.spx\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.spx\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.spx\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.spx"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".spx"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".spx"; ValueData: "ArtCoreMusic.spx"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.caf"; ValueType: string; ValueName: ""; ValueData: "CAF — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.caf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\caf.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.caf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.caf\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.caf\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.caf\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.caf\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.caf"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".caf"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".caf"; ValueData: "ArtCoreMusic.caf"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.w64"; ValueType: string; ValueName: ""; ValueData: "W64 — {cm:AudioFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.w64\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\w64.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.w64\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.w64\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.w64\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.w64\OpenWithProgids"; ValueType: none; ValueName: "{#OldProg}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.w64\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.w64"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".w64"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".w64"; ValueData: "ArtCoreMusic.w64"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u"; ValueType: string; ValueName: ""; ValueData: "M3U — {cm:PlaylistFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\m3u.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u\OpenWithProgids"; ValueType: none; ValueName: "{#OldProgList}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.m3u"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m3u"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m3u"; ValueData: "ArtCoreMusic.m3u"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u8"; ValueType: string; ValueName: ""; ValueData: "M3U8 — {cm:PlaylistFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u8\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\m3u8.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u8\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u8\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.m3u8\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u8\OpenWithProgids"; ValueType: none; ValueName: "{#OldProgList}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m3u8\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.m3u8"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".m3u8"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".m3u8"; ValueData: "ArtCoreMusic.m3u8"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.pls"; ValueType: string; ValueName: ""; ValueData: "PLS — {cm:PlaylistFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.pls\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\pls.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.pls\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.pls\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.pls\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.pls\OpenWithProgids"; ValueType: none; ValueName: "{#OldProgList}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.pls\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.pls"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pls"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".pls"; ValueData: "ArtCoreMusic.pls"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.cue"; ValueType: string; ValueName: ""; ValueData: "CUE — {cm:PlaylistFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.cue\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\formats\cue.ico"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.cue\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.cue\shell\enqueue"; ValueType: string; ValueName: ""; ValueData: "{cm:AddTo}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\ArtCoreMusic.cue\shell\enqueue\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --add ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.cue\OpenWithProgids"; ValueType: none; ValueName: "{#OldProgList}"; Flags: deletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.cue\OpenWithProgids"; ValueType: string; ValueName: "ArtCoreMusic.cue"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".cue"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "{#CapKey}\FileAssociations"; ValueType: string; ValueName: ".cue"; ValueData: "ArtCoreMusic.cue"; Tasks: openwith
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
