$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonCandidates = @(
    'D:\anaconda3\envs\sleep\python.exe'
)

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source) {
    $pythonCandidates += $pythonCommand.Source
}

$python = $pythonCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $python) {
    Write-Error "No usable Python interpreter was found. Please verify the sleep environment exists or add python to PATH."
}

& $python run_backend.py
