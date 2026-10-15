<#
.SYNOPSIS
  Allow inbound UDP traffic for the Godot server (ENet).

.DESCRIPTION
  Godot's ENetMultiplayerPeer uses UDP, which is easy to block by accident.
  Also remember to open the same UDP port in your cloud provider's security group.
#>
param(
    [int]$Port = 7000,
    [string]$RuleName = "GameLink Server UDP"
)

$ErrorActionPreference = "Stop"

if (Get-NetFirewallRule -DisplayName "$RuleName $Port" -ErrorAction SilentlyContinue) {
    Write-Host "Firewall rule already exists for UDP $Port."
} else {
    New-NetFirewallRule -DisplayName "$RuleName $Port" `
        -Direction Inbound -Protocol UDP -LocalPort $Port -Action Allow | Out-Null
    Write-Host "Opened inbound UDP $Port in Windows Firewall."
}

Write-Host "Reminder: also allow UDP $Port in the cloud provider's security group."
