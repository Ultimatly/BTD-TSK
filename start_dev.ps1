$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-PortListening {
    param(
        [int]$Port
    )

    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    } catch {
        return $false
    }
}

if (-not (Test-PortListening -Port 8000)) {
    Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'start_backend.ps1')
    Start-Sleep -Seconds 2
} else {
    Write-Host 'Backend is already running on port 8000. Skipping duplicate startup.'
}

if (-not (Test-PortListening -Port 5173)) {
    Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'start_frontend.ps1')
} else {
    Write-Host 'Frontend is already running on port 5173. Skipping duplicate startup.'
}
