param(
    [string]$Distribution = "Ubuntu",
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$repoWindows = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoWsl = (wsl.exe -d $Distribution -- wslpath -a $repoWindows).Trim()
if (-not $repoWsl) { throw "No se pudo resolver la ruta WSL" }

function New-RandomSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).Replace("+", "A").Replace("/", "B")
}

$names = @(
    "BITORA_POSTGRES_ADMIN_PASSWORD", "BITORA_APP_DB_PASSWORD", "BITORA_SESSION_SECRET",
    "BITORA_SECRET_KEY", "BITORA_SPEAKER_SECRET", "BITORA_SURVEY_SECRET",
    "BITORA_DATASET_SIGNING_KEY", "BITORA_ADMIN_BOOTSTRAP_PASSWORD"
)
foreach ($name in $names) { Set-Item -Path "Env:$name" -Value (New-RandomSecret) }
$env:BITORA_ADMIN_BOOTSTRAP_USER = "phase7-admin"
$env:BITORA_IMAGE_TAG = "5.8.2-phase7-local"
$env:BITORA_HTTPS_PORT = "9443"
$pass = @($names + "BITORA_ADMIN_BOOTSTRAP_USER", "BITORA_IMAGE_TAG", "BITORA_HTTPS_PORT")
$priorWslEnv = $env:WSLENV
$env:WSLENV = (($pass | ForEach-Object { "$_/u" }) + $priorWslEnv) -join ":"

$arguments = @("-d", $Distribution, "--", "bash", "-lc")
if ($repoWsl.Contains("'")) { throw "La ruta WSL no puede contener comillas simples" }
$command = "cd '$repoWsl' && python3 scripts/phase7_orchestrator.py"
if ($KeepRunning) { $command += " --keep-running" }
try {
    & wsl.exe @arguments $command
    exit $LASTEXITCODE
}
finally {
    foreach ($name in $names) { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
    Remove-Item -Path "Env:BITORA_ADMIN_BOOTSTRAP_USER" -ErrorAction SilentlyContinue
    $env:WSLENV = $priorWslEnv
}
