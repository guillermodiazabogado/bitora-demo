param(
    [string]$ProductionBaseUrl = $env:BITORA_ANDROID_PRODUCTION_BASE_URL,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$checks = [ordered]@{}

$uri = $null
$checks.productionEndpoint = [Uri]::TryCreate($ProductionBaseUrl, [UriKind]::Absolute, [ref]$uri) -and
    $uri.Scheme -eq "https" -and
    -not $uri.IsLoopback -and
    -not $uri.Host.EndsWith(".trycloudflare.com") -and
    -not $uri.Host.EndsWith(".example") -and
    -not $uri.Host.EndsWith(".invalid")
$checks.keystorePath = -not [string]::IsNullOrWhiteSpace($env:BITORA_ANDROID_KEYSTORE_PATH) -and
    (Test-Path -LiteralPath $env:BITORA_ANDROID_KEYSTORE_PATH -PathType Leaf)
$checks.keystorePassword = -not [string]::IsNullOrWhiteSpace($env:BITORA_ANDROID_KEYSTORE_PASSWORD)
$checks.keyAlias = -not [string]::IsNullOrWhiteSpace($env:BITORA_ANDROID_KEY_ALIAS)
$checks.keyPassword = -not [string]::IsNullOrWhiteSpace($env:BITORA_ANDROID_KEY_PASSWORD)
$checks.gradleWrapper = Test-Path -LiteralPath (Join-Path $Root "android\gradlew.bat")
$checks.applicationIds = (Select-String -Path (Join-Path $Root "android\apps\operation\build.gradle.kts") -Pattern 'applicationId = "com.bitora.operation"' -Quiet) -and
    (Select-String -Path (Join-Path $Root "android\apps\display\build.gradle.kts") -Pattern 'applicationId = "com.bitora.display"' -Quiet)

$ready = $checks.Values -notcontains $false
$result = [ordered]@{
    status = if ($ready) { "READY" } else { "BLOCKED" }
    checks = $checks
    missing = @($checks.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object Key)
}

if (-not $ready) {
    $result | ConvertTo-Json -Depth 4
    exit 1
}

if ($Build) {
    if (-not $env:JAVA_HOME) { $env:JAVA_HOME = Join-Path $HOME ".codex\android-toolchain\jdk-17" }
    if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path $HOME ".codex\android-toolchain\android-sdk" }
    $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
    Push-Location (Join-Path $Root "android")
    try {
        & .\gradlew.bat :apps:operation:assembleRelease :apps:display:assembleRelease "-PbitoraProductionBaseUrl=$ProductionBaseUrl"
        if ($LASTEXITCODE -ne 0) { throw "Release build failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
    $apks = Get-ChildItem (Join-Path $Root "android\apps") -Filter "*-release.apk" -Recurse
    $result["artifacts"] = @($apks | ForEach-Object {
        [ordered]@{
            path = $_.FullName
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            bytes = $_.Length
        }
    })
}

$result | ConvertTo-Json -Depth 5
