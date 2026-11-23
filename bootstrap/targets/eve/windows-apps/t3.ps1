$ErrorActionPreference = 'Stop'
$executable = Join-Path $env:LOCALAPPDATA 'Programs\t3code\T3 Code (Nightly).exe'
if (Test-Path $executable) {
    $version = (Get-Item $executable).VersionInfo.FileVersion
    if ($version -notmatch '^\d+\.\d+\.\d+-nightly\.\d{8}\.\d+') {
        throw "Expected a nightly T3 Code build at ${executable}, found $version"
    }
    Write-Output "T3 Code: nightly $version already installed; T3 manages updates"
    exit 0
}

$releases = Invoke-RestMethod 'https://api.github.com/repos/pingdotgg/t3code/releases?per_page=100'
$release = $releases | Where-Object { -not $_.draft -and $_.tag_name -match '^v\d+\.\d+\.\d+-nightly\.\d{8}\.\d+$' } |
    Sort-Object { [datetime]$_.published_at } -Descending | Select-Object -First 1
if (-not $release) { throw 'No T3 Code nightly release found' }
$version = $release.tag_name.Substring(1)
$assets = @($release.assets | Where-Object { $_.name -eq "T3-Code-$version-x64.exe" })
if ($assets.Count -ne 1 -or $assets[0].digest -notmatch '^sha256:[a-f0-9]{64}$') {
    throw 'Expected one T3 Code nightly x64 desktop installer with a SHA256 digest'
}
$asset = $assets[0]

$temporary = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $installer = Join-Path $temporary 't3-nightly-setup.exe'
    Write-Output "T3 Code: downloading nightly $version"
    curl.exe --fail --location --silent --show-error --output $installer $asset.browser_download_url
    if ($LASTEXITCODE -ne 0) { throw "T3 Code download failed: $LASTEXITCODE" }
    if ((Get-FileHash -Algorithm SHA256 $installer).Hash -ne $asset.digest.Substring(7)) {
        throw 'T3 Code nightly installer checksum mismatch'
    }
    $process = Start-Process -FilePath $installer -ArgumentList '/S /currentuser' -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "T3 Code installation failed: $($process.ExitCode)" }
    if (-not (Test-Path $executable)) { throw 'T3 Code nightly executable is missing after installation' }
    $installedVersion = (Get-Item $executable).VersionInfo.FileVersion
    if (($installedVersion -split '\+')[0] -ne $version) {
        throw "Expected T3 Code $version after installation, found $installedVersion"
    }
    Write-Output "T3 Code: installed nightly $installedVersion with automatic nightly updates"
}
finally {
    Remove-Item -Recurse -Force $temporary
}
