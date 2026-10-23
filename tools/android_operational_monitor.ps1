param(
    [string]$BaseUrl = $env:BITORA_ANDROID_MONITOR_BASE_URL,
    [string]$DeviceId = ""
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
$response = Invoke-RestMethod -Uri "$($BaseUrl.TrimEnd('/'))/api/admin/telemetry$query" -TimeoutSec 15
$result = [ordered]@{
    checkedAt = [DateTimeOffset]::Now.ToString("o")
    status = $response.status
    devices = @($response.items).Count
    items = @($response.items)
}
$result | ConvertTo-Json -Depth 8
if ($response.status -ne "HEALTHY") { exit 1 }
