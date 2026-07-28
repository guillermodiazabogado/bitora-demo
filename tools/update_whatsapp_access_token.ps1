param(
    [string]$EnvPath = "deployment\staging\.env.staging"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvPath)) {
    throw "No existe $EnvPath"
}

Write-Host ""
Write-Host "BITORA - Actualizar token WhatsApp" -ForegroundColor Cyan
Write-Host "El token se guarda solo en deployment\staging\.env.staging y no se muestra en el chat." -ForegroundColor Gray
Write-Host ""

$secure = Read-Host "Pegá el WHATSAPP_ACCESS_TOKEN nuevo" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ($null -eq $token) {
    $token = ""
}
$token = $token.Trim()
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "El token no puede quedar vacío."
}

$lines = Get-Content -LiteralPath $EnvPath -Encoding UTF8
$updated = $false
$newLines = foreach ($line in $lines) {
    if ($line -match "^\s*WHATSAPP_ACCESS_TOKEN\s*=") {
        $updated = $true
        "WHATSAPP_ACCESS_TOKEN=$token"
    } else {
        $line
    }
}
if (-not $updated) {
    $newLines += "WHATSAPP_ACCESS_TOKEN=$token"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines((Resolve-Path -LiteralPath $EnvPath).Path, $newLines, $utf8NoBom)

Write-Host ""
Write-Host "Token actualizado." -ForegroundColor Green
Write-Host "Volvé a Codex y escribí: listo token nuevo" -ForegroundColor Green
Write-Host ""
Read-Host "Presiona Enter para cerrar"
