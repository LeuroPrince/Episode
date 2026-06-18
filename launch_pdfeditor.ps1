$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 7865
$url = "http://127.0.0.1:$port/"

function Test-PortOpen {
    try {
        $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return [bool]$connection
    } catch {
        return $false
    }
}

if (-not (Test-PortOpen)) {
    Start-Process -FilePath "python" -ArgumentList "app.py" -WorkingDirectory $projectRoot -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline -and -not (Test-PortOpen)) {
        Start-Sleep -Seconds 1
    }
}

if (-not (Test-PortOpen)) {
    throw "PDF Editor service failed to start on port $port. Check Python or app.py."
}

Start-Process $url
