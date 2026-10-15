<#
.SYNOPSIS
  Register the generated Godot headless server as a Windows service using NSSM.

.DESCRIPTION
  Phase 1 deployment helper. Run on the Windows cloud server after the server
  build has been uploaded. Requires nssm.exe on PATH (https://nssm.cc/).

.EXAMPLE
  .\install_service.ps1 -ServerExe C:\GameLink\server\gamelink-server.exe -Port 7000
#>
param(
    [Parameter(Mandatory = $true)][string]$ServerExe,
    [int]$Port = 7000,
    [string]$ServiceName = "GameLinkServer",
    [string]$LogDir = "C:\GameLink\logs"
)

$ErrorActionPreference = "Stop"

$nssm = (Get-Command nssm.exe -ErrorAction SilentlyContinue).Source
if (-not $nssm) {
    throw "nssm.exe not found on PATH. Download NSSM from https://nssm.cc/ and add it to PATH."
}
if (-not (Test-Path $ServerExe)) {
    throw "Server executable not found: $ServerExe"
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping and removing existing service '$ServiceName'..."
    & $nssm stop $ServiceName | Out-Null
    & $nssm remove $ServiceName confirm | Out-Null
}

& $nssm install $ServiceName $ServerExe "--headless" "--server" "--port" $Port
& $nssm set $ServiceName AppStdout (Join-Path $LogDir "server.log")
& $nssm set $ServiceName AppStderr (Join-Path $LogDir "server.err.log")
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm start $ServiceName

Write-Host "Service '$ServiceName' installed and started (UDP $Port)."
