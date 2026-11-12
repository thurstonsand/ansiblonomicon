$ErrorActionPreference = 'Stop'
$package = Get-AppxPackage -Name 'com.ampcode.amp.windows'
if ($package) {
    Write-Output "Amp desktop: $($package.Version) already installed; App Installer manages updates"
    exit 0
}

$temporary = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $installer = Join-Path $temporary 'Amp.appinstaller'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://static.ampcode.com/windows/Amp.appinstaller' -OutFile $installer
    Add-AppxPackage -AppInstallerFile $installer
    $package = Get-AppxPackage -Name 'com.ampcode.amp.windows'
    if (-not $package) { throw 'Amp desktop package is missing after installation' }
    Write-Output "Amp desktop: installed $($package.Version) with automatic updates"
}
finally {
    Remove-Item -Recurse -Force $temporary
}
