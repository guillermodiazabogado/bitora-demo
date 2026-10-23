param(
    [ValidateSet("Start", "Status", "Stop")]
    [string]$Action = "Status",
    [int]$EdgePort = 8812,
    [int]$DownloadPort = 8840,
    [string]$EdgePublicUrl = $env:BITORA_ANDROID_LAB_EDGE_URL,
    [string]$DownloadPublicUrl = $env:BITORA_ANDROID_LAB_DOWNLOAD_URL
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $Root "tmp"
$StatePath = Join-Path $RuntimeDir "android_lab_runtime.json"
$EndpointConfigPath = Join-Path $RuntimeDir "android_lab_endpoints.json"
$endpointConfig = if (Test-Path -LiteralPath $EndpointConfigPath) { Get-Content -LiteralPath $EndpointConfigPath -Raw | ConvertFrom-Json } else { $null }
if (-not $EdgePublicUrl -and $endpointConfig.edgeUrl) { $EdgePublicUrl = $endpointConfig.edgeUrl }
if (-not $DownloadPublicUrl -and $endpointConfig.downloadUrl) { $DownloadPublicUrl = $endpointConfig.downloadUrl }
$ArtifactDir = if ($DownloadPublicUrl) { Join-Path $Root "android\artifacts\a11" } else { Join-Path $Root "android\artifacts\runtime" }

function Resolve-Executable([string]$EnvironmentValue, [string]$CommandName, [string]$FallbackPattern) {
    if ($EnvironmentValue -and (Test-Path -LiteralPath $EnvironmentValue -PathType Leaf)) { return $EnvironmentValue }
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and $command.Source -notlike "*WindowsApps*") { return $command.Source }
    $fallback = Get-ChildItem $FallbackPattern -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($fallback) { return $fallback.FullName }
    return ""
}

$Cloudflared = Resolve-Executable $env:BITORA_CLOUDFLARED "cloudflared" (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Cloudflare.cloudflared_*\cloudflared.exe")
$Python = Resolve-Executable $env:BITORA_PYTHON "python" (Join-Path $env:LOCALAPPDATA "Programs\Python\Python*\python.exe")

function Read-RuntimeState {
    if (Test-Path -LiteralPath $StatePath) {
        return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    }
    return $null
}

function Test-ProcessId([int]$ProcessId) {
    if ($ProcessId -le 0) { return $true }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Wait-Http([string]$Url, [int]$Seconds = 30, [string]$Method = "Get") {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method $Method -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Url"
}

function Start-HealthyTunnel([string]$LocalUrl, [string]$HealthPath, [string]$LogPrefix, [string]$Method = "Get") {
    foreach ($attempt in 1..3) {
        $logPath = Join-Path $env:TEMP "$LogPrefix-$attempt.log"
        $parameters = @{
            FilePath = $Cloudflared
            ArgumentList = @("tunnel", "--url", $LocalUrl, "--no-autoupdate", "--logfile", $logPath)
            WindowStyle = "Hidden"
            PassThru = $true
        }
        $process = Start-Process @parameters
        try {
            $url = Wait-TunnelUrl $logPath
            Wait-Http "$url$HealthPath" 45 $Method
            return [pscustomobject]@{ process = $process; url = $url; log = $logPath }
        } catch {
            if (Test-ProcessId $process.Id) { Stop-Process -Id $process.Id -Force }
            if ($attempt -eq 3) { throw }
        }
    }
}

function Wait-TunnelUrl([string]$LogPath, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if (Test-Path -LiteralPath $LogPath) {
            $match = Select-String -Path $LogPath -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches |
                Select-Object -First 1
            if ($match) { return $match.Matches[0].Value }
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Cloudflare tunnel URL was not emitted to $LogPath"
}

function Stop-Runtime {
    $state = Read-RuntimeState
    if ($state) {
        foreach ($id in @($state.edgeTunnelPid, $state.downloadTunnelPid, $state.edgeServerPid, $state.downloadServerPid)) {
            if ($id -and (Test-ProcessId ([int]$id))) {
                Stop-Process -Id ([int]$id) -Force
            }
        }
        Remove-Item -LiteralPath $StatePath -Force
    }
    [pscustomobject]@{ status = "STOPPED"; state = $StatePath } | ConvertTo-Json
}

function Get-RuntimeStatus {
    $state = Read-RuntimeState
    if (-not $state) {
        [pscustomobject]@{ status = "STOPPED"; reason = "runtime_state_missing" } | ConvertTo-Json
        return
    }
    $processes = @{
        edgeServer = Test-ProcessId ([int]$state.edgeServerPid)
        edgeTunnel = Test-ProcessId ([int]$state.edgeTunnelPid)
        downloadServer = Test-ProcessId ([int]$state.downloadServerPid)
        downloadTunnel = Test-ProcessId ([int]$state.downloadTunnelPid)
    }
    $edgeHealthy = $false
    $downloadHealthy = $false
    try { $edgeHealthy = (Invoke-WebRequest -Uri "$($state.edgeUrl)/admin/pairing" -TimeoutSec 10).StatusCode -eq 200 } catch {}
    try { $downloadHealthy = (Invoke-WebRequest -Uri $state.displayUrl -Method Head -TimeoutSec 10).StatusCode -eq 200 } catch {}
    $healthy = $edgeHealthy -and $downloadHealthy -and ($processes.Values -notcontains $false)
    [pscustomobject]@{
        status = if ($healthy) { "RUNNING" } else { "DEGRADED" }
        edgeUrl = $state.edgeUrl
        adminUrl = "$($state.edgeUrl)/admin/pairing"
        operationUrl = $state.operationUrl
        displayUrl = $state.displayUrl
        edgeHealthy = $edgeHealthy
        downloadHealthy = $downloadHealthy
        processes = $processes
    } | ConvertTo-Json -Depth 4
}

function Start-Runtime {
    if (-not (Test-Path -LiteralPath $Python)) { throw "Python 3.12 not found at $Python" }
    if (-not (Test-Path -LiteralPath $Cloudflared)) { throw "cloudflared not found at $Cloudflared" }
    New-Item -ItemType Directory -Path $RuntimeDir, $ArtifactDir -Force | Out-Null

    $old = Read-RuntimeState
    if ($old) { Stop-Runtime | Out-Null }

    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $started = [System.Collections.Generic.List[int]]::new()
    try {
        $edgeServerParameters = @{
            FilePath = $Python
            ArgumentList = @("-u", "tools/android_pairing_lab_server.py", "--host", "127.0.0.1", "--port", "$EdgePort")
            WorkingDirectory = $Root
            WindowStyle = "Hidden"
            PassThru = $true
        }
        if ($EdgePublicUrl) {
            $edgeServer = [pscustomobject]@{ Id = 0 }
            $edgeTunnel = [pscustomobject]@{ Id = 0 }
            $edgeUrl = $EdgePublicUrl.TrimEnd("/")
            Wait-Http "$edgeUrl/admin/pairing"
        } else {
            $edgeServer = Start-Process @edgeServerParameters
            $started.Add($edgeServer.Id)
            Wait-Http "http://127.0.0.1:$EdgePort/admin/pairing"

            $edge = Start-HealthyTunnel "http://127.0.0.1:$EdgePort" "/admin/pairing" "bitora-edge-$stamp"
            $edgeTunnel = $edge.process
            $started.Add($edgeTunnel.Id)
            $edgeUrl = $edge.url
        }

        if (-not $env:JAVA_HOME) { $env:JAVA_HOME = Join-Path $HOME ".codex\android-toolchain\jdk-17" }
        if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path $HOME ".codex\android-toolchain\android-sdk" }
        $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
        $gradle = Join-Path $Root "android\gradlew.bat"
        Push-Location (Join-Path $Root "android")
        try {
            & $gradle :apps:operation:assembleDebug :apps:display:assembleDebug "-PbitoraPairingBaseUrl=$edgeUrl"
            if ($LASTEXITCODE -ne 0) { throw "Android debug build failed with exit code $LASTEXITCODE" }
        } finally {
            Pop-Location
        }

        $operationApk = Join-Path $Root "android\apps\operation\build\outputs\apk\debug\operation-debug.apk"
        $displayApk = Join-Path $Root "android\apps\display\build\outputs\apk\debug\display-debug.apk"
        $operationOut = Join-Path $ArtifactDir "bitora-operation-lab.apk"
        $displayOut = Join-Path $ArtifactDir "bitora-display-lab.apk"
        Copy-Item -LiteralPath $operationApk -Destination $operationOut -Force
        Copy-Item -LiteralPath $displayApk -Destination $displayOut -Force
        Compress-Archive -LiteralPath $operationOut -DestinationPath (Join-Path $ArtifactDir "bitora-operation-lab.zip") -Force
        Compress-Archive -LiteralPath $displayOut -DestinationPath (Join-Path $ArtifactDir "bitora-display-lab.zip") -Force

        $downloadServerParameters = @{
            FilePath = $Python
            ArgumentList = @("-m", "http.server", "$DownloadPort", "--bind", "127.0.0.1")
            WorkingDirectory = $ArtifactDir
            WindowStyle = "Hidden"
            PassThru = $true
        }
        if ($DownloadPublicUrl) {
            $downloadServer = [pscustomobject]@{ Id = 0 }
            $downloadTunnel = [pscustomobject]@{ Id = 0 }
            $downloadUrl = $DownloadPublicUrl.TrimEnd("/")
        } else {
            $downloadServer = Start-Process @downloadServerParameters
            $started.Add($downloadServer.Id)
            Wait-Http "http://127.0.0.1:$DownloadPort/bitora-display-lab.zip" 30 "Head"

            $download = Start-HealthyTunnel "http://127.0.0.1:$DownloadPort" "/bitora-display-lab.zip" "bitora-download-$stamp" "Head"
            $downloadTunnel = $download.process
            $started.Add($downloadTunnel.Id)
            $downloadUrl = $download.url
        }
        $operationUrl = "$downloadUrl/bitora-operation-lab.zip"
        $displayUrl = "$downloadUrl/bitora-display-lab.zip"
        Wait-Http $displayUrl 30 "Head"

        $state = [ordered]@{
            startedAt = [DateTimeOffset]::Now.ToString("o")
            edgeUrl = $edgeUrl
            downloadUrl = $downloadUrl
            operationUrl = $operationUrl
            displayUrl = $displayUrl
            edgeServerPid = $edgeServer.Id
            edgeTunnelPid = $edgeTunnel.Id
            downloadServerPid = $downloadServer.Id
            downloadTunnelPid = $downloadTunnel.Id
            edgePort = $EdgePort
            downloadPort = $DownloadPort
            externallyManagedEdge = [bool]$EdgePublicUrl
            externallyManagedDownload = [bool]$DownloadPublicUrl
        }
        $state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8
        Get-RuntimeStatus
    } catch {
        foreach ($id in $started) {
            if (Test-ProcessId $id) { Stop-Process -Id $id -Force }
        }
        throw
    }
}

switch ($Action) {
    "Start" { Start-Runtime }
    "Status" { Get-RuntimeStatus }
    "Stop" { Stop-Runtime }
}
