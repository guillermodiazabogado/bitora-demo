param(
    [string]$EnvPath = "deployment\staging\.env.staging"
)

$ErrorActionPreference = "Stop"

function Read-RequiredValue {
    param(
        [string]$Label,
        [bool]$Secret = $false
    )
    do {
        if ($Secret) {
            $secure = Read-Host "$Label" -AsSecureString
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
        } else {
            $plain = Read-Host "$Label"
        }
        if ($null -eq $plain) {
            $plain = ""
        }
        $plain = $plain.Trim()
        if (-not [string]::IsNullOrWhiteSpace($plain)) {
            return $plain
        }
        Write-Host "Este dato es obligatorio." -ForegroundColor Yellow
    } while ($true)
}

function Read-OptionalValue {
    param(
        [string]$Label,
        [string]$Default = ""
    )
    $value = Read-Host "$Label"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value.Trim()
}

function Set-EnvValue {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )
    $escaped = $Value.Replace("`r", "").Replace("`n", "")
    $pattern = "^\s*" + [regex]::Escape($Key) + "\s*="
    $updated = $false
    $newLines = foreach ($line in $Lines) {
        if ($line -match $pattern) {
            $updated = $true
            "$Key=$escaped"
        } else {
            $line
        }
    }
    if (-not $updated) {
        $newLines += "$Key=$escaped"
    }
    return $newLines
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
    throw "No existe $EnvPath"
}

Write-Host ""
Write-Host "BITORA - Configuracion WhatsApp Staging" -ForegroundColor Cyan
Write-Host "Los secretos se escriben localmente en $EnvPath y no se muestran en el chat." -ForegroundColor Gray
Write-Host ""

$accessToken = Read-RequiredValue "WHATSAPP_ACCESS_TOKEN" $true
$phoneNumberId = Read-RequiredValue "WHATSAPP_PHONE_NUMBER_ID" $false
$businessAccountId = Read-RequiredValue "WHATSAPP_BUSINESS_ACCOUNT_ID / WABA ID" $false
$verifyToken = Read-RequiredValue "WHATSAPP_VERIFY_TOKEN" $true
$appSecret = Read-RequiredValue "WHATSAPP_APP_SECRET" $true
$recipient = Read-RequiredValue "Telefono autorizado destino, con codigo pais, solo numeros. Ej: 5492991234567" $false
$template = Read-OptionalValue "Plantilla aprobada por Meta (Enter si no aplica)" ""
$language = Read-OptionalValue "Idioma plantilla (Enter para es_AR)" "es_AR"

$lines = Get-Content -LiteralPath $EnvPath
$values = [ordered]@{
    "BITORA_LIVE_INTEGRATIONS" = "true"
    "WHATSAPP_PROVIDER" = "meta"
    "WHATSAPP_ENABLED" = "true"
    "WHATSAPP_ACCESS_TOKEN" = $accessToken
    "WHATSAPP_PHONE_NUMBER_ID" = $phoneNumberId
    "WHATSAPP_BUSINESS_ACCOUNT_ID" = $businessAccountId
    "WHATSAPP_VERIFY_TOKEN" = $verifyToken
    "WHATSAPP_APP_SECRET" = $appSecret
    "WHATSAPP_API_VERSION" = "v22.0"
    "WHATSAPP_META_API_URL" = "https://graph.facebook.com/v22.0"
    "WHATSAPP_SAFE_MODE" = "true"
    "WHATSAPP_FORCE_RECIPIENT" = $recipient
    "WHATSAPP_TEST_RECIPIENT" = $recipient
    "WHATSAPP_REGISTRATION_TEMPLATE" = $template
    "WHATSAPP_REGISTRATION_TEMPLATE_LANGUAGE" = $language
    "WHATSAPP_REGISTRATION_TEMPLATE_VARIABLES" = "nombre,evento,portal"
    "WHATSAPP_LIVE_RECEIPT_CONFIRMED" = "false"
}

foreach ($key in $values.Keys) {
    $lines = Set-EnvValue -Lines $lines -Key $key -Value $values[$key]
}

$resolvedEnvPath = (Resolve-Path -LiteralPath $EnvPath).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($resolvedEnvPath, $lines, $utf8NoBom)

Write-Host ""
Write-Host "Configuracion guardada." -ForegroundColor Green
Write-Host "Ahora podes volver a Codex y escribir: listo credenciales WhatsApp" -ForegroundColor Green
Write-Host ""
Read-Host "Presiona Enter para cerrar"
