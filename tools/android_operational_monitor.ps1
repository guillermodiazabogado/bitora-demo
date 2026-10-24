param(
    [string]$BaseUrl = $env:BITORA_ANDROID_MONITOR_BASE_URL,
    [string]$DeviceId = "",
    [string]$AdminUser = $env:BITORA_ANDROID_MONITOR_USER,
    [string]$AdminPassword = $env:BITORA_ANDROID_MONITOR_PASSWORD
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $BaseUrl) {
    $statePath = Join-Path $Root "tmp\android_lab_runtime.json"
    if (Test-Path -LiteralPath $statePath) {
        $BaseUrl = (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json).edgeUrl
    }
}
if (-not $BaseUrl) { throw "BaseUrl is required when no LAB runtime state exists" }

$query = if ($DeviceId) { "?deviceId=$([Uri]::EscapeDataString($DeviceId))" } else { "" }
$request = @{ Uri = "$($BaseUrl.TrimEnd('/'))/api/admin/telemetry$query"; TimeoutSec = 15 }
if ($AdminUser -or $AdminPassword) {
    if (-not $AdminUser -or -not $AdminPassword) { throw "Both AdminUser and AdminPassword are required" }
    $loginBody = @{ name = $AdminUser; pin = $AdminPassword } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$($BaseUrl.TrimEnd('/'))/api/auth/login" -ContentType "application/json" -Body $loginBody -SessionVariable bitoraSession -TimeoutSec 15 | Out-Null
    $request.WebSession = $bitoraSession
}
$response = Invoke-RestMethod @request
$result = [ordered]@{
    checkedAt = [DateTimeOffset]::Now.ToString("o")
    status = $response.status
    devices = @($response.items).Count
    items = @($response.items)
}
$result | ConvertTo-Json -Depth 8
if ($response.status -eq "ALERT") { exit 1 }
