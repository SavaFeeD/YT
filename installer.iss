#ifndef MyAppVersion
  #error Pass /DMyAppVersion=<VERSION> or use build.py
#endif

#ifndef MyAppIconName
  #define MyAppIconName "YT.ico"
#endif

[Setup]
AppId={{07D9D7A3-FEB7-48DB-99C3-11EDD91D2DC8}
AppName=YT
AppVersion={#MyAppVersion}
AppPublisher=YT
DefaultDirName={localappdata}\Programs\YT
DefaultGroupName=YT
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=YT-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=public\favicon.ico
UninstallDisplayIcon={app}\YT.exe
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; Flags: checkedonce

[Files]
Source: "dist\YT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "public\favicon.ico"; DestDir: "{app}\icons"; DestName: "{#MyAppIconName}"; Flags: ignoreversion

[Icons]
Name: "{group}\YT"; Filename: "{app}\YT.exe"; IconFilename: "{app}\icons\{#MyAppIconName}"; IconIndex: 0
Name: "{autodesktop}\YT"; Filename: "{app}\YT.exe"; IconFilename: "{app}\icons\{#MyAppIconName}"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\YT.exe"; Description: "Запустить YT"; Flags: nowait postinstall skipifsilent
