# The mise\amp-runner Scheduled Task starts this under a headless conhost, so the
# runner has no window to close. conhost reports every exit as success and, when
# the task stops, dies alone, so this script restarts the runner and takes it down.
$ErrorActionPreference = 'Stop'
$console = Get-Process -Id (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId

while (-not $console.HasExited) {
    # A runner started at logon once hung silently, before connecting. Waiting for
    # a successful update starts it only once the network is up, on the latest build.
    & "$HOME\.amp\bin\amp.exe" update --porcelain
    if ($LASTEXITCODE -ne 0) {
        Start-Sleep -Seconds 5
        continue
    }
    $runner = Start-Process -FilePath "$HOME\.amp\bin\amp.exe" -ArgumentList '--no-tui --remote-control-terminal --discover-dirs --runner-id eve' -NoNewWindow -PassThru
    while (-not $runner.WaitForExit(2000) -and -not $console.HasExited) {}
    if (-not $runner.HasExited) {
        Stop-Process -Id $runner.Id -Force
    }
    Start-Sleep -Seconds 5
}
