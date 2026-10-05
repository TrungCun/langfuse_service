# Run in an Administrator PowerShell on the Docker host.
# Only Web/API and S3/media are allowed, from the current local subnet.
param(
    [ValidateRange(1, 65535)][int]$WebPort = 3000,
    [ValidateRange(1, 65535)][int]$MediaPort = 9095
)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open Administrator PowerShell to create Windows Firewall LAN rules.'
}
foreach ($entry in @(@{Name='Langfuse-Service-Web-LAN'; Port=$WebPort}, @{Name='Langfuse-Service-Media-LAN'; Port=$MediaPort})) {
    $rule = Get-NetFirewallRule -Name $entry.Name -ErrorAction SilentlyContinue
    if ($rule) {
        $rule | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Any -RemoteAddress LocalSubnet
        $rule | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $entry.Port
    } else {
        New-NetFirewallRule -Name $entry.Name -DisplayName $entry.Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $entry.Port -RemoteAddress LocalSubnet -Profile Any | Out-Null
    }
    Write-Output "LAN firewall rule ready: $($entry.Name), TCP $($entry.Port), source LocalSubnet."
}
