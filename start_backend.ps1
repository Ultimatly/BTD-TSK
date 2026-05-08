$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Get-Command python -ErrorAction SilentlyContinue

if (-not $python) {
    Write-Error "未找到可用的 python 命令，请先激活项目环境后再运行 start_backend.ps1。"
}

& $python.Source run_backend.py
