param()

$ErrorActionPreference = "Stop"

function Read-PlainRequired([string]$Label) {
    while ($true) {
        $value = (Read-Host $Label).Trim()
        if ($value) { return $value }
        Write-Host "Valor obligatorio." -ForegroundColor Yellow
    }
}

function Read-SecretRequired([string]$Label) {
    while ($true) {
        $secure = Read-Host $Label -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        if ($value) { return $value.Trim() }
        Write-Host "Valor obligatorio." -ForegroundColor Yellow
    }
}

$secretDir = Join-Path $env:LOCALAPPDATA "BITORA"
$secretFile = Join-Path $secretDir "endurance_secrets.json"
New-Item -ItemType Directory -Path $secretDir -Force | Out-Null

$existing = @{}
if (Test-Path $secretFile) {
    try {
        $raw = Get-Content $secretFile -Raw
        $loaded = $raw | ConvertFrom-Json
        foreach ($property in $loaded.PSObject.Properties) {
            $existing[$property.Name] = [string]$property.Value
        }
    } catch {
        $existing = @{}
    }
}

Write-Host "BITORA - carga local de secretos Endurance R2" -ForegroundColor Cyan
Write-Host "No pegues estos valores en el chat. Se guardan solo en $secretFile" -ForegroundColor Gray

if (-not $existing.ContainsKey("BITORA_ENDURANCE_ADMIN_USER")) {
    $existing["BITORA_ENDURANCE_ADMIN_USER"] = Read-PlainRequired "Usuario admin BITORA"
}
if (-not $existing.ContainsKey("BITORA_ENDURANCE_ADMIN_PASSWORD")) {
    $existing["BITORA_ENDURANCE_ADMIN_PASSWORD"] = Read-SecretRequired "Password admin BITORA"
}

$existing["R2_BUCKET"] = Read-PlainRequired "R2 bucket"
$existing["R2_ACCOUNT_ID"] = Read-PlainRequired "Cloudflare Account ID"
$existing["R2_ACCESS_KEY_ID"] = Read-PlainRequired "R2 Access Key ID"
$existing["R2_SECRET_ACCESS_KEY"] = Read-SecretRequired "R2 Secret Access Key"
$prefix = (Read-Host "R2 prefix (Enter para staging)").Trim()
if (-not $prefix) { $prefix = "staging" }
$existing["R2_PREFIX"] = $prefix

$json = ($existing | ConvertTo-Json)
[System.IO.File]::WriteAllText($secretFile, $json, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Secretos guardados localmente." -ForegroundColor Green
Write-Host "Volvé a Codex y escribí: listo r2 endurance" -ForegroundColor Green
