$ErrorActionPreference = 'Stop'
$release = Invoke-RestMethod 'https://api.github.com/repos/vitoplantamura/MagicTrackpad2ForWindows/releases/latest'
$assets = @($release.assets | Where-Object { $_.name -match '^MT2FW11-\d+-MSSigned\.zip$' })
if ($assets.Count -ne 1 -or $assets[0].digest -notmatch '^sha256:[a-f0-9]{64}$') {
    throw 'Expected one Microsoft-signed Windows 11 archive with a SHA256 digest in the latest release'
}
$asset = $assets[0]
$sha256 = $asset.digest.Substring(7)

function Test-DriverInstalled {
    [xml]$drivers = pnputil.exe /enum-drivers /class HIDClass /format xml
    if ($LASTEXITCODE -ne 0) { throw "Driver enumeration failed: $LASTEXITCODE" }
    return [bool]($drivers.SelectNodes('/PnpUtil/Driver') | Where-Object {
        $_.OriginalName -eq 'amtptpdevice.inf' -and
        $_.ProviderName -eq 'Bingxing Wang, Vito Plantamura' -and
        ($_.DriverVersion -split ' ')[-1] -eq $version
    })
}

$temporary = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $archive = Join-Path $temporary 'driver.zip'
    Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $archive
    if ((Get-FileHash -Algorithm SHA256 $archive).Hash -ne $sha256) {
        throw 'Magic Trackpad archive checksum mismatch'
    }
    Expand-Archive -Path $archive -DestinationPath $temporary
    $catalog = Join-Path $temporary 'AMD64\amtptpdevice.cat'
    $signature = Get-AuthenticodeSignature $catalog
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notlike 'CN=Microsoft Windows Hardware Compatibility Publisher,*') {
        throw 'Magic Trackpad catalog does not have a valid Microsoft signature'
    }
    $inf = Join-Path $temporary 'AMD64\AmtPtpDevice.inf'
    $driverVersion = Select-String -Path $inf -Pattern '^DriverVer\s*=\s*[^,]+,\s*(\d+\.\d+\.\d+\.\d+)\s*$'
    if (@($driverVersion).Count -ne 1) { throw 'Expected one DriverVer in the Magic Trackpad INF' }
    $version = $driverVersion.Matches[0].Groups[1].Value
    # Inspect the driver store, so unplugging the trackpad does not trigger a reinstall.
    if (Test-DriverInstalled) {
        Write-Output "Magic Trackpad: latest release $($release.tag_name), driver $version already installed"
        exit 0
    }
    $process = Start-Process -FilePath "$env:SystemRoot\System32\pnputil.exe" `
        -ArgumentList "/add-driver `"$inf`" /install" -Verb RunAs -Wait -PassThru
    if ($process.ExitCode -notin 0, 3010) {
        throw "Magic Trackpad installation failed: $($process.ExitCode)"
    }
    if (-not (Test-DriverInstalled)) {
        throw "Magic Trackpad $version is missing from the driver store after installation"
    }
    Write-Output "Magic Trackpad: installed $version"
    if ($process.ExitCode -eq 3010) {
        Write-Warning 'Restart Windows to finish installing the Magic Trackpad driver.'
    }
}
finally {
    Remove-Item -Recurse -Force $temporary
}
